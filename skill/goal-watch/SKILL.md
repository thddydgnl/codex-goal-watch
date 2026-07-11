---
name: goal-watch
description: Stops /goal (and any long-running supervision task) from burning turns on "still running" polls. When waiting on a training run, build, deploy, or any long job, block inside ONE turn with scripts/wait_for.sh instead of ending the turn and re-checking. Use whenever a goal involves monitoring, waiting for, or babysitting a long-running process.
triggers:
  - /goal-watch
---

# goal-watch — one turn per wait, not one turn per poll

## Problem this solves

Codex `/goal` continues at turn boundaries. If a goal involves waiting for a
long job (model training, big build, deploy, batch pipeline), the default
behavior becomes: wake up → check status → report "still running" → end turn →
wake up again. Dozens of short turns that each cost tokens and rate limit, and
produce nothing.

## Core rule

**Never end a turn just to check on a job later.** If the next action depends
on a long-running process finishing, wait for it *inside the current turn* by
running one blocking command:

```bash
bash "$(dirname "$0")/scripts/wait_for.sh" --done-file <marker> --log <logfile>
```

(When invoking from a goal, use the installed path
`~/.codex/skills/goal-watch/scripts/wait_for.sh`.)

The script polls internally (default every 300s), prints a heartbeat line so
the harness sees activity, and only returns when there is something worth
acting on:

| Exit | Meaning | What to do |
|------|---------|------------|
| 0    | done condition met | proceed to the next step of the goal |
| 1    | failure detected (error regex in log, `--fail-if`, or pid died early) | diagnose using the tail it printed |
| 124  | `--max-wait` reached, still running | re-run the same command to keep waiting, or reassess |

## Reporting policy

While a job is running, do **not** produce interim status updates
("still running", "heartbeat OK", "no errors yet"). Report only when:

1. the job completed (exit 0),
2. a failure was detected (exit 1), or
3. `--max-wait` expired (exit 124) and you are deciding what to do next.

## Recipes

**ML training run** (done marker + error watch):

```bash
nohup python train.py --config exp1.yaml > runs/exp1/train.log 2>&1 &
echo $! > runs/exp1/pid
~/.codex/skills/goal-watch/scripts/wait_for.sh \
  --done-file runs/exp1/DONE \
  --pid "$(cat runs/exp1/pid)" \
  --log runs/exp1/train.log
```

Have the training script `touch runs/exp1/DONE` as its last line. If it can't
be modified, wrap it: `python train.py ... && touch runs/exp1/DONE`.

**Foreground alternative** (simplest when the session is stable): just run the
job in the foreground. The turn ends exactly when the job ends — zero polling.

**Chunked long waits** (multi-hour jobs, cautious about one giant command):

```bash
~/.codex/skills/goal-watch/scripts/wait_for.sh --done-file DONE --log train.log --max-wait 3600
```

On exit 124, run it again. One turn per hour instead of one turn per minute.

**Custom conditions** (remote queue, HTTP health check, GPU idle):

```bash
wait_for.sh --until "curl -sf http://localhost:8000/health" --interval 60
wait_for.sh --until "! squeue -j 998877 -h | grep -q ." --interval 600
wait_for.sh --fail-if "grep -q 'lease expired' scheduler.log" --done-file DONE
```

## When NOT to use this

- The check is instant and the next action doesn't depend on waiting.
- The user asked for periodic progress reports — then report at the cadence
  they asked for, but still use `wait_for.sh --max-wait` between reports.
- The job runs on infrastructure that outlives the session and the user would
  rather trigger Codex when it finishes: suggest appending
  `codex exec "the job finished — continue the plan"` to their job wrapper
  instead of keeping a goal alive.
