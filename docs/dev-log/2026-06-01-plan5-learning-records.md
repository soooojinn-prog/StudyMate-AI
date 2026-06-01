# Plan 5 — Learning Records & Dashboard (진행 중)

- **기간**: 2026-06-01 ~ (진행 중)
- **상태**: 8 tasks 중 1 완료
- **결과물 (예정)**: 모든 graded 답변이 SQLite에 저장 + 약점 Top-3 자동 산출 + `/dashboard` 페이지에서 topic 통계 + 최근 답변 렌더링. agent 그래프의 PersistAdapter + WeaknessProvider가 실 DB와 연동.

---

## 한 줄 요약 (이력서용, 잠정)

> SQLAlchemy 2.0 + Alembic으로 학습 기록 4개 테이블 영속화, 결정론적 약점 분석 (한 주제당 ≥3 답변 + 가중평균 ASC + Top-3), agent 그래프의 PersistAdapter/WeaknessProvider 콜백을 실 DB에 wire-in. /dashboard 페이지가 Architectural-Dark 테마로 약점·통계·최근 답변 카드 렌더링.

---

## 메트릭 (누적)

| 시점 | 누적 테스트 수 | 비고 |
|---|---|---|
| Task 0 (Plan 4 종료) | 93 | 베이스라인 |
| Task 1 완료 | 97 (rag 96 → 97 with subprocess tests) | SQLAlchemy 2.0 + Alembic + 4 declarative models (User/StudySession/QuestionInstance/Answer) + 0001 migration + 4 round-trip/cascade/uniq tests |

### 누적 commits (Plan 5)

| Task | commit |
|---|---|
| 1 | `d54feb9 feat(learning): add SQLAlchemy models + Alembic migration for session records` |
| 1+fix | `2cb0b03 fix(api): move RAG wiring into app.agents.wiring to honor api->rag contract` |

---

## 핵심 의사결정 (Plan 5)

### D-1. agents.wiring helper로 api → rag 직접 의존 차단

- **상황**: Plan 4 Task 2의 `app.api.dependencies` 가 `app.rag.ingest.topics` + `app.rag.retriever`를 module-level import. 그러나 import-linter contract 1: `api may only depend on agents/learning/eval/core (forbidden: rag)`. transitive까지 추적해서 broken.
- **해결**: `app.agents.wiring.build_default_graph()` 헬퍼 신설. agents 도메인이 자신의 RAG 의존성을 캡슐화. api는 `agents.wiring` 하나만 호출. `agents → rag`는 contract에서 허용됨.
- **추가 보강**: import-linter의 `ignore_imports`로 `agents.wiring -> rag.*` 경로 명시 (contract spirit 유지, intentional transit 인지).
- **면접 답변**: "API가 도메인 internal에 직접 의존하지 않도록 wiring 헬퍼를 agents 도메인에 두고 의존성 합성을 책임지게 함. import-linter가 transitive까지 추적하는 strict mode에서 의도된 transit은 ignore_imports로 명시."

---

## 트러블슈팅 로그

### T-1. import-linter는 lazy import도 transitive하게 추적

- **현상**: Plan 5 Task 1 진행 후 `lint-imports` 실행 시 contract 1 broken: `api.dependencies -> rag.retriever`. 함수 내부 lazy import + `# noqa: PLC0415` 해도 잡힘.
- **원인**: import-linter는 static AST 분석. lazy든 module-level이든 모두 detect. transitive 의존성까지 추적해서 `api → agents.wiring → rag` 같은 indirect 경로도 contract 위반으로 표시.
- **해결**: agents.wiring helper로 의도 transit 캡슐화 + ignore_imports로 정당화 표시. lazy import 의존하지 않는 더 정직한 architecture로 진화.
- **포트폴리오용 1줄**: "lazy import는 module 초기화 비용을 줄이지만 import-linter strict mode의 transitive 검사를 회피하지 못함을 학습. 의존성 캡슐화 헬퍼(`agents.wiring`)로 contract spirit 유지."

### T-2. Windows cp949 encoding이 .importlinter ini 파일의 UTF-8 화살표(→)를 거부

- **현상**: ini 파일 comment에 `api → agents.wiring → rag` 한국어 화살표 넣었더니 `'cp949' codec can't decode byte 0xe2 in position 291: illegal multibyte sequence`.
- **원인**: Windows 기본 console codepage가 cp949. import-linter가 ini 파일을 default encoding으로 읽음.
- **해결**: ASCII 화살표(`->`)로 교체. 동일 의미, encoding-safe.
- **교훈**: 설정 파일 comment조차 ASCII safe로. UTF-8 강제는 Python 코드(`encoding="utf-8"`)에서만 통제 가능.

### T-3. SQLAlchemy 2.0 `Mapped[]` + mypy strict — test fixture에 return type 필요

- **현상**: `tests/learning/test_models.py`의 fixture `def session(tmp_path: Path):` mypy strict가 missing return type 에러.
- **해결**: `from collections.abc import Iterator` + `def session(tmp_path: Path) -> Iterator[Session]:` 명시. 4 test 함수도 `-> None` 추가.
- **교훈**: `pyproject.toml`의 `[[tool.mypy.overrides]] module = "tests.*"` + `disallow_untyped_defs = false`가 새 하위 패키지 `tests/learning`까지 자동 적용되긴 하나, 함수 본문에 `Iterator` yield 타입 명시는 fixture readability에 도움. 새 test 패키지 추가 시 fixture는 explicit annotation 유지하는 패턴.

---

## 다음 진행 예정

| Task | 내용 |
|---|---|
| 2 | SessionRepository.record_answer + recent_answers |
| 3 | compute_weakness (deterministic, Top-3, ≥3 samples) |
| 4 | `__init__.py` 공개 surface 재수출 + import-linter |
| 5 | GET /dashboard/stats endpoint + DbSessionDep |
| 6 | PersistAdapter + WeaknessProvider를 agent 그래프에 wire-in |
| 7 | /dashboard 페이지 (server component, 3 sections — 약점/통계/최근) |
| 8 | E2E manual verification (사용자 액션 — credit + browser 검증) |
