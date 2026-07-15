from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL, _build_system_prompt
from migrations_engine.api.schemas import MigrationProjectConfig
from migrations_engine.db.models import ProjectDefinition


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_ddl=ddl, lookup_ddl=[], seed_data=[], stored_procedures=[], views=views or [])


def test_log_table_prepended_when_staging_schema_set():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "mig_upsert_log" in bundle
    assert bundle.index("mig_upsert_log") < bundle.index("CREATE TABLE [stg].[t]")


def test_log_table_omitted_when_staging_schema_none():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema=None)
    assert "mig_upsert_log" not in bundle


def test_if_not_exists_guard_present():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "IF OBJECT_ID" in bundle
    assert "IS NULL" in bundle


def test_system_prompt_includes_run_logging_block():
    config = MigrationProjectConfig(
        target_db_engine="mssql",
        staging_schema="oc_stag",
        destination_schema="dbo",
    )
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_claims",
        project_definition=ProjectDefinition(),
        run_ref="proj123_src456",
    )
    assert "RUN LOGGING REQUIREMENTS" in prompt
    assert "_row_num" in prompt
    assert "mig_upsert_log" in prompt
    assert "proj123_src456" in prompt
    assert "$action" in prompt


def test_system_prompt_run_ref_is_baked_in():
    config = MigrationProjectConfig(staging_schema="oc_stag")
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_master",
        project_definition=ProjectDefinition(),
        run_ref="myproject_myfeed",
    )
    assert "'myproject_myfeed'" in prompt
