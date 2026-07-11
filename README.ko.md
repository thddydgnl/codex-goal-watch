# codex-goal-watch

**Codex `/goal`이 "아직 실행 중" 확인 턴으로 사용량을 태우는 것을 막아주는 스킬입니다.**

[English README](README.md)

## 문제

Codex `/goal`은 턴이 끝날 때마다 계속할지 판단하는 구조입니다. 학습(training),
긴 빌드, 배포처럼 오래 걸리는 작업을 감시시키면 이렇게 됩니다:

```
30초 동안 작업     → "job 정상 실행 중, heartbeat 정상"
1분 21초 동안 작업 → "계속 실행 중, stall 아님"
29초 동안 작업     → "기술 오류 아직 없음, 감시 유지"
2분 25초 동안 작업 → "첫 checkpoint 대기 중"
...
```

짧은 턴 수십 개가 토큰과 요청 한도를 소모하면서 "아직 실행 중"이라는 말만
반복합니다. 이 주기를 조절하는 config 옵션은 존재하지 않습니다 — goal의
동작 방식 자체가 이렇습니다.

## 해결

`goal-watch`는 대기를 **턴 사이가 아니라 턴 안으로** 옮기는
[Agent Skill](https://agentskills.io)입니다. 턴을 끝내고 다시 확인하는 대신,
Codex가 blocking 명령 하나(`wait_for.sh`)를 실행합니다. 이 스크립트는 내부에서
폴링하다가 job이 **완료**되거나 **실패**하거나 **최대 대기 시간**이 지났을 때만
반환됩니다.

폴링 1번당 턴 1개가 아니라, **대기 1번당 턴 1개**가 됩니다.

## 설치

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash
```

**권장:** `~/.codex/AGENTS.md`에 상시 적용 규칙까지 추가하면 goal마다 스킬을
언급할 필요 없이 **모든 세션에 결정론적으로** 적용됩니다. 스킬 자동 발견은
요청 내용이 스킬 설명과 매칭될 때 동작하는 확률적 방식이지만, AGENTS.md는
매 세션 무조건 로드되기 때문입니다:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/main/install.sh | bash -s -- --agents-md
```

또는 수동으로:

```bash
git clone https://github.com/thddydgnl/codex-goal-watch.git
cd codex-goal-watch && ./install.sh --agents-md
```

`~/.codex/skills/goal-watch`에 설치됩니다 (`$CODEX_HOME` 지원). AGENTS.md
블록은 마커로 구분되어 있고 중복 실행해도 한 번만 추가되며, 블록을 지우면
원상복구됩니다. bash와 coreutils만 있으면 되고 macOS·Linux에서 동작합니다.

## 사용법

설치하면 goal이 긴 작업을 기다려야 할 때 Codex가 자동으로 이 스킬을 참고합니다.
직접 호출할 수도 있습니다:

```
/goal-watch
/goal Idea 1의 세 variant를 순서대로 학습시키고 strict finalization까지 진행해
```

스킬이 Codex에게 가르치는 대기 패턴:

```bash
nohup python train.py --config exp1.yaml > runs/exp1/train.log 2>&1 &
echo $! > runs/exp1/pid
~/.codex/skills/goal-watch/scripts/wait_for.sh \
  --done-file runs/exp1/DONE \
  --pid "$(cat runs/exp1/pid)" \
  --log runs/exp1/train.log
```

`wait_for.sh`는 5분 간격(조절 가능)으로 확인하고, 하니스가 활동을 인식하도록
heartbeat 한 줄씩 출력하며, 다음 종료 코드로 반환됩니다:

| 종료 코드 | 의미 |
|-----------|------|
| `0` | 완료 — 마커 파일 생성 / `--until` 명령 성공 |
| `1` | 실패 — 로그에서 오류 패턴 발견, `--fail-if` 충족, 또는 프로세스가 완료 전에 종료 |
| `124` | `--max-wait` 도달, 아직 실행 중 — 다시 실행하면 계속 대기 |

### 옵션

```
--done-file PATH      PATH가 생기면 성공
--until "CMD"         CMD가 exit 0이면 성공
--fail-if "CMD"       CMD가 exit 0이면 실패
--log FILE            FILE에서 오류 패턴 감시
--error-regex REGEX   오류로 간주할 패턴 (기본값: Traceback/OOM/NaN/RuntimeError 등)
--pid PID             프로세스 종료 감지
--interval SECONDS    내부 폴링 간격 (기본 300)
--max-wait SECONDS    이 시간이 지나면 exit 124로 반환 (기본: 무제한 대기)
--tail N              실패 시 출력할 로그 줄 수 (기본 50)
--quiet               heartbeat 출력 생략
```

### 추가 레시피

```bash
# HTTP 서비스가 뜰 때까지 1분 간격으로 대기
wait_for.sh --until "curl -sf http://localhost:8000/health" --interval 60

# Slurm job이 큐에서 빠질 때까지 대기
wait_for.sh --until '! squeue -j 998877 -h | grep -q .' --interval 600

# 끊어서 대기 (shell tool 타임아웃에 안전): exit 124가 나오면 에이전트가
# 같은 턴 안에서 재실행 — 폴링하러 턴을 끝내는 일이 없음
wait_for.sh --done-file DONE --log train.log --interval 60 --max-wait 240 --quiet
```

> **왜 끊어서 대기하나?** Codex의 shell tool에는 명령별 `timeout_ms`가 있고,
> 모델이 몇 시간짜리 대기에 맞게 충분히 크게 설정해준다는 보장이 없습니다.
> 대기 호출 하나를 4분 이내로 유지하고 exit 124가 나오면 같은 턴 안에서
> 재실행하는 방식은 이 타임아웃과 무관하게 동작하면서도, 폴링을 위해 턴을
> 끝내는 일은 여전히 없습니다. SKILL.md가 에이전트에게 정확히 이 동작을
> 지시합니다.

## 폴링 자체를 없애는 방법

job이 어차피 Codex 세션보다 오래 살아있다면, goal로 감시하지 말고 job이 끝나는
순간 Codex를 호출하는 게 가장 쌉니다:

```bash
python train.py --config exp1.yaml
codex exec "exp1 학습이 끝났다. 결과를 확인하고 다음 variant를 시작해."
```

## 제거

```bash
rm -rf ~/.codex/skills/goal-watch
```

## 라이선스

MIT
