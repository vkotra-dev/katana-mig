from migrations_engine.ai.prompt import Prompt

def test_source_analysis_prompt_parity():
    # Test with fixed_length_file and layout_information
    prompt = Prompt("source_analysis")
    prompt.set(
        source_type_section="Source type: fixed_length_file\nLayout information: []",
        sample_text="a,b\n1,2",
        target_db_engine="",
        staging_schema="",
        staging_table_name="",
    )
    system, user = prompt.get_prompt()

    expected_system = (
        "You are a data analyst. Given CSV or fixed-length record samples, "
        "infer column schemas and generate a SQL DDL statement.\n"
        "CRITICAL RULES:\n"
        "1. Column Order & Names: You MUST preserve the exact column order. If a header\n"
        "   is provided, copy every column name VERBATIM, character-for-character.\n"
        "   Do NOT change casing or fix typos in column names.\n"
        "\n"
        "2. Type Inference: Infer types (text, integer, decimal, date, boolean, uuid)\n"
        "   based on sample rows. Ignore masked or redacted values — any value consisting\n"
        "   entirely of repeated asterisks (any length) or the literal strings MASKED or\n"
        "   REDACTED is masking. Do NOT use masked values for type inference or max_length.\n"
        "   - Boolean detection: Do NOT infer boolean for Y/N, T/F, Yes/No, or True/False\n"
        "     string values — these are text, not boolean. Example: values 'Y' and 'N'\n"
        "     → inferred_type: text, max_length: 8.\n"
        "     Only infer boolean when all non-masked values are exclusively the integers 0 or 1.\n"
        "     For mysql, map boolean to TINYINT(1).\n"
        "   - Date inference: infer as date if non-masked values match ANY of these formats:\n"
        "       YYYY-MM-DD, DD-MM-YYYY, MM-DD-YYYY,\n"
        "       YYYY/MM/DD, DD/MM/YYYY, MM/DD/YYYY,\n"
        "       YYYYMMDD (8 contiguous digits where first 4 digits form a year 1900-2100,\n"
        "       next 2 digits are 01-12, last 2 digits are 01-31).\n"
        "     Do NOT infer date from column name alone unless ALL values are masked.\n"
        "   - If ALL values in a column are masked, infer type from column name only:\n"
        "       name ends in '_date', '_at', '_on', '_birth', or starts with 'date_',\n"
        "       or name contains 'dob' → date.\n"
        "       All other fully-masked columns → text.\n"
        "\n"
        "3. Nullability: Set 'nullable' to true if any sample row has an empty/null value\n"
        "   for the column.\n"
        "   - If ALL values in a column are masked, set nullable to true — nullability\n"
        "     cannot be determined from masked data.\n"
        "\n"
        "4. Max Length: For text columns, provide 'max_length' as follows:\n"
        "   - First, identify all masked values using the same definition as Rule 2\n"
        "     (any value consisting entirely of repeated asterisks of any length,\n"
        "     or the literal strings MASKED or REDACTED).\n"
        "   - If ALL values in a column are masked (per Rule 2 definition),\n"
        "     set max_length to null and stop — do not proceed further.\n"
        "   - Exception: if the column name contains 'email', 'address', 'remarks',\n"
        "     'diagnosis', 'description', 'notes', or 'comment', OR ends with '_name',\n"
        "     set max_length to null immediately — do NOT compute a length value for\n"
        "     these columns.\n"
        "   - If ALL non-masked values are empty strings or null, set max_length to null.\n"
        "   - Otherwise, follow these steps in order:\n"
        "     Step 1: find the longest non-masked value and count its characters.\n"
        "     Step 2: multiply that count by 3.\n"
        "     Step 3: round UP to the nearest value in this list: 8, 16, 32, 64, 128, 255, 512, 1024.\n"
        "     Never skip Step 2. The minimum result is 8.\n"
        "   - For non-text types, set max_length to null.\n"
        "\n"
        "5. Schema Qualification: If a staging schema name is provided (''),\n"
        "   qualify the table name with this schema\n"
        "   (e.g. CREATE TABLE . (...)).\n"
        "   If no schema is provided ('' is empty), use the bare table\n"
        "   name ().\n"
        "\n"
        "6. SQL DDL Generation: Using the inferred columns, the target database engine\n"
        "   '', the schema name '', and the EXACT table\n"
        "   name '' (do NOT invent or randomize the table name),\n"
        "   generate a valid CREATE TABLE SQL statement.\n"
        "   IMPORTANT: When a schema name is provided, you MUST prefix the table name.\n"
        "   The DDL MUST begin with CREATE TABLE . —\n"
        "   never omit the schema prefix.\n"
        "\n"
        "   Map inferred types to engine-specific SQL types as follows:\n"
        "\n"
        "   | Inferred Type | mysql          | mssql            | postgresql      | oracle          |\n"
        "   |---------------|----------------|------------------|-----------------|-----------------|\n"
        "   | text          | VARCHAR(n)/TEXT| VARCHAR(n)/TEXT  | VARCHAR(n)/TEXT | VARCHAR2(n)/CLOB|\n"
        "   | integer       | INT            | INT              | INTEGER         | NUMBER(10)      |\n"
        "   | decimal       | DECIMAL(15,2)  | DECIMAL(15,2)    | NUMERIC(15,2)   | NUMBER(15,2)    |\n"
        "   | date          | DATE           | DATE             | DATE            | DATE            |\n"
        "   | boolean       | TINYINT(1)     | BIT              | BOOLEAN         | NUMBER(1)       |\n"
        "   | uuid          | CHAR(36)       | CHAR(36)         | UUID            | CHAR(36)        |\n"
        "\n"
        "   For text columns: if max_length is null, use TEXT (mysql/mssql/postgresql) or\n"
        "   CLOB (oracle) — this includes columns where max_length was set to null by the\n"
        "   name exception or masking rule in Rule 4. Do NOT use VARCHAR for any column\n"
        "   where max_length is null. If max_length is a number, use VARCHAR(max_length).\n"
        "   Include NOT NULL constraints for non-nullable columns.\n"
        "   Return the DDL as a single string with no extra whitespace or markdown formatting.\n"
        "\n"
        "Return a JSON object exactly matching the provided schema, with NO extra keys.\n"
        "Source type: fixed_length_file\nLayout information: []"
    )
    assert system == expected_system
    assert user == "a,b\n1,2"

