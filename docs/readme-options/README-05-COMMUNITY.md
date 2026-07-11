<div align="center">

# Codex OneTurn

## Help build the missing wait primitive for long-running Codex work.

No repeated status turns. No model polling while a local job runs.
Continue when the result is ready.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Issues welcome](https://img.shields.io/badge/issues-welcome-22C55E.svg)](https://github.com/thddydgnl/codex-goal-watch/issues)

**English** · [한국 사용자를 위한 안내](#한국-사용자를-위한-안내)

</div>

---

## The problem we want to solve

Coding agents can reason about a failure. They do not need to reason about a
process that is simply still running.

Yet a long build or training run can produce a loop like this:

```text
wake → check → “still running” → end turn → wake → check → repeat
```

OneTurn is an open-source Codex plugin that moves waiting into a local MCP call
and uses a completion hook to keep unfinished work in the active turn.

The first goal is intentionally small:

```text
one local process
one terminal event
one logical Codex turn
zero model polling while waiting
```

> This is an unofficial community project and is not affiliated with OpenAI.

## Try the v0.1 prototype

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

Restart Codex, start a new task, and review the plugin hooks through `/hooks`.

Then try:

```text
Use OneTurn to run this repository's complete test suite,
fix every failure, and verify the final artifact.
```

Or:

```text
$one-turn run a two-minute simulated job and verify its output file.
```

The two-minute example is only for testing. Without an explicit duration, the
default deadline is seven days.

## Two activation paths

| Path | Behavior |
|---|---|
| Direct | Include `OneTurn` or `$one-turn` in the request; no second confirmation |
| Ask | Request long work normally; the Skill asks before activation |

There is no silent Auto mode. User approval is part of the contract.

## What is implemented

- Codex plugin manifest and repository marketplace
- OneTurn Agent Skill
- dependency-free Python stdio MCP server
- blocking `run` tool with exit, deadline, artifact, and cancellation handling
- explicit `finish` tool for final objective completion
- UserPromptSubmit activation hook
- Stop completion gate with a three-block fail-open limit
- migration that removes the old shell-based goal watcher
- Windows, macOS, and Linux CI

## What needs community validation

We will not publish a token-reduction percentage without a reproducible test.
The most useful early reports are:

1. A before/after trace from the same long command.
2. Codex turn IDs before and after Stop continuation.
3. Model request counts while `run` is pending.
4. Cancellation behavior for process trees.
5. Compatibility reports across Codex Desktop and CLI releases.

Please include your Codex version, OS, command shape, activation path, and hook
trust state in every report.

## How it works

```text
User
  │ approves OneTurn
  ▼
Activation hook ── stores activation_id + turn_id
  │
  ▼
MCP run ────────── starts argv process and waits locally
  │                 model is not polled here
  ▼
Terminal result ── exit / failure / cancel / deadline
  │
  ▼
Codex ──────────── analyzes, fixes, verifies
  │
  ▼
finish ─────────── marks complete
  │
  ▼
Stop hook ──────── allows the same logical turn to end
```

## Security review checklist

Before trusting the hooks, verify these files yourself:

- [`plugins/codex-one-turn/hooks/hooks.json`](plugins/codex-one-turn/hooks/hooks.json)
- [`plugins/codex-one-turn/hooks/oneturn_hook.py`](plugins/codex-one-turn/hooks/oneturn_hook.py)
- [`plugins/codex-one-turn/mcp/server.py`](plugins/codex-one-turn/mcp/server.py)

Current boundaries:

- commands use argv arrays and never `shell=True`;
- execution uses Codex MCP approval;
- artifact paths stay inside `cwd`;
- cancellation targets the child process group;
- no OpenAI credential access;
- no plugin-owned network requests;
- hook errors fail open;
- logs remain local.

## Roadmap

### v0.1 — current

- local process waiting
- same-session turn continuation
- exit, deadline, artifact, and cancellation handling
- Ask and direct activation
- Windows, macOS, and Linux support

### Next

- reproducible E2E benchmark and demo GIF
- parallel job groups
- better progress UI without model-visible polling
- durable job metadata

### Research

- restart-safe suspended turns
- remote CI, deploy, Slurm, and Kubernetes terminal events
- upstream lifecycle primitives that can replace plugin-level coordination

## 한국 사용자를 위한 안내

OneTurn은 빌드·테스트·학습이 실행되는 동안 Codex가 “아직 실행 중” 확인을 위해
새 Goal turn을 반복하지 않게 만드는 플러그인입니다.

```text
OneTurn으로 전체 테스트를 실행하고 실패를 모두 고친 뒤 결과를 검증해줘.
```

공식 Codex Desktop과 CLI를 그대로 사용하며 별도 Codex 프로그램을 실행하지 않습니다.
설치 후 `/hooks`에서 코드를 직접 검토하고 신뢰해야 합니다. Windows, macOS, Linux를
지원하며 Codex 재시작 후 같은 turn ID 복구는 아직 지원하지 않습니다.

한국어 Issue와 PR도 환영합니다.

## Contributing

- Start with a reproducible issue.
- Keep security-sensitive changes small and reviewable.
- Add tests for lifecycle and process-management changes.
- Do not add performance claims without scripts and raw results.
- Korean and English documentation improvements are equally welcome.

If this solves a real problem for you, star the repository and share your
trace. Early evidence will shape the project more than feature requests alone.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

## License

MIT
