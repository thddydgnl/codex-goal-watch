#!/usr/bin/env bash
# Installs the goal-watch skill into ~/.codex/skills (or $CODEX_HOME/skills).
#
#   curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash
#
# or from a local clone:
#
#   ./install.sh
set -euo pipefail

REPO="thddydgnl/codex-goal-watch"
DEST="${CODEX_HOME:-$HOME/.codex}/skills/goal-watch"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/skill/goal-watch" ]; then
  SRC="$SCRIPT_DIR/skill/goal-watch"
  TMP=""
else
  TMP="$(mktemp -d)"
  trap '[ -n "$TMP" ] && rm -rf "$TMP"' EXIT
  echo "Downloading $REPO ..."
  if command -v git >/dev/null 2>&1; then
    git clone --quiet --depth 1 "https://github.com/$REPO.git" "$TMP/repo"
  else
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
    mv "$TMP"/*-main "$TMP/repo"
  fi
  SRC="$TMP/repo/skill/goal-watch"
fi

mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"
chmod +x "$DEST/scripts/wait_for.sh"

echo "Installed goal-watch skill to: $DEST"
echo
echo "Try it in Codex:"
echo "  /goal-watch                       # invoke the skill directly"
echo "  /goal <objective that involves waiting on a long job>"
echo
echo "Uninstall with: rm -rf \"$DEST\""
