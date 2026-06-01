# Plan 4 — Study UI & API (진행 중)

- **기간**: 2026-06-01 ~ (진행 중)
- **상태**: 10 tasks 중 9 완료 (Tasks 1-9 코드 완료, Task 10 E2E는 ANTHROPIC_API_KEY credit 충전 후 사용자 액션 대기)
- **결과물 (예정)**: 브라우저 `/study` 페이지에서 세션 시작 → 문제 → 답안 입력 → 채점 결과 카드까지 Architectural-Dark 디자인으로 작동

---

## 한 줄 요약 (이력서용, 잠정)

> FastAPI 3 endpoints (`POST /sessions`, `POST /sessions/{id}/answer`, `GET /sessions/{id}`)로 Plan 3 LangGraph 그래프를 HTTP 표면화하고, Next.js 14 App Router + shadcn/ui로 Architectural-Dark 디자인의 Study 페이지 구현. backend 테스트는 dependency_overrides로 mock graph 주입해 LLM 호출 없이 검증.

## 두 줄 요약 (포트폴리오용, 잠정)

> StudyMate AI의 사용자 표면 (Plan 4). FastAPI에서 LangGraph 그래프를 lifespan에서 한 번 build하고 Depends()로 주입, 학습 세션 3개 endpoint(`POST /sessions`, `POST /sessions/{id}/answer`, `GET /sessions/{id}`)를 노출. Next.js Study 페이지는 서버 컴포넌트가 `createSession`을 호출하고 클라이언트 컴포넌트가 답안 입력+채점 결과 렌더링. shadcn/ui 4개 primitive(Button, Textarea, Badge, Card)를 Architectural-Dark 토큰으로 재칠해 일반적 AI slop을 회피.

---

## 메트릭 (누적, task 진행에 따라 append)

| 시점 | 누적 테스트 수 | 비고 |
|---|---|---|
| Task 0 (Plan 3 종료) | 76 | 베이스라인 |
| Task 1 완료 | 82 | DTOs (CreateSessionRequest/SessionStateDTO/SubmitAnswerRequest) + thread-safe SessionStore + 6 tests |
| Task 2 완료 | 82 | dependencies.py (Depends() factories + lifespan graph singleton) + main.py lifespan |
| Task 3 완료 | 86 | POST /sessions (mocked-graph TDD) + 4 tests |
| Task 4 완료 | 90 | POST /sessions/{id}/answer + 4 tests |
| Task 5 완료 | 92 | GET /sessions/{id} snapshot + 2 tests |
| Task 6 완료 | 93 | Full /sessions lifecycle 통합 테스트 (POST→POST→GET) + 1 test |
| Task 7 완료 | 93 | Frontend shadcn 4 primitives (Button/Textarea/Badge/Card) + Architectural-Dark Tailwind 토큰 + globals.css |
| Task 8 완료 | 93 | lib/api.ts 확장 (SessionState type + createSession/submitAnswer/getSession) |
| Task 9 완료 | 93 | /study page (server: createSession) + SessionView client (Architectural-Dark, 답안 입력 → 채점 결과 카드) + 랜딩 페이지 update |

### 누적 commits (Plan 4)

| Task | commit |
|---|---|
| 1 | `936ad75 feat(api): add session DTOs and in-memory session store` |
| 2 | `ec69476 feat(api): wire graph + session store as FastAPI singletons via lifespan` |
| 3 | `f1c7cb0 feat(api): add POST /sessions endpoint with mocked-graph TDD` |
| 4 | `ec1027b feat(api): add POST /sessions/{id}/answer endpoint` |
| 5 | `18e33cf feat(api): add GET /sessions/{id} snapshot endpoint` |
| 6 | `907cead test(api): full /sessions create->answer->get flow with mocked graph` |
| 7 | `4cf3744 feat(frontend): add shadcn primitives + Architectural-Dark tokens` |
| 8 | `d1360eb feat(frontend): add session API client wrappers (createSession, submitAnswer, getSession)` |
| 9 | `49977bf feat(frontend): add /study page with Architectural-Dark session view` |

---

## 핵심 의사결정 (Plan 4)

### D-1. Plan 4의 backend tests는 mock graph만 사용

- **결정**: pytest는 `dependency_overrides[get_graph]`로 fake graph 주입. real Anthropic API 호출 없음.
- **근거**: Plan 4의 책임은 HTTP 표면, 즉 라우팅·DTO 매핑·에러 처리. LangGraph 그래프 자체는 Plan 3에서 검증됨. CI 비용·시간 절감.
- **면접 답변**: "API 계층 테스트는 그래프 mock으로, 그래프 자체는 Plan 3 통합 테스트로, 실 LLM은 Plan 6 eval 단계로 — 각 layer를 독립적으로 검증."

### D-2. shadcn/ui 도입 + Architectural-Dark 토큰 override

- **결정**: shadcn primitives(button, textarea, badge, card)를 init하되 default slate palette를 CSS variables로 완전히 override.
- **근거**: shadcn의 일반적 외관(흰 배경 + 둥근 카드 + 회색)을 그대로 두면 generic AI slop. CSS variables 매핑으로 Architectural-Dark 일관성 유지.

### D-3. Plan 4의 lifespan은 ANTHROPIC_API_KEY 없으면 graph=None

- **결정**: lifespan이 key가 없으면 graph 빌드를 skip하고 app.state.graph=None.
- **근거**: 테스트에서 dependency_overrides로 graph를 mock 주입. 실제 deploy에서 key 없을 때 503으로 명시적 실패 → silent error 방지.

---

## 트러블슈팅 로그

(아직 없음 — task 진행 시 append)

---

## 다음 진행 예정

| Task | 내용 |
|---|---|
| 1 | Backend DTOs (CreateSessionRequest, SessionStateDTO, SubmitAnswerRequest) + in-memory SessionStore |
| 2 | Dependencies (lifespan builds graph singleton; Depends() injects) |
| 3 | POST /sessions endpoint (mocked-graph TDD) |
| 4 | POST /sessions/{id}/answer endpoint |
| 5 | GET /sessions/{id} snapshot endpoint |
| 6 | Full /sessions lifecycle integration test |
| 7 | Frontend: shadcn/ui init + Architectural-Dark CSS tokens + 4 primitives |
| 8 | Frontend: API client extensions (createSession, submitAnswer, getSession) |
| 9 | Frontend: /study page + SessionView client component |
| 10 | E2E manual verification (사용자 액션 — credit 충전 후 브라우저 검증) |
