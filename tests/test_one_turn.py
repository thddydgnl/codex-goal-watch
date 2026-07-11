from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
