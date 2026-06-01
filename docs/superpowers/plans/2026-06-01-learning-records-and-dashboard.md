# Learning Records & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every graded session to SQLite via SQLAlchemy 2.0 + Alembic, compute weakness topics deterministically from the answer history, wire the agent graph's `PersistAdapter` + `WeaknessProvider` to the real DB, and add a `/dashboard` page that renders topic-level stats + weakness Top-3 in the Architectural-Dark theme. End-to-end: every `/sessions/{id}/answer` call writes a row, the next `Coordinator` invocation steers toward weak topics, and `/dashboard` shows the history.

**Architecture:** New `app.learning` domain module is the only place SQLAlchemy lives. Public surface: `SessionRepository.record_answer(payload)` (called from Persist node) + `compute_weakness(user_id, lookback_days=30) -> list[TopicWeakness]` (called from Coordinator). Same SQLite file as Plan 3's LangGraph SqliteSaver (`data/studymate.db`) — distinct tables, no collision. Alembic migrations let Postgres swap in via `DATABASE_URL` change. Frontend `/dashboard` is a server component that fetches `GET /dashboard/stats` and renders weakness Top-3 + per-topic accuracy + recent sessions in shadcn `Card` + `Badge`.

**Tech Stack:** SQLAlchemy 2.0 / Alembic / Pydantic v2 / FastAPI / pytest + pytest-asyncio | Next.js 14 server components / Tailwind / shadcn

**This plan is plan 5 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §5.1, §5.4, §6.

**Deferred from spec:**
- **SRS (spaced repetition / 망각곡선)** — V2 (spec §1.3 비-목표).
- **Multi-user auth** — V1 is single local user.
- **Postgres deploy migrations** — Plan 7 (V2 deploy).
- **Real-time stats streaming via SSE** — request/response is fine for V1.

---

## File Structure

```
studymate-ai/
├─ backend/
│  ├─ pyproject.toml                       # MODIFY: add sqlalchemy, alembic, aiosqlite
│  ├─ alembic.ini                          # MODIFY/CREATE: Alembic config
│  ├─ alembic/                             # NEW: Alembic env
│  │  ├─ env.py
│  │  ├─ script.py.mako
│  │  └─ versions/
│  │     └─ 0001_initial_learning_tables.py
│  └─ app/
│     ├─ learning/
│     │  ├─ __init__.py                    # re-export: SessionRepository, compute_weakness, TopicWeakness
│     │  ├─ models.py                      # SQLAlchemy 2.0 declarative — User, StudySession, QuestionInstance, Answer
│     │  ├─ database.py                    # engine + Session factory + Base
│     │  ├─ repository.py                  # SessionRepository.record_answer(payload)
│     │  └─ analytics.py                   # compute_weakness(user_id) — deterministic
│     ├─ api/
│     │  ├─ routes/
│     │  │  └─ dashboard.py                # NEW: GET /dashboard/stats
│     │  └─ schemas/
│     │     └─ dashboard.py                # NEW: DTOs
│     └─ main.py                            # MODIFY: wire PersistAdapter + WeaknessProvider to learning
└─ frontend/
   └─ src/
      ├─ app/
      │  └─ dashboard/
      │     └─ page.tsx                    # server: fetchStats() → render
      └─ lib/
         └─ api.ts                          # MODIFY: add fetchDashboardStats + DashboardStats type
backend/tests/learning/
├─ __init__.py
├─ conftest.py                              # in-memory SQLite fixtures + seed helpers
├─ test_models.py                           # round-trip + constraints
├─ test_repository.py                       # record_answer + retrieval
├─ test_analytics.py                        # weakness ranking edge cases
└─ test_dashboard_api.py                    # GET /dashboard/stats
```

### File-by-file responsibility

- **`app/learning/database.py`** — Single SQLAlchemy engine + Session factory, all settings-driven. Other modules NEVER instantiate engines.
- **`app/learning/models.py`** — Declarative models for 4 tables (User, StudySession, QuestionInstance, Answer). Maps Plan 3's `PersistAdapter` payload into rows.
- **`app/learning/repository.py`** — One class `SessionRepository`. Single write method `record_answer(payload)` (called per Persist) + read methods `recent_answers(user_id, days)`, `topic_stats(user_id, days)`.
- **`app/learning/analytics.py`** — Pure function `compute_weakness(user_id, lookback_days=30) -> list[TopicWeakness]`. No DB connection — takes a `SessionRepository` arg.
- **`app/api/routes/dashboard.py`** — `GET /dashboard/stats?user_id=...` returns `DashboardStatsDTO`.
- **`app/main.py`** — `lifespan` now wires `PersistAdapter` callback that calls `SessionRepository.record_answer(...)` and `WeaknessProvider` callback that calls `compute_weakness(...)`.
- **`alembic/`** — Standard Alembic layout. One migration creates the 4 tables.

---

## Task 1: Dependencies + module skeleton + Alembic init

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/learning/__init__.py`
- Create: `backend/app/learning/database.py`
- Create: `backend/app/learning/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial_learning_tables.py`
- Create: `backend/tests/learning/__init__.py`
- Create: `backend/tests/learning/test_models.py`
- Modify: `backend/app/core/settings.py` (add `database_url`)

- [ ] **Step 1: Add deps to `backend/pyproject.toml`**

Append to `[project] dependencies`:
```toml
  "sqlalchemy>=2.0.36",
  "alembic>=1.14.0",
