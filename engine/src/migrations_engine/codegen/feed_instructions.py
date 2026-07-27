from __future__ import annotations

from pathlib import Path
from string import Template

import yaml

_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "feed_transformation_instructions.yaml"


def render_feed_instructions_template(feed_text: str | None) -> str:
    """Render feed-specific transformation instructions through the YAML template.

    Wraps raw user text with consistent AI-facing context from the YAML template.
    Uses the system:/user: key pattern and Python string.Template ($payload)
    consistent with other prompt YAML files in this codebase.
    Returns "(none)" when feed_text is None or empty.
    """
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    system_raw = data.get("system", "").strip()

    if not feed_text or not feed_text.strip():
        return "(none)"

    header = Template(system_raw).substitute(payload=feed_text.strip()).rstrip("\n")
    return header
