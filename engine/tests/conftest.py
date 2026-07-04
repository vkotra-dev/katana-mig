from __future__ import annotations

import pytest

# Use pytest_runtest_setup hook to dynamically set SessionLocal and engine
# before any test or its setup fixtures run.

def pytest_runtest_setup(item) -> None:
    module = item.module
    engine = getattr(module, "_sqlite_engine", None)
    if engine is None:
        # Check if the test module has explicitly imported or defined SQLite variables
        uses_sqlite = (
            "_sqlite_engine" in module.__dict__ or
            "TEST_ENGINE" in module.__dict__ or
            "sqlite_test_support" in module.__dict__
        )
        if uses_sqlite:
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


@pytest.fixture(scope="module", autouse=True)
def bootstrap_shared_sqlite(request) -> None:
    module = request.module
    uses_shared = (
        "TEST_ENGINE" in module.__dict__ or
        "sqlite_test_support" in module.__dict__
    )

    if uses_shared:
        import uuid
        from sqlalchemy import select
        import sqlite_test_support
        from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
        from migrations_engine.config import get_settings
        from migrations_engine.db.models import User
        from migrations_engine.auth.passwords import hash_password

        # Create all tables on TEST_ENGINE
        Base.metadata.create_all(bind=TEST_ENGINE)

        settings = get_settings()
        if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
            pytest.skip("bootstrap credentials not configured")

        with SessionLocal() as db:
            admin_email = settings.bootstrap_admin_email.strip().lower()
            if db.scalar(select(User).where(User.email == admin_email)) is None:
                db.add(
                    User(
                        user_id=str(uuid.uuid4()),
                        email=admin_email,
                        display_name=settings.bootstrap_admin_display_name,
                        password_hash=hash_password(settings.bootstrap_admin_password),
                        role="central_team",
                        status="active",
                    )
                )
                db.commit()
