#!/usr/bin/env python3
"""Dependency-free stdio MCP server for OneTurn long-running jobs."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from state_store import read_state, state_root, write_state  # noqa: E402


SERVER_NAME = "codex-one-turn"
SERVER_VERSION = "0.1.0"
MAX_TIMEOUT_SECONDS = 7 * 24 * 60 * 60
DEFAULT_TIMEOUT_SECONDS = MAX_TIMEOUT_SECONDS
MAX_TAIL_BYTES = 64 * 1024


class ToolError(Exception):
    pass


class OneTurnServer:
    def __init__(self) -> None:
        self.root = state_root(PLUGIN_ROOT)
        self.write_lock = threading.Lock()
        self.lifecycle_lock = threading.Lock()
        self.cancel_events: dict[str, threading.Event] = {}
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="one-turn")

    def write(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self.write_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()

    def respond(self, request_id: Any, result: dict[str, Any]) -> None:
        self.write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def error(self, request_id: Any, code: int, message: str) -> None:
        self.write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def handle(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            requested = params.get("protocolVersion")
            self.respond(
                request_id,
                {
                    "protocolVersion": requested or "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        elif method == "ping":
            self.respond(request_id, {})
        elif method == "tools/list":
            self.respond(request_id, {"tools": tool_definitions()})
        elif method == "tools/call":
            self._start_tool_call(request_id, params)
        elif method == "notifications/cancelled":
            cancelled_id = str(params.get("requestId", ""))
            with self.lifecycle_lock:
                event = self.cancel_events.get(cancelled_id)
            if event:
                event.set()
        elif request_id is not None and method not in {
            "notifications/initialized",
            "notifications/progress",
        }:
            self.error(request_id, -32601, f"method not found: {method}")

    def _start_tool_call(self, request_id: Any, params: dict[str, Any]) -> None:
        key = str(request_id)
        cancel_event = threading.Event()
        with self.lifecycle_lock:
            self.cancel_events[key] = cancel_event
        self.pool.submit(self._run_tool_call, request_id, key, params, cancel_event)

    def _run_tool_call(
        self,
        request_id: Any,
        key: str,
        params: dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        try:
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name == "run":
                result = self.run_tool(arguments, key, cancel_event)
            elif name == "finish":
                result = self.finish_tool(arguments)
            else:
                raise ToolError(f"unknown tool: {name}")
            self.respond(request_id, result)
        except ToolError as exc:
            self.respond(request_id, tool_result(str(exc), is_error=True))
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            self.respond(
                request_id,
                tool_result(f"OneTurn internal error: {type(exc).__name__}: {exc}", is_error=True),
            )
        finally:
            with self.lifecycle_lock:
                self.cancel_events.pop(key, None)
                self.processes.pop(key, None)

    def require_activation(self, activation_id: Any) -> dict[str, Any]:
        if not isinstance(activation_id, str):
            raise ToolError("activation_id is required")
        state = read_state(self.root, activation_id)
        if not state:
            raise ToolError("activation_id is unknown or expired; activate OneTurn from the user prompt")
        if state.get("status") != "active":
            raise ToolError(f"activation is not active (status={state.get('status')})")
        return state

    def run_tool(
        self,
        arguments: dict[str, Any],
        request_key: str,
        cancel_event: threading.Event,
    ) -> dict[str, Any]:
        activation_id = arguments.get("activation_id")
        state = self.require_activation(activation_id)
        command = validate_command(arguments.get("command"))
        cwd = validate_cwd(arguments.get("cwd"))
        timeout_seconds = validate_timeout(
            arguments.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        )
        success_codes = validate_success_codes(arguments.get("success_exit_codes", [0]))
        artifacts = validate_artifacts(arguments.get("required_artifacts", []), cwd)

        job_id = uuid.uuid4().hex
        log_path = self.root / "jobs" / f"{job_id}.log"
        state["current_job"] = {
            "job_id": job_id,
            "command": command,
            "cwd": str(cwd),
            "status": "running",
            "started_at": int(time.time()),
            "log_path": str(log_path),
        }
        write_state(self.root, state)

        popen_kwargs: dict[str, Any] = {
            "cwd": str(cwd),
            "stdin": subprocess.DEVNULL,
            "stdout": None,
            "stderr": subprocess.STDOUT,
            "shell": False,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        started = time.monotonic()
        timed_out = False
        cancelled = False
        with log_path.open("wb") as log_handle:
            popen_kwargs["stdout"] = log_handle
            try:
                process = subprocess.Popen(command, **popen_kwargs)
            except OSError as exc:
                state["current_job"].update(status="failed_to_start", error=str(exc))
                write_state(self.root, state)
                raise ToolError(f"failed to start command: {exc}") from exc

            with self.lifecycle_lock:
                self.processes[request_key] = process

            while process.poll() is None:
                if cancel_event.wait(0.25):
                    cancelled = True
                    terminate_process(process)
                    break
                if time.monotonic() - started >= timeout_seconds:
                    timed_out = True
                    terminate_process(process)
                    break
            exit_code = process.wait()

        elapsed = round(time.monotonic() - started, 3)
        missing_artifacts = [str(path.relative_to(cwd)) for path in artifacts if not path.exists()]
        succeeded = (
            not cancelled
            and not timed_out
            and exit_code in success_codes
            and not missing_artifacts
        )
        status = (
            "cancelled"
            if cancelled
            else "timed_out"
            if timed_out
            else "succeeded"
            if succeeded
            else "failed"
        )
        tail = read_tail(log_path)
        job_result = {
            "job_id": job_id,
            "status": status,
            "succeeded": succeeded,
            "exit_code": exit_code,
            "elapsed_seconds": elapsed,
            "missing_artifacts": missing_artifacts,
            "log_path": str(log_path),
            "output_tail": tail,
        }
        state["current_job"] = None
        state.setdefault("jobs", []).append(job_result)
        state["jobs"] = state["jobs"][-20:]
        write_state(self.root, state)

        summary = (
            f"OneTurn job {job_id} {status}; exit_code={exit_code}; "
            f"elapsed={elapsed}s; missing_artifacts={len(missing_artifacts)}"
        )
        if tail:
            summary += f"\n\nOutput tail:\n{tail}"
        return tool_result(summary, structured=job_result, is_error=False)

    def finish_tool(self, arguments: dict[str, Any]) -> dict[str, Any]:
        activation_id = arguments.get("activation_id")
        if not isinstance(activation_id, str):
            raise ToolError("activation_id is required")
        state = read_state(self.root, activation_id)
        if not state:
            raise ToolError("activation_id is unknown or expired")
        if state.get("status") == "finished":
            return tool_result(
                "OneTurn was already marked complete.",
                structured={"activation_id": activation_id, "status": "finished"},
            )
        if state.get("status") != "active":
            raise ToolError(f"activation is not active (status={state.get('status')})")
        summary = arguments.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ToolError("summary is required before finishing OneTurn")
        if state.get("current_job"):
            raise ToolError("cannot finish while a OneTurn job is still running")
        state["status"] = "finished"
        state["completion_summary"] = summary.strip()[:4000]
        state["finished_at"] = int(time.time())
        write_state(self.root, state)
        return tool_result(
            "OneTurn completion recorded. The Stop hook will allow this turn to end.",
            structured={"activation_id": activation_id, "status": "finished"},
        )

    def shutdown(self) -> None:
        with self.lifecycle_lock:
            events = list(self.cancel_events.values())
            processes = list(self.processes.values())
        for event in events:
            event.set()
        for process in processes:
            if process.poll() is None:
                terminate_process(process)
        self.pool.shutdown(wait=False, cancel_futures=True)


def validate_command(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 256:
        raise ToolError("command must be a non-empty argv array with at most 256 items")
    if not all(isinstance(item, str) and item and "\x00" not in item for item in value):
        raise ToolError("every command item must be a non-empty string without NUL bytes")
    return value


def validate_cwd(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ToolError("cwd must be an absolute directory path")
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise ToolError("cwd must be an absolute directory path")
    cwd = raw.resolve()
    if not cwd.is_dir():
        raise ToolError(f"cwd is not an existing directory: {cwd}")
    return cwd


def validate_timeout(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TIMEOUT_SECONDS:
        raise ToolError(f"timeout_seconds must be an integer from 1 to {MAX_TIMEOUT_SECONDS}")
    return value


def validate_success_codes(value: Any) -> set[int]:
    if not isinstance(value, list) or not value or len(value) > 32:
        raise ToolError("success_exit_codes must be a non-empty integer array")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise ToolError("success_exit_codes must contain only integers")
    return set(value)


def validate_artifacts(value: Any, cwd: Path) -> list[Path]:
    if not isinstance(value, list) or len(value) > 128:
        raise ToolError("required_artifacts must be an array with at most 128 paths")
    paths: list[Path] = []
    for item in value:
        if not isinstance(item, str) or not item or "\x00" in item:
            raise ToolError("artifact paths must be non-empty strings")
        candidate = (cwd / item).resolve() if not Path(item).is_absolute() else Path(item).resolve()
        try:
            candidate.relative_to(cwd)
        except ValueError as exc:
            raise ToolError(f"artifact path must stay within cwd: {item}") from exc
        paths.append(candidate)
    return paths


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            terminate_windows_process_tree(process, force=False)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        try:
            if os.name == "nt":
                terminate_windows_process_tree(process, force=True)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.kill()


def terminate_windows_process_tree(
    process: subprocess.Popen[bytes], *, force: bool
) -> None:
    """Terminate a Windows process and every descendant created beneath it."""
    command = ["taskkill.exe", "/PID", str(process.pid), "/T"]
    if force:
        command.append("/F")
    try:
        subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if force:
                process.kill()
            else:
                process.terminate()
            pass


def read_tail(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_TAIL_BYTES))
            data = handle.read()
        text = data.decode("utf-8", errors="replace")
        if size > MAX_TAIL_BYTES:
            text = "[output truncated]\n" + text
        return text.rstrip()
    except OSError:
        return ""


def tool_result(
    text: str,
    *,
    structured: dict[str, Any] | None = None,
    is_error: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }
    if structured is not None:
        result["structuredContent"] = structured
    return result


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "run",
            "description": (
                "Run one approved long local command and wait inside the current Codex turn. "
                "Returns only after completion, failure, cancellation, or deadline."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "activation_id": {"type": "string"},
                    "command": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 256,
                        "items": {"type": "string", "minLength": 1},
                        "description": "Executable and arguments as argv; shell syntax is not accepted.",
                    },
                    "cwd": {"type": "string", "description": "Absolute working directory."},
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_TIMEOUT_SECONDS,
                        "default": DEFAULT_TIMEOUT_SECONDS,
                    },
                    "success_exit_codes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "default": [0],
                    },
                    "required_artifacts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
                "required": ["activation_id", "command", "cwd"],
            },
            "annotations": {
                "title": "Run a long command in OneTurn",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        },
        {
            "name": "finish",
            "description": (
                "Mark the active OneTurn request complete after all requested work and final "
                "verification have finished."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "activation_id": {"type": "string"},
                    "summary": {"type": "string", "minLength": 1, "maxLength": 4000},
                },
                "required": ["activation_id", "summary"],
            },
            "annotations": {
                "title": "Finish OneTurn",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
    ]


def main() -> int:
    server = OneTurnServer()
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                if isinstance(message, dict):
                    server.handle(message)
            except json.JSONDecodeError as exc:
                server.error(None, -32700, f"parse error: {exc}")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
