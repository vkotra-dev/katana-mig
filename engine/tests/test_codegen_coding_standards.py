from migrations_engine.codegen.coding_standards import render_coding_standards_template


def test_mssql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="stg", destination_schema="cxp"
    )
    assert '"cxp" schema' in result
    assert '"stg" schema' in result
    assert "Database Engine Conventions (mssql)" in result
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result
    assert "General Best Practices" in result


def test_sqlserver_alias_resolves_to_mssql_block():
    result = render_coding_standards_template(
        db_engine="sqlserver", staging_schema="stg", destination_schema="cxp"
    )
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result


def test_postgresql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="stg", destination_schema="cxp"
    )
    assert "PL/pgSQL using dollar-quoting" in result
    assert "SET XACT_ABORT" not in result


def test_mysql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="stg", destination_schema="cxp"
    )
    assert "DELIMITER declarations" in result


def test_oracle_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="stg", destination_schema="cxp"
    )
    assert "Oracle length limits" in result


def test_unrecognized_engine_falls_back_to_shared_sections_only():
    result = render_coding_standards_template(
        db_engine="sqlite", staging_schema="stg", destination_schema="cxp"
    )
    assert "Database Engine Conventions (sqlite)" in result
    assert "General Best Practices" in result
    assert "SET XACT_ABORT" not in result
    assert "PL/pgSQL" not in result


def test_missing_config_falls_back_to_default_placeholder_names():
    result = render_coding_standards_template(
        db_engine=None, staging_schema=None, destination_schema=None
    )
    assert '"destination" schema' in result
    assert '"staging" schema' in result
    assert "Database Engine Conventions (target database)" in result
