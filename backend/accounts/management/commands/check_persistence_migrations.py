"""Block automatic release before legacy credit and content ownership adoption."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from accounts.persistence import sqlite_file_missing


LEGACY_CREDIT_MIGRATION = ("learning", "0004_migrate_old_credits")
DESTRUCTIVE_CREDIT_MIGRATION = ("learning", "0005_pushsubscription_and_more")
LEGACY_CREDIT_TABLES = (
    "learning_creditlot",
    "learning_credittransaction",
    "learning_creditpackage",
)
LEGACY_ACCOUNT_TABLE = "learning_aicreditaccount"


class Command(BaseCommand):
    help = "Read-only release check for legacy credit data and unassigned class content."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-existing-database", action="store_true",
            help="Refuse an unattended release into a database without migration history.",
        )

    def handle(self, *args, **options):
        try:
            populated_tables = self._populated_legacy_tables(
                require_existing=options.get("require_existing_database", False)
            )
        except CommandError:
            raise
        except Exception:
            # Driver errors can contain a connection URL, username, or password.
            # Preserve a closed gate without printing the underlying exception.
            raise CommandError(
                "Could not verify persistence migration safety. Automatic migrations "
                "are blocked. Check database connectivity and read permissions, "
                "then rerun check_persistence_migrations."
            ) from None

        if populated_tables:
            raise CommandError(
                "Automatic migrations blocked: learning.0005_pushsubscription_and_more "
                "is pending and drops legacy credit tables without transferring their "
                "data to the credits app. Existing data was found in: "
                + ", ".join(populated_tables)
                + ". Back up the database, rehearse the data transfer on staging, "
                "and verify a manual transfer before applying this migration manually. "
                "This check has not changed any data."
            )

        self.stdout.write(self.style.SUCCESS("Persistence migration preflight passed."))

    @staticmethod
    def _populated_legacy_tables(*, require_existing=False):
        if connection.vendor == "sqlite" and sqlite_file_missing(connection.settings_dict):
            if require_existing:
                raise CommandError(
                    "Automatic release blocked: the existing database file is missing."
                )
            return []
        tables = set(connection.introspection.table_names())
        applied = (
            MigrationRecorder(connection).applied_migrations()
            if "django_migrations" in tables
            else set()
        )
        if require_existing and not applied:
            raise CommandError(
                "Automatic release blocked: no migration history was found. Verify "
                "the existing database target before deploying. An intentional first "
                "installation requires an explicit, separately reviewed initialization."
            )
        ownership_migrated = ('curriculum', '0006_class_content_ownership') in applied
        for table in ('curriculum_subject', 'curriculum_slide', 'curriculum_material', 'curriculum_slidedeck'):
            if table not in tables:
                continue
            with connection.cursor() as cursor:
                predicate = ' WHERE class_group_id IS NULL' if ownership_migrated else ''
                cursor.execute(f'SELECT 1 FROM {connection.ops.quote_name(table)}{predicate} LIMIT 1')
                if cursor.fetchone() is not None:
                    raise CommandError(
                        'Automatic release blocked: class ownership adoption is incomplete. '
                        'Back up and rehearse curriculum.0006 plus assign_content_classes on staging; '
                        'review the explicit mapping before a manual maintenance rollout. '
                        'No existing content has been reassigned or deleted.'
                    )
        if DESTRUCTIVE_CREDIT_MIGRATION in applied:
            return []

        protected_tables = list(LEGACY_CREDIT_TABLES)
        if LEGACY_CREDIT_MIGRATION not in applied:
            # 0004 grants daily credits to every old account, even accounts with
            # no remaining monthly balance. These would then be deleted by 0005.
            protected_tables.append(LEGACY_ACCOUNT_TABLE)

        candidates = [table for table in protected_tables if table in tables]
        if not candidates:
            return []

        populated_tables = []
        with connection.cursor() as cursor:
            for table in candidates:
                quoted_table = connection.ops.quote_name(table)
                cursor.execute(f"SELECT 1 FROM {quoted_table} LIMIT 1")
                if cursor.fetchone() is not None:
                    populated_tables.append(table)
        return populated_tables
