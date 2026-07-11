# Codex OneTurn 프로젝트 기획서

> 문서 상태: v0.1 프로토타입 구현(2026-07-11)
> 대상 프로젝트: 신규 `Codex OneTurn` 확장
> 핵심 목표: 공식 Codex Desktop과 CLI를 그대로 사용하면서, 장기 작업을 기다리는 Goal이 불필요한 새 턴을 반복 생성하지 않게 한다.

## 1. 한 문장 소개

Codex OneTurn은 학습, 빌드, 테스트, 배포처럼 오래 걸리는 작업을 Codex가 로컬에서 기다렸다가 **같은 논리적 턴에서 이어서 처리**하도록 만드는 초보자 친화적인 확장 기능이다.

### 현재 구현 상태

다음 v0.1 구성요소가 저장소에 구현되어 있다.

- `.codex-plugin/plugin.json`과 repo marketplace
- Ask·직접 명시 두 경로를 정의한 OneTurn Skill
- 프로세스 종료까지 반환하지 않는 dependency-free Python MCP `run` 도구
- 전체 완료를 기록하는 MCP `finish` 도구
- 명시적 OneTurn 요청을 turn-scoped activation으로 만드는 `UserPromptSubmit` hook
- 완료 전 종료를 같은 turn ID에서 최대 세 번 계속하는 `Stop` hook
- 기존 `goal-watch`, `wait_for.sh`, `AGENTS.md` 블록 제거 migration
- 설치·재설치·제거 스크립트
- 성공, artifact 검증, 취소, completion gate 및 fail-open 단위 테스트

로컬에서는 plugin/Skill validator, 6개 단위 테스트, 실제 marketplace 설치 및 설치된 MCP discovery smoke test를 통과했다. 남은 검증은 Codex를 재시작하고 hook을 신뢰한 새 task에서 실제 turn ID와 대기 중 모델 호출 수를 계측하는 end-to-end 테스트다.

## 2. 만들려는 이유

Codex Goal이 장기 작업을 감독할 때 다음과 같은 흐름이 반복될 수 있다.

```text
작업 시작
→ 아직 실행 중인지 확인
→ “정상 실행 중”이라고 응답하며 턴 종료
→ Goal이 새 continuation turn 시작
→ 다시 상태 확인
→ 반복
```

이 과정은 사용자에게 의미 있는 진전 없이 다음 비용을 만든다.

- “아직 실행 중”이라는 중간 응답이 계속 쌓인다.
- 상태 확인마다 모델 호출, 토큰 및 요청 한도를 소비할 수 있다.
- 하나의 작업이 여러 턴으로 잘게 나뉘어 진행 상황을 이해하기 어렵다.
- 사용자가 Goal을 믿고 맡기기보다 계속 확인해야 한다.
- PID, 로그, 완료 파일, polling 간격 같은 내부 구현을 사용자가 알아야 한다.

이 프로젝트는 단순히 polling 간격을 늘리는 것이 아니라, **기다림 자체를 모델 턴 사이가 아닌 로컬 실행 계층으로 옮기는 것**을 목표로 한다.

## 3. 제품 목표

### 사용자 목표

사용자는 공식 Codex Desktop 또는 CLI를 계속 사용하면서 평소처럼 Goal을 요청한다.

```text
세 가지 학습 variant를 순서대로 실행하고 결과를 비교한 뒤 최종 검증까지 완료해.
```

사용자는 다음 항목을 직접 다루지 않아야 한다.

- `nohup`, PID 및 프로세스 관리
- `DONE` 또는 `FAILED` marker 파일
- shell timeout과 heartbeat
- polling 간격과 재시도 횟수
- 별도의 Codex 포크 또는 대체 CLI

### 기술 목표

장기 작업이 실행되는 동안에는 다음 조건을 만족해야 한다.

1. 새로운 Goal continuation turn을 만들지 않는다.
2. 기다리는 동안 상태 확인 목적의 모델 호출을 만들지 않는다.
3. 프로세스 완료 또는 실패 이벤트가 발생하면 같은 논리적 턴에서 처리를 재개한다.
4. 사용자가 정한 완료 기준을 검증한 뒤에만 Goal 완료를 허용한다.
5. 사용자가 언제든 안전하게 취소할 수 있다.

### 성공을 판단하는 핵심 지표

