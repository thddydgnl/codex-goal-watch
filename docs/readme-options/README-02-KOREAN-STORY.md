<div align="center">

# Codex OneTurn

## Codex가 “아직 실행 중”이라는 말만 반복하지 않게.

긴 작업은 로컬에서 기다리고, 끝났을 때 같은 논리적 턴에서 이어갑니다.

[![Tests](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml/badge.svg)](https://github.com/thddydgnl/codex-goal-watch/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Codex Plugin](https://img.shields.io/badge/Codex-Plugin-111827)](https://github.com/openai/codex)

[English summary](#english-summary)

</div>

---

Codex에게 오래 걸리는 학습이나 테스트를 맡겨보면 이런 장면을 만나게 됩니다.

```text
“학습은 정상적으로 실행 중입니다.”
“아직 checkpoint를 기다리고 있습니다.”
“오류는 없으며 계속 감시하겠습니다.”
```

작업은 그대로인데 Goal turn만 계속 늘어납니다. 상태를 확인할 때마다 모델이 다시
실행되고, 사용자는 같은 문장을 반복해서 보게 됩니다.

**OneTurn은 기다리는 일을 모델에게 맡기지 않습니다.**

```text
작업 시작
→ 로컬에서 종료 이벤트 대기
→ 완료 또는 실패할 때만 Codex 재개
→ 결과 분석과 최종 검증
→ 같은 논리적 턴 종료
```

공식 Codex Desktop과 CLI는 그대로 사용합니다. 별도 Codex 포크나 대체 프로그램을
실행하지 않습니다.

> Codex OneTurn은 OpenAI의 공식 제품이 아닌 커뮤니티 프로젝트입니다.

## 30초 설치

macOS·Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

설치 후 세 가지만 하면 됩니다.

1. Codex를 재시작하고 새 task를 엽니다.
2. CLI에서 `/hooks`를 실행합니다.
3. OneTurn hook 두 개의 코드를 확인하고 신뢰합니다.

요구 사항: Codex CLI 0.133 이상, Python 3.10 이상.

## 사용법

### 직접 명시

가장 확실하고 간단한 방법입니다.

```text
OneTurn으로 전체 빌드와 테스트를 실행하고 실패를 모두 고쳐줘.
```

```text
$one-turn 세 가지 학습 variant를 순서대로 실행하고 결과를 비교해줘.
```

시간을 적을 필요는 없습니다. 별도 시간이 없으면 각 실행의 기본 deadline은
**7일**입니다.

### Ask

평소처럼 요청해도 됩니다.

```text
전체 테스트가 통과할 때까지 고쳐줘.
```

Skill이 오래 걸릴 가능성을 발견하면 실행 전에 OneTurn을 사용할지 묻습니다.
`OneTurn으로 실행`이라고 답해야 활성화됩니다. 사용자 동의 없는 Auto 모드는 없습니다.

## 무엇이 달라지나요?

| 기존 흐름 | OneTurn |
|---|---|
| 모델이 상태를 다시 확인 | 로컬 MCP가 종료 이벤트를 기다림 |
| “아직 실행 중” turn 반복 | 기다리는 동안 추가 Goal turn 없음 |
| PID·marker·polling 관리 | 사용자가 알 필요 없음 |
| 완료 선언에 의존 | exit code·deadline·artifact 검증 가능 |
| 조기 종료 가능 | Stop hook이 같은 turn에서 계속 |

## 핵심 원리

### 1. `run`이 반환하지 않고 기다립니다

Codex가 OneTurn `run` 도구를 호출하면 해당 도구는 프로세스가 끝나기 전까지
결과를 돌려주지 않습니다. 모델은 기다리는 동안 다시 호출되지 않습니다.

### 2. Stop hook이 조기 종료를 막습니다

프로세스 하나가 끝났어도 오류 수정이나 최종 검증이 남을 수 있습니다. Codex가
`finish` 전에 턴을 끝내려 하면 Stop hook이 같은 turn ID에서 계속하도록 지시합니다.

### 3. 무한히 가두지 않습니다

Stop hook은 최대 세 번만 종료를 막습니다. hook 오류나 반복 실패가 생기면 안전하게
턴 종료를 허용하는 fail-open 방식입니다.

## 안전하게 실행합니다

- shell 문자열 대신 argv 배열 사용
- 실행 전 Codex MCP 승인
- 작업 폴더 밖 artifact 검사 거부
- 취소 시 child process group 종료
- API key와 ChatGPT 로그인 정보에 접근하지 않음
- 플러그인 자체 네트워크 요청 없음
- hook을 설치만으로 자동 신뢰하지 않음

구현을 직접 확인할 수 있습니다.

- [`mcp/server.py`](plugins/codex-one-turn/mcp/server.py)
- [`hooks/oneturn_hook.py`](plugins/codex-one-turn/hooks/oneturn_hook.py)
- [`skills/one-turn/SKILL.md`](plugins/codex-one-turn/skills/one-turn/SKILL.md)

## 현재 지원 범위

- macOS·Linux
- 로컬 단일 프로세스
- Codex 프로세스와 세션이 살아 있는 동안 동일 turn 유지
- exit code·deadline·필수 artifact 검증
- 사용자 취소

Codex 종료 후 동일 turn 복구와 Windows 지원은 후속 버전 범위입니다. 실제 공개
benchmark는 E2E 측정이 재현 가능해진 뒤 숫자와 함께 게시합니다.

## 제거

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

## English summary

Codex OneTurn is a community plugin that keeps long-running local jobs inside
one logical Codex turn. Its MCP `run` call waits for a terminal process event,
so the model does not wake up merely to poll status. A Stop hook prevents
premature completion until final verification is recorded with `finish`.

Activate it explicitly:

```text
Use OneTurn to run the full test suite, fix every failure, and verify the result.
```

Or let the Skill ask before a likely long command. There is no unapproved Auto
mode. The default deadline is seven days. macOS and Linux are supported in v0.1.

## 함께 만들어요

사용 중 문제가 생기면 Codex 버전, 운영체제, 실행한 명령, hook 신뢰 여부를 포함해
Issue를 남겨주세요. 재현 가능한 사례와 E2E 측정 PR을 환영합니다.

실제로 불필요한 대기 turn을 줄여줬다면 Star로 다른 Codex 사용자에게 알려주세요.

## 라이선스

MIT