```

Then `cd backend && uv sync`.

- [ ] **Step 2: Add `database_url` to `backend/app/core/settings.py`**

Find the `# ── Agents ─` block and add ONE line just above it:

```python
    # ── Database ───────────────────────────────────────────
    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{_PROJECT_ROOT / 'data' / 'studymate.db'}"
    )
```

(Keep all existing fields. The new field goes between the RAG block and the Agents block.)

- [ ] **Step 3: Create `backend/app/learning/__init__.py`**

```python
"""Learning Records domain.

Single public surface for the agent graph's PersistAdapter and
WeaknessProvider hooks. Outside callers import only what is re-exported
here. SQLAlchemy lives strictly inside this module.
"""
```

(Re-exports added in Task 6.)

- [ ] **Step 4: Create `backend/app/learning/database.py`**

```python
"""SQLAlchemy engine and session factory."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import settings


class Base(DeclarativeBase):
    """Project-wide declarative base."""


_engine = create_engine(settings.database_url, future=True)
_SessionFactory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    """Build a new ORM session bound to the project engine."""
    return _SessionFactory()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional context manager: commit on success, rollback on error."""
    sess = get_session()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
```

- [ ] **Step 5: Create `backend/app/learning/models.py`**

```python
"""SQLAlchemy 2.0 declarative models for learning records.

Matches spec §5.1 exactly. The LangGraph SqliteSaver uses its own
tables in the same SQLite file — no schema collision.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.learning.database import Base


def _now() -> datetime:
    return datetime.now(tz=UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(32), default="topic")  # 'weakness' | 'topic' | 'review'
    target_topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=5)
    thread_id: Mapped[str] = mapped_column(String(36))  # LangGraph checkpointer key
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list["QuestionInstance"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class QuestionInstance(Base):
    __tablename__ = "question_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("study_sessions.id"))
    seq: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(128))
    difficulty: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    rubric_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    ref_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[StudySession] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question_instance", uselist=False, cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("question_instance_id", name="uq_one_answer_per_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_instances.id"), unique=True
    )
    user_answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str] = mapped_column(Text)
    missing_points_json: Mapped[list[str]] = mapped_column(JSON)
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question_instance: Mapped[QuestionInstance] = relationship(back_populates="answer")
```

- [ ] **Step 6: Create `backend/alembic.ini`** at backend/ root

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///../data/studymate.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 7: Create `backend/alembic/env.py`**

```python
"""Alembic environment — uses app settings for connection."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.settings import settings
from app.learning.database import Base
from app.learning import models  # noqa: F401  # import models so metadata is registered

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the .ini URL with the runtime settings URL.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Create `backend/alembic/script.py.mako`** (standard Alembic template)

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 9: Create the initial migration `backend/alembic/versions/0001_initial_learning_tables.py`**

```python
"""initial learning tables

Revision ID: 0001
Revises:
Create Date: 2026-06-01

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("nickname", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("target_topic", sa.String(128), nullable=True),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(36), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "question_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("study_sessions.id"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("model_answer", sa.Text(), nullable=False),
        sa.Column("rubric_json", sa.JSON(), nullable=False),
        sa.Column("ref_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_instance_id",
            sa.String(36),
            sa.ForeignKey("question_instances.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("missing_points_json", sa.JSON(), nullable=False),
        sa.Column("graded_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("answers")
    op.drop_table("question_instances")
    op.drop_table("study_sessions")
    op.drop_table("users")
```

- [ ] **Step 10: Create `backend/tests/learning/__init__.py`** (empty)

```python
```

- [ ] **Step 11: Write `backend/tests/learning/test_models.py`**

```python
"""Tests for app.learning.models — table creation + round-trip."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.learning.database import Base
from app.learning.models import Answer, QuestionInstance, StudySession, User


@pytest.fixture
def session(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def test_user_round_trip(session: Session):
    user = User(id="u1", nickname="홍길동", created_at=datetime.now(tz=UTC))
    session.add(user)
    session.commit()
    fetched = session.get(User, "u1")
    assert fetched is not None
    assert fetched.nickname == "홍길동"


def test_full_session_chain(session: Session):
    user = User(id="u1", nickname="홍길동", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1",
        user_id="u1",
        mode="weakness",
        target_count=5,
        thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1",
        session_id="s1",
        seq=1,
        topic="정규화",
        difficulty=2,
        question_text="문제",
        model_answer="답",
        rubric_json=[{"point": "p", "weight": 1.0, "keywords": []}],
        ref_chunk_ids=["c1"],
        generated_at=datetime.now(tz=UTC),
    )
    a = Answer(
        id="a1",
        question_instance_id="q1",
        user_answer="학습자 답",
        score=0.7,
        rationale="r",
        feedback="f",
        missing_points_json=[],
        graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a])
    session.commit()
    expected_score = 0.7
    answer = session.get(Answer, "a1")
    assert answer is not None
    assert answer.score == expected_score
    assert answer.question_instance.topic == "정규화"


