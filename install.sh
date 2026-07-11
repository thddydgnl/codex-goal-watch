#!/usr/bin/env bash
# Installs the goal-watch skill into ~/.codex/skills (or $CODEX_HOME/skills).
#
#   curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash
#
# Add --agents-md to also append an always-on rule to ~/.codex/AGENTS.md so the
# skill applies deterministically to every session (recommended):
#
#   curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash -s -- --agents-md
#
# or from a local clone:
#
#   ./install.sh [--agents-md]
set -euo pipefail

REPO="thddydgnl/codex-goal-watch"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
DEST="$CODEX_DIR/skills/goal-watch"

WITH_AGENTS_MD=0
for arg in "$@"; do
  case "$arg" in
    --agents-md) WITH_AGENTS_MD=1 ;;
    *) echo "install.sh: unknown option: $arg" >&2; exit 2 ;;
  esac
done

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

AGENTS_MD="$CODEX_DIR/AGENTS.md"
MARKER_START="<!-- goal-watch:start -->"
if [ "$WITH_AGENTS_MD" -eq 1 ]; then
  if [ -f "$AGENTS_MD" ] && grep -qF "$MARKER_START" "$AGENTS_MD"; then
    echo "AGENTS.md rule already present; skipping."
  else
    [ -f "$AGENTS_MD" ] && [ -s "$AGENTS_MD" ] && printf '\n' >> "$AGENTS_MD"
    cat >> "$AGENTS_MD" <<'EOF'
<!-- goal-watch:start -->
## Long-running jobs (goal-watch skill)

When a task or /goal involves waiting on a long-running process (training run,
build, deploy, batch job), never end a turn just to poll status. Follow
~/.codex/skills/goal-watch/SKILL.md: block inside the current turn with
scripts/wait_for.sh (chunked with --max-wait 240, re-run on exit 124 in the
same turn). Do not emit interim "still running" reports — report only on
completion, failure, or when deciding what to do after a wait budget expires.
<!-- goal-watch:end -->
EOF
    echo "Appended always-on rule to: $AGENTS_MD"
    echo "  (remove the goal-watch block from that file to undo)"
  fi
else
  echo
  echo "Tip: re-run with --agents-md to add an always-on rule to $AGENTS_MD"
  echo "     so the skill applies to every goal without being mentioned."
fi

echo
echo "Try it in Codex:"
echo "  /goal-watch                       # invoke the skill directly"
echo "  /goal <objective that involves waiting on a long job>"
echo
echo "Uninstall with: rm -rf \"$DEST\""