| 지표 | 목표 |
|---|---:|
| 장기 작업 1개를 기다리는 동안 생성되는 추가 Goal turn | 0 |
| 기다리는 동안 상태 확인용 모델 호출 | 0 |
| 정상 시나리오의 논리적 turn ID | 처음부터 끝까지 동일 |
| 설치에 필요한 사용자 명령 | 1개 이하 |
| PID·marker·timeout을 사용자가 직접 설정하는 단계 | 0 |

## 4. 목표 사용자

주요 사용자는 전문 시스템 개발자가 아니라 Codex로 결과물을 빠르게 만드는 사람들이다.

- 바이브코더 및 개인 개발자
- 장시간 빌드와 테스트를 실행하는 앱 개발자
- 모델 학습과 실험을 반복하는 연구자
- 배포 또는 데이터 처리 작업을 Codex에 맡기는 사용자
- 터미널과 프로세스 관리에 익숙하지 않은 초보자

따라서 기능의 우수성만큼 다음 경험이 중요하다.

- 공식 Codex를 교체하지 않는 안전한 설치
- 장기 작업을 감지하면 적용 여부를 묻는 간단한 `Ask` 경험
- 필요할 때 요청에 OneTurn 사용을 직접 명시할 수 있는 명확한 사용법
- 현재 무엇을 기다리는지 알 수 있는 간단한 상태 표시
- 취소와 제거가 쉬운 구조
- 동작 범위와 한계에 대한 솔직한 설명

## 5. 제품 원칙

### 공식 Codex를 그대로 사용한다

별도 포크나 `goalx` 같은 대체 실행 파일을 주 제품으로 삼지 않는다. 가능하다면 공식 Codex의 플러그인, Skill, hook, MCP 등 공개 확장 지점만 사용한다.

### 대기는 로컬에서, 판단은 모델이 한다

프로세스가 실행 중인지 확인하는 일은 로컬 helper가 담당한다. 프로세스가 끝난 뒤 결과를 해석하고 다음 행동을 결정하는 일만 모델이 담당한다.

### polling 결과를 모델에게 반복 전달하지 않는다

UI용 진행 상태는 표시할 수 있지만, heartbeat나 “아직 실행 중” 결과를 매번 모델 입력으로 반환하지 않는다. 모델은 완료, 실패, 취소 또는 deadline 도달처럼 행동이 필요한 이벤트가 있을 때만 다시 실행한다.

### 실패해도 사용자를 턴에 가두지 않는다

hook 또는 helper가 오작동하면 무한 루프에 빠지지 않아야 한다. 비상 해제, 최대 대기 시간, 취소, 오류 시 안전한 종료 정책이 필요하다.

### 자동화하되 실행 내용을 숨기지 않는다

사용자는 실행 명령, 작업 폴더, 경과 시간, 취소 방법을 확인할 수 있어야 한다. 인증 정보나 API key에는 접근하지 않는다.

## 6. 기존 `goal-watch` 제거 정책

`Codex OneTurn`은 기존 `goal-watch`를 확장하거나 fallback으로 유지하지 않는 **완전히 새로운 제품**으로 개발한다.

다음 구성은 최종 제품에서 모두 제거한다.

- `goal-watch` Agent Skill
- `wait_for.sh`
- `AGENTS.md`에 삽입하는 장기 대기 규칙
- PID, `DONE`·`FAILED` marker 및 로그 정규식 기반 polling
- plugin 미지원 버전을 위한 shell fallback
- `/goal-watch` 또는 `$goal-watch` 사용법

기존 저장소를 그대로 전환한다면 출시 전에 위 파일과 설치 경로를 삭제하고, 저장소 이름·README·설치 프로그램도 `Codex OneTurn` 기준으로 교체한다. 이미 `goal-watch`를 설치한 사용자를 위해서는 fallback을 유지하는 대신, 기존 스킬과 `AGENTS.md` 블록을 깨끗하게 제거하는 **일회성 migration/uninstall 절차**만 제공한다.

OneTurn이 요구하는 Codex 확장 API를 지원하지 않는 환경에서는 기능을 축소해 흉내 내지 않는다. 설치 단계에서 지원하지 않는 버전임을 알리고 설치를 중단하거나 Codex 업데이트를 안내한다.

## 7. 제안 아키텍처

