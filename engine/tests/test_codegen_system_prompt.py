from migrations_engine.codegen.service import _build_system_prompt
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
    assert "mig_upsert_log" not in result
    assert "Custom standards go here." in result