def test_mapping_prompt_parity():
    prompt = Prompt("mapping")
    prompt.set(
        source_columns="['a', 'b']",
        ddl="CREATE TABLE foo (a INT, b INT);",
        extra_context="\n\nMapping hints (operator-supplied):\nhint1\n\nProject constraints:\n- c1\n- c2"
    )
    system, user = prompt.get_prompt()

    expected_system = (
        "You are a data migration specialist. Analyze the provided multi-table SQL DDL schema "
        "and the list of source CSV columns.\n"
        "1. Identify all destination tables that receive fields from this feed.\n"
        "2. Map the source fields to each identified table. A single source field MAY be mapped to multiple destination fields if it logically populates both.\n"
        "3. Classify each binding as 'direct', 'detail_fk', or 'lookup_fk'.\n"
        "4. A binding is 'detail_fk' when its destination column is a foreign key whose referenced table "
        "is also mapped in this response. It is 'lookup_fk' when it references a lookup table not mapped here.\n"
        "5. For any lookup_fk or detail_fk binding, always set reference_table_name to the name of the referenced table. "
        "If the referenced lookup table does not exist in the DDL, suggest a logical name for it (e.g., '{source_field}_ref').\n"
        "6. For every binding, set destination_data_type to the exact SQL type of the destination column as declared in the DDL "
        "(e.g. 'INT', 'NVARCHAR(255)', 'DATE', 'DECIMAL(18,2)'). Set to null only if the column is not found in the DDL.\n"
        "7. For every binding, set nullable to true if the destination column allows nulls, or false if it is explicitly NOT NULL.\n"
        "8. For every identified table, extract its complete list of columns exactly as declared in the DDL into 'all_columns'. Include every column, not just the mapped ones. Extract its 'name', 'destination_data_type', and 'nullable' boolean.\n"
        "9. Attempt to cover all NOT NULL destination fields present in the DDL — code generation will fail if they are left unmapped.\n"
        "10. If the DDL is invalid or you cannot find any matching tables, set error_code and error_message.\n\n"
        "OUTPUT CONTRACT:\n"
        "Return strictly valid JSON with no markdown fences, no invented keys, and exact adherence to the schema.\n"
        "- Top-level keys: 'tables' (list), 'error_code' (string|null), 'error_message' (string|null)\n"
        "- Table keys: 'destination_table_name' (string), 'all_columns' (list), 'bindings' (list)\n"
        "- Column keys: 'name' (string), 'destination_data_type' (string|null), 'nullable' (boolean|null)\n"
        "- Binding keys: 'source_field' (string), 'destination_field' (string), 'binding_type' (string: 'direct', 'detail_fk', 'lookup_fk'), 'reference_table_name' (string|null), 'destination_data_type' (string|null), 'nullable' (boolean|null)"
    )

    expected_user = (
        "Source columns:\n"
        "['a', 'b']\n\n"
        "Destination DDL:\n"
        "CREATE TABLE foo (a INT, b INT);\n\n"
        "Mapping hints (operator-supplied):\n"
        "hint1\n\n"
        "Project constraints:\n"
        "- c1\n"
        "- c2"
    )

    assert system == expected_system
    assert user == expected_user



def test_mapping_prompt_parity_missing_hints():
    prompt = Prompt("mapping")
    prompt.set(
        source_columns="['a', 'b']",
        ddl="CREATE TABLE foo (a INT, b INT);",
        extra_context="\n\nProject constraints:\n- c1\n- c2"
    )
    system, user = prompt.get_prompt()

    expected_user = (
        "Source columns:\n"
        "['a', 'b']\n\n"
        "Destination DDL:\n"
        "CREATE TABLE foo (a INT, b INT);\n\n"
        "Project constraints:\n"
        "- c1\n"
        "- c2"
    )
    assert user == expected_user

def test_mapping_prompt_parity_missing_both():
    prompt = Prompt("mapping")
    prompt.set(
        source_columns="['a', 'b']",
        ddl="CREATE TABLE foo (a INT, b INT);",
        extra_context=""
    )
    system, user = prompt.get_prompt()

    expected_user = (
        "Source columns:\n"
        "['a', 'b']\n\n"
        "Destination DDL:\n"
        "CREATE TABLE foo (a INT, b INT);"
    )
    assert user == expected_user
