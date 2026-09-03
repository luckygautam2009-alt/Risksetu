"""
Declarative base for all ORM models.

Kept separate from session.py so Alembic's env.py can import model metadata
without pulling in the engine/session machinery (avoids import-cycle and
side-effect issues once app/models/* starts importing from here in Phase 1).
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
