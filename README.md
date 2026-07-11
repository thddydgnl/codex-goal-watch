# codex-goal-watch

**Stop Codex `/goal` from burning your rate limit on "still running" polls.**

[한국어 README](README.ko.md)

## The problem

Codex `/goal` continues work at turn boundaries. When a goal involves waiting
for something slow — a model training run, a long build, a deploy — the default
behavior looks like this:

```
worked for 30s   → "job is still running, heartbeat OK"
worked for 1m21s → "still running, not stalled"
worked for 29s   → "no errors yet, keeping goal monitoring"
worked for 2m25s → "waiting for the first checkpoint"
...
```

Dozens of short wake-up turns, each consuming tokens and requests, each
producing nothing but "still running". There is no config option to change
this cadence — it's how goal continuation works.

## The fix

`goal-watch` is an [Agent Skill](https://agentskills.io) that moves the wait
*inside* a single turn. Instead of ending the turn and re-checking, Codex runs
one blocking command — `wait_for.sh` — that polls internally and only returns
when the job **finished**, **failed**, or a **max-wait budget** expired.

One turn per wait, not one turn per poll.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/thddydgnl/codex-goal-watch.git
cd codex-goal-watch && ./install.sh
```

This copies the skill to `~/.codex/skills/goal-watch` (respects `$CODEX_HOME`).
No dependencies beyond bash and coreutils; works on macOS and Linux.

## Use

Once installed, Codex picks the skill up automatically whenever a goal
involves babysitting a long job. You can also invoke it explicitly:

```
/goal-watch
/goal Train all three variants of Idea 1 sequentially, then run strict finalization
```

The skill teaches Codex to write waits like this:

```bash
nohup python train.py --config exp1.yaml > runs/exp1/train.log 2>&1 &
echo $! > runs/exp1/pid
~/.codex/skills/goal-watch/scripts/wait_for.sh \
  --done-file runs/exp1/DONE \
  --pid "$(cat runs/exp1/pid)" \
  --log runs/exp1/train.log
```

`wait_for.sh` checks every 5 minutes (configurable), prints a heartbeat line
so the harness sees activity, and exits with:

| Exit code | Meaning |
|-----------|---------|
| `0` | done — marker file appeared / `--until` command succeeded |
| `1` | failed — error regex matched the log, `--fail-if` fired, or the pid died before finishing |
| `124` | `--max-wait` reached while still running — rerun to keep waiting |

### Options

```
--done-file PATH      succeed when PATH exists
--until "CMD"         succeed when CMD exits 0
--fail-if "CMD"       fail when CMD exits 0
--log FILE            watch FILE for error patterns
--error-regex REGEX   what counts as an error (default covers Traceback/OOM/NaN/RuntimeError)
--pid PID             react when the process exits
--interval SECONDS    internal poll interval (default 300)
--max-wait SECONDS    give up with exit 124 after this long (default: wait forever)
--tail N              log lines to dump on failure (default 50)
--quiet               no heartbeat lines
```

### More recipes

```bash
# Wait for an HTTP service to come up, checking every minute
wait_for.sh --until "curl -sf http://localhost:8000/health" --interval 60

# Wait for a Slurm job to leave the queue
wait_for.sh --until '! squeue -j 998877 -h | grep -q .' --interval 600

# Chunked waiting for multi-hour jobs: one turn per hour
wait_for.sh --done-file DONE --log train.log --max-wait 3600   # rerun on exit 124
```

## Zero-polling alternative

If your job outlives your Codex session anyway, skip goal babysitting
entirely and trigger Codex when the job ends:

```bash
python train.py --config exp1.yaml
codex exec "Training for exp1 finished — check the results and start the next variant."
```

## Uninstall

```bash
rm -rf ~/.codex/skills/goal-watch
```

## License

MIT
