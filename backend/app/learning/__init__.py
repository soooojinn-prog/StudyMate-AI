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
