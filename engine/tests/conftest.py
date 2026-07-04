from __future__ import annotations

import pytest

# Use pytest_runtest_setup hook to dynamically set SessionLocal and engine
# before any test or its setup fixtures run.

def pytest_runtest_setup(item) -> None:
    module = item.module
    engine = getattr(module, "_sqlite_engine", None)
    if engine is None:
        try:
            import sqlite_test_support
            engine = sqlite_test_support.TEST_ENGINE
        except ImportError:
            pass

    if engine is not None:
        from migrations_engine.db import session as db_session
        from migrations_engine.api import deps as deps_module
        from sqlalchemy.orm import sessionmaker

        # Monkeypatch the engine and sessionmaker globally
        db_session.engine = engine
        db_session.SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            class_=db_session.Session,
        )
        deps_module.SessionLocal = db_session.SessionLocal

        # Update the SessionLocal reference inside the test module itself if it has one
        if hasattr(module, "SessionLocal"):
            setattr(module, "SessionLocal", db_session.SessionLocal)
