from __future__ import annotations

from pathlib import Path
from string import Template

import yaml

_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"
_LOGGING_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_logging_standards.yaml"


def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    logging_data = yaml.safe_load(_LOGGING_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    mapping = {"dest": dest, "stg": stg, "engineName": engine_name}
    header = Template(data["shared_header"]).substitute(mapping).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific_raw = data.get(engine_key, "")
    logging_raw = logging_data.get(engine_key, "")

    if specific_raw:
        specific = Template(specific_raw).substitute(mapping)
        header = header + "\n" + specific.rstrip("\n")

    if logging_raw:
        logging_block = Template(logging_raw).substitute(mapping)
        header = header + "\n" + logging_block.rstrip("\n")

    return f"{header}\n\n{footer}"
