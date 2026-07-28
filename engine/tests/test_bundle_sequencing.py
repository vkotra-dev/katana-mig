from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
from migrations_engine.db.models import (
    Base,
    CodeGenerationArtifact,
    Feed,
    LookupSnapshot,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.api.schemas import FiberActionRequest
from migrations_engine.codegen import service as codegen_service_module
from migrations_engine.management.fibers import trigger_fiber
from sqlite_test_support import SessionLocal, TEST_ENGINE


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)


VALUE_MAP = {"DB": "Database Account", "SAV": "Savings Account"}


def _new_project(db, *, domain_config: dict | None = None) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Test Project",
            domain_config=domain_config or {},
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Test Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.flush()
    return project_id


def _new_user(db) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        password_hash="hash",
        role="central_team",
        status="active",
    )
    db.add(user)
    db.flush()
    return user


def _new_lookup_fiber(
    db,
    *,
    project_id: str,
    feed_id: str,
    fiber_key: str,
    status: str = "business_approved",
    source: str = "manual",
) -> ProjectFiber:
    fiber = ProjectFiber(
        fiber_id=str(uuid.uuid4()),
        feed_id=feed_id,
        project_id=project_id,
        fiber_type="lookup",
        fiber_key=fiber_key,
        status=status,
        source=source,
    )
    db.add(fiber)
    db.flush()
    return fiber


def _new_domain_fiber(
    db,
    *,
    project_id: str,
    feed_id: str,
    fiber_key: str,
    status: str = "business_approved",
    source: str = "manual",
) -> ProjectFiber:
    fiber = ProjectFiber(
        fiber_id=str(uuid.uuid4()),
        feed_id=feed_id,
        project_id=project_id,
        fiber_type="domain_object",
        fiber_key=fiber_key,
        status=status,
        source=source,
    )
    db.add(fiber)
    db.flush()
    return fiber


def _new_lookup_snapshot(
    db,
    *,
    project_id: str,
    lookup_name: str,
    value_map: dict[str, str],
) -> LookupSnapshot:
    snapshot = LookupSnapshot(
        lookup_snapshot_id=str(uuid.uuid4()),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=str(uuid.uuid4()),
        value_map=value_map,
        status="approved",
        approved_at=datetime.now(UTC),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _seed_lookup_project(
    db,
    *,
    domain_config: dict | None = None,
    lookup_name: str = "acct_type",
) -> tuple[str, str, User]:
    project_id = _new_project(db, domain_config=domain_config)
    feed_id = str(uuid.uuid4())
    db.add(
        Feed(
            source_definition_id=feed_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            destination_object_references=[lookup_name],
            source_details={"label": "Lookup Feed", "encoding": "utf-8"},
            status="active",
        )
    )
    actor = _new_user(db)
    return project_id, feed_id, actor


def test_postgresql_generates_on_conflict() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "postgresql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON CONFLICT (source_val) DO UPDATE SET id = EXCLUDED.id" in sql
    assert "'DB'" in sql
    assert "'Savings Account'" in sql


def test_mysql_generates_on_duplicate_key() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mysql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON DUPLICATE KEY UPDATE id = VALUES(id)" in sql


def test_mssql_generates_merge() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mssql")
    assert "IF OBJECT_ID('account_type_ref', 'U') IS NULL" in sql
    assert "MERGE account_type_ref AS target" in sql
    assert "WHEN MATCHED THEN UPDATE SET target.id = source.id" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql


def test_oracle_generates_merge() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "oracle")
    assert "MERGE" in sql
    assert "WHEN MATCHED THEN UPDATE SET" in sql


def test_none_engine_defaults_to_pg_syntax() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, None)
    assert "ON CONFLICT" in sql


def test_unknown_engine_defaults_to_pg_syntax() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "redshift")
    assert "ON CONFLICT" in sql


def test_empty_value_map_omits_upsert_dml() -> None:
    sql = generate_lookup_upsert_sql("account_type", {}, "postgresql")
    assert "account_type_ref" in sql
    assert "ON CONFLICT" not in sql


def test_single_quotes_in_values_are_escaped() -> None:
    sql = generate_lookup_upsert_sql("test_lookup", {"O'Brien": "John O'Brien"}, "postgresql")
    assert "O''Brien" in sql


def test_ref_table_name_has_no_double_suffix() -> None:
    sql = generate_lookup_upsert_sql("product_type", VALUE_MAP, "postgresql")
    assert "product_type_ref" in sql
    assert "product_type_ref_ref" not in sql


