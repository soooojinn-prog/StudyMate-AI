# StudyMate AI — 설계 문서 (V1)

- **작성일**: 2026-05-30
- **대상 도메인 (V1)**: 정보처리기사 실기 시험
- **프로젝트 성격**: 취업용 포트폴리오 (AI 엔지니어)
- **상태**: 설계 승인 대기

---

## 1. 목표와 우선순위

### 1.1 프로젝트 목표
멀티 에이전트 + RAG 기반 학습 시스템을 만들어, 학습자가 자신의 약점을 자동으로 식별받고 그에 맞는 문제를 풀며 의미 기반 채점 + 보강 가이드를 받는 경험을 제공한다. V1은 정보처리기사 실기에 특화하되, 도메인 교체가 용이한 구조를 유지한다.

### 1.2 우선순위 (포트폴리오 관점)
1. **실제 동작 데모** — 면접에서 라이브로 5분 안에 학습 사이클을 보여줄 수 있어야 한다.
2. **기술 깊이 ("왜?" 설명)** — 모든 기술 선택에 대해 트레이드오프와 근거를 답할 수 있어야 한다.
3. **아키텍처 확장성** — 다른 도메인으로 확장 가능한 구조이되, V1에서는 확장 자체를 구현하지 않는다.

### 1.3 비-목표 (V1에서 안 하는 것)
- 코딩 문제, SQL 문제 채점 (서술형 + 단답형만)
- 멀티 유저 인증 (V1은 단일 로컬 유저)
- 모바일 앱
- 망각 곡선/SRS 기반 복습 알고리즘
- 다국어 지원
- 결제·정산
- 튜터·분석 에이전트의 별도 LangGraph 노드화 (확장 자리만 남김)

---

## 2. 스코프 (V1)

### 2.1 V1에 포함
- 에이전트 3개: **Coordinator + QuestionGenerator + Grader**
- RAG: 공개 기출문제 PDF 인덱싱 + 한국어 임베딩 (BGE-M3) + ChromaDB
- 학습 기록: 세션/문제/답변 영속 + 주제별 정답률 + 약점 Top 3
- 평가셋: 50문항 골든셋 + 메트릭 대시보드 + CI 회귀 검사
- 웹 UI: Next.js 14, 학습 세션 + 대시보드 + 풀이 이력
- 배포: 로컬 Docker Compose 단일 명령어 실행

### 2.2 V2 후보 (스코프 밖)
- 튜터 에이전트 (보강 학습 자료 큐레이션)
- 분석 에이전트 (현재 결정론적 `learning.analytics` 를 LangGraph 노드로 승격)
- 코딩/SQL 문제 채점 + Sandbox 실행
- 다른 자격증 도메인 확장 (토픽 집합 + 인덱스 컬렉션 교체)
- SRS 기반 복습 알고리즘
- 멀티 유저 + 인증

---

## 3. 시스템 아키텍처

### 3.1 전체 구성도

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (Next.js 14, App Router)                                │
│  ├─ /study     학습 세션 (출제→답변→채점→피드백)                  │
│  ├─ /dashboard 약점 주제 / 정답률 / 평가 메트릭                   │
│  └─ /history   풀이 이력 + 오답 노트                              │
└────────────────────────────┬─────────────────────────────────────┘
                             │ REST + SSE (스트리밍 피드백)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI (Modular Monolith)                                      │
│                                                                  │
│  ┌─────────────┐  ┌──────────────────────────────────────────┐  │
│  │ api/        │→ │ agents/  (LangGraph 워크플로우)          │  │
│  │ 라우터      │  │   ├─ coordinator                          │  │
│  │ DTOs        │  │   ├─ question_generator                   │  │
│  │             │  │   └─ grader                               │  │
│  └─────────────┘  └────────┬──────────────────────┬────────────┘ │
│                            │                      │              │
│              ┌─────────────▼────────┐  ┌──────────▼───────────┐ │
│              │ rag/                 │  │ learning/            │ │
│              │  ChromaDB retriever  │  │  세션, 채점결과,       │ │
│              │  PDF 파서/임베딩     │  │  주제별 통계, 약점    │ │
│              └─────────────┬────────┘  └──────────┬───────────┘ │
│                            │                      │              │
│              ┌─────────────▼──────────────────────▼───────────┐ │
│              │ eval/  골든셋 실행 + 메트릭 산출 + 리포트       │ │
│              └────────────────────────────────────────────────┘ │
│                                                                  │
│              ┌─────────────────────────────────────────────────┐│
│              │ core/  Claude 클라이언트, 설정, 로깅, 예외       ││
│              └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
        │                    │                       │
        ▼                    ▼                       ▼
   ChromaDB              SQLite                 LangSmith
   (벡터 인덱스)         (학습 기록)           (트레이싱, 선택)
