# Codex OneTurn

공식 Codex Desktop과 CLI에서 장기 작업을 기다리는 동안 반복적인
“아직 실행 중” Goal turn과 모델 호출을 만들지 않는 플러그인입니다.

[English](README.md) · [프로젝트 기획서](docs/PROJECT_VISION.ko.md)

> 비공식 커뮤니티 프로젝트이며 OpenAI의 공식 제품이 아닙니다.

## 다음 README 선택하기

GitHub 공개용 README 후보 5개를 직접 확인할 수 있습니다.

1. [Global Launch](docs/readme-options/README-01-GLOBAL-LAUNCH.md) — 해외 노출과 Star 확보 중심 추천안
2. [Korean Story](docs/readme-options/README-02-KOREAN-STORY.md) — 국내 바이브코더가 공감하기 쉬운 서사형
3. [Engineering Trust](docs/readme-options/README-03-ENGINEERING-TRUST.md) — 아키텍처·보장 범위·보안 중심
4. [Minimal](docs/readme-options/README-04-MINIMAL.md) — 짧고 빠른 한영 병기형
5. [Community](docs/readme-options/README-05-COMMUNITY.md) — 초기 사용자와 기여자 모집형

[5개 후보 비교표 보기 →](docs/readme-options/README.md)

## 동작 방식

```text
Codex 모델
  → OneTurn run 도구 호출
  → 로컬 프로세스 실행 ─────────────→ 종료 이벤트
       대기 중 모델 호출 0회
       추가 Goal turn 0회
  → 같은 Codex turn에서 결과 분석
  → 최종 검증
  → OneTurn finish
  → turn 종료
```

`run` MCP 도구 호출 자체가 프로세스 종료까지 반환하지 않습니다. 모델은 기다리는
동안 다시 실행되지 않습니다. 모델이 완료 전에 턴을 끝내려 하면 Stop hook이 최대
세 번 같은 turn ID에서 continuation을 주입합니다.

## 요구 사항

- Codex CLI `0.133.0` 이상
- macOS 또는 Linux
- Python 3.10 이상
- Codex hooks 기능 활성화(기본값)

## 설치

저장소를 clone한 경우:

```bash
git clone https://github.com/thddydgnl/codex-goal-watch.git
cd codex-goal-watch
./install.sh
```

한 줄 설치:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

설치 프로그램은 기존 `goal-watch`, `wait_for.sh` 및 관련 `AGENTS.md` 규칙을
완전히 제거한 뒤 OneTurn marketplace와 플러그인을 설치합니다.

설치 후:

1. Codex Desktop 또는 CLI를 다시 시작합니다.
2. CLI에서 `/hooks`를 열어 OneTurn의 두 hook을 검토하고 신뢰합니다.
3. 새 task에서 사용합니다. 설치 이전에 열려 있던 task에는 새 Skill과 MCP 도구가
   나타나지 않을 수 있습니다.

## 사용하는 두 가지 방법

### 1. Ask

평소처럼 장기 작업을 요청합니다.

```text
전체 테스트를 실행하고 실패한 부분을 모두 고쳐줘.
```

OneTurn Skill이 장기 작업을 감지하면 실행 전에 묻습니다.

```text
이 작업은 오래 걸릴 수 있습니다. OneTurn으로 실행할까요?
사용하려면 “OneTurn으로 실행”이라고 답해주세요.
```

사용자가 명시적으로 승인한 이후에만 OneTurn이 활성화됩니다.

### 2. 직접 명시

최초 요청에 직접 적으면 확인 질문을 생략합니다.

```text
OneTurn으로 빌드와 전체 테스트를 완료하고 결과까지 검증해줘.
```

또는 Skill을 명시적으로 선택합니다.

```text
$one-turn 세 가지 학습 variant를 순서대로 실행하고 결과를 비교해줘.
```

Auto 모드는 없습니다. Ask 승인이나 직접 명시 없이 자동으로 활성화되지 않습니다.

## 실행 권한과 보안

- 명령은 shell 문자열이 아니라 argv 배열로 실행됩니다.
- Codex의 MCP 도구 승인을 통해 실행 명령을 확인합니다.
- 작업 디렉터리 밖의 artifact 검증은 거부합니다.
- API key와 ChatGPT 로그인 정보에 접근하지 않습니다.
- 외부 네트워크 요청을 자체적으로 만들지 않습니다.
- 출력은 로컬 plugin data 디렉터리에 기록하고 마지막 64KiB만 모델에 반환합니다.
- Esc로 tool call을 취소하면 child process group도 종료합니다.
- hook 오류 또는 세 번의 completion block 이후에는 턴을 안전하게 해제합니다.

## 현재 범위

- 하나의 Codex 프로세스와 세션이 살아 있는 동안 같은 turn ID 유지
- 로컬 단일 프로세스 실행
- exit code, deadline 및 필수 artifact 검증
- 사용자 취소
- macOS와 Linux

사용자가 시간을 따로 지정하지 않으면 각 OneTurn `run`의 기본 deadline은
**7일(604,800초)**입니다. 더 짧은 시간이 명시되면 해당 값을 우선 적용합니다.

Codex가 종료되거나 crash되면 동일 turn ID 복구는 보장하지 않습니다. “한 논리적
턴”은 모델 호출이 전체 작업에서 한 번뿐이라는 의미도 아닙니다. 코드 분석과 오류
수정에는 모델이 다시 실행될 수 있지만, 장기 프로세스를 기다리는 동안에는 호출되지
않습니다.

## 제거

```bash
./install.sh --uninstall
```

원격 설치만 사용한 경우:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash -s -- --uninstall
```

프로젝트 결과물과 OneTurn job 로그는 자동으로 삭제하지 않습니다.

## 개발 검증

```bash
python3 -m unittest discover -s tests -v
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/codex-one-turn
```

## 라이선스

MIT
