from migrations_engine.ai.prompt import Prompt

def test_source_analysis_prompt_parity():
    # Test with fixed_length_file and layout_information
    prompt = Prompt("source_analysis")
    prompt.set(
        source_type_section="Source type: fixed_length_file\nLayout information: []",
        sample_text="a,b\n1,2"
    )
    system, user = prompt.get_prompt()
    
    expected_system = (
        "You are a data analyst. Given CSV or fixed-length record samples, "
        "infer column schemas and generate a SQL DDL statement.\n"
        "CRITICAL RULES:\n"
        "1. Column Order & Names: You MUST preserve the exact column order. "
        "If a header is provided, copy every column name VERBATIM, character-for-character. "
        "Do NOT change casing or fix typos in column names.\n"
        "2. Type Inference: Infer types (text, integer, decimal, date, boolean, uuid) based on sample rows. "
        "Ignore masked or redacted values (e.g. 'MASKED', '****') when inferring types.\n"
        "3. Nullability: Set 'nullable' to true if any sample row has an empty/null value for the column.\n"
        "4. Max Length: For text columns, provide 'max_length' as the maximum character count found. "
        "For other types, set max_length to null.\n"
        "5. SQL DDL Generation: Using the inferred columns and the target database engine '', "
        "generate a valid CREATE TABLE SQL statement. Use appropriate SQL data types for the target engine (e.g. VARCHAR for text, INT for integer, DECIMAL(p,s) for decimal, DATE for date, BOOLEAN for boolean, CHAR(36) for uuid). Include NOT NULL constraints for non-nullable columns. Return the DDL as a single string with no extra whitespace or markdown formatting.\n"
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
    # We will adjust expected string to exactly match what was there.
    # The old user string was: f"Source columns:\n{source_columns!r}\n\nDestination DDL:\n{ddl}" + "\n\n" + extra_context
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