```

### 3.2 디렉토리 구조

```
studymate-ai/
├─ backend/
│  └─ app/
│     ├─ api/              # HTTP 경계. Pydantic DTO, FastAPI 라우터
│     ├─ agents/           # LangGraph 그래프 + 노드
│     │  ├─ graph.py
│     │  ├─ state.py       # TypedDict: SessionState
│     │  ├─ nodes/
│     │  │  ├─ coordinator.py
│     │  │  ├─ question_generator.py
│     │  │  └─ grader.py
│     │  └─ prompts/       # 프롬프트는 코드와 분리
│     ├─ rag/              # 인덱싱 파이프라인 + Retriever
│     │  ├─ ingest/
│     │  ├─ embedder.py
│     │  └─ retriever.py
│     ├─ learning/         # 학습 기록 도메인
│     │  ├─ models.py      # SQLAlchemy
│     │  ├─ repository.py
│     │  └─ analytics.py   # 약점 주제 계산
│     ├─ eval/             # 골든셋 실행, 메트릭, 리포트
│     │  ├─ datasets/
│     │  ├─ runner.py
│     │  └─ metrics.py
│     └─ core/             # LLM/임베딩 클라이언트, settings, logging
├─ frontend/               # Next.js 14
├─ data/                   # 기출 PDF 원본 (gitignored), 정제본
├─ docker-compose.yml
└─ docs/
```

### 3.3 모듈 경계 규칙 (import-linter로 CI 강제)

| 모듈 | 의존 허용 | 금지 |
|---|---|---|
| `api/` | `agents/`, `learning/`, `eval/` | `rag/` 직접 호출 |
| `agents/` | `rag/`, `learning/`, `core/` | `api/` import |
| `rag/` | `core/` | 외부에서 ChromaDB 직접 접근 — 반드시 `retriever.retrieve()` 통과 |
| `learning/` | `core/` | 외부에서 SQLAlchemy 모델 직접 접근 — 반드시 `repository`/`service` 통과 |
| `eval/` | `agents/`, `rag/`, `learning/`, `core/` | — |
| `core/` | (없음) | 다른 모듈 import 금지 |

---

## 4. LangGraph 워크플로우

### 4.1 그래프 토폴로지

```
       ┌──────────────────┐
START ─│ Coordinator      │  의도 파악 + 약점 기반 주제/난이도 결정
       └────────┬─────────┘
                │ {topic, difficulty, target_weakness}
                ▼
       ┌──────────────────┐
       │ QuestionGenerator│  RAG로 관련 기출 검색 → 문제 + 루브릭 생성
       └────────┬─────────┘
                │ {question, model_answer, rubric, ref_chunks}
                ▼
       ┌──────────────────┐
       │ AWAIT_ANSWER     │  ← LangGraph interrupt_before (HITL)
       └────────┬─────────┘
                │ {user_answer}
                ▼
       ┌──────────────────┐
       │ Grader           │  의미 매칭 + 부분점수 + 근거 chunk 인용
       └────────┬─────────┘
                │ {score, rationale, feedback, missing_points}
                ▼
       ┌──────────────────┐
       │ Persist & Stats  │  세션/답변/통계 갱신 → 약점 재계산
       └────────┬─────────┘
                │ 조건부 분기
                ├─ 더 풀기 → Coordinator (loop)
                └─ 종료    → END
```

### 4.2 공유 상태 (SessionState)

```python
class SessionState(TypedDict, total=False):
    # 식별자 — session_id는 LangGraph checkpointer의 thread_id로 그대로 사용 (1:1)
    user_id: str
    session_id: str
    # Coordinator 결정
    topic: str
    difficulty: int                  # 1~3
    target_weakness: bool
    # QuestionGenerator 산출
    question: str
    model_answer: str
    rubric: list[RubricItem]         # 채점 기준 + 가중치
    ref_chunks: list[Chunk]          # RAG 인용 근거
    # 사용자 입력
    user_answer: str
    # Grader 산출
    score: float                     # 0.0~1.0
    rationale: str
    feedback: str
    missing_points: list[str]
    # 루프 제어
    questions_done: int
    target_count: int                # 세션당 문제 수 (기본 5)
