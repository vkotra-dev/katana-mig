from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from migrations_engine.db import session as db_session
from migrations_engine.db.base import Base  # noqa: F401

TEST_ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

db_session.engine = TEST_ENGINE
db_session.SessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    autocommit=False,
    class_=db_session.Session,
)

SessionLocal = db_session.SessionLocal
