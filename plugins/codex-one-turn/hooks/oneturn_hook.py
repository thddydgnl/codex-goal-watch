#!/usr/bin/env python3
"""UserPromptSubmit activation and Stop completion gate for OneTurn."""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from state_store import cleanup_old_states, find_turn_state, state_root, write_state  # noqa: E402


ACTIVATION_PATTERN = re.compile(r"(?i)(?:\$one-turn|\bone[ -]?turn|원턴)")
MAX_STOP_BLOCKS = 3


def emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")


def activate(payload: dict, root: Path) -> None:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not ACTIVATION_PATTERN.search(prompt):
        emit({})
        return

    session_id = str(payload.get("session_id", ""))
    turn_id = str(payload.get("turn_id", ""))
    existing = find_turn_state(root, session_id, turn_id)
    if existing and existing.get("status") == "active":
        activation_id = existing["activation_id"]
    else:
        activation_id = uuid.uuid4().hex
        write_state(
            root,
            {
                "activation_id": activation_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "cwd": payload.get("cwd"),
                "status": "active",
                "stop_blocks": 0,
                "created_at": int(time.time()),
            },
        )

    context = (
        f"OneTurn is active for this turn. activation_id={activation_id}. "
        "Use the bundled OneTurn run tool for long commands and pass this exact activation_id. "
        "Do not background or poll those commands. Call the bundled finish tool with the same "
        "activation_id only after the entire user request and final verification are complete."
    )
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    )


def stop(payload: dict, root: Path) -> None:
    state = find_turn_state(
        root,
        str(payload.get("session_id", "")),
        str(payload.get("turn_id", "")),
    )
    if not state:
        emit({})
        return
    if state.get("status") == "finished":
        emit({})
        return

    blocks = int(state.get("stop_blocks", 0))
    if blocks >= MAX_STOP_BLOCKS:
        state["status"] = "released"
        write_state(root, state)
        emit(
            {
                "systemMessage": (
                    "OneTurn safety release: the completion gate already continued this turn "
                    "three times without finish(). The turn is being allowed to end."
                )
            }
        )
        return

    state["stop_blocks"] = blocks + 1
    write_state(root, state)
    activation_id = state["activation_id"]
    emit(
        {
            "decision": "block",
            "reason": (
                f"OneTurn activation {activation_id} is not finalized. Continue in this same "
                "turn. If every requested task and final verification are complete, call the "
                "bundled OneTurn finish tool with this activation_id before the final response. "
                "Otherwise continue the work. Do not only report that a job is still running."
            ),
        }
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        root = state_root(PLUGIN_ROOT)
        cleanup_old_states(root)
        event = payload.get("hook_event_name")
        if event == "UserPromptSubmit":
            activate(payload, root)
        elif event == "Stop":
            stop(payload, root)
        else:
            emit({})
        return 0
    except Exception as exc:  # Fail open: hook bugs must never trap a turn.
        emit({"systemMessage": f"OneTurn hook failed open: {type(exc).__name__}: {exc}"})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