def test_sql_includes_comment_header() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "postgresql")
    assert "-- Lookup reference table: account_type" in sql


def test_values_sorted_for_deterministic_output() -> None:
    sql_a = generate_lookup_upsert_sql("t", {"Z": "z", "A": "a"}, "postgresql")
    sql_b = generate_lookup_upsert_sql("t", {"A": "a", "Z": "z"}, "postgresql")
    assert sql_a == sql_b


def test_trigger_fiber_lookup_creates_active_artifact() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(db, project_id=project_id, lookup_name="acct_type", value_map={"A": "Alpha", "B": "Beta"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="acct_type")
        db.commit()

        result = trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    assert result.status == "codegen_complete"

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_acct_type",
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None


def test_trigger_fiber_lookup_destination_name_has_0000_prefix() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(db, project_id=project_id, lookup_name="prod_type", value_map={"X": "Y"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="prod_type")
        db.commit()

        trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None
    assert artifact.destination_object_name == "0000_prod_type"


def test_trigger_fiber_lookup_sets_output_sql_with_pg_syntax() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(db, project_id=project_id, lookup_name="cust_type", value_map={"P": "Premium"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="cust_type")
        db.commit()

        result = trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    assert result.output_sql is not None
    assert "cust_type_ref" in result.output_sql
    assert "ON CONFLICT" in result.output_sql


def test_trigger_fiber_lookup_supersedes_previous_artifact() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(db, project_id=project_id, lookup_name="sup_type", value_map={"A": "Alpha"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="sup_type")
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_sup_type",
                sql_bundle="-- old SQL",
                status="active",
            )
        )
        db.commit()

        trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    with SessionLocal() as db:
        active = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                    CodeGenerationArtifact.destination_object_name == "0000_sup_type",
                    CodeGenerationArtifact.status == "active",
                )
            )
        )
        superseded = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                    CodeGenerationArtifact.destination_object_name == "0000_sup_type",
                    CodeGenerationArtifact.status == "superseded",
                )
            )
        )
    assert len(active) == 1
    assert len(superseded) == 1
    assert "old SQL" in (superseded[0].sql_bundle or "")


def test_trigger_fiber_lookup_skips_artifact_when_no_snapshot() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="missing_type")
        db.commit()

        result = trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    assert result.status == "operator_triggered"

    with SessionLocal() as db:
        artifacts = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                )
            )
        )
    assert artifacts == []


def test_trigger_fiber_domain_object_does_not_create_artifact() -> None:
    with SessionLocal() as db:
        project_id = _new_project(db)
        feed_id = str(uuid.uuid4())
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                status="active",
            )
        )
        actor = _new_user(db)
        fiber = _new_domain_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="customers")
        db.commit()

        result = trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    assert result.status == "operator_triggered"

    with SessionLocal() as db:
        artifacts = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                )
            )
        )
    assert artifacts == []


def test_trigger_fiber_mssql_creates_merge_artifact() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "mssql"})
        _new_lookup_snapshot(db, project_id=project_id, lookup_name="mssql_type", value_map={"A": "Alpha"})
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="mssql_type")
        db.commit()

        trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None
    assert "MERGE" in (artifact.sql_bundle or "")


def test_trigger_fiber_artifact_stores_snapshot_version() -> None:
    with SessionLocal() as db:
        project_id, feed_id, actor = _seed_lookup_project(db, domain_config={"target_db_engine": "postgresql"})
        snapshot = _new_lookup_snapshot(db, project_id=project_id, lookup_name="ver_type", value_map={"V": "Value"})
        snapshot_version = snapshot.lookup_snapshot_version
        fiber = _new_lookup_fiber(db, project_id=project_id, feed_id=feed_id, fiber_key="ver_type")
        db.commit()

        trigger_fiber(
            db,
            project_id=project_id,
            feed_id=feed_id,
            fiber_id=fiber.fiber_id,
            actor=actor,
            body=FiberActionRequest(),
        )

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_ver_type",
            )
        )
    assert artifact is not None
    assert artifact.lookup_snapshot_version == snapshot_version


class _FakeAnalysis:
    def __init__(self, sequence: list[str]) -> None:
        self.destination_object_sequence = sequence


def test_lookup_artifacts_placed_before_domain_when_schema_analysis_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "accounts"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_account_type",
                status="active",
                sql_bundle="-- UPSERT SQL",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="customers",
                status="active",
                sql_bundle="-- customers DDL",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="accounts",
                status="active",
                sql_bundle="-- accounts DDL",
            )
        )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 3
    assert result.sql_bundle.index("-- 0000_account_type") < result.sql_bundle.index("-- [01] customers")