def test_one_answer_per_question_constraint(session: Session):
    user = User(id="u1", nickname="n", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1", user_id="u1", mode="topic", target_count=1, thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1", session_id="s1", seq=1, topic="x", difficulty=1,
        question_text="q", model_answer="m", rubric_json=[], ref_chunk_ids=[],
        generated_at=datetime.now(tz=UTC),
    )
    a1 = Answer(
        id="a1", question_instance_id="q1", user_answer="x", score=0.5,
        rationale="r", feedback="f", missing_points_json=[], graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a1])
    session.commit()

    a2 = Answer(
        id="a2", question_instance_id="q1", user_answer="y", score=0.6,
        rationale="r2", feedback="f2", missing_points_json=[], graded_at=datetime.now(tz=UTC),
    )
    session.add(a2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_cascade_delete_session_removes_questions_and_answers(session: Session):
    user = User(id="u1", nickname="n", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1", user_id="u1", mode="topic", target_count=1, thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1", session_id="s1", seq=1, topic="x", difficulty=1,
        question_text="q", model_answer="m", rubric_json=[], ref_chunk_ids=[],
        generated_at=datetime.now(tz=UTC),
    )
    a = Answer(
        id="a1", question_instance_id="q1", user_answer="x", score=0.5,
        rationale="r", feedback="f", missing_points_json=[], graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a])
    session.commit()

    session.delete(sess)
    session.commit()
    assert session.get(QuestionInstance, "q1") is None
    assert session.get(Answer, "a1") is None
```

- [ ] **Step 12: Run migration locally to create tables in `data/studymate.db`**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade -> 0001, initial learning tables`.

- [ ] **Step 13: Run tests**

```bash
cd backend && uv run pytest tests/learning -v
```

Expected: 4 passed.

- [ ] **Step 14: Lint + types**

```bash
cd backend && uv run ruff check app/learning tests/learning alembic && uv run ruff format --check app/learning tests/learning alembic && uv run mypy app/learning tests/learning
```

Add a mypy override for `alembic.*` if it complains about stubs (in `pyproject.toml`):

```toml
[[tool.mypy.overrides]]
module = "alembic.*"
ignore_missing_imports = true
```

- [ ] **Step 15: Verify import-linter still happy**

```bash
cd backend && uv run lint-imports --config .importlinter
```

Expected: 5 kept, 0 broken. `app.learning` may import `app.core` (allowed); no other domains touched.

- [ ] **Step 16: Commit + push**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/learning/ backend/alembic.ini backend/alembic/ backend/app/core/settings.py backend/tests/learning/
git commit -m "feat(learning): add SQLAlchemy models + Alembic migration for session records"
git push
```

---

## Task 2: SessionRepository — `record_answer(payload)`

**Files:**
- Create: `backend/app/learning/repository.py`
- Create: `backend/tests/learning/conftest.py`
- Create: `backend/tests/learning/test_repository.py`

- [ ] **Step 1: Shared fixtures `backend/tests/learning/conftest.py`**

```python
"""Shared fixtures for app.learning tests."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.learning.database import Base


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()
```

- [ ] **Step 2: Write the failing test in `backend/tests/learning/test_repository.py`**

```python
"""Tests for SessionRepository."""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository


def _seed_user(session: Session, user_id: str = "u1") -> None:
    session.add(User(id=user_id, nickname="n", created_at=datetime.now(tz=UTC)))
    session.flush()


def _seed_session(session: Session, session_id: str = "s1", user_id: str = "u1") -> None:
    session.add(
        StudySession(
            id=session_id,
            user_id=user_id,
            mode="topic",
            target_count=5,
            thread_id=session_id,
            started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()


def test_record_answer_writes_question_and_answer_rows(db_session: Session):
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)

    payload = {
        "user_id": "u1",
        "session_id": "s1",
        "topic": "정규화",
        "difficulty": 2,
        "question": "Q?",
        "model_answer": "A.",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": ["k"]}],
        "ref_chunk_ids": ["c1"],
        "user_answer": "ua",
        "score": 0.7,
        "rationale": "r",
        "feedback": "f",
        "missing_points": ["x"],
    }
    repo.record_answer(payload)
    db_session.commit()

    answers = repo.recent_answers("u1", days=30)
    expected_count = 1
    assert len(answers) == expected_count
    assert answers[0].topic == "정규화"
    expected_score = 0.7
    assert answers[0].score == expected_score


def test_record_answer_increments_seq_per_session(db_session: Session):
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)
    base_payload = {
        "user_id": "u1",
        "session_id": "s1",
        "topic": "정규화",
        "difficulty": 1,
        "question": "Q",
        "model_answer": "A",
        "rubric": [],
        "ref_chunk_ids": [],
        "user_answer": "ua",
        "rationale": "r",
        "feedback": "f",
        "missing_points": [],
    }
    repo.record_answer({**base_payload, "score": 0.5})
    repo.record_answer({**base_payload, "score": 0.8})
    db_session.commit()
    answers = repo.recent_answers("u1", days=30)
    expected_count = 2
    assert len(answers) == expected_count
    assert {a.seq for a in answers} == {1, 2}


def test_recent_answers_filters_by_user(db_session: Session):
    _seed_user(db_session, "u1")
    _seed_user(db_session, "u2")
    _seed_session(db_session, "s1", "u1")
    _seed_session(db_session, "s2", "u2")
    repo = SessionRepository(db_session)
    for uid, sid in [("u1", "s1"), ("u2", "s2")]:
        repo.record_answer(
            {
                "user_id": uid,
                "session_id": sid,
                "topic": "x",
                "difficulty": 1,
                "question": "q",
                "model_answer": "m",
                "rubric": [],
                "ref_chunk_ids": [],
                "user_answer": "ua",
                "score": 0.5,
                "rationale": "r",
                "feedback": "f",
                "missing_points": [],
            }
        )
    db_session.commit()
    assert len(repo.recent_answers("u1", days=30)) == 1
    assert len(repo.recent_answers("u2", days=30)) == 1


def test_recent_answers_filters_by_lookback(db_session: Session):
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)
    repo.record_answer(
        {
            "user_id": "u1",
            "session_id": "s1",
            "topic": "x",
            "difficulty": 1,
            "question": "q",
            "model_answer": "m",
            "rubric": [],
            "ref_chunk_ids": [],
            "user_answer": "ua",
            "score": 0.5,
            "rationale": "r",
            "feedback": "f",
            "missing_points": [],
        }
    )
    db_session.commit()
    # Backdate the answer beyond the lookback
    answer = repo.recent_answers("u1", days=30)[0]
    answer.graded_at = datetime.now(tz=UTC) - timedelta(days=60)
    db_session.commit()
    assert repo.recent_answers("u1", days=30) == []
```

- [ ] **Step 3: Implement `backend/app/learning/repository.py`**

```python
"""Repository wrapping all reads/writes against the learning tables."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.learning.models import Answer, QuestionInstance, StudySession


