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
