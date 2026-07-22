from __future__ import annotations

from pathlib import Path
from string import Template

import yaml

_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"


def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    header = Template(data["shared_header"]).substitute(
        dest=dest, stg=stg, engineName=engine_name
    ).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific = data.get(engine_key, "")

    if specific:
        header = header + "\n" + specific.rstrip("\n")

    return f"{header}\n\n{footer}"
