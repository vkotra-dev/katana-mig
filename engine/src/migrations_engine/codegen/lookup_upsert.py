from __future__ import annotations


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _ref_table_name(lookup_name: str) -> str:
    if lookup_name.endswith("_ref"):
        return lookup_name
    return f"{lookup_name}_ref"


def _values_clause(value_map: dict[str, str]) -> str:
    rows = [f"('{_escape(source)}', '{_escape(destination)}')" for source, destination in sorted(value_map.items())]
    return ", ".join(rows)


def _table_ddl(ref_table: str, *, use_if_not_exists: bool) -> str:
    if use_if_not_exists:
        return (
            f"CREATE TABLE IF NOT EXISTS {ref_table} (\n"
            f"    source_val VARCHAR(255) PRIMARY KEY,\n"
            f"    dest_val VARCHAR(255) NOT NULL\n"
            f");"
        )

    return (
        f"IF OBJECT_ID('{ref_table}', 'U') IS NULL\n"
        f"CREATE TABLE {ref_table} (\n"
        f"    source_val NVARCHAR(255) PRIMARY KEY,\n"
        f"    dest_val NVARCHAR(255) NOT NULL\n"
        f");"
    )


def _pg_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = _table_ddl(ref_table, use_if_not_exists=True)
    if not value_map:
        return f"{header}\n{ddl}"

    values = _values_clause(value_map)
    dml = (
        f"INSERT INTO {ref_table} (source_val, dest_val)\n"
        f"VALUES {values}\n"
        f"ON CONFLICT (source_val) DO UPDATE SET dest_val = EXCLUDED.dest_val;"
    )
    return f"{header}\n{ddl}\n{dml}"


def _mysql_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = _table_ddl(ref_table, use_if_not_exists=True)
    if not value_map:
        return f"{header}\n{ddl}"

    values = _values_clause(value_map)
    dml = (
        f"INSERT INTO {ref_table} (source_val, dest_val)\n"
        f"VALUES {values}\n"
        f"ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val);"
    )
    return f"{header}\n{ddl}\n{dml}"


def _mssql_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = _table_ddl(ref_table, use_if_not_exists=False)
    if not value_map:
        return f"{header}\n{ddl}"

    values = _values_clause(value_map)
    merge = (
        f"MERGE {ref_table} AS target\n"
        f"USING (VALUES {values}) AS source (source_val, dest_val)\n"
        f"ON target.source_val = source.source_val\n"
        f"WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val\n"
        f"WHEN NOT MATCHED THEN INSERT (source_val, dest_val)\n"
        f"VALUES (source.source_val, source.dest_val);"
    )
    return f"{header}\n{ddl}\n\n{merge}"


def _oracle_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = _table_ddl(ref_table, use_if_not_exists=False)
    if not value_map:
        return f"{header}\n{ddl}"

    values = _values_clause(value_map)
    merge = (
        f"MERGE {ref_table} AS target\n"
        f"USING (VALUES {values}) AS source (source_val, dest_val)\n"
        f"ON target.source_val = source.source_val\n"
        f"WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val\n"
        f"WHEN NOT MATCHED THEN INSERT (source_val, dest_val)\n"
        f"VALUES (source.source_val, source.dest_val);"
    )
    return f"{header}\n{ddl}\n\n{merge}"


def generate_lookup_upsert_sql(
    lookup_name: str,
    value_map: dict[str, str],
    target_db_engine: str | None,
) -> str:
    ref_table = _ref_table_name(lookup_name)
    engine = (target_db_engine or "").lower()

    if engine == "mysql":
        return _mysql_sql(lookup_name, ref_table, value_map)
    if engine == "mssql":
        return _mssql_sql(lookup_name, ref_table, value_map)
    if engine == "oracle":
        return _oracle_sql(lookup_name, ref_table, value_map)
    return _pg_sql(lookup_name, ref_table, value_map)
