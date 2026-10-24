"""Read-only deployment inventory; never emit credentials or application rows."""

import hashlib
import json
import os
from pathlib import Path

import cloudinary
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder

from accounts.persistence import sqlite_file_missing


LOCAL_APPS = {"accounts", "curriculum", "learning", "credits", "pastquestions"}
DEFAULT_PORTS = {"postgresql": "5432", "mysql": "3306", "oracle": "1521"}


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def database_fingerprint(config, vendor):
    """Compare effective destinations without including usernames or passwords."""
    name = str(config.get("NAME") or "")
    host = str(config.get("HOST") or "")
    port = str(config.get("PORT") or DEFAULT_PORTS.get(vendor, ""))
    if vendor == "sqlite":
        if name and name != ":memory:" and not name.startswith("file:"):
            name = os.path.normcase(str(Path(name).resolve()))
        host, port = "", ""
    elif not host.startswith("/"):
        # Empty HOST can mean a Unix socket, so do not equate it to localhost.
        host = host.lower().rstrip(".")
    if port.isdecimal():
        port = str(int(port))
    return fingerprint({"vendor": vendor, "host": host, "port": port, "name": name})


def configuration_source(config):
    source = getattr(settings, "DATABASE_CONFIG_SOURCE", None)
    if source:
        return source
    if config.get("ENGINE", "").endswith("sqlite3"):
        return "SQLite"
    if os.environ.get("DATABASE_URL"):
        return "DATABASE_URL"
    if os.environ.get("DB_NAME"):
        return "DB fields"
    return "Django settings"


def report_models():
    for model in apps.get_models(include_auto_created=True):
        meta = model._meta
        owner = meta.auto_created
        user_relation = owner and owner._meta.label_lower == "auth.user"
        if not meta.proxy and (
            meta.app_label in LOCAL_APPS
            or meta.label_lower == "auth.user"
            or user_relation
        ):
            yield model


class Command(BaseCommand):
    help = "Print a read-only, secret-free JSON persistence inventory."
    requires_system_checks = []
    requires_migrations_checks = False

    def handle(self, *args, **options):
        connection = connections["default"]
        config = connection.settings_dict
        report = {
            "schema_version": 1,
            "debug": bool(settings.DEBUG),
            "database": {
                "alias": "default",
                "engine": config["ENGINE"],
                "vendor": connection.vendor,
                "configuration_source": configuration_source(config),
                "target_sha256": database_fingerprint(config, connection.vendor),
            },
            "cloudinary": {},
            "counts": {},
            "applied_migrations": [],
            "errors": [],
            "limitations": [
                "Counts are observations, not a backup or a consistent snapshot during writes.",
                "Matching counts do not prove that row contents are identical.",
                "File metadata counts do not prove that file bytes exist or are readable.",
                "Cloudinary configuration is inspected locally; no provider is contacted.",
            ],
        }
        try:
            cloud = cloudinary.config()
            configured = {
                "cloud_name_configured": bool(cloud.cloud_name),
                "api_key_configured": bool(cloud.api_key),
                "api_secret_configured": bool(cloud.api_secret),
            }
            report["cloudinary"] = {
                **configured,
                "configured": all(configured.values()),
                "target_sha256": fingerprint(str(cloud.cloud_name)) if cloud.cloud_name else None,
            }
        except Exception:
            report["errors"].append({"code": "cloudinary_configuration_unavailable"})

        if connection.vendor == "sqlite" and sqlite_file_missing(config):
            report["errors"].append({"code": "sqlite_database_file_missing"})
        else:
            try:
                models = sorted(report_models(), key=lambda model: model._meta.label_lower)
                for model in models:
                    label = model._meta.label_lower
                    try:
                        report["counts"][label] = model._base_manager.using("default").count()
                    except Exception:
                        # Backend exception messages may contain connection credentials.
                        report["counts"][label] = None
                        report["errors"].append({"code": "model_count_failed", "model": label})
            except Exception:
                report["errors"].append({"code": "model_inventory_failed"})
            try:
                recorder = MigrationRecorder(connection)
                if not recorder.has_table():
                    report["errors"].append({"code": "migration_table_missing"})
                else:
                    report["applied_migrations"] = [
                        {"app": app, "name": name}
                        for app, name in sorted(recorder.applied_migrations())
                    ]
            except Exception:
                report["errors"].append({"code": "migration_inventory_failed"})

        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if report["errors"]:
            raise CommandError("Persistence report has errors; see the JSON errors field.")
