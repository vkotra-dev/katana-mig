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
            uses_sqlite = True
            if uses_sqlite:
                engine = sqlite_test_support.TEST_ENGINE
                module.__uses_shared_sqlite__ = True
        except ImportError:
            pass

    if engine is not None:
        module.__uses_sqlite__ = True
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
def bootstrap_sqlite_database(request) -> None:
    module = request.module
    if not getattr(module, "__uses_sqlite__", False):
        return

    # Only bootstrap if the module does not define its own custom setup fixture
    has_own_setup = (
        "_setup_sqlite_db" in module.__dict__ or
        "_seed_users" in module.__dict__
    )

    if not has_own_setup:
        engine = None
        if getattr(module, "__uses_shared_sqlite__", False):
            try:
                import sqlite_test_support
                engine = sqlite_test_support.TEST_ENGINE
            except ImportError:
                pass
        else:
            engine = getattr(module, "_sqlite_engine", None)

        if engine is not None:
            import uuid
            from sqlalchemy import select
            from sqlalchemy.orm import sessionmaker
            from migrations_engine.config import get_settings
            from migrations_engine.db.models import User
            from migrations_engine.auth.passwords import hash_password
            from migrations_engine.db.base import Base

            # Create all tables on this engine
            Base.metadata.create_all(bind=engine)

            settings = get_settings()
            if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
                pytest.skip("bootstrap credentials not configured")

            local_sessionmaker = sessionmaker(bind=engine)
            with local_sessionmaker() as db:
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
                if db.scalar(select(User).where(User.email == "pm@example.com")) is None:
                    db.add(
                        User(
                            user_id=str(uuid.uuid4()),
                            email="pm@example.com",
                            display_name="Project Manager",
                            password_hash=hash_password("pm-password"),
                            role="pm",
                            status="active",
                        )
                    )
                if db.scalar(select(User).where(User.email == "admin@example.com")) is None:
                    db.add(
                        User(
                            user_id=str(uuid.uuid4()),
                            email="admin@example.com",
                            display_name="Manager",
                            password_hash=hash_password("admin-password"),
                            role="admin",
                            status="active",
                        )
                    )
                db.commit()

from sqlalchemy import event
from sqlalchemy.orm import Session
from migrations_engine.db.models import ProjectRegistry, ProjectMembership, User

@event.listens_for(Session, "before_flush")
def auto_add_test_membership(session, flush_context, instances):
    new_projects = [obj for obj in session.new if isinstance(obj, ProjectRegistry)]
    if not new_projects:
        return
    from migrations_engine.config import get_settings
    settings = get_settings()
    admin_email = settings.bootstrap_admin_email.strip().lower()
    user = session.query(User).filter(User.email == admin_email).first()
    if not user:
        return
    for proj in new_projects:
        exists_in_session = any(
            isinstance(obj, ProjectMembership) and
            obj.project_id == proj.project_id and
            obj.user_id == user.user_id
            for obj in session.new
        )
        if not exists_in_session:
            exists = session.query(ProjectMembership).filter(
                ProjectMembership.project_id == proj.project_id,
                ProjectMembership.user_id == user.user_id
            ).first()
            if not exists:
                session.add(
                    ProjectMembership(
                        project_id=proj.project_id,
                        user_id=user.user_id
                    )
                )
