# Plan 1 — Foundation & Walking Skeleton (회고)

- **기간**: 2026-05-30
- **상태**: 완료 (9 tasks / 15 commits / CI green)
- **결과물**: `docker compose up` 대신 `make dev` 한 줄로 백엔드(FastAPI) + 프론트엔드(Next.js) 동시 실행, 브라우저 `/health`에서 양쪽 통신 작동 확인

---

## 한 줄 요약 (이력서용)

> FastAPI + Next.js 14 모듈러 모놀리식 구조의 walking skeleton을 9개 task / 15 commit으로 완성. import-linter로 6개 도메인 모듈 경계를 CI에서 자동 강제, ruff + mypy strict + pytest 4단 게이트, GitHub Actions로 PR마다 자동 검증.

## 두 줄 요약 (포트폴리오용)

> StudyMate AI의 walking skeleton (Plan 1, 9 tasks). FastAPI + Pydantic v2 + uv 기반 백엔드와 Next.js 14 + Tailwind + pnpm 기반 프론트엔드를 모듈러 모놀리식으로 구성하고, import-linter로 도메인 간 의존 방향을 CI에서 자동 강제. Docker Desktop의 Windows 비용(RAM 2~8GB)을 피하기 위해 V1은 호스트 직접 실행을 선택하고 lock 파일로 재현성을 확보.

---

## 메트릭

| 분류 | 항목 | 값 |
|---|---|---|
| 코드 | 백엔드 LOC | 약 250 lines (`backend/app/`) |
| 코드 | 프론트엔드 LOC | 약 100 lines (`frontend/src/`) |
| 코드 | 테스트 LOC | 약 100 lines (4 test files) |
| 테스트 | 통과 수 | 4 / 4 |
| 테스트 | 커버리지 (백엔드) | 96% |
| 품질 | ruff + format | clean (E, F, I, B, UP, SIM, RET, PL, PT) |
| 품질 | mypy strict | clean |
| 품질 | import-linter contracts | 5 kept / 0 broken |
| 빌드 | `pnpm build` First Load JS | 94 kB (landing) / 87.2 kB (/health) |
| 빌드 | `make ci-local` 종합 시간 | 약 30초 (CI는 더 짧음, 캐시 활용) |
| Git | commits | 15 |
| Git | 평균 commit 크기 | 약 50~80 lines 변경 |

## 모듈 경계 contract (5개, import-linter)

| # | 규칙 | 효과 |
|---|---|---|
| 1 | `api` may not import `rag` | API 라우터가 RAG에 직접 의존 금지 |
| 2 | `agents` may not import `api`, `eval` | 에이전트가 HTTP 레이어/평가에 역방향 의존 금지 |
| 3 | `rag` may not import `api`, `agents`, `learning`, `eval` | RAG는 도메인 중립 |
| 4 | `learning` may not import `api`, `agents`, `rag`, `eval` | 학습 기록은 도메인 중립 |
| 5 | `core` may not import any other `app.*` | 설정·로깅은 zero-dep |

위반 시 CI 실패 — 매 PR마다 자동 검증.

---

## 핵심 의사결정 & 근거

### D-1. Docker 제거 (V1 → V2로 연기)

- **상황**: Plan 1 첫 안은 Dockerfile + docker-compose로 walking skeleton을 묶는 안.
- **재고**: 사용자 환경(Windows 11) 기준 Docker Desktop은 평시 2~4GB RAM, 빌드 시 4~8GB. WSL2 오버헤드로 파일 I/O 느림. 노트북 부팅 시 자동 시작 시 전체 부팅 체감 저하.
- **대안 평가**: 재현성은 `uv.lock` + `pnpm-lock.yaml`로, 한 줄 실행은 GNU Make `make dev` (POSIX/WSL/Git Bash), 배포는 Railway/Vercel 네이티브 빌드팩으로 동등 달성.
- **결정**: V1은 호스트 직접 실행. Docker는 Plan 7에 "선택적 컨테이너화" task로 보류.
- **면접 답변**: "포트폴리오 작품에서 RAM 4~8GB 차지하는 Docker Desktop은 비용 대비 효용 낮다고 판단. 재현성은 lock 파일로, 배포는 Railway/Vercel로 동등 달성. Plan 7에 컨테이너화 옵션 남겨둠."

