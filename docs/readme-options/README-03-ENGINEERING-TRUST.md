# Codex OneTurn

**A lifecycle-safe waiting primitive for long-running Codex jobs.**

OneTurn packages a Skill, a local stdio MCP server, and Codex lifecycle hooks
into one plugin. It keeps a long process inside the active tool call, resumes
the same Codex turn after a terminal event, and gates premature completion.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Codex 0.133+](https://img.shields.io/badge/Codex-0.133%2B-111827)](https://github.com/openai/codex)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)

> 한국어: 긴 작업을 기다리는 동안 모델 polling과 추가 Goal turn을 만들지 않고,
> 완료 이벤트 후 같은 논리적 턴에서 작업을 계속하는 비공식 Codex 플러그인입니다.

## The invariant

While a managed process is running:

```text
model requests caused by status polling = 0
additional Goal turns caused by status polling = 0
```

This does not claim that an entire objective uses one model request. Analysis,
repairs, and verification may require additional model steps inside the same
logical turn.

## Why this exists

Goal continuation is useful for unfinished work, but process waiting is not a
reasoning task. Repeatedly asking a model whether a process is still running
adds latency, context, and noisy status messages without changing the state of
the job.

OneTurn separates the two responsibilities:

| Responsibility | Owner |
|---|---|
| Start and supervise a local process | OneTurn MCP server |
| Wait for exit, cancellation, or deadline | OneTurn MCP server |
| Interpret output and repair failures | Codex model |
| Decide whether the whole objective is complete | Codex model + `finish` |
| Prevent premature turn completion | Stop hook |

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ Official Codex Desktop / CLI                                │
│                                                              │
│  UserPromptSubmit hook                                       │
│    └─ explicit approval → activation_id scoped to turn_id    │
│                                                              │
│  OneTurn Skill                                               │
│    ├─ Ask before likely long work                            │
│    └─ direct activation with OneTurn or $one-turn            │
│                                                              │
│  MCP server                                                  │
│    ├─ run(argv, cwd, deadline, artifacts)                    │
│    └─ finish(activation_id, summary)                         │
│                                                              │
│  Stop hook                                                   │
│    ├─ finished → allow completion                            │
│    ├─ active → continue same TurnContext                     │
│    └─ three blocks → fail open                               │
└──────────────────────────────────────────────────────────────┘
```

The MCP server is dependency-free Python and speaks JSON-RPC over stdio. The
`run` request remains open until a terminal event. Output is written to a local
log and only the final tail is returned.

## State machine

```text
User approval
    │
    ▼
 active ── run ──► running ── exit ──► active
    │                 │
    │                 ├─ cancel ─────► active + cancelled result
    │                 └─ deadline ───► active + timed_out result
    │
    ├─ finish ───────► finished ─────► turn may end
    └─ Stop × 3 ─────► released ─────► fail-open turn end
```

State files are written atomically under the Codex plugin data directory.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

After installation:

1. Restart Codex and start a new task.
2. Open `/hooks` in Codex CLI.
3. Review and trust the UserPromptSubmit and Stop hooks.

Supported in v0.1: macOS, Linux, Codex CLI 0.133+, Python 3.10+.

## Activation policy

OneTurn has no automatic mode.

### Direct

```text
Use OneTurn to run the build, fix all failures, and verify the release artifact.
```

```text
$one-turn train the model and verify the final checkpoint.
```

### Ask

For a likely long-running command, the Skill asks for confirmation. The user
must reply with `Run with OneTurn` or `OneTurn으로 실행`. No process starts
before explicit approval.

## `run` contract

Conceptual input:

```json
{
  "activation_id": "turn-scoped token",
  "command": ["python", "train.py", "--config", "exp1.yaml"],
  "cwd": "/absolute/project/path",
  "timeout_seconds": 604800,
  "success_exit_codes": [0],
  "required_artifacts": ["runs/exp1/final.pt"]
}
```

Success requires all of the following:

- the process was not cancelled;
- the deadline was not exceeded;
- the exit code is allowed;
- every required artifact exists inside `cwd`.

A successful process does not finalize the OneTurn objective. Codex must finish
all requested analysis and verification, then call `finish`.

## Safety properties

- No `shell=True`; commands are argv arrays.
- Working directories must be absolute and exist.
- Artifact paths must resolve inside `cwd`.
- MCP execution defaults to approval mode `prompt`.
- Cancellation terminates the child process group.
- Hook failures return success with a warning and do not trap the turn.
- The Stop gate releases after three continuations.
- The plugin does not access OpenAI credentials or make its own network calls.

## Guarantees and non-guarantees

| Statement | Status |
|---|---|
| No model polling while `run` is pending | Designed and component-tested |
| Stop continuation keeps the current Codex turn context | Supported by current Codex hook lifecycle |
| Default job deadline is seven days | Implemented and tested |
| Same turn survives a Codex process restart | Not supported |
| Windows process-group semantics | Not supported in v0.1 |
| Every long command is detected automatically | Intentionally not supported |
| Public token/turn reduction percentage | Not claimed before reproducible E2E measurement |

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/codex-one-turn
```

The test suite covers:

- explicit versus non-explicit activation;
- blocking until `finish`;
- three-block fail-open behavior;
- successful process execution and artifact verification;
- cancellation and process-group termination;
- absolute working-directory enforcement;
- seven-day default deadline.

## Source map

| Component | Path |
|---|---|
| Plugin manifest | [`plugins/codex-one-turn/.codex-plugin/plugin.json`](plugins/codex-one-turn/.codex-plugin/plugin.json) |
| Skill | [`plugins/codex-one-turn/skills/one-turn/SKILL.md`](plugins/codex-one-turn/skills/one-turn/SKILL.md) |
| MCP server | [`plugins/codex-one-turn/mcp/server.py`](plugins/codex-one-turn/mcp/server.py) |
| Hooks | [`plugins/codex-one-turn/hooks/oneturn_hook.py`](plugins/codex-one-turn/hooks/oneturn_hook.py) |
| Tests | [`tests/test_one_turn.py`](tests/test_one_turn.py) |

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

## Contributing

High-value contributions include reproducible turn traces, cancellation edge
cases, Windows process supervision, restart recovery design, and independent
security review.

## License

MIT
