"""Pure unit tests: no project settings, production environment, or database access."""

import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from django.core.management.base import CommandError

from accounts.management.commands import persistence_report as audit


def make_model(label, count=1, owner=False, proxy=False):
    model = Mock()
    model._meta = SimpleNamespace(
        label_lower=label,
        app_label=label.split(".")[0],
        auto_created=owner,
        proxy=proxy,
    )
    model._base_manager.using.return_value.count.return_value = count
    return model


class FingerprintTests(TestCase):
    def test_database_defaults_and_dns_host_normalization(self):
        implicit = {"NAME": "emby", "HOST": "DB.EXAMPLE.COM.", "PORT": ""}
        explicit = {"NAME": "emby", "HOST": "db.example.com", "PORT": 5432}
        self.assertEqual(
            audit.database_fingerprint(implicit, "postgresql"),
            audit.database_fingerprint(explicit, "postgresql"),
        )

    def test_credentials_do_not_change_target_but_database_does(self):
        original = {"NAME": "emby", "USER": "first", "PASSWORD": "secret"}
        rotated = {**original, "USER": "second", "PASSWORD": "different"}
        self.assertEqual(
            audit.database_fingerprint(original, "postgresql"),
            audit.database_fingerprint(rotated, "postgresql"),
        )
        self.assertNotEqual(
            audit.database_fingerprint(original, "postgresql"),
            audit.database_fingerprint({**original, "NAME": "another"}, "postgresql"),
        )

    def test_sqlite_paths_normalize_and_missing_files_are_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "never-created.sqlite3"
            config = {"NAME": str(path)}
            self.assertTrue(audit.sqlite_file_missing(config))
            self.assertTrue(audit.sqlite_file_missing({"NAME": path.as_uri() + "?mode=ro"}))
            self.assertFalse(path.exists())
        self.assertFalse(audit.sqlite_file_missing({"NAME": ":memory:"}))
        self.assertFalse(audit.sqlite_file_missing({"NAME": "file:local?mode=memory&cache=shared"}))

    def test_source_reports_only_a_label(self):
        with patch.object(audit, "settings", SimpleNamespace()), patch.dict(
            audit.os.environ, {"DATABASE_URL": "postgres://user:secret@host/db"}, clear=True
        ):
            self.assertEqual(audit.configuration_source({"ENGINE": "postgresql"}), "DATABASE_URL")
            self.assertEqual(audit.configuration_source({"ENGINE": "django.db.backends.sqlite3"}), "SQLite")


class PersistenceReportTests(TestCase):
    def setUp(self):
        self.connection = SimpleNamespace(
            vendor="postgresql",
            settings_dict={
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "private_database",
                "HOST": "private_host",
                "USER": "private_user",
                "PASSWORD": "private_password",
                "PORT": "5432",
            },
        )
        self.cloud = SimpleNamespace(
            cloud_name="private_cloud", api_key="private_key", api_secret="private_secret"
        )
        self.user = make_model("auth.user", count=3)
        self.models = [
            self.user,
            make_model("auth.user_groups", count=4, owner=self.user),
            make_model("auth.group", count=5),
            make_model("accounts.profile", count=3),
            make_model("curriculum.slide", count=12),
            make_model("learning.practiceattempt", count=8),
            make_model("credits.creditlot", count=2),
            make_model("pastquestions.pastquestionupload", count=1),
            make_model("curriculum.quiz_questions", count=9, owner=make_model("curriculum.quiz")),
            make_model("unrelated.record", count=99),
        ]
        self.recorder = Mock()
        self.recorder.has_table.return_value = True
        self.recorder.applied_migrations.return_value = {
            ("curriculum", "0001_initial"): Mock(),
            ("accounts", "0001_initial"): Mock(),
        }
        patches = [
            patch.object(audit, "connections", {"default": self.connection}),
            patch.object(audit, "settings", SimpleNamespace(DEBUG=False, DATABASE_CONFIG_SOURCE="DB fields")),
            patch.object(audit.cloudinary, "config", return_value=self.cloud),
            patch.object(audit.apps, "get_models", return_value=self.models),
            patch.object(audit, "MigrationRecorder", return_value=self.recorder),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = io.StringIO()
        self.command = audit.Command(stdout=self.output, stderr=io.StringIO())

    def run_report(self, failure=False):
        if failure:
            with self.assertRaises(CommandError) as error:
                self.command.handle()
            self.assertNotIn("private_", str(error.exception))
        else:
            self.command.handle()
        text = self.output.getvalue()
        self.assertNotIn("private_", text)
        return json.loads(text)

    def test_json_inventory_includes_local_models_user_and_through_tables(self):
        result = self.run_report()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["counts"]["curriculum.slide"], 12)
        self.assertEqual(result["counts"]["auth.user_groups"], 4)
        self.assertEqual(result["counts"]["curriculum.quiz_questions"], 9)
        self.assertNotIn("auth.group", result["counts"])
        self.assertNotIn("unrelated.record", result["counts"])
        self.assertEqual(result["applied_migrations"][0], {"app": "accounts", "name": "0001_initial"})
        self.assertTrue(result["cloudinary"]["configured"])
        self.assertEqual(len(result["database"]["target_sha256"]), 64)
        self.assertEqual(len(result["cloudinary"]["target_sha256"]), 64)
        self.recorder.ensure_schema.assert_not_called()
        self.user._base_manager.using.assert_called_once_with("default")

    def test_query_failure_is_sanitized_and_fails_the_command(self):
        self.user._base_manager.using.return_value.count.side_effect = RuntimeError("private_password")
        result = self.run_report(failure=True)
        self.assertIsNone(result["counts"]["auth.user"])
        self.assertIn({"code": "model_count_failed", "model": "auth.user"}, result["errors"])

    def test_migration_query_failure_is_sanitized(self):
        self.recorder.applied_migrations.side_effect = RuntimeError("private_password")
        result = self.run_report(failure=True)
        self.assertIn({"code": "migration_inventory_failed"}, result["errors"])

    def test_missing_migration_table_is_an_error(self):
        self.recorder.has_table.return_value = False
        result = self.run_report(failure=True)
        self.assertIn({"code": "migration_table_missing"}, result["errors"])
        self.recorder.applied_migrations.assert_not_called()

    def test_missing_sqlite_database_is_not_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.sqlite3"
            self.connection.vendor = "sqlite"
            self.connection.settings_dict = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(path)}
            result = self.run_report(failure=True)
            self.assertEqual(result["errors"], [{"code": "sqlite_database_file_missing"}])
            self.assertEqual(result["counts"], {})
            self.assertFalse(path.exists())
            self.user._base_manager.using.assert_not_called()
            self.recorder.has_table.assert_not_called()

    def test_unconfigured_cloud_has_no_target_fingerprint(self):
        self.cloud.cloud_name = ""
        result = self.run_report()
        self.assertFalse(result["cloudinary"]["configured"])
        self.assertIsNone(result["cloudinary"]["target_sha256"])
