#!/usr/bin/env python3
"""
Ensure references are extracted from references.zip when needed.

Usage:
    python scripts/ensure_references.py
"""

import argparse
from pathlib import Path
import zipfile


def references_ready(references_dir):
    """Return True when references dir exists and includes rule markdown files."""
    if not references_dir.is_dir():
        return False
    return any(references_dir.glob("coding_rules_*/rules/*.md"))


def ensure_references(skill_root, force=False):
    references_zip = skill_root / "references.zip"
    references_dir = skill_root / "references"

    if references_ready(references_dir) and not force:
        print(f"References already extracted: {references_dir}")
        return 0

    if not references_zip.is_file():
        print(f"references.zip not found: {references_zip}")
        return 1

    references_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(references_zip, "r") as zip_ref:
            zip_ref.extractall(skill_root)
    except zipfile.BadZipFile:
        print(f"Invalid zip file: {references_zip}")
        return 1

    if references_ready(references_dir):
        print(f"References extracted successfully to: {references_dir}")
        return 0

    print("Extraction finished but no rule files were found under references/.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract references.zip only when references/ is missing or incomplete."
    )
    parser.add_argument(
        "--skill-root",
        default=None,
        help="Skill root path. Defaults to parent of scripts/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extract even if references/ appears ready.",
    )
    args = parser.parse_args()

    if args.skill_root:
        skill_root = Path(args.skill_root).resolve()
    else:
        skill_root = Path(__file__).resolve().parent.parent

    return ensure_references(skill_root=skill_root, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