### D-2. shadcn/ui 도입 시점 = Plan 4

- **상황**: Plan 1 walking skeleton에는 인터랙티브 UI 컴포넌트가 없음.
- **결정**: shadcn/ui는 Plan 4 Study UI에서 첫 도입. Plan 1~3은 Tailwind만으로 충분.
- **근거**: YAGNI. 필요할 때 도입.

### D-3. 디자인 방향 = Architectural Dark (Plan 4 적용 예정)

- **상황**: walking skeleton의 화면이 너무 빈약해서 디자인 방향을 미리 잡기로 결정.
- **탐색**: 두 가지 standalone HTML mock 제작 (`docs/design-explorations/`).
  - v1: Editorial Paper (잡지 인쇄 메타포, warm paper + 잉크 빨강 액센트, EB Garamond)
  - v2: Architectural Dark (도면 메타포, deep navy + cyan blueprint grid, Fraunces variable serif)
- **결정**: v2 채택. Plan 4부터 적용. 의사결정 기록 `docs/design-explorations/DECISION.md`.
- **차별화 포인트**: 일반적 AI slop (보라 그라데이션 + Inter + 둥근 카드)을 피하고, 한글 본문 Pretendard + 영문 디스플레이 Fraunces italic + JetBrains Mono meta + 단일 cyan 액센트로 구성. 사이드바·blueprint grid·corner crop·italic Fraunces 숫자는 의도된 시그니처.

---

## 트러블슈팅 로그

### T-1. uv PATH 등록 (PowerShell 세션 캐시 이슈)

- **현상**: `uv` 설치 후 PowerShell에서 `uv --version` 실행 시 "용어로 인식되지 않습니다". 절대 경로(`C:\Users\emdak\.local\bin\uv.exe`)로는 정상 작동.
- **원인**: 설치 스크립트가 user 환경변수 PATH에 등록을 안 함. 또한 기존 셸 세션은 시작 시점의 PATH를 캐시.
- **해결**:
  ```powershell
  [Environment]::SetEnvironmentVariable("Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\emdak\.local\bin",
    "User")
  $env:Path = "C:\Users\emdak\.local\bin;$env:Path"  # 현재 창에도 즉시 적용
  ```
- **교훈**: `setx`는 1024자 한도로 PATH 절단 위험 — `[Environment]::SetEnvironmentVariable`이 안전. 새 PowerShell 창에서 검증 필수.
- **포트폴리오용 1줄**: "Windows 사용자 환경변수 PATH를 안전하게 갱신하기 위해 `setx` 대신 `[Environment]::SetEnvironmentVariable`을 사용 — `setx`는 1024자 한도로 기존 PATH를 자를 수 있음."

### T-2. `pnpm lint`가 ESLint config 부재 시 interactive prompt → CI hang 위험

- **현상**: Task 7 (CI yaml) 작성 후 code-reviewer가 발견. `frontend/.eslintrc.json` 없이 `pnpm lint`(=`next lint`) 실행 시 "Strict/Base/Cancel" 인터랙티브 메뉴 표시.
- **영향**: GitHub Actions의 non-TTY 환경에서는 hang하거나 EOF 비정상 종료. CI 첫 실행 시 빨갛게 됨.
- **해결**:
  ```json
  // frontend/.eslintrc.json
  { "extends": "next/core-web-vitals" }
  ```
- **교훈**: Plan 작성 시 "이 명령이 실제로 어떻게 동작하는가"까지 검증 필요. 단순 verbatim copy는 안전망이 아님.
- **포트폴리오용 1줄**: "코드리뷰 단계에서 `next lint`의 인터랙티브 프롬프트가 CI를 hang시킬 위험을 발견하고 `.eslintrc.json`을 추가 — Plan의 verbatim copy도 동작 검증이 필요함을 학습."

### T-3. `BACKEND_URL`을 root `.env`에 두면 Next.js는 무시함

