# Codex OneTurn README 후보 5종

조사일: 2026-07-11

각 파일은 저장소 루트의 `README.md`로 교체하는 것을 전제로 작성한 후보입니다.
아직 측정하지 않은 benchmark, 사용자 수, 절감률은 넣지 않았습니다.

## 조사한 한국 프로젝트

| 프로젝트 | 조사 당시 Stars | README에서 가져온 강점 |
|---|---:|---|
| [Korean Law MCP](https://github.com/chrisryugj/korean-law-mcp) | 2.2k | 강한 한 문장 가치, GIF 데모, 실제 질문→결과, 별도 영문 README |
| [kordoc](https://github.com/chrisryugj/kordoc) | 1.4k | 제작자 서사, “30초 설치”, 한 명령 설치, 바로 아래 troubleshooting |
| [Korea Real Estate MCP](https://github.com/tae0y/real-estate-mcp) | 358 | 영어 기본·한국어 분리, 명확한 prerequisites, 여러 클라이언트 연결 문서, 솔직한 deprecation 공지 |
| [Daiso MCP](https://github.com/hmmhmmhm/daiso-mcp) | 308 | 중앙 정렬 hero, 로고·스크린샷, API key 없는 진입, coverage·uptime, 복사 가능한 실제 프롬프트 |
| [cowork-plugins](https://github.com/modu-ai/cowork-plugins) | 251 | 수치 badge, 빠른 설치, 카탈로그 표, 문서·FAQ·릴리스 바로가기 |
| [korean-skills](https://github.com/DaleSeo/korean-skills) | 101 | 짧고 정돈된 구조, 한 줄 설치, 스킬별 예시, 영문 문서 분리 |

Stars는 조사 시점 GitHub 표시값이며 프로젝트 품질의 절대 순위가 아닙니다.

## 공통으로 적용한 원칙

1. 첫 화면에서 문제와 결과를 10초 안에 이해시킨다.
2. 설치 명령과 첫 프롬프트를 접기 전에 보여준다.
3. `wait_for.sh`, PID 같은 내부 구현보다 사용자 결과를 먼저 말한다.
4. 영어를 기본 진입점으로 두거나, 한영 요약을 같은 화면에 제공한다.
5. badge는 신뢰에 필요한 것만 사용한다.
6. 실제 E2E 수치가 나오기 전에는 절감률이나 benchmark를 주장하지 않는다.
7. 비공식 프로젝트, hook 신뢰, 지원 OS, 재시작 한계를 숨기지 않는다.
8. 변경 이력은 README 상단이 아니라 Releases 또는 CHANGELOG로 보낸다.

## 후보 비교

| 후보 | 콘셉트 | 가장 적합한 목표 | 한글/영문 전략 |
|---|---|---|---|
| [01 Global Launch](README-01-GLOBAL-LAUNCH.md) | 제품 출시형 | 해외 유입과 스타 확보 | 영어 본문 + 한국어 요약 |
| [02 Korean Story](README-02-KOREAN-STORY.md) | 문제 공감·제작 서사형 | 국내 바이브코더 확산 | 한국어 본문 + 영어 요약 |
| [03 Engineering Trust](README-03-ENGINEERING-TRUST.md) | 기술 신뢰형 | 개발자·기여자 설득 | 영어 중심 양언어 안내 |
| [04 Minimal](README-04-MINIMAL.md) | 짧고 현대적인 미니멀형 | 빠른 이해·낮은 이탈 | 한영 병기 |
| [05 Community](README-05-COMMUNITY.md) | 오픈소스 커뮤니티형 | 이슈·PR·초기 사용자 확보 | 영어 중심 + 한국 사용자 안내 |

## 추천

공개 첫 버전에는 **01 Global Launch**를 추천합니다. 해외 검색에 유리한 영어 제목과
첫 문단을 유지하면서, 국내 사용자는 상단의 한국어 요약으로 바로 이해할 수 있습니다.
E2E GIF와 실제 benchmark가 준비되면 01의 Before/After 영역에 넣기 가장 쉽습니다.

국내 커뮤니티에서 먼저 반응을 모으려면 **02 Korean Story**가 더 적합합니다.

## 공개 전에 꼭 할 일

- 저장소 이름을 `codex-goal-watch`에서 `codex-one-turn`으로 변경
- 실제 Codex 화면의 15~25초 Before/After GIF 추가
- 동일 turn ID와 대기 중 모델 호출 수를 측정한 재현 가능한 benchmark 추가
- GitHub About 설명과 topics 설정: `codex`, `openai`, `mcp`, `agent-skills`, `plugins`, `developer-tools`
- 첫 release와 checksum 또는 provenance 제공
- `SECURITY.md`, `CONTRIBUTING.md`, issue templates 추가
