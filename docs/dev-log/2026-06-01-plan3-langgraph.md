# Plan 3 — LangGraph Workflow & 3 Agents (진행 중)

- **기간**: 2026-06-01 ~ (진행 중)
- **상태**: 10 tasks 중 0 완료
- **결과물 (예정)**: `app.agents.run_session(user_id, ...)` + `app.agents.resume_session(thread_id, user_answer)` 공개 API. Coordinator → QuestionGenerator → AWAIT (interrupt) → Grader → Persist 그래프 + SqliteSaver checkpointer로 세션 일시정지/재개 지원.

---

## 한 줄 요약 (이력서용, 잠정)

> LangGraph 0.2 기반 멀티 에이전트 학습 워크플로우 — Coordinator (Haiku) + QuestionGenerator (Sonnet, 루브릭 동시 생성) + Grader (Sonnet, strict JSON + 1-retry + fallback) + Persist (결정론적). `interrupt_before`로 HITL 답변 입력 대기, SqliteSaver로 프로세스 재시작 후에도 세션 재개.

## 두 줄 요약 (포트폴리오용, 잠정)

> StudyMate AI의 멀티 에이전트 오케스트레이션 레이어 (Plan 3). LangGraph StateGraph로 Coordinator/QuestionGenerator/Grader 3개 에이전트와 결정론적 Persist 노드를 연결, `interrupt_before=["await_answer"]`로 학습자 답변 입력을 위한 HITL 일시정지 구현. SqliteSaver 체크포인터로 세션 상태를 영속화해 프로세스 재시작 후에도 같은 세션 재개 가능. 각 노드는 의존성 주입 패턴(Retriever / Anthropic client / WeaknessProvider / PersistAdapter)으로 테스트에서 mock 가능.

---

## 메트릭 (누적, task 진행에 따라 append)

| 시점 | 누적 테스트 수 | 백엔드 패키지 수 | 코드 LOC (agents) | 비고 |
|---|---|---|---|---|
| Task 0 (Plan 2 종료) | 46 | 252 | 0 | 베이스라인 |
| Task 1 완료 | 51 | 267 (+ langgraph 1.2.2, langchain-core 1.4.0, +transitive) | 78 (state.py + models.py) | LangGraph deps + SessionState TypedDict + RubricItem/QuestionPayload/GradingResult Pydantic + 5 tests |
| Task 2 완료 | 55 | 267 | 177 (+ coordinator.py 68, prompts.py 31) | Coordinator (Haiku) + topic allowlist enforcement + weak-topic preference + malformed-JSON fallback + 4 tests |
| Task 3 완료 | 59 | 267 | 267 (+ question_generator.py 63, prompts.py +27) | QuestionGenerator (Sonnet) + RAG retriever 통합 + 루브릭 동시 생성 + fail-loud on invalid LLM output + 4 tests |
| Task 4 완료 | 62 | 267 | 336 (+ grader.py 69, prompts.py +39) | Grader (Sonnet) + 1-retry on JSON parse fail + 0.5 score fallback (spec §8) + 3 tests |
| Task 5 완료 | 66 | 267 | 382 (+ persist.py 46) | Persist 노드 결정론적 + PersistAdapter Protocol callback (Plan 5에서 DB 쓰기 주입) + 4 tests |
| Task 5+security | 66 | 267 | 393 (+ prompts.py +11 보안 강화) | Grader prompt injection 방어 — JSON-encode + `<LEARNER_ANSWER>` tag + length cap 4000 + system prompt 명시 |
| Task 6 완료 | 69 | 270 (+ langgraph-checkpoint-sqlite 3.1.0, aiosqlite, sqlite-vec) | 416 (+ checkpointer.py 23) | SqliteSaver factory + 자동 parent dir 생성 + 3 tests |
| Task 7 완료 | 71 | 270 | 532 (+ graph.py 116) | StateGraph 토폴로지 + interrupt_before=["await_answer"] + run_session/resume_session 공개 API + 2 구조 tests |
| Task 8 완료 | 73 | 270 | 688 (+ test_run_session_with_mocks.py 156) | **풀 흐름 통합 테스트** — Coordinator→QGen→AWAIT 인터럽트→resume(answer)→Grader→Persist 검증 + SqliteSaver 영속성(프로세스 재시작 시뮬레이션)까지 2 tests |

### 누적 commits (Plan 3)

| Task | commit |
|---|---|
| 1 | `ba40b1f feat(agents): add LangGraph deps and state/models skeleton` |
| 2 | `37b1ee9 feat(agents): add Coordinator node with topic-allowlist fallback` |
| 3 | `5a876d3 feat(agents): add QuestionGenerator node with co-generated rubric` |
| 4 | `5edf542 feat(agents): add Grader node with 1-retry strict-JSON parsing` |
| 5 | `0b47ec4 feat(agents): add deterministic Persist node with adapter hook` |
| 5+ | `67c08e1 fix(agents): harden Grader against prompt injection via untrusted user_answer` |
| 6 | `2b943b7 feat(agents): add SqliteSaver checkpointer factory` |
| 7 | `55d72f4 feat(agents): wire LangGraph topology with await_answer interrupt` |
| 8 | `dd3dc41 test(agents): full graph run + interrupt + resume + checkpointer persistence` |

---

## 핵심 의사결정 (Plan 3)

### D-1. `Persist` 노드는 결정론적 + 어댑터 콜백

- **결정**: Persist 노드는 LLM 호출 없음. `PersistAdapter | None` 콜백을 받아 DB 쓰기 작업을 Plan 5에서 주입.
- **근거**: Plan 3에서 DB 모델까지 만들면 spec §5.1(Plan 5 영역)을 침범. 콜백 패턴으로 인터페이스만 정의하고 구현은 Plan 5에 미룸.

### D-2. SqliteSaver checkpointer는 학습 기록과 같은 SQLite 파일에 공존

- **결정**: LangGraph의 `checkpoints`/`writes`/`versions` 테이블과 Plan 5의 `StudySession`/`QuestionInstance`/`Answer` 테이블이 같은 `data/studymate.db` 파일에 공존.
- **근거**: 두 도메인의 데이터를 같은 트랜잭션 경계 안에 둘 수 있고, 백업/복원/배포가 단일 파일로 끝남.

### D-3. Grader: 1-retry on strict-JSON parse fail + 0.5 fallback

- **결정**: Grader가 JSON 파싱에 실패하면 1회 자동 재요청 → 그래도 실패면 score=0.5 + `feedback="parse_failed ..."` 를 채우고 세션 진행.
- **근거**: spec §8 에러 처리 표. 단일 LLM 실패가 세션 전체를 죽이지 않게 함.

---

## 트러블슈팅 로그

(아직 없음 — task 진행 시 append)

---

## 다음 진행 예정

| Task | 내용 |
|---|---|
| 1 | LangGraph deps + agents 모듈 스켈레톤 + Pydantic state |
| 2 | Coordinator 노드 (Haiku, topic allowlist fallback) |
| 3 | QuestionGenerator 노드 (Sonnet, 루브릭 동시 생성) |
| 4 | Grader 노드 (Sonnet, 1-retry + 0.5 fallback) |
| 5 | Persist 노드 (결정론적 + PersistAdapter 콜백) |
| 6 | SqliteSaver checkpointer 팩토리 |
| 7 | `build_graph()` 토폴로지 + interrupt_before |
| 8 | run_session + resume_session 통합 테스트 (mocked) |
| 9 | 공개 API 재수출 + import-linter 검증 |
| 10 | CLI smoke harness (real Anthropic, optional) |
