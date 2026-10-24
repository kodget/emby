"""Migration safety checks use mocked connections and never access a database."""

from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from django.core.management.base import CommandError

from accounts.management.commands import check_persistence_migrations as preflight


class PersistenceMigrationTests(unittest.TestCase):
    def setUp(self):
        # Supplying the replacement avoids unittest.mock introspecting Django's
        # lazy connection proxy and loading real project settings.
        self.connection_patch = patch.object(preflight, "connection", MagicMock())
        self.connection = self.connection_patch.start()
        self.connection.vendor = "postgresql"
        self.addCleanup(self.connection_patch.stop)
        self.recorder_patch = patch.object(preflight, "MigrationRecorder")
        self.recorder = self.recorder_patch.start()
        self.addCleanup(self.recorder_patch.stop)
        self.connection.introspection.table_names.return_value = []
        self.connection.ops.quote_name.side_effect = lambda name: f'"{name}"'
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = None
        self.recorder.return_value.applied_migrations.return_value = set()
        self.output = StringIO()
        self.command = preflight.Command(stdout=self.output, no_color=True)

    def test_new_database_passes_without_creating_migration_history(self):
        self.command.handle()

        self.assertIn("passed", self.output.getvalue())
        self.recorder.assert_not_called()
        self.connection.cursor.assert_not_called()

    def test_pending_ownership_migration_blocks_release_over_existing_content(self):
        self.connection.introspection.table_names.return_value = ['django_migrations', 'curriculum_slide']
        self.recorder.return_value.applied_migrations.return_value = {preflight.DESTRUCTIVE_CREDIT_MIGRATION}
        self.cursor.fetchone.return_value = (1,)
        with self.assertRaisesRegex(CommandError, 'class ownership adoption'):
            self.command.handle()
        self.cursor.execute.assert_called_once_with('SELECT 1 FROM "curriculum_slide" LIMIT 1')

    def test_unassigned_ownership_blocks_release_even_after_schema_migration(self):
        self.connection.introspection.table_names.return_value = ['django_migrations', 'curriculum_slide']
        self.recorder.return_value.applied_migrations.return_value = {
            preflight.DESTRUCTIVE_CREDIT_MIGRATION, ('curriculum', '0006_class_content_ownership')}
        self.cursor.fetchone.return_value = (1,)
        with self.assertRaisesRegex(CommandError, 'class ownership adoption'):
            self.command.handle()
        self.cursor.execute.assert_called_once_with('SELECT 1 FROM "curriculum_slide" WHERE class_group_id IS NULL LIMIT 1')

    def test_release_refuses_database_without_migration_history(self):
        with self.assertRaisesRegex(CommandError, "existing database"):
            self.command.handle(require_existing_database=True)
        self.connection.cursor.assert_not_called()
        self.recorder.assert_not_called()

    def test_release_refuses_empty_migration_history(self):
        self.connection.introspection.table_names.return_value = ["django_migrations"]
        with self.assertRaisesRegex(CommandError, "existing database"):
            self.command.handle(require_existing_database=True)
        self.connection.cursor.assert_not_called()

    def test_missing_sqlite_file_is_not_created_by_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "never-created.sqlite3"
            self.connection.vendor = "sqlite"
            self.connection.settings_dict = {"NAME": str(path)}
            self.command.handle()
            self.assertFalse(path.exists())
            self.connection.introspection.table_names.assert_not_called()

    def test_release_refuses_missing_sqlite_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "never-created.sqlite3"
            self.connection.vendor = "sqlite"
            self.connection.settings_dict = {"NAME": str(path)}
            with self.assertRaisesRegex(CommandError, "existing database file is missing"):
                self.command.handle(require_existing_database=True)
            self.assertFalse(path.exists())
            self.connection.introspection.table_names.assert_not_called()

    def test_empty_legacy_tables_pass_with_only_read_queries(self):
        candidates = [*preflight.LEGACY_CREDIT_TABLES, preflight.LEGACY_ACCOUNT_TABLE]
        self.connection.introspection.table_names.return_value = [
            "django_migrations", *candidates, "auth_user", "credits_creditlot"
        ]

        self.command.handle()

        self.assertEqual(
            self.cursor.execute.call_args_list,
            [call(f'SELECT 1 FROM "{table}" LIMIT 1') for table in candidates],
        )
        self.assertIn("passed", self.output.getvalue())
        self.recorder.return_value.ensure_schema.assert_not_called()

    def test_each_populated_legacy_table_blocks_pending_migrations(self):
        for table in [*preflight.LEGACY_CREDIT_TABLES, preflight.LEGACY_ACCOUNT_TABLE]:
            with self.subTest(table=table):
                self.connection.introspection.table_names.return_value = [
                    "django_migrations", table
                ]
                self.cursor.fetchone.return_value = (1,)

                with self.assertRaises(CommandError) as caught:
                    self.command.handle()

                message = str(caught.exception)
                self.assertIn(table, message)
                self.assertIn("Back up the database", message)
                self.assertIn("staging", message)
                self.assertIn("manual transfer", message)
                self.assertEqual(self.output.getvalue(), "")

    def test_legacy_rows_without_migration_history_still_block(self):
        self.connection.introspection.table_names.return_value = ["learning_creditlot"]
        self.cursor.fetchone.return_value = (1,)

        with self.assertRaises(CommandError):
            self.command.handle()

        self.recorder.assert_not_called()

    def test_old_accounts_block_even_before_credit_tables_exist(self):
        self.connection.introspection.table_names.return_value = [
            "django_migrations", "learning_aicreditaccount"
        ]
        self.recorder.return_value.applied_migrations.return_value = {
            ("learning", "0001_initial")
        }
        self.cursor.fetchone.return_value = (1,)

        with self.assertRaisesRegex(CommandError, "learning_aicreditaccount"):
            self.command.handle()

        self.cursor.execute.assert_called_once_with(
            'SELECT 1 FROM "learning_aicreditaccount" LIMIT 1'
        )

    def test_old_accounts_do_not_block_when_conversion_already_applied(self):
        self.connection.introspection.table_names.return_value = [
            "django_migrations", "learning_aicreditaccount"
        ]
        self.recorder.return_value.applied_migrations.return_value = {
            preflight.LEGACY_CREDIT_MIGRATION
        }

        self.command.handle()

        self.connection.cursor.assert_not_called()
        self.assertIn("passed", self.output.getvalue())

    def test_populated_credit_table_blocks_after_conversion_applied(self):
        self.connection.introspection.table_names.return_value = [
            "django_migrations", "learning_credittransaction"
        ]
        self.recorder.return_value.applied_migrations.return_value = {
            preflight.LEGACY_CREDIT_MIGRATION
        }
        self.cursor.fetchone.return_value = (1,)

        with self.assertRaisesRegex(CommandError, "learning_credittransaction"):
            self.command.handle()

    def test_already_applied_destructive_migration_does_not_block_deploy(self):
        self.connection.introspection.table_names.return_value = [
            "django_migrations", *preflight.LEGACY_CREDIT_TABLES,
            preflight.LEGACY_ACCOUNT_TABLE,
        ]
        self.recorder.return_value.applied_migrations.return_value = {
            preflight.DESTRUCTIVE_CREDIT_MIGRATION
        }

        self.command.handle()

        self.connection.cursor.assert_not_called()
        self.assertIn("passed", self.output.getvalue())

    def test_inspection_failures_block_without_exposing_database_errors(self):
        private_error = "postgresql://private-user:private-password@private-host/db"
        failing_operations = (
            self.connection.introspection.table_names,
            self.recorder.return_value.applied_migrations,
            self.connection.cursor,
            self.connection.ops.quote_name,
            self.cursor.execute,
            self.cursor.fetchone,
        )
        for operation in failing_operations:
            with self.subTest(operation=operation):
                self.connection.introspection.table_names.return_value = [
                    "django_migrations", "learning_creditlot"
                ]
                original_side_effect = operation.side_effect
                operation.side_effect = RuntimeError(private_error)
                try:
                    with self.assertRaises(CommandError) as caught:
                        self.command.handle()
                    self.assertIn("Automatic migrations are blocked", str(caught.exception))
                    self.assertNotIn(private_error, str(caught.exception))
                    self.assertTrue(caught.exception.__suppress_context__)
                    self.assertEqual(self.output.getvalue(), "")
                finally:
                    operation.side_effect = original_side_effect


if __name__ == "__main__":
    unittest.main()