- **현상**: Task 8 (Makefile + .env.example + README) 코드리뷰에서 발견. README가 `cp .env.example .env`를 안내하는데, Next.js는 root의 `.env`를 안 보고 `frontend/.env.local`만 자동 로드.
- **영향**: dev에서는 default literal(`http://localhost:8000`)이 일치해서 문제 없음. 그러나 staging URL로 바꾸려고 root `.env`를 수정하면 frontend가 무시 → 침묵 실패.
- **해결**:
  1. `frontend/.env.example` 신설 (frontend 전용 BACKEND_URL)
  2. root `.env.example`에서 BACKEND_URL 제거
  3. README Quick Start에 두 `cp` 단계 명시 + Windows PowerShell 비호환 주의문 추가
- **교훈**: 프레임워크별 env 파일 로딩 규칙은 default 값이 일치하는 한 침묵 실패하므로 문서로 명시화.
- **포트폴리오용 1줄**: "Next.js의 env 파일 로딩 규칙(`frontend/.env.local`만 자동 로드)과 충돌하는 README 단계를 발견 — backend/frontend env example을 분리해 의도된 동작과 문서를 일치시킴."

### T-4. ruff PLR2004 magic value 규칙이 테스트에서 반복 발화

- **현상**: Task 2 코드리뷰 단계에서 `assert response.status_code == 200` 같은 줄에 PLR2004 발화.
- **해결**: `from http import HTTPStatus` 사용 → `HTTPStatus.OK`. 그 외 테스트에서는 `expected_X = N` 명명 지역변수 추출.
- **교훈**: PLR2004는 test code에도 적용. HTTP 상태 코드는 `HTTPStatus.*` 사용이 정석.
- **포트폴리오용 1줄**: "ruff strict 환경에서 테스트의 magic number도 정직하게 명명 — `HTTPStatus.OK`/`HTTPStatus.UNPROCESSABLE_ENTITY` 등 stdlib enum 활용."

### T-5. Subagent 실행 timeout (sentence-transformers ~1.5GB 다운로드)

- **현상**: Plan 2 Task 1 subagent dispatch 시 `uv sync`가 sentence-transformers + torch + transformers 약 1.5GB를 받는 동안 14분 timeout. subagent가 "Waiting for uv sync"로 끝.
- **해결**: 직접 `uv sync` 다시 실행 → 86초로 마무리. 남은 step(ruff/mypy/pytest/commit)을 controller가 직접 수행.
- **교훈**: 큰 의존성 첫 설치는 subagent timeout(약 14분)을 넘길 수 있음. controller가 fallback으로 받아 처리하면 시간 손실 최소화.
- **포트폴리오용 1줄**: "약 1.5GB 의존성 설치로 subagent timeout이 발생한 케이스에서, controller가 mid-pipeline fallback으로 받아 완성해 처리 시간을 최소화."

---

## 결과물 (Tasks 9개)

| Task | 결과 | commit |
|---|---|---|
| 1 | Backend bootstrap (pyproject, settings, main, 6 domain modules) | `bf9780b` |
| 2 | `/health` endpoint TDD (test → impl → pass) | `20a1bfd` |
| 3 | Import-linter 5 contracts + guard test | `0574bad` (+ `2297739` 추가 보강) |
| 4 | Ruff format + mypy strict 통과 + smoke test | `09c6b97` + `5751655` |
| 5 | Next.js 14 + Tailwind + pnpm 스캐폴딩 | `efc9290` (+ `2d346d3` eslintrc fix) |
| 6 | `/health` page SSR fetching backend | `7663438` |
| 7 | GitHub Actions CI (backend + frontend jobs) | `19b6531` |
| 8 | Makefile + `.env.example` + README | `6eff15b` (+ `c960794` env split) |
| 9 | E2E verification (`make dev`, browser /health) | (검증만, lock file 변경 없음) |

총 15 commits, 모두 GitHub `main` 브랜치 origin에 push 완료.

GitHub 리포지토리: <https://github.com/soooojinn-prog/StudyMate-AI>