```

### 4.3 에이전트별 책임 + 모델 선택

| 에이전트 | 책임 | 모델 | 선택 근거 |
|---|---|---|---|
| **Coordinator** | 사용자 의도(첫 학습 / 주제 선택 / 오답 복습) 분류 → `learning.analytics`로 약점 Top 3 조회 → 다음 `(topic, difficulty)` 결정 | **Claude Haiku 4.5** | 단순 라우팅 + 요약. 비용/지연 민감. 약점 계산은 결정론적 로직이라 LLM은 의도 분류만 |
| **QuestionGenerator** | `rag.retrieve(topic, k=5)` → 검색 컨텍스트로 새 문제 1개 + **모범답안 + 채점 루브릭** 동시 생성 (structured output) | **Claude Sonnet 4.6** | 문제 품질이 데모 첫인상. 루브릭 동시 생성으로 채점 일관성 확보 |
| **Grader** | 학습자 답변을 루브릭 항목별 채점 → 부분점수 + 인용 근거 + 보강 가이드. 출력은 strict JSON schema | **Claude Sonnet 4.6** | 의미 매칭 정확도가 핵심 어필. eval 단계에서 Haiku 다운그레이드 가능성 측정 |
| 임베딩 | RAG 인덱싱/쿼리 | **BGE-M3** (multilingual, sentence-transformers, 로컬) | 한국어 강함, 비용 0, 차원 1024. 추상화로 Voyage-3 교체 가능 |

### 4.4 핵심 설계 결정

1. **루브릭 동시 생성** — QuestionGenerator가 문제 + 모범답안 + 루브릭을 한 트랜잭션에. Grader는 이 루브릭에만 의존 → 채점 재현성 + LLM 변동성 격리.
2. **`interrupt_before`로 HITL** — `AWAIT_ANSWER` 노드에서 그래프 정지 + checkpointer에 직렬화 → 사용자 답변 제출 시 `resume`. 멀티턴/장기 세션 자연스럽게 지원.
3. **Grader 출력은 strict JSON** — `response_format` + Pydantic 검증. 파싱 실패 시 1회 자동 재시도 → fallback 점수 + 에러 로깅.
4. **Persist 노드는 결정론적** — LLM 미사용. 트랜잭션 단위 명확, 테스트 쉬움.
5. **분석 에이전트 확장 자리** — `learning.analytics` 모듈이 약점 계산을 도맡고 있어서, V2에서 별도 LangGraph 노드로 승격하면 "분석 에이전트" 추가 가능.

---

## 5. 데이터 모델 & RAG

### 5.1 학습 기록 DB (SQLite + SQLAlchemy 2.0 + Alembic)

```python
class User(Base):
    id: str                     # UUID
    nickname: str
    created_at: datetime

class StudySession(Base):
    id: str
    user_id: str (FK)
    mode: Literal["weakness", "topic", "review"]
    target_topic: str | None
    target_count: int           # 기본 5
    started_at: datetime
    ended_at: datetime | None
    thread_id: str              # LangGraph checkpointer 키

class QuestionInstance(Base):
    id: str
    session_id: str (FK)
    seq: int                    # 세션 내 순번
    topic: str
    difficulty: int
    question_text: str
    model_answer: str
    rubric_json: JSON           # [{point, weight, keywords[]}, ...]
    ref_chunk_ids: JSON         # ["chunk_uuid", ...]
    generated_at: datetime

class Answer(Base):
    id: str
    question_instance_id: str (FK, unique)
    user_answer: str
    score: float                # 0.0~1.0
    rationale: str
    feedback: str
    missing_points_json: JSON
    graded_at: datetime
```

**LangGraph 체크포인터**: `SqliteSaver`를 같은 DB 파일에 별도 테이블로 보관. `StudySession.thread_id`만 들고 그래프 상태를 복원.

### 5.2 RAG 인덱스 (ChromaDB)

```
collection: "jeongcheo_v1"
  ids:        <chunk_uuid>
  documents:  <청크 텍스트, ~400 tokens, overlap 50>
  embeddings: BGE-M3 (1024-dim)
  metadatas:
    source:      "2024_1회_기출.pdf"
    page:        12
    topic:       "정규화"
    chunk_type:  "concept" | "problem" | "explanation"
    difficulty:  1~3 (problem 청크에만)