@dataclass
class AnswerView:
    """Flat read shape for analytics — joins QuestionInstance and Answer."""

    session_id: str
    topic: str
    difficulty: int
    score: float
    seq: int
    graded_at: datetime


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _next_seq(self, session_id: str) -> int:
        stmt = select(func.coalesce(func.max(QuestionInstance.seq), 0)).where(
            QuestionInstance.session_id == session_id
        )
        return int(self.session.execute(stmt).scalar_one() or 0) + 1

    def record_answer(self, payload: dict[str, Any]) -> None:
        """Persist a graded question+answer pair from the Persist node payload."""
        session_id = str(payload["session_id"])
        seq = self._next_seq(session_id)
        q_id = str(uuid.uuid4())
        a_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)
        self.session.add(
            QuestionInstance(
                id=q_id,
                session_id=session_id,
                seq=seq,
                topic=str(payload.get("topic", "")),
                difficulty=int(payload.get("difficulty", 1)),
                question_text=str(payload.get("question", "")),
                model_answer=str(payload.get("model_answer", "")),
                rubric_json=list(payload.get("rubric", [])),
                ref_chunk_ids=list(payload.get("ref_chunk_ids", [])),
                generated_at=now,
            )
        )
        self.session.add(
            Answer(
                id=a_id,
                question_instance_id=q_id,
                user_answer=str(payload.get("user_answer", "")),
                score=float(payload.get("score", 0.0)),
                rationale=str(payload.get("rationale", "")),
                feedback=str(payload.get("feedback", "")),
                missing_points_json=list(payload.get("missing_points", [])),
                graded_at=now,
            )
        )

    def recent_answers(self, user_id: str, *, days: int) -> list[Answer]:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        stmt = (
            select(Answer)
            .join(QuestionInstance, Answer.question_instance_id == QuestionInstance.id)
            .join(StudySession, QuestionInstance.session_id == StudySession.id)
            .where(StudySession.user_id == user_id)
            .where(Answer.graded_at >= cutoff)
            .order_by(Answer.graded_at.desc())
        )
        # Attach topic/difficulty/seq via the relationship for convenience in analytics.
        rows = list(self.session.execute(stmt).scalars().all())
        for r in rows:
            # Eager-touch the related question (single SELECT under autoflush=False).
            _ = r.question_instance.topic
        return rows
```

- [ ] **Step 4: Run, confirm 4 passed.**

```bash
cd backend && uv run pytest tests/learning/test_repository.py -v
```

- [ ] **Step 5: Lint + types.**

- [ ] **Step 6: Commit + push:**

```bash
git add backend/app/learning/repository.py backend/tests/learning/
git commit -m "feat(learning): add SessionRepository.record_answer + recent_answers"
git push
```

---

## Task 3: Weakness analytics

**Files:**
- Create: `backend/app/learning/analytics.py`
- Create: `backend/tests/learning/test_analytics.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/learning/test_analytics.py`:

```python
"""Tests for compute_weakness — deterministic, no LLM."""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.learning.analytics import compute_weakness
from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository


