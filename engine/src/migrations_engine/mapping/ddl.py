from __future__ import annotations

import re

_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[\w$]+\.)?\"?(?P<table>[\w$]+)\"?",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(r'^\s*["`]?(?P<name>[A-Za-z_][\w$]*)["`]?\s+[A-Za-z]')
_CONSTRAINT_PREFIXES = ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")


def parse_all_ddl_tables(ddl: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    current_table: str | None = None
    current_columns: list[str] = []
    
    for line in ddl.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("/*"):
            continue
            
        table_match = _TABLE_RE.search(stripped)
        if table_match:
            if current_table and current_columns:
                tables[current_table] = current_columns
            current_table = table_match.group("table")
            current_columns = []
            continue
            
        if current_table:
            if stripped.upper().startswith(_CONSTRAINT_PREFIXES):
                continue
            if stripped.startswith(")") or stripped.startswith(";"):
                tables[current_table] = current_columns
                current_table = None
                current_columns = []
                continue
                
            column_match = _COLUMN_RE.match(stripped)
            if column_match:
                col_name = column_match.group("name")
                if col_name not in current_columns:
                    current_columns.append(col_name)
                    
    if current_table and current_columns:
        tables[current_table] = current_columns
        
    return tables


def parse_ddl(ddl: str) -> tuple[str, list[str]]:
    lines = [line.rstrip() for line in ddl.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    table_match = _TABLE_RE.search(lines[0])
    if table_match is None:
        for line in lines:
            table_match = _TABLE_RE.search(line)
            if table_match is not None:
                break
    if table_match is None:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    columns: list[str] = []
    for line in lines[1:]:
        stripped = line.strip().rstrip(",")
        if not stripped or stripped.startswith(")") or stripped.startswith("--"):
            continue
        if stripped.upper().startswith(_CONSTRAINT_PREFIXES):
            continue
        column_match = _COLUMN_RE.match(line)
        if column_match is None:
            continue
        column_name = column_match.group("name")
        if column_name not in columns:
            columns.append(column_name)

    if not columns:
        raise ValueError("Destination schema DDL has no parseable column definitions.")
    return table_match.group("table"), columns
