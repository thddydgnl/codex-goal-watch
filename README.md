<div align="center">

# Codex OneTurn

### Codex가 “아직 실행 중”이라는 말만 하려고 깨어나지 않게.

로컬 실행. 모델 polling 없이 대기. 같은 논리적 턴에서 재개.

### Keep Codex from waking up just to say “still running.”

Run locally. Wait without model polling. Resume in the same logical turn.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Codex 0.133+](https://img.shields.io/badge/Codex-0.133%2B-111827)](https://github.com/openai/codex)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)

[**English ↓**](#english)

</div>

---

Codex Goal은 끝나지 않은 작업을 이어가는 데 유용합니다. 하지만 긴 빌드, 학습,
테스트를 기다리는 동안에는 상태만 확인하는 continuation turn이 반복될 수 있습니다.

OneTurn은 기다림을 로컬 MCP 도구 호출 안으로 옮깁니다. 프로세스가 실행되는 동안
모델은 쉬고, 실제로 처리할 결과가 생겼을 때만 같은 논리적 턴에서 작업을 재개합니다.

## 왜 만들었나요?

Codex 사용량이 얼마 남지 않았을 때 Goal로 긴 작업을 시작하면, 이미 실행된 로컬
프로세스는 사용량이 소진된 뒤에도 계속 돌 수 있습니다. 하지만 기존 Goal 흐름은
대기 중간에 turn을 끝내고 새 continuation turn을 시작할 수 있으며, 바로 이 경계에서
사용량 제한에 걸리면 실행 흐름이 멈출 수 있습니다.

OneTurn은 이 **turn 종료 → 새 turn 시작** 과정을 없애기 위해 만들었습니다. 긴 작업을
하나의 MCP 호출 안에서 기다리고 Stop hook으로 조기 종료를 막아, Codex 세션이 살아
있는 동안 Goal을 하나의 논리적 turn에서 이어갑니다.

> **사용량이 얼마 남지 않았을 때 OneTurn을 사용하면**, 대기 도중 Codex 사용량이
> 모두 소진되더라도 이미 시작된 로컬 작업 자체는 멈추지 않고 완료 조건까지 계속
> 실행됩니다. 대기 중 상태 확인을 위한 모델 호출도 발생하지 않습니다.

```text
남은 Codex 사용량이 적음
        │
        ▼
OneTurn으로 Goal의 긴 로컬 작업 시작
        │
        ├── 사용량 소진 → 로컬 작업은 계속 실행
        ├── 중간 polling turn 없음
        └── turn 종료·재시작 경계 없음
        │
        ▼
작업 완료 → 같은 논리적 turn에서 결과 전달
```

OneTurn은 사용량 제한을 우회하거나 사용량을 복구하지는 않습니다. 작업이 끝난 뒤
추가 분석, 코드 수정 또는 새로운 모델 호출이 필요하다면 사용 가능한 Codex 사용량이
다시 필요할 수 있습니다.

```text
기존 방식

Turn 1  작업 시작
Turn 2  아직 실행 중
Turn 3  아직 실행 중
Turn 4  아직 실행 중
Turn 5  결과 확인

OneTurn

Turn 1  작업 시작 ───── 로컬 대기 ───── 결과 확인 ───── 완료
                       대기 중 모델 polling: 0
```

> Codex OneTurn은 OpenAI의 공식 제품이 아닌 커뮤니티 플러그인입니다.

## 설치

Codex에서 새 task를 열고 아래 내용을 그대로 전달하세요.

```text
https://github.com/thddydgnl/codex-goal-watch

이 저장소의 Codex OneTurn 플러그인을 설치해줘.
기존 goal-watch가 설치되어 있으면 완전히 제거하고,
설치 후 필요한 Codex 재시작과 hook 신뢰 방법도 안내해줘.
```

Codex가 저장소를 확인하고 설치 명령을 실행하기 전에 필요한 권한을 요청합니다.

설치가 끝나면:

1. Codex를 재시작하고 새 task를 엽니다.
2. Codex CLI에서 `/hooks`를 실행합니다.
3. OneTurn hook 두 개를 검토하고 신뢰합니다.

요구 사항: Codex CLI 0.133 이상, Python 3.10 이상, macOS 또는 Linux.

## 사용법

### OneTurn 직접 지정

```text
OneTurn으로 전체 빌드와 테스트를 실행하고 실패를 모두 고친 뒤
최종 결과까지 검증해줘.
```

또는 포함된 Skill을 직접 선택합니다.

```text
$one-turn 세 가지 학습 variant를 모두 실행하고 결과를 비교해줘.
```

### OneTurn이 먼저 물어보게 하기

평소처럼 요청해도 됩니다.

```text
전체 테스트를 실행하고 실패를 모두 고쳐줘.
```

Skill이 오래 걸릴 가능성이 높은 명령을 발견하면 OneTurn을 사용할지 먼저 묻습니다.
`OneTurn으로 실행`이라고 답하기 전에는 활성화되지 않습니다.

사용자 동의 없는 Auto 모드는 없습니다.

## 달라지는 점

| 항목 | OneTurn 동작 |
|---|---|
| 대기 | MCP 호출이 프로세스의 종료 이벤트까지 유지됨 |
| 모델 polling | 상태 확인만을 위한 반복 모델 호출 없음 |
| 턴 생명주기 | Stop hook이 같은 turn ID에서 조기 종료 방지 |
| 완료 판정 | exit code, deadline, 필수 artifact 확인 가능 |
| 취소 | tool 취소 시 child process group 종료 |
| 기본 deadline | 더 짧은 시간이 없으면 7일 |

## 작동 원리

```text
사용자 승인
    │
    ▼
UserPromptSubmit hook이 turn 범위 activation ID 생성
    │
    ▼
Codex가 one_turn.run(argv, cwd, deadline, artifacts) 호출
    │
    ├── 로컬 child process 실행
    ├── stdout/stderr를 로컬 로그에 기록
    └── exit, 취소 또는 deadline까지 MCP 호출 유지
    │
    ▼
Codex가 terminal result를 한 번 받고 같은 턴에서 작업 계속
    │
    ▼
최종 검증 → one_turn.finish → Stop hook이 턴 종료 허용
```

Stop hook은 미완료 상태의 조기 종료를 최대 세 번 차단합니다. 이후에는 플러그인
오류로 task가 영원히 갇히지 않도록 fail-open 방식으로 종료를 허용합니다.

## 보안 모델

- 명령은 shell 문자열이 아니라 argv 배열로 실행합니다.
- 실행 전에 Codex MCP 승인을 사용합니다.
- artifact 경로는 선택한 working directory 밖으로 나갈 수 없습니다.
- ChatGPT 인증 정보나 OpenAI API key를 읽지 않습니다.
- 플러그인 자체 네트워크 요청을 만들지 않습니다.
- hook은 자동 신뢰되지 않으며 `/hooks`에서 직접 검토합니다.
- 로그는 로컬 Codex plugin data 디렉터리에 보관합니다.

구현 확인: [`server.py`](plugins/codex-one-turn/mcp/server.py) ·
[`oneturn_hook.py`](plugins/codex-one-turn/hooks/oneturn_hook.py)

## 현재 한계

- 같은 턴의 연속성은 Codex 프로세스와 세션이 실행 중일 때만 보장됩니다.
- Codex 재시작 후 turn 복구는 v0.1에 포함되지 않습니다.
- Windows는 아직 지원하지 않습니다.
- 하나의 논리적 턴이 모델 호출 한 번을 뜻하지는 않습니다. 분석과 오류 수정에는
  여러 모델 단계가 필요할 수 있지만, 프로세스를 기다리는 동안에는 polling하지 않습니다.
- 공개 Before/After benchmark는 재현 가능한 E2E 측정이 끝난 뒤 게시합니다.

## 제거

Codex에 같은 저장소 URL과 함께 제거를 요청하세요.

```text
https://github.com/thddydgnl/codex-goal-watch

이 저장소에서 설치한 Codex OneTurn 플러그인을 완전히 제거해줘.
OneTurn marketplace와 기존 goal-watch 흔적도 함께 정리해줘.
```

## 기여하기

버그 재현, E2E turn trace, 플랫폼 호환성 개선 PR을 환영합니다. Issue를 작성할 때
Codex 버전, 운영체제, 활성화 방식, hook 신뢰 여부를 함께 적어주세요.

OneTurn이 실제 대기 문제를 해결했다면 Star로 다른 Codex 사용자에게 알려주세요.

## 라이선스

MIT

---

<a id="english"></a>

<div align="center">

# Codex OneTurn — English

### Let Codex wait for long jobs—without waking up just to say “still running.”

Run locally. Wait without model polling. Resume in the same logical turn.

[**↑ 한국어로 돌아가기**](#codex-oneturn)

</div>

---

Codex Goals are great at continuing work. They are less great at waiting.
A long build, training run, or test suite can turn into repeated continuation
turns that do nothing except check status and report that the job is still
running.

OneTurn moves that wait into a local MCP tool call. The model sleeps while the
process runs and resumes only when something actionable happens.

## Why I built it

When only a small amount of Codex usage remains, a local process already
started by a Goal can keep running even after that usage is exhausted. The
problem is the Goal lifecycle around it: Codex may end the current turn and
start a new continuation turn while waiting. If the usage limit is reached at
that boundary, the workflow can stop even though the local job could have
continued.

OneTurn was built to remove that **end turn → start another turn** cycle. It
waits inside one MCP call and uses a Stop hook to prevent premature completion,
keeping the Goal in one logical turn while the Codex process and session remain
alive.

> **When your Codex usage is almost gone, OneTurn lets an already-started local
> job keep running toward its completion condition even if the remaining usage
> is exhausted during the wait.** It makes no model calls merely to poll status.

```text
Only a small amount of Codex usage remains
        │
        ▼
Start the Goal's long local job with OneTurn
        │
        ├── usage exhausted → local job keeps running
        ├── no intermediate polling turns
        └── no end-turn/restart boundary
        │
        ▼
Job completes → result returns in the same logical turn
```

OneTurn does not bypass or restore Codex usage limits. If the completed job
still requires model reasoning, code changes, or another model call, available
Codex usage may be required at that point.

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

Open a new Codex task and paste the following message:

```text
https://github.com/thddydgnl/codex-goal-watch

Install the Codex OneTurn plugin from this repository.
Remove any legacy goal-watch installation first, then tell me how to restart
Codex and review the required hooks after installation.
```

Codex inspects the repository and requests permission before running the
required installation commands.

After installation:

1. Restart Codex and start a new task.
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

Ask Codex to remove the plugin using the same repository URL:

```text
https://github.com/thddydgnl/codex-goal-watch

Remove the Codex OneTurn plugin installed from this repository.
Also remove its marketplace and any remaining legacy goal-watch files.
```

## Contributing

Bug reports, reproducible E2E traces, and platform compatibility PRs are
welcome. Please include your Codex version, OS, activation path, and whether
the hook was trusted.

If OneTurn solves a real waiting problem for you, consider starring the repo.
It helps other Codex users find the project.

## License

MIT
