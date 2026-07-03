from __future__ import annotations

from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql


VALUE_MAP = {"DB": "Database Account", "SAV": "Savings Account"}


def test_postgresql_generates_on_conflict() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "postgresql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON CONFLICT (source_val) DO UPDATE SET dest_val = EXCLUDED.dest_val" in sql
    assert "'DB'" in sql
    assert "'Savings Account'" in sql


def test_mysql_generates_on_duplicate_key() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mysql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val)" in sql


def test_mssql_generates_merge() -> None:
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mssql")
    assert "IF OBJECT_ID('account_type_ref', 'U') IS NULL" in sql
    assert "MERGE account_type_ref AS target" in sql
    assert "WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val" in sql
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