```text
공식 Codex Desktop / CLI
        │
        ├─ OneTurn Skill
        │    └─ 사용자가 승인하거나 직접 명시한 작업에 OneTurn 도구 사용
        │
        ├─ 사전 도구 실행 제어
        │    └─ 장기 작업을 감지하면 자동 실행하지 않고 사용자에게 적용 여부 질문
        │
        ├─ OneTurn 로컬 도구 서버
        │    ├─ 작업 시작
        │    ├─ stdout/stderr 기록
        │    ├─ 종료 이벤트 대기
        │    ├─ 결과와 artifact 검증
        │    └─ 취소 및 deadline 처리
        │
        └─ 턴 종료 제어
             ├─ Goal 완료 → 종료 허용
             ├─ 실행 중인 job 존재 → 완료 이벤트까지 대기
             └─ 남은 작업 존재 → 같은 논리적 턴에서 계속
```

### 주요 구성 요소

#### 1. OneTurn Skill

모델이 장기 작업을 일반 shell background 실행과 반복 상태 확인으로 처리하지 않고, 전용 도구를 사용하도록 안내한다. Skill은 행동을 유도하는 계층이며 동일 턴 보장의 근거가 되어서는 안 된다.

#### 2. 로컬 Job Manager

장기 프로세스의 전체 생명주기를 관리한다.

```text
queued → running → succeeded | failed | cancelled | timed_out
```

각 job에는 최소한 다음 정보가 필요하다.

```text
job_id
goal_id
turn_id
command 및 working directory
started_at / finished_at
process identity
exit code
log path
required artifacts
deadline
```

#### 3. 장기 실행 도구

첫 버전에서는 단일 foreground 작업을 안전하게 실행하고 기다리는 도구 하나면 충분하다.

개념적 입력 예시는 다음과 같다.

```json
{
  "command": ["python", "train.py", "--config", "exp1.yaml"],
  "cwd": "/workspace/project",
  "successExitCodes": [0],
  "requiredArtifacts": ["runs/exp1/final_checkpoint.pt"],
  "deadlineSeconds": 604800
}
```

도구는 heartbeat마다 반환하지 않고 terminal event가 발생했을 때만 결과를 반환한다.

#### 4. 턴 종료 제어

모델이 중간 상태 문장을 최종 응답으로 생성하더라도 OneTurn Goal이 활성 상태라면 턴 종료를 보류해야 한다. 실행 중인 job이 있으면 이벤트를 기다리고, job은 없지만 해야 할 일이 남았다면 같은 논리적 턴에 continuation context를 전달한다.

이 기능은 Codex가 실제로 제공하는 hook 또는 lifecycle API의 동작과 한계가 확인된 뒤 구현 방식을 확정한다.

#### 5. Completion Contract

자연어 Goal만으로는 런타임이 완료 여부를 완전히 검증할 수 없다. 기계적으로 확인할 수 있는 조건은 별도의 contract로 표현한다.

```text
- 허용된 exit code인가
- 필요한 파일이 생성되었는가
- 검증 명령이 성공했는가
- 결과 JSON이 지정 조건을 만족하는가
```

모델의 완료 선언과 completion contract의 검증이 모두 성공해야 Goal을 완료한다.

## 8. 예상 사용자 경험

### 설치

최종 목표는 한 번의 설치 동작이다.

```text
1. 설치 링크 또는 명령 실행
2. Codex가 확장 기능과 로컬 helper의 권한을 설명
3. 사용자가 한 번 승인
4. Codex 재시작 후 자동 사용
```

설치 프로그램은 다음을 처리해야 한다.

- Codex Desktop/CLI 및 최소 지원 버전 확인
- 운영체제와 CPU에 맞는 helper 설치
- checksum 또는 서명 검증
- plugin, Skill, hook, tool 설정 등록
- 설치 상태 진단
- 완전한 제거 및 원상복구

### 평상시 사용

OneTurn은 자동으로 작업을 전환하지 않는다. 사용자는 아래 두 가지 활성화 방식 중 하나를 사용한다.

#### 방식 1 — Ask

사용자가 평소처럼 자연어로 요청하면 Codex가 장기 작업을 감지한다.

```text
앱을 빌드하고 전체 테스트가 통과할 때까지 고친 뒤 결과를 알려줘.
```

OneTurn은 곧바로 실행하지 않고 사용자에게 한 번 확인한다.

```text
이 작업에는 오래 실행될 수 있는 빌드와 테스트가 포함됩니다.
OneTurn으로 실행하면 기다리는 동안 새 Goal turn이나 상태 확인용 모델 호출을 만들지 않습니다.

[OneTurn으로 실행] [일반 방식으로 실행]
```

사용자가 승인한 현재 작업에만 OneTurn을 적용한다. 거절하면 공식 Codex의 일반 실행 방식으로 진행한다. Ask는 장기 작업을 놓치지 않게 도와주는 감지 기능일 뿐, 사용자 확인 없는 자동 적용 기능이 아니다.

