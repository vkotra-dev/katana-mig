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
    assert "oc_stag" not in result
    assert "[_row_num] BIGINT IDENTITY(1,1) NOT NULL" in result


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


def test_postgresql_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "gen_random_uuid()" in result
    assert "stg.mig_upsert_log" in result
    assert "xmax = 0" in result


def test_mysql_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "ROW_COUNT()" in result
    assert "stg.mig_upsert_log" in result
    assert "row-by-row" in result


def test_oracle_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "BULK COLLECT INTO" in result
    assert "stg.mig_upsert_log" in result
    assert "RETURNING" in result
    assert "does not support RETURNING" in result


def test_merge_fields_substitute_inside_engine_specific_section():
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="my_custom_stg", destination_schema="my_custom_dest"
    )
    assert "$stg" not in result
    assert "$dest" not in result
    assert "my_custom_stg" in result
    assert "my_custom_dest" in result


# ── New tests for 001ev: codegen logging prompt extraction ──────────────────


def test_mssql_logging_block_comes_from_separate_file():
    """General block (from codegen_coding_standards.yaml) and logging block
    (from codegen_logging_standards.yaml) are both present in mssql output.
    mssql is the only platform NOT covered by the three existing mig_upsert_log
    assertions, so this is the primary regression guard for the split."""
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="stg", destination_schema="cxp"
    )
    # General block still present
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result
    # Logging block from new file is appended — mssql uses bracketed schema notation
    assert "mig_upsert_log" in result
    assert "OUTPUT" in result
    # Shared footer still appended last
    assert "General Best Practices" in result


def test_postgresql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for postgresql."""
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_mssql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for mssql."""
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="my_stg", destination_schema="my_dest"
    )
    # mssql uses bracketed notation: [my_stg].[mig_upsert_log]
    assert "[my_stg].[mig_upsert_log]" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_oracle_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for oracle."""
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_mysql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for mysql."""
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_unknown_engine_has_no_logging_block_and_does_not_error():
    """An unrecognized engine key that has no entry in codegen_logging_standards.yaml
    must not raise; it silently omits the logging block."""
    result = render_coding_standards_template(
        db_engine="sqlite", staging_schema="stg", destination_schema="dest"
    )
    # Shared content still present
    assert "General Best Practices" in result
    # No mig_upsert_log injected for unknown engine
    assert "mig_upsert_log" not in result
