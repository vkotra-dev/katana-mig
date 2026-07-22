from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL


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