#### 방식 2 — 사용자가 직접 명시

사용자는 최초 요청이나 후속 메시지에 OneTurn 사용을 직접 적을 수 있다.

```text
OneTurn으로 앱을 빌드하고 전체 테스트가 통과할 때까지 고쳐줘.
```

```text
이 학습 작업은 OneTurn을 사용해서 완료될 때까지 같은 논리적 턴에서 기다려줘.
```

Codex 버전에서 명시적 Skill 선택 문법을 지원한다면 다음과 같은 짧은 호출도 제공할 수 있다.

```text
$one-turn 빌드와 전체 테스트를 완료해줘.
```

직접 명시한 경우에는 별도의 OneTurn 적용 확인을 반복하지 않는다. 다만 실제 명령 실행에 필요한 Codex의 기존 보안 승인과 sandbox 확인은 그대로 적용한다.

긴 작업이 감지되면 화면에는 다음 정보만 간단히 표시한다.

```text
OneTurn이 로컬 작업 완료를 기다리는 중

작업: npm test
경과: 12분 08초
대기 중 모델 호출: 0
취소: Esc
```

작업 완료 후에는 같은 논리적 턴에서 결과 분석과 후속 작업을 계속한다.

### 활성화 정책

| 활성화 방식 | 시작 조건 | 사용자 확인 |
|---|---|---|
| Ask | Codex가 장기 작업을 감지 | 작업마다 OneTurn 적용 여부 확인 |
| 직접 명시 | 요청에 `OneTurn` 또는 지원되는 명시적 호출을 포함 | OneTurn 적용 확인은 생략 |

`Auto` 모드는 제공하지 않는다. OneTurn은 턴의 생명주기와 장기 프로세스를 제어하므로 사용자의 승인 없이 자동으로 활성화해서는 안 된다. 별도의 `Off` 모드도 필요하지 않다. Ask에서 거절하거나 요청에 OneTurn을 명시하지 않으면 일반 Codex 동작을 사용한다.

## 9. 범위

### v0.1에 포함

- 공식 Codex CLI에서 설치 및 로딩
- 가능하다면 동일 패키지의 Desktop 지원
- 로컬 단일 프로세스 실행과 이벤트 기반 종료 대기
- 정상 종료, 비정상 종료, deadline 및 사용자 취소
- exit code와 필수 artifact 검증
- 실패 시 제한된 로그 tail 전달
- 같은 논리적 turn ID 유지 검증
- 대기 중 모델 호출 0회 검증
- 설치, 진단, 제거 흐름
- macOS, Linux 우선 지원

### 후속 버전

- Windows 지원
- 여러 job의 병렬 실행
- GitHub Actions, 배포 서비스 등 원격 job 대기
- 앱 재시작 후 job 상태 복구
- suspended turn의 영속화와 복원
- 설정 UI와 상세 상태 화면
- 자동 업데이트 및 공개 marketplace 배포

### 명시적 비목표

- 공식 Codex 바이너리를 덮어쓰기
- Codex 인증 정보 또는 API key 관리
- 모든 shell 명령을 강제로 OneTurn으로 전환
- 사용자 확인이나 직접 명시 없이 OneTurn을 자동 활성화
- 기존 `goal-watch`, `wait_for.sh` 또는 shell fallback 유지
- v0.1에서 Codex 종료 후 동일 turn ID 복원
- 무제한 대기 또는 취소 불가능한 실행

## 10. 중요한 한계

동일 턴 보장은 Codex 프로세스와 세션이 살아 있는 동안만 가능할 수 있다. Codex가 종료, 업데이트 또는 crash되면 기존 turn을 그대로 복구하려면 별도의 durable suspended-turn 기능이 필요하다.

초기 버전은 다음과 같이 보장 범위를 명시한다.

> Codex 세션이 실행 중인 동안에는 장기 작업을 같은 논리적 턴에서 기다린다. Codex가 종료되면 background job의 처리 정책에 따라 작업은 종료되거나 계속될 수 있지만, 재개 시 동일 turn ID는 보장하지 않는다.

또한 “한 논리적 턴”은 모델 호출이 정확히 한 번이라는 뜻이 아니다. 작업 시작, 결과 분석 및 후속 조치를 위해 모델은 여러 번 실행될 수 있다. 보장하려는 것은 기다리는 동안 새 Goal continuation turn과 상태 확인용 모델 호출을 만들지 않는 것이다.

