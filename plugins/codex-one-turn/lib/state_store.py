"""Small atomic state store shared by the OneTurn hooks and MCP server."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "codex-one-turn"


def state_root(plugin_root: Path | None = None) -> Path:
    override = os.environ.get("ONETURN_STATE_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.environ.get("PLUGIN_DATA"):
        root = Path(os.environ["PLUGIN_DATA"])
    else:
        root = _derive_plugin_data(plugin_root or Path.cwd())
    root.mkdir(parents=True, exist_ok=True)
    (root / "states").mkdir(exist_ok=True)
    (root / "jobs").mkdir(exist_ok=True)
    return root


def _derive_plugin_data(plugin_root: Path) -> Path:
    resolved = plugin_root.resolve()
    parts = resolved.parts
    try:
        cache_index = len(parts) - 1 - tuple(reversed(parts)).index("cache")
        marketplace = parts[cache_index + 1]
        plugin = parts[cache_index + 2]
        codex_home = Path(*parts[: cache_index - 1])
        if parts[cache_index - 1] == "plugins" and plugin == PLUGIN_NAME:
            return codex_home / "plugins" / "data" / f"{plugin}-{marketplace}"
    except (ValueError, IndexError):
        pass
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "plugins" / "data" / f"{PLUGIN_NAME}-local"


def state_path(root: Path, activation_id: str) -> Path:
    if not activation_id or any(ch not in "0123456789abcdef" for ch in activation_id):
        raise ValueError("invalid activation_id")
    return root / "states" / f"{activation_id}.json"


def read_state(root: Path, activation_id: str) -> dict[str, Any] | None:
    path = state_path(root, activation_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def write_state(root: Path, state: dict[str, Any]) -> None:
    path = state_path(root, str(state["activation_id"]))
    state["updated_at"] = int(time.time())
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def iter_states(root: Path) -> Iterable[dict[str, Any]]:
    for path in (root / "states").glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                yield value
        except (OSError, json.JSONDecodeError):
            continue


def find_turn_state(root: Path, session_id: str, turn_id: str) -> dict[str, Any] | None:
    matches = [
        state
        for state in iter_states(root)
        if state.get("session_id") == session_id
        and state.get("turn_id") == turn_id
        and state.get("status") in {"active", "finished"}
    ]
    return max(matches, key=lambda item: int(item.get("updated_at", 0)), default=None)


def cleanup_old_states(root: Path, max_age_seconds: int = 7 * 24 * 60 * 60) -> None:
    cutoff = time.time() - max_age_seconds
    for directory in (root / "states", root / "jobs"):
        for path in directory.iterdir():
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except (FileNotFoundError, OSError):
                continue
