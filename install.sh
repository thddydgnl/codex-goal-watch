#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="codex-one-turn"
MARKETPLACE_NAME="codex-one-turn"
REMOTE_SOURCE="thddydgnl/codex-goal-watch"
MIN_CODEX_VERSION="0.133.0"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

version_at_least() {
  local current="$1" minimum="$2" index
  local IFS=.
  local -a have need
  read -r -a have <<<"$current"
  read -r -a need <<<"$minimum"
  for index in 0 1 2; do
    local h="${have[$index]:-0}" n="${need[$index]:-0}"
    h="${h%%[^0-9]*}"; n="${n%%[^0-9]*}"
    [ "${h:-0}" -gt "${n:-0}" ] && return 0
    [ "${h:-0}" -lt "${n:-0}" ] && return 1
  done
  return 0
}

remove_legacy_agents_block() {
  local file="$1" tmp
  [ -f "$file" ] || return 0
  grep -q '<!-- goal-watch:start -->' "$file" || return 0
  tmp="$(mktemp)"
  awk '
    /<!-- goal-watch:start -->/ { skip=1; next }
    /<!-- goal-watch:end -->/ { skip=0; next }
    !skip { print }
  ' "$file" >"$tmp"
  mv "$tmp" "$file"
  say "Removed legacy goal-watch block from $file"
}

remove_legacy_goal_watch() {
  local legacy="$CODEX_DIR/skills/goal-watch"
  if [ -d "$legacy" ]; then
    rm -rf "$legacy"
    say "Removed legacy goal-watch skill from $legacy"
  fi
  remove_legacy_agents_block "$CODEX_DIR/AGENTS.md"
  remove_legacy_agents_block "$CODEX_DIR/AGENTS.override.md"
}

uninstall() {
  if command -v codex >/dev/null 2>&1; then
    codex plugin remove "$PLUGIN_NAME@$MARKETPLACE_NAME" >/dev/null 2>&1 || true
    codex plugin marketplace remove "$MARKETPLACE_NAME" >/dev/null 2>&1 || true
  fi
  remove_legacy_goal_watch
  say "Codex OneTurn has been uninstalled. Job logs were preserved."
}

[ "${1:-}" = "--uninstall" ] && { uninstall; exit 0; }
[ "$#" -eq 0 ] || fail "unknown option: $1"

command -v codex >/dev/null 2>&1 || fail "Codex CLI is required"
command -v python >/dev/null 2>&1 || \
  fail "Python 3.10 or newer must be available as the 'python' command"

CODEX_VERSION="$(codex --version | awk '{print $2}')"
version_at_least "$CODEX_VERSION" "$MIN_CODEX_VERSION" || \
  fail "Codex $MIN_CODEX_VERSION or newer is required (found $CODEX_VERSION)"

PYTHON_VERSION="$(python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
version_at_least "$PYTHON_VERSION" "3.10.0" || \
  fail "Python 3.10 or newer is required (found $PYTHON_VERSION)"

remove_legacy_goal_watch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/.agents/plugins/marketplace.json" ]; then
  SOURCE="$SCRIPT_DIR"
  SOURCE_KIND="local"
else
  SOURCE="$REMOTE_SOURCE"
  SOURCE_KIND="git"
fi

if codex plugin marketplace list | awk 'NR > 1 {print $1}' | grep -qx "$MARKETPLACE_NAME"; then
  if [ "$SOURCE_KIND" = "git" ]; then
    codex plugin marketplace upgrade "$MARKETPLACE_NAME" >/dev/null
    say "Updated marketplace: $MARKETPLACE_NAME"
  else
    say "Using local marketplace: $MARKETPLACE_NAME"
  fi
else
  codex plugin marketplace add "$SOURCE" >/dev/null
  say "Added marketplace: $MARKETPLACE_NAME"
fi

codex plugin add "$PLUGIN_NAME@$MARKETPLACE_NAME" >/dev/null
say "Installed plugin: $PLUGIN_NAME"
say ""
say "Next steps:"
say "  1. Restart Codex and start a new task."
say "  2. In Codex CLI, open /hooks and trust the two OneTurn hooks."
say "  3. Ask normally, or write: OneTurn으로 이 작업을 실행해줘."
say ""
say "Uninstall: $0 --uninstall"
