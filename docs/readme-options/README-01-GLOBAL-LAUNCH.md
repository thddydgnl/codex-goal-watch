<div align="center">

# Codex OneTurn

### Let Codex wait for long jobs—without waking up just to say “still running.”

Run locally. Wait without model polling. Resume in the same logical turn.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Codex 0.133+](https://img.shields.io/badge/Codex-0.133%2B-111827)](https://github.com/openai/codex)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)

**English** · [한국어 요약](#한국어-요약)

</div>

---

Codex Goals are great at continuing work. They are less great at waiting.
A long build, training run, or test suite can turn into repeated continuation
turns that do nothing except check status and report that the job is still
running.

OneTurn moves that wait into a local MCP tool call. The model sleeps while the
process runs and resumes only when something actionable happens.

```text
Before

Turn 1  start job
Turn 2  still running
Turn 3  still running
Turn 4  still running
Turn 5  inspect result

With OneTurn

Turn 1  start job ───── local wait ───── inspect result ───── finish
                        model polling: 0
```

> OneTurn is an unofficial community plugin for Codex. It is not affiliated
> with or endorsed by OpenAI.

## Install

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

Then:

1. Restart Codex and open a new task.
2. Run `/hooks` in Codex CLI.
3. Review and trust the two OneTurn hooks.

Requirements: Codex CLI 0.133+, Python 3.10+, macOS or Linux.

## Use it

### Say OneTurn directly

```text
Use OneTurn to run the full build and test suite, fix every failure,
and verify the final result.
```

Or invoke the bundled Skill:

```text
$one-turn run all three training variants and compare the results.
```

### Let OneTurn ask

Ask normally:

```text
Run the full test suite and fix every failure.
```

For a likely long-running command, the Skill asks before switching to OneTurn.
Nothing is activated until you reply with `Run with OneTurn` or
`OneTurn으로 실행`.

There is no Auto mode.

## What you get

| | OneTurn behavior |
|---|---|
| Waiting | The MCP call stays open until a terminal event |
| Model polling | No repeated model calls just to check status |
| Turn lifecycle | A Stop hook prevents premature completion in the same turn ID |
| Completion | Exit code, deadline, and required artifacts can be checked |
| Cancellation | Cancelling the tool terminates the child process group |
| Default deadline | 7 days when no shorter duration is requested |

## How it works

```text
User approval
    │
    ▼
UserPromptSubmit hook creates a turn-scoped activation ID
    │
    ▼
Codex calls one_turn.run(argv, cwd, deadline, artifacts)
    │
    ├── local child process runs
    ├── stdout/stderr goes to a local log
    └── the MCP call waits for exit, cancellation, or deadline
    │
    ▼
Codex receives one terminal result and continues the task
    │
    ▼
Final verification → one_turn.finish → Stop hook allows completion
```

The Stop hook blocks premature completion at most three times. After that it
fails open so a plugin bug cannot trap a task forever.

## Security model

- Commands are argv arrays, not shell strings.
- The execution tool uses Codex MCP approval.
- Artifact checks cannot escape the selected working directory.
- The plugin does not read ChatGPT credentials or OpenAI API keys.
- The plugin makes no network requests of its own.
- Hooks are not trusted automatically; you review them in `/hooks`.
- Logs stay in the local Codex plugin data directory.

Read the implementation: [`server.py`](plugins/codex-one-turn/mcp/server.py) ·
[`oneturn_hook.py`](plugins/codex-one-turn/hooks/oneturn_hook.py)

## Current limits

- Same-turn continuity requires the Codex process and session to stay alive.
- Restart recovery is not part of v0.1.
- Windows is not supported yet.
- One logical turn does not mean one model call. Analysis and fixes can still
  require multiple model steps; waiting itself does not poll the model.
- The public Before/After benchmark will be published after the E2E harness is
  reproducible.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

## 한국어 요약

Codex OneTurn은 긴 빌드·테스트·학습 작업을 기다리는 동안 “아직 실행 중” 확인을
위한 새 Goal turn과 모델 polling을 만들지 않도록 설계된 Codex 플러그인입니다.

```text
OneTurn으로 전체 테스트를 실행하고 실패를 모두 고친 뒤 최종 결과까지 검증해줘.
```

사용자가 직접 OneTurn을 명시하거나 Ask 질문에 승인한 경우에만 활성화됩니다.
시간을 지정하지 않으면 기본 deadline은 7일입니다. 설치 후 Codex를 재시작하고
`/hooks`에서 hook 두 개를 직접 검토·신뢰해야 합니다.

최종 선택된 한국어 우선·영문 통합 구성은 [메인 README](../../README.md)를 참고하세요.

## Contributing

Bug reports, reproducible E2E traces, and platform compatibility PRs are
welcome. Please include your Codex version, OS, activation path, and whether
the hook was trusted.

If OneTurn solves a real waiting problem for you, consider starring the repo.
It helps other Codex users find the project.

## License

MIT
