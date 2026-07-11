#!/usr/bin/env bash
# wait_for.sh — block inside a single agent turn until a long-running job
# finishes or fails, instead of ending the turn and re-polling across turns.
#
# Exit codes:
#   0   = done condition met (or watched pid exited cleanly with no done condition)
#   1   = failure detected (error pattern in log, --fail-if met, or pid died early)
#   124 = --max-wait reached while still running (caller may re-run to keep waiting)
#   2   = usage error
set -u

usage() {
  cat <<'EOF'
Usage: wait_for.sh [options]

Done conditions (at least one of these, or --pid, is required):
  --done-file PATH      succeed when PATH exists
  --until "CMD"         succeed when CMD exits 0

Failure conditions (optional):
  --log FILE            watch FILE for --error-regex matches
  --error-regex REGEX   extended regex marking failure
                        (default: "Traceback|CUDA out of memory|OutOfMemoryError|nan loss|NaN detected|RuntimeError")
  --fail-if "CMD"       fail when CMD exits 0

Process watch (optional):
  --pid PID             stop waiting when PID exits; if a done condition was
                        given and is not met at that point, treat as failure

Pacing:
  --interval SECONDS    seconds between checks (default: 300)
  --max-wait SECONDS    give up after this long with exit 124 (default: 0 = wait forever)
  --tail N              log lines to print on failure (default: 50)
  --quiet               suppress heartbeat lines while waiting

Examples:
  # ML training: done when checkpoint marker appears, fail on OOM/NaN in log
  wait_for.sh --done-file runs/exp1/DONE --log runs/exp1/train.log

  # Wait for a background process, checking every 2 minutes, at most 1 hour
  wait_for.sh --pid 12345 --interval 120 --max-wait 3600

  # Custom condition: remote job status
  wait_for.sh --until "squeue -j 998877 -h | grep -qv ." --interval 600
EOF
}

INTERVAL=300
MAX_WAIT=0
DONE_FILE=""
UNTIL_CMD=""
FAIL_CMD=""
LOG_FILE=""
ERROR_REGEX="Traceback|CUDA out of memory|OutOfMemoryError|nan loss|NaN detected|RuntimeError"
PID=""
TAIL_LINES=50
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --done-file)   DONE_FILE="$2"; shift 2 ;;
    --until)       UNTIL_CMD="$2"; shift 2 ;;
    --fail-if)     FAIL_CMD="$2"; shift 2 ;;
    --log)         LOG_FILE="$2"; shift 2 ;;
    --error-regex) ERROR_REGEX="$2"; shift 2 ;;
    --pid)         PID="$2"; shift 2 ;;
    --interval)    INTERVAL="$2"; shift 2 ;;
    --max-wait)    MAX_WAIT="$2"; shift 2 ;;
    --tail)        TAIL_LINES="$2"; shift 2 ;;
    --quiet)       QUIET=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) echo "wait_for.sh: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$DONE_FILE" ] && [ -z "$UNTIL_CMD" ] && [ -z "$PID" ]; then
  echo "wait_for.sh: need at least one of --done-file, --until, or --pid" >&2
  usage >&2
  exit 2
fi

dump_log() {
  if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
    echo "--- last $TAIL_LINES lines of $LOG_FILE ---"
    tail -n "$TAIL_LINES" "$LOG_FILE"
  fi
}

START=$(date +%s)
while :; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))

  # Failure checks come first so a job that errored out and also touched its
  # done marker is still reported as failed.
  if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ] && grep -qE "$ERROR_REGEX" "$LOG_FILE"; then
    echo "FAILED: error pattern (/$ERROR_REGEX/) matched in $LOG_FILE after ${ELAPSED}s"
    dump_log
    exit 1
  fi
  if [ -n "$FAIL_CMD" ] && eval "$FAIL_CMD" >/dev/null 2>&1; then
    echo "FAILED: --fail-if condition met after ${ELAPSED}s"
    dump_log
    exit 1
  fi

  if [ -n "$DONE_FILE" ] && [ -e "$DONE_FILE" ]; then
    echo "DONE: $DONE_FILE exists (waited ${ELAPSED}s)"
    exit 0
  fi
  if [ -n "$UNTIL_CMD" ] && eval "$UNTIL_CMD" >/dev/null 2>&1; then
    echo "DONE: --until condition met (waited ${ELAPSED}s)"
    exit 0
  fi

  if [ -n "$PID" ] && ! kill -0 "$PID" 2>/dev/null; then
    if [ -n "$DONE_FILE$UNTIL_CMD" ]; then
      echo "FAILED: pid $PID exited after ${ELAPSED}s but done condition was not met"
      dump_log
      exit 1
    fi
    echo "DONE: pid $PID exited (waited ${ELAPSED}s)"
    exit 0
  fi

  if [ "$MAX_WAIT" -gt 0 ] && [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo "STILL_RUNNING: max wait of ${MAX_WAIT}s reached; job has not finished"
    exit 124
  fi

  if [ "$QUIET" -eq 0 ]; then
    echo "[wait_for] ${ELAPSED}s elapsed; still running; next check in ${INTERVAL}s"
  fi
  sleep "$INTERVAL"
done
