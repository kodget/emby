#!/usr/bin/env python3
"""Compare redacted persistence reports captured from Render services."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("could not read valid JSON") from None
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported persistence report format")
    if report.get("errors"):
        raise ValueError("persistence report contains errors")

    database = report.get("database")
    cloudinary = report.get("cloudinary")
    if not isinstance(database, dict) or not FINGERPRINT.fullmatch(
        str(database.get("target_sha256", ""))
    ):
        raise ValueError("database target fingerprint is missing")
    if (
        not isinstance(cloudinary, dict)
        or cloudinary.get("configured") is not True
        or not FINGERPRINT.fullmatch(str(cloudinary.get("target_sha256", "")))
    ):
        raise ValueError("configured Cloudinary account fingerprint is missing")

    migrations = report.get("applied_migrations")
    if not isinstance(migrations, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("app"), str)
        or not isinstance(item.get("name"), str)
        for item in migrations
    ):
        raise ValueError("migration history is missing or malformed")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that web and worker reports target the same database and "
            "Cloudinary account and have matching migration history."
        )
    )
    parser.add_argument("web_report", type=Path)
    parser.add_argument("worker_report", type=Path)
    args = parser.parse_args()

    try:
        web = load_report(args.web_report)
        worker = load_report(args.worker_report)
    except ValueError as error:
        print(json.dumps({"status": "invalid", "reason": str(error)}))
        return 2

    checks = {
        "database_target_matches": (
            web["database"]["target_sha256"]
            == worker["database"]["target_sha256"]
        ),
        "cloudinary_account_matches": (
            web["cloudinary"]["target_sha256"]
            == worker["cloudinary"]["target_sha256"]
        ),
        "migration_history_matches": (
            sorted((item["app"], item["name"]) for item in web["applied_migrations"])
            == sorted((item["app"], item["name"]) for item in worker["applied_migrations"])
        ),
    }
    matched = all(checks.values())
    print(json.dumps({"status": "match" if matched else "mismatch", "checks": checks}, indent=2))
    return 0 if matched else 1


if __name__ == "__main__":
    sys.exit(main())