## 11. 보안 및 신뢰 요구사항

- 공식 Codex 인증 흐름을 변경하지 않는다.
- API key와 ChatGPT 로그인 정보에 접근하지 않는다.
- 기본 구현은 local stdio 통신을 사용하고 자체 네트워크 요청을 하지 않는다.
- 실행할 명령과 working directory를 사용자에게 표시한다.
- helper binary의 checksum과 빌드 출처를 공개한다.
- 사용자가 즉시 취소할 수 있어야 한다.
- Codex 종료 시 child process를 종료할지 유지할지 정책을 명확히 한다.
- 오류 시 무한히 턴 종료를 막지 않는 fail-safe를 둔다.
- 비상 해제 및 완전한 uninstall 방법을 제공한다.

공개 배포 시에는 비공식 커뮤니티 프로젝트임을 명확히 밝히고, 공식 Codex와의 차이 및 수집하는 데이터가 있다면 그 범위를 공개한다.

## 12. 반드시 통과해야 하는 테스트

### 핵심 동작

1. 20분짜리 모의 작업에서도 Goal turn이 추가 생성되지 않는다.
2. 대기 중 모델 요청 수가 증가하지 않는다.
3. 작업 완료 후 처리 재개 시 최초 turn ID가 유지된다.
4. 여러 순차 작업을 하나의 논리적 턴 안에서 완료한다.
5. 성공 exit code와 필수 artifact를 모두 검증한다.
6. 비정상 종료 정보를 같은 턴의 모델에게 전달한다.
7. Goal이 active인 동안 조기 종료 시도를 안전하게 막는다.
8. completion contract 실패 시 완료 선언을 거부한다.

### 안전성

9. 사용자가 기다리는 중 취소할 수 있다.
10. hook 또는 helper crash 시 무한 loop에 빠지지 않는다.
11. deadline 도달 시 명확한 결과와 복구 선택지를 제공한다.
12. Codex 종료 시 child process 정책이 문서와 일치한다.
13. 공식 Codex의 일반 작업과 Goal 동작을 방해하지 않는다.
14. Ask에서 거절한 작업은 OneTurn 개입 없이 공식 기본 동작으로 진행한다.
15. 요청에 OneTurn을 직접 명시하면 적용 여부를 다시 묻지 않고 활성화한다.
16. 사용자 승인이나 직접 명시 없이 OneTurn이 자동 활성화되지 않는다.

### 설치

17. 깨끗한 환경에서 한 번의 설치로 사용할 수 있다.
18. 재설치와 업데이트가 기존 설정을 손상시키지 않는다.
19. 제거 후 생성된 설정과 실행 파일이 남지 않는다.
20. migration이 기존 `goal-watch` Skill과 `AGENTS.md` 블록을 완전히 제거한다.

## 13. 먼저 검증해야 할 기술 가설

대화에서 제안된 일부 내용은 제품 방향을 잡기 위한 가설이며, 구현에 들어가기 전에 현재 배포된 Codex Desktop과 CLI에서 확인해야 한다.

| 가설 | 검증 질문 |
|---|---|
| 플러그인이 Skill, local tool server, lifecycle hook을 함께 배포할 수 있다 | 현재 공개 manifest schema와 배포판이 모두 지원하는가? |
| 턴 종료 hook이 종료를 막고 같은 turn context를 재개할 수 있다 | 실제 hook의 decision schema와 turn ID 동작은 무엇인가? |
| 장기 MCP tool call이 모델 호출 없이 계속 대기할 수 있다 | Desktop/CLI별 timeout과 취소 semantics는 무엇인가? |
| CLI용 플러그인을 Desktop에서도 동일하게 로딩할 수 있다 | 지원 버전과 설치 경로가 동일한가? |
| 공개 marketplace 또는 설치 링크를 제공할 수 있다 | 외부 개발자가 사용할 수 있는 공식 배포 절차가 있는가? |

이 가설 중 핵심 항목이 지원되지 않으면 다음 대안을 순서대로 검토한다.

1. 지원되는 공식 확장 지점만으로 가능한 범위의 플러그인
2. Codex Core에 필요한 lifecycle API를 제안
3. 최후의 선택으로 별도 downstream binary 제공

기존 `goal-watch` 또는 `wait_for.sh` 방식으로 되돌아가는 대안은 채택하지 않는다.

## 14. 개발 단계

### Phase 0 — 사실 확인과 최소 실험

