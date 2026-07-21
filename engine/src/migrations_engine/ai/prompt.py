import logging
import yaml
from pathlib import Path
from string import Template

_LOGGER = logging.getLogger(__name__)
_PROMPTS_DIR = Path(__file__).parent / "prompts"

class _WarnOnMissing(dict[str, str]):
    def __init__(self, name: str, mapping: dict[str, str]) -> None:
        super().__init__(mapping)
        self._name = name

    def __missing__(self, key: str) -> str:
        _LOGGER.warning("Missing prompt field '%s' in prompt '%s'", key, self._name)
        return ""

class Prompt:
    def __init__(self, name: str) -> None:
        self._name = name
        path = _PROMPTS_DIR / f"{name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._system = data["system"]
        self._user = data["user"]
        self._fields: dict[str, str] = {}

    def set(self, **kwargs: str) -> "Prompt":
        self._fields.update(kwargs)
        return self

    def get_prompt(self) -> tuple[str, str]:
        mapping = _WarnOnMissing(self._name, self._fields)
        system = Template(self._system).substitute(mapping).strip()
        user = Template(self._user).substitute(mapping).strip()
        return system, user
