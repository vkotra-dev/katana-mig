from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_ddl=ddl, lookup_ddl=[], seed_data=[], stored_procedures=[], views=views or [])


def test_log_table_prepended_when_staging_schema_set():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="mssql")
    assert "mig_upsert_log" in bundle
    assert bundle.index("mig_upsert_log") < bundle.index("CREATE TABLE [stg].[t]")


def test_log_table_omitted_when_staging_schema_none():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema=None, db_engine="mssql")
    assert "mig_upsert_log" not in bundle


def test_if_not_exists_guard_present():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="mssql")
    assert "IF OBJECT_ID" in bundle
    assert "IS NULL" in bundle


def test_unset_engine_defaults_to_mssql_ddl():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine=None)
    assert "IF OBJECT_ID" in bundle
    assert "IDENTITY(1,1)" in bundle


def test_postgresql_uses_create_table_if_not_exists():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="postgresql")
    assert "CREATE TABLE IF NOT EXISTS stg.mig_upsert_log" in bundle
    assert "BIGSERIAL" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_mysql_uses_create_table_if_not_exists():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="mysql")
    assert "CREATE TABLE IF NOT EXISTS stg.mig_upsert_log" in bundle
    assert "AUTO_INCREMENT" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_oracle_uses_execute_immediate_guard():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="oracle")
    assert "EXECUTE IMMEDIATE" in bundle
    assert "GENERATED ALWAYS AS IDENTITY" in bundle
    assert "ORA-00955" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_sqlserver_alias_resolves_to_mssql_ddl():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="sqlserver")
    assert "IF OBJECT_ID" in bundle
