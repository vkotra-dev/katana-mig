#!/usr/bin/env python3
"""Validate Google OKF compliance for docs/domain/ knowledge bundle.

Checks:
  1. Every .md file has valid YAML frontmatter with required 'type' field
  2. Recommended fields (title, description, tags, timestamp) are present
  3. README.md index lists all .md files in the directory
  4. Timestamp staleness warning if file was git-modified after its timestamp

Usage:
  python scripts/validate_okf.py
  python scripts/validate_okf.py --strict   # exit 1 on warnings too
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

DOMAIN_DIR = Path(__file__).resolve().parent.parent / "docs" / "domain"
REQUIRED_FIELDS = {"type"}
RECOMMENDED_FIELDS = {"title", "description", "tags", "timestamp"}
ALL_FIELDS = REQUIRED_FIELDS | RECOMMENDED_FIELDS


def parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.index("---", 3)
    if end < 0:
        return None
    try:
        return yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None


def git_last_modified(path: Path) -> date | None:
    """Get the last git commit date for a file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(path)],
            capture_output=True,
            text=True,
            cwd=path.parent,
        )
        if result.returncode == 0 and result.stdout.strip():
            return date.fromisoformat(result.stdout.strip()[:10])
    except Exception:
        pass
    return None


def check_readme_index(readme: Path, md_files: list[Path]) -> list[str]:
    """Check that README.md references all sibling .md files."""
    warnings = []
    if not readme.exists():
        warnings.append("README.md is missing — bundle has no index/manifest")
        return warnings

    readme_text = readme.read_text(encoding="utf-8")
    for md in md_files:
        if md.name == "README.md":
            continue
        if md.name not in readme_text:
            warnings.append(f"README.md does not reference {md.name}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OKF compliance")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    if not DOMAIN_DIR.is_dir():
        print(f"ERROR: {DOMAIN_DIR} not found")
        return 1

    md_files = sorted(DOMAIN_DIR.glob("*.md"))
    if not md_files:
        print(f"ERROR: No .md files in {DOMAIN_DIR}")
        return 1

    print(f"Checking {len(md_files)} files in {DOMAIN_DIR}\n")

    for md in md_files:
        fm = parse_frontmatter(md)

        if fm is None:
            errors.append(f"{md.name}: missing YAML frontmatter")
            continue

        # Required fields
        for field in REQUIRED_FIELDS:
            if field not in fm or not fm[field]:
                errors.append(f"{md.name}: missing required field '{field}'")

        # Recommended fields
        for field in RECOMMENDED_FIELDS:
            if field not in fm or not fm[field]:
                warnings.append(f"{md.name}: missing recommended field '{field}'")

        # Timestamp staleness
        if "timestamp" in fm and fm["timestamp"]:
            try:
                ts = date.fromisoformat(str(fm["timestamp"]))
                git_date = git_last_modified(md)
                if git_date and git_date > ts:
                    warnings.append(
                        f"{md.name}: timestamp ({ts}) is older than last git commit ({git_date}) "
                        f"— bump the timestamp"
                    )
            except (ValueError, TypeError):
                warnings.append(f"{md.name}: timestamp '{fm['timestamp']}' is not a valid date")

        status = "✓" if not any(md.name in e for e in errors) else "✗"
        print(f"  {status} {md.name} (type={fm.get('type', '?')})")

    # Check README index
    readme_warnings = check_readme_index(DOMAIN_DIR / "README.md", md_files)
    warnings.extend(readme_warnings)

    print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")

    if not errors and not warnings:
        print("✓ All files OKF-compliant. No issues found.")
        return 0

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
