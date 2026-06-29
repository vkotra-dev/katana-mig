from __future__ import annotations

from typing import Final

CENTRAL_TEAM_ROLE: Final = "central_team"
PROJECT_STAKEHOLDER_ROLE: Final = "project_stakeholder"
READ_ONLY_AUDITOR_ROLE: Final = "read_only_auditor"

PLATFORM_ROLES: Final[tuple[tuple[str, str], ...]] = (
    (CENTRAL_TEAM_ROLE, "Administrative role; manages users and project membership"),
    (PROJECT_STAKEHOLDER_ROLE, "Project-scoped stakeholder; requires project membership"),
    (READ_ONLY_AUDITOR_ROLE, "View-only access across projects"),
)


def format_roles() -> str:
    lines = ["Platform roles:"]
    for role, description in PLATFORM_ROLES:
        lines.append(f"  - {role}: {description}")
    return "\n".join(lines)