def test_lookup_heading_has_no_nn_bracket_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_lookup_x",
                status="active",
                sql_bundle="-- SQL",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="customers",
                status="active",
                sql_bundle="-- DDL",
            )
        )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert "-- 0000_lookup_x" in result.sql_bundle
    lookup_idx = result.sql_bundle.index("-- 0000_lookup_x")
    assert "-- [" not in result.sql_bundle[:lookup_idx]
    assert "-- [01] customers" in result.sql_bundle


def test_domain_artifacts_numbered_independently_of_lookup_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "orders"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        for name in ("0000_type_a", "0000_type_b"):
            db.add(
                CodeGenerationArtifact(
                    codegen_artifact_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name=name,
                    status="active",
                    sql_bundle="-- UPSERT",
                )
            )
        for name in ("customers", "orders"):
            db.add(
                CodeGenerationArtifact(
                    codegen_artifact_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name=name,
                    status="active",
                    sql_bundle="-- DDL",
                )
            )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert "-- [01] customers" in result.sql_bundle
    assert "-- [02] orders" in result.sql_bundle
    assert "-- [03]" not in result.sql_bundle


def test_multiple_lookup_artifacts_sorted_alphabetically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_zone_type",
                status="active",
                sql_bundle="-- SQL zone",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_acct_type",
                status="active",
                sql_bundle="-- SQL acct",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="customers",
                status="active",
                sql_bundle="-- DDL",
            )
        )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert result.sql_bundle.index("0000_acct_type") < result.sql_bundle.index("0000_zone_type")
    assert result.sql_bundle.index("0000_zone_type") < result.sql_bundle.index("-- [01] customers")


def test_no_schema_analysis_all_artifacts_alphabetical_no_nn_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: None,
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_acct_type",
                status="active",
                sql_bundle="-- UPSERT",
            )
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="customers",
                status="active",
                sql_bundle="-- DDL",
            )
        )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert "-- [" not in result.sql_bundle
    assert result.sql_bundle.index("-- 0000_acct_type") < result.sql_bundle.index("-- customers")


def test_only_lookup_artifacts_no_domain_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis([]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="0000_acct_type",
                status="active",
                sql_bundle="-- UPSERT",
            )
        )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 1
    assert "-- 0000_acct_type" in result.sql_bundle
    assert "-- [" not in result.sql_bundle


def test_only_domain_artifacts_no_lookup_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "orders"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        for name in ("orders", "customers"):
            db.add(
                CodeGenerationArtifact(
                    codegen_artifact_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name=name,
                    status="active",
                    sql_bundle=f"-- {name} DDL",
                )
            )
        db.commit()
        result = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 2
    assert result.sql_bundle.index("-- [01] customers") < result.sql_bundle.index("-- [02] orders")


def test_generate_lookup_upsert_sql_handles_one_to_many_stacked_mappings() -> None:
    stacked_map = {"A": "ACTIVE", "B": "ACTIVE", "C": "BLOCKED"}

    pg_sql = generate_lookup_upsert_sql("status_code", stacked_map, "postgresql")
    assert "('A', 'ACTIVE')" in pg_sql
    assert "('B', 'ACTIVE')" in pg_sql
    assert "('C', 'BLOCKED')" in pg_sql
    assert "ON CONFLICT (source_val) DO UPDATE SET id = EXCLUDED.id;" in pg_sql

    mysql_sql = generate_lookup_upsert_sql("status_code", stacked_map, "mysql")
    assert "('A', 'ACTIVE')" in mysql_sql
    assert "('B', 'ACTIVE')" in mysql_sql
    assert "('C', 'BLOCKED')" in mysql_sql
    assert "ON DUPLICATE KEY UPDATE id = VALUES(id);" in mysql_sql

    mssql_sql = generate_lookup_upsert_sql("status_code", stacked_map, "mssql")
    assert "('A', 'ACTIVE')" in mssql_sql
    assert "('B', 'ACTIVE')" in mssql_sql
    assert "('C', 'BLOCKED')" in mssql_sql
    assert "MERGE status_code_ref AS target" in mssql_sql

    oracle_sql = generate_lookup_upsert_sql("status_code", stacked_map, "oracle")
    assert "('A', 'ACTIVE')" in oracle_sql
    assert "('B', 'ACTIVE')" in oracle_sql
    assert "('C', 'BLOCKED')" in oracle_sql
    assert "MERGE" in oracle_sql
    assert "WHEN MATCHED THEN UPDATE SET" in oracle_sql