- 현재 Codex의 plugin 및 hook 공식 schema 확인
- Desktop과 CLI의 지원 버전 및 차이 확인
- 5분짜리 모의 job으로 장기 tool call timeout 측정
- hook block 전후의 turn ID와 모델 호출 수 계측
- 사용자 취소와 Codex 종료 시 동작 확인

산출물은 기능 구현이 아니라 “공식 확장만으로 동일 턴 보장이 가능한가”에 대한 재현 가능한 실험 결과다.

### Phase 1 — 기술 프로토타입

- 단일 로컬 job 실행 도구
- 완료 이벤트까지 비 polling 대기
- 종료 코드와 artifact 검증
- 최소 Skill과 턴 종료 제어
- turn ID 및 모델 요청 수 integration test

### Phase 2 — 초보자용 제품화

- 한 번의 설치와 제거
- 권한 및 실행 명령 안내
- Ask와 직접 명시 두 가지 활성화 방식
- 기존 `goal-watch` 완전 제거 migration
- 상태 표시와 취소 UX
- macOS/Linux 릴리스 자동 빌드 및 checksum
- 한국어/영어 README와 데모

### Phase 3 — 공개 베타

- 실제 빌드, 테스트, 학습 시나리오 benchmark
- 공식 Codex 대비 before/after 측정
- 오류 및 호환성 리포트 수집
- 지원 버전 표와 troubleshooting 문서

### Phase 4 — 확장

- Windows 및 원격 job
- durable job 상태
- 재시작 복구
- 공식 생태계 배포 및 upstream 제안

## 15. 공개 프로젝트 포지셔닝

README 첫 화면에서는 내부 기술보다 사용자가 얻는 결과를 먼저 설명한다.

```text
Keep long-running Codex goals in one logical turn.

- No repeated “still running” turns
- Zero model calls while a job is waiting
- Continue when the job finishes
- Keep using official Codex Desktop and CLI
```

실제 수치는 자동 테스트로 재현된 결과만 게시한다.

```text
Test: 20-minute simulated build

기본 동작: Goal turns N회 / 대기 중 모델 호출 M회
OneTurn: Goal turns 1회 / 대기 중 모델 호출 0회
```

신뢰를 위해 다음을 함께 공개한다.

- 지원하는 Codex 버전
- 설치되는 파일과 권한
- 네트워크 및 telemetry 정책
- 재현 가능한 빌드와 checksum
- 알려진 한계
- 정확한 제거 방법

## 16. 결정 사항 요약

현재까지의 제품 방향은 다음과 같다.

1. 문제의 본질은 polling 속도가 아니라 Goal이 기다리는 동안 새 턴과 모델 호출을 반복하는 구조다.
2. 최종 제품은 공식 Codex Desktop과 CLI를 교체하지 않는 확장 기능이어야 한다.
3. 기존 `goal-watch`, `wait_for.sh` 및 shell fallback은 최종 제품에서 완전히 제거한다.
4. 장기 작업 대기는 로컬의 이벤트 기반 Job Manager가 맡아야 한다.
5. 기다리는 동안 모델 호출은 0회여야 하며 완료 이벤트 후 같은 논리적 턴에서 재개해야 한다.
6. 초보자는 PID, marker, timeout 또는 별도 CLI를 배울 필요가 없어야 한다.
7. 실제 구현에 앞서 Codex plugin, hook 및 장기 tool call의 현재 지원 여부를 재현 가능한 실험으로 검증해야 한다.
8. v0.1은 로컬 단일 프로세스와 세션이 살아 있는 동안의 동일 턴 보장에 집중한다.
9. OneTurn은 Ask에서 사용자가 승인하거나 요청에 직접 명시한 경우에만 활성화한다.
10. 사용자 확인 없는 Auto 모드와 별도의 Off 모드는 제공하지 않는다.

## 17. 다음 작업

1. Codex를 재시작하고 `/hooks`에서 OneTurn hook을 검토·신뢰한다.
2. 새 task에서 직접 명시 경로로 2~5분짜리 모의 job을 실행한다.
3. 최초 turn ID와 Stop continuation 이후 turn ID가 동일한지 기록한다.
4. MCP `run`이 대기하는 동안 모델 요청 수가 증가하지 않는지 계측한다.
5. Ask 경로에서 승인 전에는 명령이 실행되지 않고, `OneTurn으로 실행` 응답 후에만 활성화되는지 확인한다.
6. E2E 결과를 README benchmark로 공개한 뒤 첫 베타 tag를 만든다.
