from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "codex-one-turn"
HOOK = PLUGIN_ROOT / "hooks" / "oneturn_hook.py"
SERVER_PATH = PLUGIN_ROOT / "mcp" / "server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("one_turn_server", SERVER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OneTurnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "state"
        self.env = os.environ.copy()
        self.env["ONETURN_STATE_DIR"] = str(self.state_dir)
        self.previous_override = os.environ.get("ONETURN_STATE_DIR")
        os.environ["ONETURN_STATE_DIR"] = str(self.state_dir)

    def tearDown(self) -> None:
        if self.previous_override is None:
            os.environ.pop("ONETURN_STATE_DIR", None)
        else:
            os.environ["ONETURN_STATE_DIR"] = self.previous_override
        self.temp.cleanup()

    def hook(self, event: str, prompt: str | None = None) -> dict:
        payload = {
            "hook_event_name": event,
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": self.temp.name,
        }
        if prompt is not None:
            payload["prompt"] = prompt
        completed = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )
        return json.loads(completed.stdout)

    def activate(self) -> str:
        output = self.hook("UserPromptSubmit", "OneTurn으로 실행해줘")
        context = output["hookSpecificOutput"]["additionalContext"]
        return context.split("activation_id=", 1)[1].split(".", 1)[0]

    def test_non_explicit_prompt_does_not_activate(self) -> None:
        self.assertEqual(self.hook("UserPromptSubmit", "전체 테스트를 실행해줘"), {})
        self.assertEqual(list((self.state_dir / "states").glob("*.json")), [])

    def test_stop_blocks_until_finish(self) -> None:
        activation_id = self.activate()
        blocked = self.hook("Stop")
        self.assertEqual(blocked["decision"], "block")
        self.assertIn(activation_id, blocked["reason"])

        module = load_server_module()
        server = module.OneTurnServer()
        try:
            result = server.finish_tool(
                {"activation_id": activation_id, "summary": "requested work verified"}
            )
            self.assertFalse(result["isError"])
        finally:
            server.shutdown()
        self.assertEqual(self.hook("Stop"), {})

    def test_stop_gate_fails_open_after_three_blocks(self) -> None:
        self.activate()
        for _ in range(3):
            self.assertEqual(self.hook("Stop")["decision"], "block")
        released = self.hook("Stop")
        self.assertIn("safety release", released["systemMessage"])

    def test_run_waits_and_verifies_artifact(self) -> None:
        activation_id = self.activate()
        workdir = Path(self.temp.name) / "work"
        workdir.mkdir()
        module = load_server_module()
        server = module.OneTurnServer()
        try:
            result = server.run_tool(
                {
                    "activation_id": activation_id,
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; print('done'); Path('result.txt').write_text('ok')",
                    ],
                    "cwd": str(workdir),
                    "timeout_seconds": 10,
                    "required_artifacts": ["result.txt"],
                },
                "request-1",
                threading.Event(),
            )
        finally:
            server.shutdown()

        structured = result["structuredContent"]
        self.assertTrue(structured["succeeded"])
        self.assertEqual(structured["status"], "succeeded")
        self.assertEqual(structured["missing_artifacts"], [])
        self.assertIn("done", structured["output_tail"])

    def test_relative_working_directory_is_rejected(self) -> None:
        activation_id = self.activate()
        module = load_server_module()
        server = module.OneTurnServer()
        try:
            with self.assertRaises(module.ToolError):
                server.run_tool(
                    {
                        "activation_id": activation_id,
                        "command": [sys.executable, "-c", "print('no')"],
                        "cwd": ".",
                    },
                    "request-relative",
                    threading.Event(),
                )
        finally:
            server.shutdown()

    def test_default_deadline_is_seven_days(self) -> None:
        module = load_server_module()
        self.assertEqual(module.DEFAULT_TIMEOUT_SECONDS, 604_800)
        run_tool = next(tool for tool in module.tool_definitions() if tool["name"] == "run")
        timeout_schema = run_tool["inputSchema"]["properties"]["timeout_seconds"]
        self.assertEqual(timeout_schema["default"], 604_800)
        self.assertEqual(timeout_schema["maximum"], 604_800)

    def test_cancel_terminates_process(self) -> None:
        activation_id = self.activate()
        module = load_server_module()
        server = module.OneTurnServer()
        cancel = threading.Event()
        cancel.set()
        try:
            result = server.run_tool(
                {
                    "activation_id": activation_id,
                    "command": [sys.executable, "-c", "import time; time.sleep(30)"],
                    "cwd": self.temp.name,
                    "timeout_seconds": 60,
                },
                "request-cancel",
                cancel,
            )
        finally:
            server.shutdown()
        self.assertEqual(result["structuredContent"]["status"], "cancelled")

    def test_windows_termination_targets_the_process_tree(self) -> None:
        module = load_server_module()
        process = mock.Mock()
        process.pid = 4242
        process.poll.return_value = None
        with mock.patch.object(module.subprocess, "run") as run:
            module.terminate_windows_process_tree(process, force=True)
        run.assert_called_once_with(
            ["taskkill.exe", "/PID", "4242", "/T", "/F"],
            check=False,
            stdin=module.subprocess.DEVNULL,
            stdout=module.subprocess.DEVNULL,
            stderr=module.subprocess.DEVNULL,
            timeout=5,
        )

    @unittest.skipUnless(os.name == "nt", "Windows process-tree integration test")
    def test_windows_cancel_terminates_descendants(self) -> None:
        import ctypes

        activation_id = self.activate()
        module = load_server_module()
        server = module.OneTurnServer()
        cancel = threading.Event()
        workdir = Path(self.temp.name) / "windows-tree"
        workdir.mkdir()
        child_pid_path = workdir / "child.pid"
        results: list[dict] = []
        parent_script = (
            "import pathlib, subprocess, sys, time; "
            "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "pathlib.Path('child.pid').write_text(str(child.pid)); "
            "time.sleep(60)"
        )

        thread = threading.Thread(
            target=lambda: results.append(
                server.run_tool(
                    {
                        "activation_id": activation_id,
                        "command": [sys.executable, "-c", parent_script],
                        "cwd": str(workdir),
                        "timeout_seconds": 60,
                    },
                    "request-windows-tree",
                    cancel,
                )
            )
        )
        child_pid = 0
        try:
            thread.start()
            deadline = time.monotonic() + 10
            while not child_pid_path.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(child_pid_path.exists(), "child process did not start")
            child_pid = int(child_pid_path.read_text())
            cancel.set()
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "OneTurn cancellation did not return")
            self.assertEqual(results[0]["structuredContent"]["status"], "cancelled")

            def descendant_is_active() -> bool:
                process = ctypes.windll.kernel32.OpenProcess(0x1000, False, child_pid)
                if not process:
                    return False
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(process)
                return exit_code.value == 259

            deadline = time.monotonic() + 5
            while descendant_is_active() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(descendant_is_active(), "descendant process is still active")
        finally:
            cancel.set()
            thread.join(timeout=5)
            server.shutdown()
            if child_pid:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(child_pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


if __name__ == "__main__":
    unittest.main()
