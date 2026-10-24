"""Configuration regressions: no real database, dotenv file or provider access."""

import importlib.util
from pathlib import Path
import unittest

from django.core.exceptions import ImproperlyConfigured


_path = Path(__file__).resolve().parents[1] / "backend" / "database_config.py"
_spec = importlib.util.spec_from_file_location("database_config_under_test", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
database_config = _module.database_config


class DatabaseConfigTests(unittest.TestCase):
    base_dir = Path("/isolated-development")
    postgres_url = "postgresql://emby:secret@db.example.test:5432/emby?sslmode=require"
    db_fields = {
        "DB_NAME": "emby", "DB_USER": "emby",
        "DB_PASSWORD": "private-password", "DB_HOST": "db.example.test",
    }

    def config(self, env, *, debug=False):
        return database_config(env, self.base_dir, debug=debug)

    def test_production_without_database_fails_instead_of_creating_sqlite(self):
        for env in ({}, {"DATABASE_URL": "  "}, {"DB_PORT": "5432"}):
            with self.subTest(env=env), self.assertRaisesRegex(
                ImproperlyConfigured, "No production database configured"
            ):
                self.config(env)

    def test_sqlite_override_cannot_hide_production_postgres(self):
        for value in ("true", "1", " YES ", "on"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ImproperlyConfigured, "USE_SQLITE requires DEBUG=True"
            ):
                self.config({"USE_SQLITE": value, "DATABASE_URL": self.postgres_url})

    def test_production_rejects_sqlite_urls(self):
        for url in ("sqlite:///db.sqlite3", "sqlite://:memory:"):
            with self.subTest(url=url), self.assertRaisesRegex(
                ImproperlyConfigured, "persistent PostgreSQL"
            ):
                self.config({"DATABASE_URL": url})

    def test_production_rejects_other_database_engines(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "persistent PostgreSQL"):
            self.config({"DATABASE_URL": "mysql://user:password@host/emby"})

    def test_postgres_url_preserves_ssl_and_connection_health_checks(self):
        result = self.config({"DATABASE_URL": self.postgres_url})
        self.assertEqual(result["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(result["NAME"], "emby")
        self.assertEqual(result["OPTIONS"]["sslmode"], "require")
        self.assertEqual(result["CONN_MAX_AGE"], 60)
        self.assertTrue(result["CONN_HEALTH_CHECKS"])

    def test_url_keeps_precedence_over_individual_fields(self):
        result = self.config({**self.db_fields, "DATABASE_URL": self.postgres_url,
                              "DB_NAME": "different_database"})
        self.assertEqual(result["NAME"], "emby")

    def test_missing_url_target_components_fail(self):
        for url in ("postgresql://user:secret@host/", "postgresql:///emby",
                    "postgresql://host/emby"):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                self.config({"DATABASE_URL": url})

    def test_malformed_url_errors_do_not_disclose_credentials(self):
        for url in ("invalid://user:do-not-leak@host/db",
                    "postgresql://user:do-not-leak@host:wrong/db",
                    "postgresql://user:do-not-leak@[broken/db"):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as error:
                self.config({"DATABASE_URL": url})
            self.assertNotIn("do-not-leak", str(error.exception))
            self.assertIsNone(error.exception.__cause__)
            self.assertTrue(error.exception.__suppress_context__)

    def test_partial_production_fields_fail_with_missing_names_only(self):
        for missing in self.db_fields:
            env = {key: value for key, value in self.db_fields.items() if key != missing}
            with self.subTest(missing=missing), self.assertRaisesRegex(
                ImproperlyConfigured, missing
            ) as error:
                self.config(env)
            self.assertNotIn("private-password", str(error.exception))

    def test_blank_production_field_fails(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "DB_HOST"):
            self.config({**self.db_fields, "DB_HOST": " "})

    def test_non_string_environment_values_are_normalized(self):
        result = self.config({"USE_SQLITE": True, "SQLITE_NAME": ":memory:"}, debug=True)
        self.assertEqual(result["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(result["NAME"], ":memory:")

        result = self.config({"DB_NAME": "emby", "DB_USER": "emby", "DB_PASSWORD": "secret", "DB_HOST": "db.example.test", "DB_PORT": 5432}, debug=False)
        self.assertEqual(result["PORT"], "5432")
        self.assertEqual(result["HOST"], "db.example.test")

    def test_complete_fields_and_optional_sslmode_work(self):
        result = self.config({**self.db_fields, "DB_SSLMODE": "require"})
        self.assertEqual(result["NAME"], "emby")
        self.assertEqual(result["PORT"], "5432")
        self.assertEqual(result["OPTIONS"]["sslmode"], "require")
        self.assertTrue(result["CONN_HEALTH_CHECKS"])

    def test_development_fallback_is_retained(self):
        result = self.config({}, debug=True)
        self.assertEqual(result["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(result["NAME"], str(self.base_dir / "db.sqlite3"))

    def test_explicit_development_sqlite_uses_requested_test_file(self):
        result = self.config({"USE_SQLITE": "true", "SQLITE_NAME": ":memory:",
                              "DATABASE_URL": self.postgres_url}, debug=True)
        self.assertEqual(result["NAME"], ":memory:")
        self.assertEqual(result["ENGINE"], "django.db.backends.sqlite3")

    def test_development_can_use_local_passwordless_postgres(self):
        result = self.config({"DB_NAME": "emby_dev"}, debug=True)
        self.assertEqual(result["HOST"], "localhost")
        self.assertEqual(result["NAME"], "emby_dev")

    def test_partial_development_fields_do_not_silently_switch_database(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "DB_NAME"):
            self.config({"DB_HOST": "db.example.test"}, debug=True)


if __name__ == "__main__":
    unittest.main()
