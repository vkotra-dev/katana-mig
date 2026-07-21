import pytest
from migrations_engine.mapping.ddl import parse_ddl, parse_all_ddl_tables


def test_parse_ddl():
    ddl = """
    CREATE TABLE IF NOT EXISTS "my_table" (
        id INT PRIMARY KEY,
        "name" VARCHAR(255),
        created_at TIMESTAMP,
        CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
    table_name, columns = parse_ddl(ddl)
    assert table_name == "my_table"
    assert columns == ["id", "name", "created_at"]


def test_parse_all_ddl_tables():
    ddl = """
    CREATE TABLE table1 (
        col1 INT,
        col2 TEXT
    );

    -- some comment
    CREATE TABLE public.table2 (
        "ID" INT,
        "DESC" VARCHAR
    );
    """
    tables = parse_all_ddl_tables(ddl)
    assert len(tables) == 2
    assert tables["table1"] == ["col1", "col2"]
    assert tables["table2"] == ["ID", "DESC"]

def test_parse_ddl_raises_on_invalid():
    with pytest.raises(ValueError, match="Could not parse table name"):
        parse_ddl("SELECT * FROM USERS;")

    with pytest.raises(ValueError, match="Destination schema DDL has no parseable column definitions"):
        parse_ddl("CREATE TABLE empty_table ();")
