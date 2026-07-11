<div align="center">

# OneTurn

**Long job. One Codex turn. No “still running” loop.**

긴 작업은 로컬에서 기다리고, 끝났을 때 같은 논리적 턴에서 이어갑니다.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

```text
without OneTurn                     with OneTurn

start                               start
  ↓                                   ↓
still running → new turn            local wait
  ↓                                   ↓
still running → new turn            job finished
  ↓                                   ↓
done                                verify → done
```

OneTurn is a local Codex plugin for long builds, tests, training runs, deploys,
and batch jobs.

- no model polling while the managed process runs;
- resume work in the same logical turn;
- verify exit codes, deadlines, and required artifacts;
- cancel the whole child process group;
- use official Codex Desktop and CLI.

> Unofficial community project. Not affiliated with OpenAI.

## Install / 설치

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

Restart Codex → open `/hooks` → review and trust both OneTurn hooks → start a
new task.

Codex를 재시작한 뒤 `/hooks`에서 hook 두 개를 검토·신뢰하고 새 task를 여세요.

Requires Codex 0.133+, Python 3.10+, Windows, macOS, or Linux.

## Use / 사용

Direct:

```text
Use OneTurn to run the entire test suite, fix failures, and verify the result.
```

```text
OneTurn으로 전체 테스트를 실행하고 실패를 모두 고쳐줘.
```

Skill:

```text
$one-turn run all training variants and compare the results.
```

Or ask normally. The Skill asks before a likely long command. There is no Auto
mode and no activation without approval.

평소처럼 요청해도 장기 작업이면 먼저 물어봅니다. 승인 없는 Auto 모드는 없습니다.

## Under the hood

```text
approval
  → turn-scoped activation
  → MCP run stays open until a terminal event
  → Codex analyzes the result
  → finish marks the objective complete
  → Stop hook allows the turn to end
```

No duration specified? The default deadline is **7 days**.

시간을 지정하지 않으면 기본 deadline은 **7일**입니다.

## Safe by default

- argv execution; no shell command strings
- Codex approval before process execution
- artifacts restricted to the working directory
- cancellation terminates the process group
- no credential access and no plugin-owned network calls
- Stop hook fails open after three blocks

## Limits

Same-turn continuity requires the Codex process to remain open. Restart
recovery is not included in v0.1. Windows, macOS, and Linux are supported.

Codex 프로세스가 종료되면 같은 turn ID 복구는 보장하지 않습니다. Windows,
macOS, Linux를 지원합니다.

## Remove / 제거

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

## License

MIT