```

### 5.3 인덱싱 파이프라인 (`rag/ingest/`)

```
data/raw/*.pdf
   │
   ▼ pdfplumber  (페이지/표 메타데이터 유지)
data/extracted/<source>.jsonl
   │
   ▼ cleaner.py  (헤더·푸터·페이지번호 제거)
   ▼ chunker.py  (문단 기반 + 토큰 한도)
   ▼ topic_tagger.py  (Haiku로 chunk → topic 라벨)
data/chunks/<source>.jsonl
   │
   ▼ embedder.py  (BGE-M3, 배치)
ChromaDB persist
```

- 모든 중간 산출물은 jsonl로 디스크에 남김 → 재인덱싱 빠름, 임베딩 모델 교체 시 1단계만 재실행.
- 토픽 집합: 정보처리기사 실기 12과목 + 자주 등장하는 세부 주제 → V1은 ~20개 코어 토픽, `data/topics.yaml`에 명시.

### 5.4 약점 분석 로직 (`learning/analytics.py`)

```python
def compute_weakness(user_id: str, lookback_days: int = 30) -> list[TopicWeakness]:
    # 1) 최근 N일 내 답변 필터
    # 2) 주제별 가중 평균 점수 (recency decay 적용)
    # 3) 최소 표본수 < 3 → 약점 산출 제외, "미학습 영역"으로 별도 노출
    # 4) ORDER BY 가중평균 ASC, 표본수 DESC → Top 3 반환
```

LLM 미사용. Coordinator가 이 함수의 결과를 받아 다음 `(topic, difficulty)`를 결정.

### 5.5 데이터 시드 전략
- 최초 인덱싱: 최근 5개년 정도의 공개 기출 + 12과목 핵심 개념 위키 요약 (직접 정제).
- 골든 평가셋: 50문항 + 모범답안 + 루브릭 + 인간 채점한 학습자 답변 3종(상/중/하) → `eval/datasets/golden_v1.jsonl`에 git으로 버전 관리. 학습용 데이터와 분리.

---

## 6. 평가 시스템

### 6.1 골든 평가셋
- **문항**: 50개. 12과목 균등 분포, 난이도 1~3 균등 분포
- **각 문항 구성**: 문제 + 모범답안 + 루브릭 + 학습자 답변 예시 3종(상/중/하) + 각 답변에 대한 인간 채점 점수
- **총 채점 케이스**: 50문항 × 3답변 = **150 케이스** (Grading Accuracy 계산의 모집단)
- 위치: `eval/datasets/golden_v1.jsonl`

### 6.2 측정 메트릭 (V1 목표치)

| 메트릭 | 정의 | 목표 |
|---|---|---|
| **Grading Accuracy** | \|AI 점수 − 인간 점수\| ≤ 0.15 인 비율 | ≥ 80% |
| **Retrieval Recall@5** | 모범답안 키워드를 포함한 chunk가 Top-5 안에 있는 비율 | ≥ 75% |
| **End-to-end Latency p95** | Coordinator → Question → Grader 한 사이클 | ≤ 8초 |

### 6.3 러너 & 리포트

```bash
$ python -m app.eval.runner --dataset golden_v1 --tag $(git rev-parse --short HEAD)
→ eval/reports/2026-05-30_<sha>.html  # 메트릭 + 실패 사례 diff
→ eval/reports/history.csv             # 시계열
```

- 대시보드 페이지(`/dashboard`)에 최신 리포트 임베드 + 시계열 그래프
- **GitHub Actions에서 PR마다 자동 실행** + 회귀 감지 (목표치 미달 시 fail)

---

## 7. 테스트 전략

| 레이어 | 대상 | 도구 | 의도 |
|---|---|---|---|
| **Unit** | `analytics`, `chunker`, `cleaner`, `repository` | pytest | 결정론적 로직, 빠르고 안정 |
| **Component** | 각 LangGraph 노드 단독 (LLM Mock) | pytest + `respx` | 입출력 스키마 검증 |
| **Integration** | `agents.run_session()` 풀 그래프 (LLM은 녹화된 fixture) | pytest + VCR-style cassette | 그래프 토폴로지/상태 전파 |
| **Eval** | 골든셋 50문항 (실제 LLM 호출) | `eval/runner.py` | 시스템 품질 회귀 |

- LLM 호출은 unit/integration에선 mock, eval에서만 실호출 → CI 비용 통제.
- 커버리지 목표: 결정론적 로직 80%+, 노드 입출력 검증 100%.

---

## 8. 에러 처리 (실패 모드별)

| 실패 | 대응 |
|---|---|
| LLM timeout / 5xx | `tenacity` 지수 백오프 2회 → 사용자에게 안내 + Sentry 로깅 |
| Grader JSON 파싱 실패 | 1회 자동 재요청 → 그래도 실패면 점수 0.5 + 에러 플래그, 세션 유지 |
| RAG 검색 결과 0건 | QuestionGenerator가 상위 카테고리로 토픽 폴백 → 일반 문제 생성 (덜 특화됨 명시) |
| 세션 중간 종료 | LangGraph SqliteSaver가 매 노드 후 저장 → 같은 사용자 재접속 시 "이어서 풀기" 노출 |
| 빈 답변 | API 레이어 400 차단, 그래프 진입 금지 |

---

## 9. 배포

### V1: 로컬 프로세스 (Make 기반)

Docker Desktop이 Windows에서 차지하는 비용(평시 RAM 2~4GB, 빌드 시 4~8GB, WSL2 오버헤드)을 피하기 위해 **V1은 컨테이너 없이 호스트에서 직접 실행**한다. 재현성은 lock 파일(`uv.lock`, `pnpm-lock.yaml`)이 담당.

```bash
make install   # 백엔드: uv sync, 프론트엔드: pnpm install
make dev       # 백엔드(uvicorn)와 프론트엔드(next dev) 동시 실행
make seed      # PDF 다운로드 + 인덱싱 + 골든셋 로드
```

- 백엔드: `uv run uvicorn app.main:app --reload --port 8000`
- 프론트엔드: `pnpm dev` (Next.js dev server, 3000 포트)
- ChromaDB는 임베디드 모드 (`./chroma` 파일 영속)
- SQLite는 `./data/studymate.db`

### V2 후보
- (선택) **컨테이너화** — Dockerfile + Docker Compose. Plan 7에 "선택적 컨테이너화" task로 포함. 어필 가치는 있지만 Windows에선 무거우니 마지막에 옵션으로 추가.
- 백엔드 배포: Railway 또는 Render (Python 빌드팩 직접 사용)
- 프론트엔드 배포: Vercel (Next.js 네이티브)
- 면접 며칠 전 띄워서 URL 공유

---

## 10. 기술 스택 최종

| 영역 | 채택 | 한 줄 근거 |
|---|---|---|
| Frontend | **Next.js 14 (App Router) + Tailwind + shadcn/ui** | SSE 스트리밍, 빠른 데모 UI |
| Backend | **FastAPI + Pydantic v2** | 비동기 SSE, 타입 안전, OpenAPI 자동 |
| Orchestration | **LangGraph + SqliteSaver checkpointer** | 상태 그래프 + HITL + 세션 재개 |
| LLM | **Claude Sonnet 4.6 (QGen·Grader) + Haiku 4.5 (Coordinator)** | 품질/비용 분리 |
| Embedding | **BGE-M3** (sentence-transformers, 로컬) | 한국어 강함, 비용 0, 교체 가능 |
| Vector DB | **ChromaDB** (persistent client, embedded) | V1 단순함 |
| RDB | **SQLite + SQLAlchemy 2.0 + Alembic** | V1 충분, Postgres 교체 쉬움 |
| Observability | **LangSmith** (선택) + `structlog` JSON 로그 | 그래프 추적 |
| Tests | **pytest + respx + httpx** | 표준 |
| CI | **GitHub Actions** (lint + test + eval) | 평가셋 회귀 자동화 |
| Lint/format | **ruff + mypy strict + import-linter** | 모듈 경계 CI 강제 |
| 패키지 매니저 | **uv** (백엔드) / **pnpm** (프론트) | 빠른 설치, 재현성 |

---

## 11. 면접 답변 준비표

| 예상 질문 | 답변 요지 |
|---|---|
| 왜 LangGraph? CrewAI/Agent SDK 대신? | 상태 공유 명시적, HITL을 위한 interrupt + checkpointer가 핵심. 3개 에이전트지만 의도가 명확해 오버킬 아님 |
| 왜 채점에 Sonnet? Haiku로도 되지 않나? | Eval 단계에서 두 모델 비교. 목표치 안에서 차이 없으면 다운그레이드 옵션 열어둠 (실제 수치로 답변) |
| 왜 SQLite? | V1 빠른 검증 + SQLAlchemy/Alembic 추상화. Postgres 교체는 `database_url` 변경 + 마이그레이션 한 번 |
| 모듈 경계는 어떻게 강제? | import-linter 규칙 + CI 차단. 시연 가능 |
| RAG 품질 어떻게 검증? | retrieval@k + grading accuracy, 평가셋 50문항, 매 PR 회귀 검사 |
| 확장성? | 분석 에이전트 추가(분석 로직 → LangGraph 노드 승격), 다른 도메인은 토픽 집합 + 인덱스 컬렉션만 교체 |
| 왜 BGE-M3? | 한국어 RAG에서 OpenAI text-embedding-3 대비 가성비, 로컬 호스팅으로 비용 0. 추상화로 Voyage-3 교체 가능 |
| 왜 ChromaDB? Qdrant/Weaviate 대신? | V1 임베디드 모드로 운영 단순. 50문항 규모 + 문서 수만 단위에선 차이 미미. 인덱스 추상화로 교체 가능 |
| 왜 Docker 안 썼나? | Windows에서 Docker Desktop은 평시 RAM 2~4GB, 빌드 시 4~8GB 차지하고 WSL2 오버헤드 큼. 포트폴리오 작품에서 비용 대비 효용 낮다고 판단. 재현성은 `uv.lock` + `pnpm-lock.yaml`로, 배포는 Railway+Vercel 네이티브로 동등 달성. Plan 7에 선택적 컨테이너화 옵션 남겨둠 |

---

## 12. 위험 요소 및 완화책

| 위험 | 영향 | 완화책 |
|---|---|---|
| 공개 기출문제 저작권 | 데이터 사용 불가 | 한국산업인력공단 공개 자료 우선 사용 + 위키/교과서 요약본 직접 정제. 외부 배포 시 사용 출처 명시 |
| Grader 채점 정확도 미달 | 핵심 어필 약화 | 골든셋 50문항 기준 80% 목표. 미달 시 루브릭 프롬프트 튜닝 → 모범답안 인간 검증 단계 추가 검토 |
| 한국어 BGE-M3 RAG 품질 | retrieval 부족 시 문제 품질 저하 | retrieval@5 75% 목표. 미달 시 reranker(BGE-reranker-v2) 추가 |
| LangGraph 학습 곡선 | 구현 지연 | 공식 튜토리얼 + interrupt 예제 우선 학습. 첫 주에 그래프 토폴로지만 단순 echo로 구현해 검증 |
| 데이터 시드 작업량 | 인덱싱 안 되면 데모 불가 | 최소 1년치 + 12과목 요약본으로 출시 가능한 분량 확보. 추가는 V2 |

---

## 13. 마일스톤 (참고용 — 구체 계획은 writing-plans에서)

| 주차 | 목표 |
|---|---|
| 1주차 | 프로젝트 스캐폴딩, 모듈 경계 셋업, Docker Compose, import-linter |
| 2주차 | RAG 파이프라인 (PDF → ChromaDB), 시드 데이터 1년치 |
| 3주차 | LangGraph 그래프 + 3개 노드 + SessionState, 노드별 단위 테스트 |
| 4주차 | API 라우터 + Next.js 학습 페이지 (단일 문제 풀이 흐름) |
| 5주차 | 학습 기록 DB + 약점 분석 + 대시보드 페이지 |
| 6주차 | 골든 평가셋 50문항 + 러너 + 메트릭 + CI 통합 |
| 7주차 | 에러 처리, 세션 재개, SSE 스트리밍 마무리 |
| 8주차 | 면접 시연 시나리오 다듬기, README, 데모 영상 |

---

## 14. 승인

- [ ] 사용자 검토
- [ ] writing-plans로 전환하여 구체 구현 계획 작성
