from unittest.mock import MagicMock, patch

from migrations_engine.codegen.service import _build_lookup_tables, _build_system_prompt
from migrations_engine.api.schemas import MigrationProjectConfig
from migrations_engine.db.models import ProjectDefinition


def test_build_system_prompt_no_longer_appends_run_logging_requirements():
    project_definition = ProjectDefinition(
        definition_id="def-1",
        project_id="proj-1",
        name="Test",
        status="active",
        codegen_instructions="Custom standards go here.",
    )
    config = MigrationProjectConfig(target_db_engine="postgresql", staging_schema="stg")

    result = _build_system_prompt(
        project_config=config,
        destination_object_name="customer",
        project_definition=project_definition,
    )

    assert "RUN LOGGING REQUIREMENTS" not in result
    # mig_upsert_log is now present only in lookup resolution rules (error logging guidance)
    assert "mig_upsert_log" in result
    assert "Custom standards go here." in result


def test_build_lookup_tables_builds_structured_lookup_info():
    mock_db = MagicMock()
    mock_snapshot = MagicMock()
    mock_snapshot.value_map = {"APPROVED": "3", "REJECTED": "1", "PENDING": "2"}
    mock_snapshot.lookup_snapshot_version = "snap-123"

    mock_mapping = MagicMock()
    mock_mapping.field_bindings = [
        {"source_field": "status", "destination_field": "status_code", "lookup_name": "status_code", "destination_data_type": "INT"},
    ]

    with patch(
        "migrations_engine.codegen.service.select_latest_approved_lookup_snapshot",
        return_value=mock_snapshot,
    ):
        result = _build_lookup_tables(mock_db, project_id="proj-1", mapping_snapshot=mock_mapping)

    assert len(result) == 1
    entry = result[0]
    assert entry["lookup_name"] == "status_code"
    assert entry["ref_table_name"] == "status_code_ref"
    assert entry["snapshot_version"] == "snap-123"
    assert len(entry["sample_mappings"]) == 3
    assert entry["sample_mappings"][0] == {"source_val": "APPROVED", "dest_val": "3"}
    assert entry["columns"] == ["source_val VARCHAR(255) PRIMARY KEY", "dest_val VARCHAR(255) NOT NULL"]


def test_build_lookup_tables_skips_missing_snapshots():
    from migrations_engine.mapping.exceptions import SnapshotNotFoundError

    mock_db = MagicMock()
    mock_mapping = MagicMock()
    mock_mapping.field_bindings = [
        {"source_field": "status", "destination_field": "status_code", "lookup_name": "missing_lookup", "destination_data_type": "INT"},
    ]

    with patch(
        "migrations_engine.codegen.service.select_latest_approved_lookup_snapshot",
        side_effect=SnapshotNotFoundError("not found"),
    ):
        result = _build_lookup_tables(mock_db, project_id="proj-1", mapping_snapshot=mock_mapping)

    assert result == []