def _seed_basic(session: Session, user_id: str = "u1", session_id: str = "s1") -> None:
    session.add(User(id=user_id, nickname="n", created_at=datetime.now(tz=UTC)))
    session.add(
        StudySession(
            id=session_id, user_id=user_id, mode="topic", target_count=10,
            thread_id=session_id, started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()


def _record_n(repo: SessionRepository, topic: str, scores: list[float]) -> None:
    for s in scores:
        repo.record_answer(
            {
                "user_id": "u1", "session_id": "s1", "topic": topic, "difficulty": 2,
                "question": "q", "model_answer": "m", "rubric": [], "ref_chunk_ids": [],
                "user_answer": "ua", "score": s, "rationale": "r", "feedback": "f",
                "missing_points": [],
            }
        )


def test_compute_weakness_ranks_low_average_first(db_session: Session):
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    _record_n(repo, "정규화", [0.9, 0.95, 0.92])      # strong
    _record_n(repo, "네트워크", [0.3, 0.4, 0.35])     # weak
    _record_n(repo, "SQL", [0.6, 0.65, 0.7])          # mid
    db_session.commit()

    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_count = 3
    assert len(weak) == expected_count
    assert weak[0].topic == "네트워크"
    assert weak[1].topic == "SQL"
    assert weak[2].topic == "정규화"


def test_compute_weakness_excludes_topics_with_fewer_than_3_samples(db_session: Session):
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    _record_n(repo, "정규화", [0.5, 0.6, 0.7])         # ≥3 — counts
    _record_n(repo, "네트워크", [0.1, 0.2])            # only 2 — excluded
    db_session.commit()
    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_count = 1
    assert len(weak) == expected_count
    assert weak[0].topic == "정규화"


def test_compute_weakness_returns_at_most_top_3(db_session: Session):
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    for t in ["a", "b", "c", "d", "e"]:
        _record_n(repo, t, [0.5, 0.5, 0.5])
    db_session.commit()
    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_top = 3
    assert len(weak) == expected_top


def test_compute_weakness_empty_for_no_data(db_session: Session):
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    db_session.commit()
    assert compute_weakness(repo, user_id="u1", lookback_days=30) == []
```

- [ ] **Step 2: Implement `backend/app/learning/analytics.py`**

```python
"""Deterministic weakness ranking — no LLM, no random."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.learning.repository import SessionRepository


_MIN_SAMPLES_PER_TOPIC = 3
_TOP_N = 3


@dataclass(frozen=True)
class TopicWeakness:
    topic: str
    avg_score: float
    sample_count: int


def compute_weakness(
    repo: SessionRepository,
    *,
    user_id: str,
    lookback_days: int = 30,
) -> list[TopicWeakness]:
    """Return up to top-3 topics with the lowest average score.

    A topic must have at least 3 graded answers in the lookback window to be
    counted (avoids ranking a topic by a single bad answer).
    """
    answers = repo.recent_answers(user_id, days=lookback_days)
    by_topic: dict[str, list[float]] = defaultdict(list)
    for a in answers:
        by_topic[a.question_instance.topic].append(a.score)

    eligible: list[TopicWeakness] = []
    for topic, scores in by_topic.items():
        if len(scores) < _MIN_SAMPLES_PER_TOPIC:
            continue
        eligible.append(
            TopicWeakness(
                topic=topic,
                avg_score=sum(scores) / len(scores),
                sample_count=len(scores),
            )
        )
    eligible.sort(key=lambda w: (w.avg_score, -w.sample_count))
    return eligible[:_TOP_N]
```

- [ ] **Step 3: Run, confirm 4 passed.**

- [ ] **Step 4: Lint + types.**

- [ ] **Step 5: Commit + push:**

```bash
git add backend/app/learning/analytics.py backend/tests/learning/test_analytics.py
git commit -m "feat(learning): add deterministic compute_weakness (Top-3 by avg score)"
git push
```

---

## Task 4: Re-exports + module public surface

**Files:**
- Modify: `backend/app/learning/__init__.py`

- [ ] **Step 1: Modify `backend/app/learning/__init__.py`**

```python
"""Learning Records domain.

Single public surface for the agent graph's PersistAdapter and
WeaknessProvider hooks. Outside callers import only what is re-exported
here. SQLAlchemy lives strictly inside this module.
"""
from app.learning.analytics import TopicWeakness, compute_weakness
from app.learning.database import get_session, session_scope
from app.learning.repository import SessionRepository

__all__ = [
    "SessionRepository",
    "TopicWeakness",
    "compute_weakness",
    "get_session",
    "session_scope",
]
```

- [ ] **Step 2: Run import-linter + full pytest**

```bash
cd backend && uv run lint-imports --config .importlinter && uv run pytest -v
```

Expected: 5 kept 0 broken, all tests pass.

- [ ] **Step 3: Lint + types.**

- [ ] **Step 4: Commit + push:**

```bash
git add backend/app/learning/__init__.py
git commit -m "feat(learning): export SessionRepository + compute_weakness public surface"
git push
```

---

## Task 5: Dashboard API endpoint

**Files:**
- Create: `backend/app/api/schemas/dashboard.py`
- Create: `backend/app/api/routes/dashboard.py`
- Create: `backend/tests/api/test_dashboard_api.py`
- Modify: `backend/app/main.py` (include dashboard router)

- [ ] **Step 1: Create `backend/app/api/schemas/dashboard.py`**

```python
"""DTOs for /dashboard/stats."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WeakTopicDTO(BaseModel):
    topic: str
    avg_score: float
    sample_count: int


class TopicStatDTO(BaseModel):
    topic: str
    answer_count: int
    avg_score: float


class RecentAnswerDTO(BaseModel):
    session_id: str
    topic: str
    score: float
    graded_at: datetime


class DashboardStatsDTO(BaseModel):
    user_id: str
    weak_topics: list[WeakTopicDTO] = Field(default_factory=list)
    topic_stats: list[TopicStatDTO] = Field(default_factory=list)
    recent_answers: list[RecentAnswerDTO] = Field(default_factory=list)
    total_answers: int = 0
```

- [ ] **Step 2: Write the failing test in `backend/tests/api/test_dashboard_api.py`**

```python
"""GET /dashboard/stats — returns weakness + topic-level stats."""
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db_session
from app.learning.database import Base
from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository
from app.main import create_app


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def client(db_session: Session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


def _seed_history(session: Session) -> None:
    session.add(User(id="u1", nickname="n", created_at=datetime.now(tz=UTC)))
    session.add(
        StudySession(
            id="s1", user_id="u1", mode="topic", target_count=10,
            thread_id="s1", started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()
    repo = SessionRepository(session)
    for s in [0.3, 0.4, 0.35]:
        repo.record_answer(_payload("네트워크", s))
    for s in [0.8, 0.85, 0.9]:
        repo.record_answer(_payload("정규화", s))
    session.commit()


def _payload(topic: str, score: float) -> dict[str, Any]:
    return {
        "user_id": "u1", "session_id": "s1", "topic": topic, "difficulty": 2,
        "question": "q", "model_answer": "m", "rubric": [], "ref_chunk_ids": [],
        "user_answer": "ua", "score": score, "rationale": "r", "feedback": "f",
        "missing_points": [],
    }


def test_stats_returns_weakness_and_topic_stats(client: TestClient, db_session: Session):
    _seed_history(db_session)
    response = client.get("/dashboard/stats", params={"user_id": "u1"})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["user_id"] == "u1"
    expected_total = 6
    assert body["total_answers"] == expected_total
    assert body["weak_topics"][0]["topic"] == "네트워크"
    topics = {t["topic"] for t in body["topic_stats"]}
    assert topics == {"네트워크", "정규화"}


def test_stats_empty_for_unknown_user(client: TestClient, db_session: Session):
    response = client.get("/dashboard/stats", params={"user_id": "ghost"})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total_answers"] == 0
    assert body["weak_topics"] == []
```

- [ ] **Step 3: Modify `backend/app/api/dependencies.py` — add `get_db_session` Depends**

Append to the file:

```python
from sqlalchemy.orm import Session

from app.learning.database import get_session as _make_session


def get_db_session() -> Session:
    return _make_session()


DbSessionDep = Annotated[Session, Depends(get_db_session)]
```

- [ ] **Step 4: Create `backend/app/api/routes/dashboard.py`**

```python
"""Dashboard endpoints — read-only stats over the learning tables."""
from __future__ import annotations

from collections import defaultdict
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.api.dependencies import DbSessionDep
from app.api.schemas.dashboard import (
    DashboardStatsDTO,
    RecentAnswerDTO,
    TopicStatDTO,
    WeakTopicDTO,
)
from app.learning.analytics import compute_weakness
from app.learning.repository import SessionRepository


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


_DEFAULT_LOOKBACK_DAYS = 30
_MAX_RECENT_ROWS = 10


@router.get("/stats", response_model=DashboardStatsDTO)
def stats(user_id: str, db: DbSessionDep) -> DashboardStatsDTO:
    if not user_id.strip():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="user_id_required"
        )
    repo = SessionRepository(db)
    answers = repo.recent_answers(user_id, days=_DEFAULT_LOOKBACK_DAYS)

    weak = compute_weakness(repo, user_id=user_id, lookback_days=_DEFAULT_LOOKBACK_DAYS)

    # topic_stats — every topic with ≥ 1 answer in the window
    by_topic: dict[str, list[float]] = defaultdict(list)
    for a in answers:
        by_topic[a.question_instance.topic].append(a.score)
    topic_stats = [
        TopicStatDTO(
            topic=t,
            answer_count=len(scores),
            avg_score=round(sum(scores) / len(scores), 3),
        )
        for t, scores in sorted(by_topic.items())
    ]

    recent = [
        RecentAnswerDTO(
            session_id=a.question_instance.session_id,
            topic=a.question_instance.topic,
            score=a.score,
            graded_at=a.graded_at,
        )
        for a in answers[:_MAX_RECENT_ROWS]
    ]

    return DashboardStatsDTO(
        user_id=user_id,
        weak_topics=[
            WeakTopicDTO(topic=w.topic, avg_score=w.avg_score, sample_count=w.sample_count)
            for w in weak
        ],
        topic_stats=topic_stats,
        recent_answers=recent,
        total_answers=len(answers),
    )
```

- [ ] **Step 5: Modify `backend/app/main.py`** — include the dashboard router (after sessions router):

In `create_app()`, after `app.include_router(sessions.router)`, add:

```python
    from app.api.routes import dashboard  # noqa: PLC0415

    app.include_router(dashboard.router)
```

- [ ] **Step 6: Run, confirm 2 passed for test_dashboard_api.py + full pytest.**

- [ ] **Step 7: Lint + types.**

- [ ] **Step 8: Commit + push:**

```bash
git add backend/app/api/schemas/dashboard.py backend/app/api/routes/dashboard.py backend/app/api/dependencies.py backend/app/main.py backend/tests/api/test_dashboard_api.py
git commit -m "feat(api): add GET /dashboard/stats endpoint"
git push
```

---

## Task 6: Wire PersistAdapter + WeaknessProvider to the agent graph

**Files:**
- Modify: `backend/app/api/dependencies.py` (build adapters from settings; pass to graph)
- Modify: `backend/app/main.py` lifespan

- [ ] **Step 1: Modify `_build_graph_singleton` in `backend/app/api/dependencies.py`**

Replace the existing function body with:

```python
def _build_graph_singleton() -> Any:
    """Construct the agent graph with real Anthropic + real retriever +
    real DB-backed persistence and weakness lookup."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever = default_retriever()
    topics = load_topics(settings.topics_file)
    saver = make_checkpointer(settings.studymate_db)

    def _persist(payload: dict[str, Any]) -> None:
        from app.learning.database import session_scope  # noqa: PLC0415
        from app.learning.repository import SessionRepository  # noqa: PLC0415

        with session_scope() as sess:
            SessionRepository(sess).record_answer(payload)

    def _weakness(user_id: str) -> list[str]:
        from app.learning.analytics import compute_weakness  # noqa: PLC0415
        from app.learning.database import session_scope  # noqa: PLC0415
        from app.learning.repository import SessionRepository  # noqa: PLC0415

        with session_scope() as sess:
            weak = compute_weakness(
                SessionRepository(sess), user_id=user_id, lookback_days=30
            )
            return [w.topic for w in weak]

    return build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=_weakness,
        persist_adapter=_persist,
        topics=topics,
        sonnet_model=settings.anthropic_model_sonnet,
        haiku_model=settings.anthropic_model_haiku,
    )
```

- [ ] **Step 2: Run full pytest — all Plan 3/4 tests + new Plan 5 tests must still pass.**

The graph is still mocked in tests; the real adapter only runs when `ANTHROPIC_API_KEY` is set.

- [ ] **Step 3: Lint + types.**

- [ ] **Step 4: Commit + push:**

```bash
git add backend/app/api/dependencies.py
git commit -m "feat(learning): wire PersistAdapter + WeaknessProvider into agent graph"
git push
```

---

## Task 7: Frontend — `/dashboard` page

**Files:**
- Modify: `frontend/src/lib/api.ts` (add `fetchDashboardStats`)
- Create: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/app/page.tsx` (link to /dashboard)

- [ ] **Step 1: Append to `frontend/src/lib/api.ts`** — new types + function

Add after the existing exports:

```typescript
export type WeakTopic = {
  topic: string;
  avg_score: number;
  sample_count: number;
};

export type TopicStat = {
  topic: string;
  answer_count: number;
  avg_score: number;
};

export type RecentAnswer = {
  session_id: string;
  topic: string;
  score: number;
  graded_at: string;
};

export type DashboardStats = {
  user_id: string;
  weak_topics: WeakTopic[];
  topic_stats: TopicStat[];
  recent_answers: RecentAnswer[];
  total_answers: number;
};

export async function fetchDashboardStats(userId: string): Promise<DashboardStats> {
  const url = new URL(`${backendUrl()}/dashboard/stats`);
  url.searchParams.set("user_id", userId);
  return _json<DashboardStats>(url.toString());
}
```

- [ ] **Step 2: Create `frontend/src/app/dashboard/page.tsx`**

```tsx
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fetchDashboardStats, type DashboardStats } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let stats: DashboardStats | null = null;
  let error: string | null = null;
  try {
    stats = await fetchDashboardStats("local-user");
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error || !stats) {
    return (
      <main className="mx-auto max-w-4xl p-10">
        <div className="border border-danger/40 bg-danger/5 p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-danger">
            dashboard_load_failed
          </p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-ink-mid">{error}</pre>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-10 py-12 bg-blueprint-grid bg-[length:36px_36px]">
      <header className="flex items-baseline justify-between border-y border-panel-line py-3 mb-10 font-mono text-[11px] uppercase tracking-[0.22em] text-ink-soft">
        <span><span className="text-cyan">●</span> Dashboard · {stats.user_id}</span>
        <span>{stats.total_answers} answers · last 30 days</span>
      </header>

      {/* weakness top-3 */}
      <section className="mb-12">
        <Badge tone="amber" className="mb-4">
          · Weakness Top-3 · 가중평균 낮은 주제
        </Badge>
        {stats.weak_topics.length === 0 ? (
          <p className="text-ink-mid">데이터가 충분하지 않습니다 (한 주제당 ≥3개 답변 필요).</p>
        ) : (
          <ol className="grid gap-3">
            {stats.weak_topics.map((w, i) => (
              <Card key={w.topic} className="grid grid-cols-[60px_1fr_auto] items-center gap-4">
                <span className="font-display italic text-[40px] leading-none text-amber">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="text-[20px] font-medium">{w.topic}</p>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                    {w.sample_count} answers
                  </p>
                </div>
                <span className="font-display text-[36px] text-amber">
                  {w.avg_score.toFixed(2)}
                </span>
              </Card>
            ))}
          </ol>
        )}
      </section>

      {/* topic stats */}
      <section className="mb-12">
        <Badge tone="cyan" className="mb-4">
          · Topic Stats · 주제별 평균
        </Badge>
        {stats.topic_stats.length === 0 ? (
          <p className="text-ink-mid">아직 풀이 이력이 없습니다.</p>
        ) : (
          <ol className="border-t border-panel-line">
            {stats.topic_stats.map((t) => (
              <li
                key={t.topic}
                className="grid grid-cols-[1fr_auto_auto] items-center gap-6 py-3 border-b border-panel-line"
              >
                <span className="text-[16.5px]">{t.topic}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t.answer_count} answers
                </span>
                <span className="font-display text-[20px] text-cyan">
                  {t.avg_score.toFixed(2)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* recent answers */}
      <section>
        <Badge tone="magenta" className="mb-4">
          · Recent · 최근 답변 10건
        </Badge>
        {stats.recent_answers.length === 0 ? (
          <p className="text-ink-mid">최근 답변이 없습니다.</p>
        ) : (
          <ol className="border-t border-panel-line">
            {stats.recent_answers.map((r, i) => (
              <li
                key={`${r.session_id}-${i}`}
                className="grid grid-cols-[120px_1fr_auto_auto] items-center gap-4 py-3 border-b border-panel-line"
              >
                <span className="font-mono text-[10.5px] tracking-[0.18em] uppercase text-ink-soft">
                  {new Date(r.graded_at).toISOString().slice(0, 16).replace("T", " ")}
                </span>
                <span className="text-ink">{r.topic}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-mid">
                  {r.session_id.slice(0, 8)}
                </span>
                <span
                  className={
                    "font-display text-[24px] " +
                    (r.score >= 0.7 ? "text-cyan" : r.score >= 0.4 ? "text-amber" : "text-danger")
                  }
                >
                  {r.score.toFixed(2)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Modify `frontend/src/app/page.tsx`** — add a dashboard link button

Find the existing button row (the `<div className="mt-10 flex gap-3">` block) and replace with:

```tsx
      <div className="mt-10 flex gap-3 flex-wrap">
        <Button asChild>
          <Link href="/study">학습 시작 →</Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/dashboard">대시보드</Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/health">시스템 상태</Link>
        </Button>
      </div>
```

- [ ] **Step 4: Typecheck + lint + build**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```

Expected: `/`, `/health`, `/study`, `/dashboard` all in the route table.

- [ ] **Step 5: Commit + push**

```bash
git add frontend/src/lib/api.ts frontend/src/app/dashboard/ frontend/src/app/page.tsx
git commit -m "feat(frontend): add /dashboard page with weak topics, topic stats, recent answers"
git push
```

---

## Task 8: End-to-end manual verification

This task requires `ANTHROPIC_API_KEY` + credit + Plan 2 Task 12 seed (BGE-M3 + Chroma ingest).

- [ ] **Step 1: Confirm prerequisites**

```bash
grep ANTHROPIC_API_KEY .env | grep -v "^#"   # key set
cd backend && uv run python -m scripts.seed status   # chunks > 0
cd backend && uv run alembic upgrade head    # tables exist
```

- [ ] **Step 2: Start backend + frontend (two terminals)**

```bash
# Terminal A
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal B
cd frontend && pnpm dev
```

- [ ] **Step 3: Browser flow**

1. Visit <http://localhost:3000>. Click "학습 시작 →".
2. Page loads with a question. Type an intentionally partial answer (e.g., "정규화는 데이터 중복을 줄입니다."). Submit.
3. After ~10s, score card + rubric + reinforcement note appear. Score < 1.0 because key concepts are missing.
4. Repeat the cycle 3+ times on the same topic so the topic enters the weakness ranking.
5. Visit <http://localhost:3000/dashboard>. Weakness Top-3 should include the topic you've been answering badly. Topic stats and recent answers populated.

- [ ] **Step 4: Programmatic smoke**

```bash
curl --fail "http://localhost:8000/dashboard/stats?user_id=local-user" | python -m json.tool
```

- [ ] **Step 5: Commit lock files + dev-log if changed**

```bash
git status
git add backend/uv.lock 2>/dev/null || true
git diff --cached --quiet || git commit -m "chore: lock files after Plan 5 verification"
git push
```

---

## Acceptance Criteria

Plan 5 is complete when **all** of the following hold:

1. `cd backend && uv run pytest -v` passes 100%.
2. `cd backend && uv run lint-imports --config .importlinter` reports `5 kept, 0 broken`.
3. `cd backend && uv run mypy app tests` passes.
4. `cd backend && uv run alembic upgrade head` runs cleanly on a fresh DB.
5. `cd frontend && pnpm typecheck && pnpm lint && pnpm build` clean. `/dashboard` route present.
6. `GET /dashboard/stats?user_id=local-user` returns the right shape (200 with weak_topics, topic_stats, recent_answers, total_answers).
7. After 3+ /study sessions on the same topic with sub-0.7 scores, `/dashboard` shows that topic in the weakness Top-3, and the next /study session's Coordinator picks a weak topic (target_weakness=true).

---

## What's Next

Plan 6: **Evaluation System & Metrics CI**. Build the 50-question × 3-answer = 150-case golden eval set, write `eval/runner.py` that produces Grading Accuracy / Retrieval Recall@5 / End-to-end Latency p95 metrics + an HTML report, and wire GitHub Actions to run it on every PR with a regression gate. This is the "how do you know it works?" answer in interviews.
