"""Real ORM transfers against recreated historical tables, never production data."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from django.utils import timezone

from credits.legacy_transfer import (
    CONVERSION_MIGRATION, DROP_MIGRATION, LOT_TABLE, PACKAGE_TABLE,
    PROVENANCE_KEY, SOURCE_TABLES, TRANSACTION_TABLE, TRANSFER_MIGRATION,
    LegacyTransferError, transfer_legacy_credits,
)
from credits.models import CreditLot, CreditPackage, CreditTransaction, LegacyCreditRecord


class LegacyCreditTransferTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        apps = MigrationLoader(connection).project_state([CONVERSION_MIGRATION]).apps
        cls.OldPackage = apps.get_model("learning", "CreditPackage")
        cls.OldLot = apps.get_model("learning", "CreditLot")
        cls.OldTransaction = apps.get_model("learning", "CreditTransaction")

    def setUp(self):
        self.recorder = MigrationRecorder(connection)
        self.recorder.record_unapplied(*DROP_MIGRATION)
        with connection.schema_editor() as editor:
            for model in (self.OldPackage, self.OldLot, self.OldTransaction):
                editor.create_model(model)
        self.user = get_user_model().objects.create_user(username="legacy-test")
        self.when = (timezone.now() - timedelta(days=5)).replace(microsecond=123456)

    def tearDown(self):
        with connection.schema_editor() as editor:
            for model in (self.OldTransaction, self.OldLot, self.OldPackage):
                editor.delete_model(model)
        for migration in (CONVERSION_MIGRATION, DROP_MIGRATION, TRANSFER_MIGRATION):
            self.recorder.record_applied(*migration)
        super().tearDown()

    def source_ledger(self):
        purchased = self.OldLot.objects.create(
            id=101, user_id=self.user.pk, source="PURCHASE", original_amount=25,
            remaining_amount=19, granted_at=self.when, expires_at=None,
            purchase_reference="old-payment-reference",
        )
        daily = self.OldLot.objects.create(
            id=102, user_id=self.user.pk, source="DAILY_FREE", original_amount=10,
            remaining_amount=4, granted_at=self.when,
            expires_at=timezone.now() + timedelta(days=2), allocation_date=self.when.date(),
        )
        self.OldLot.objects.create(
            id=103, user_id=self.user.pk, source="DAILY_FREE", original_amount=10,
            remaining_amount=7, granted_at=self.when - timedelta(days=30),
            expires_at=self.when, allocation_date=self.when.date() - timedelta(days=30),
        )
        transaction = self.OldTransaction.objects.create(
            id=uuid.UUID("01234567-89ab-cdef-0123-456789abcdef"), user_id=self.user.pk,
            type="AI_USAGE", amount=-12, balance_before=35, balance_after=23,
            action="CHAT", reference_lot_id=daily.pk,
            lot_breakdown=[{"lot_id": str(purchased.pk), "amount": 6, "source": "PURCHASE"},
                           {"lot_id": str(daily.pk), "amount": 6, "source": "DAILY_FREE"}],
            description="Historical use", metadata={"request_id": "old-request"},
        )
        package = self.OldPackage.objects.create(
            id=101, name="Legacy package", credits=50, price_naira=1500, is_active=True,
        )
        self.OldLot.objects.all().update(created_at=self.when, updated_at=self.when)
        self.OldTransaction.objects.all().update(created_at=self.when)
        self.OldPackage.objects.all().update(created_at=self.when, updated_at=self.when)
        return purchased, daily, transaction, package

    def test_dry_run_reports_active_balance_without_changing_any_table(self):
        self.source_ledger()
        before = list(self.OldLot.objects.values())
        report = transfer_legacy_credits()
        self.assertEqual(report["active_credit_balance"], 23)
        self.assertEqual((report["lots"], report["transactions"], report["packages_archived_only"]), (3, 1, 1))
        self.assertEqual(report["status"], "ready")
        for model in (CreditLot, CreditTransaction, CreditPackage, LegacyCreditRecord):
            self.assertFalse(model.objects.exists())
        self.assertEqual(before, list(self.OldLot.objects.values()))

    def test_transfer_preserves_history_and_full_precision_archives_all_original_fields(self):
        purchased, daily, old_tx, _ = self.source_ledger()
        before = {table: list(model.objects.values()) for table, model in zip(
            SOURCE_TABLES, (self.OldLot, self.OldTransaction, self.OldPackage)
        )}
        report = transfer_legacy_credits(apply=True)
        self.assertEqual(report["status"], "transferred-and-verified")
        self.assertEqual(LegacyCreditRecord.objects.count(), 5)
        self.assertEqual(CreditLot.objects.count(), 3)
        self.assertEqual(CreditTransaction.objects.count(), 1)
        self.assertFalse(CreditPackage.objects.exists())
        archived = LegacyCreditRecord.objects.get(source_table=LOT_TABLE, source_pk="101")
        self.assertEqual(archived.payload["purchase_reference"], "old-payment-reference")
        self.assertIn("123456", archived.payload["updated_at"])
        self.assertEqual(CreditLot.objects.get(pk=archived.target_pk).created_at, self.when)
        tx = CreditTransaction.objects.get()
        self.assertEqual((tx.amount, tx.balance_before, tx.balance_after), (-12, 35, 23))
        self.assertEqual(tx.created_at, self.when)
        self.assertEqual(tx.reference_id, f"legacy-learning:{old_tx.pk}")
        self.assertEqual(tx.metadata["request_id"], "old-request")
        lot_map = {record.source_pk: record.target_pk for record in LegacyCreditRecord.objects.filter(source_table=LOT_TABLE)}
        self.assertEqual(tx.metadata[PROVENANCE_KEY]["reference_lot_id"], lot_map[str(daily.pk)])
        self.assertEqual(tx.metadata[PROVENANCE_KEY]["lot_breakdown"][0]["lot_id"], str(lot_map[str(purchased.pk)]))
        package = LegacyCreditRecord.objects.get(source_table=PACKAGE_TABLE)
        self.assertEqual(package.payload["price_naira"], 1500)
        self.assertEqual(package.target_model, "")
        self.assertIsNone(package.target_pk)
        after = {table: list(model.objects.values()) for table, model in zip(
            SOURCE_TABLES, (self.OldLot, self.OldTransaction, self.OldPackage)
        )}
        self.assertEqual(before, after)

    def test_unchanged_rerun_is_noop_with_no_duplicate_credits(self):
        self.source_ledger()
        transfer_legacy_credits(apply=True)
        before = list(LegacyCreditRecord.objects.values())
        for apply in (False, True):
            report = transfer_legacy_credits(apply=apply)
            self.assertEqual(report["status"], "already-transferred-and-verified")
        self.assertEqual(before, list(LegacyCreditRecord.objects.values()))
        self.assertEqual(CreditLot.objects.count(), 3)

    def test_nonempty_destination_is_never_merged_or_overwritten(self):
        self.source_ledger()
        existing = CreditLot.objects.create(user=self.user, source="PURCHASE", original_amount=5, remaining_amount=5)
        for apply in (False, True):
            with self.assertRaisesRegex(LegacyTransferError, "not empty"):
                transfer_legacy_credits(apply=apply)
        existing.refresh_from_db()
        self.assertEqual(existing.remaining_amount, 5)
        self.assertFalse(LegacyCreditRecord.objects.exists())

    def test_changed_source_requires_reconciliation_without_additional_credits(self):
        self.source_ledger()
        transfer_legacy_credits(apply=True)
        self.OldLot.objects.filter(pk=101).update(remaining_amount=18)
        with self.assertRaisesRegex(LegacyTransferError, "Source rows changed"):
            transfer_legacy_credits(apply=True)
        self.assertEqual(CreditLot.objects.get(remaining_amount=19).original_amount, 25)

    def test_changed_destination_requires_reconciliation_without_overwriting_it(self):
        self.source_ledger()
        transfer_legacy_credits(apply=True)
        CreditLot.objects.filter(remaining_amount=19).update(remaining_amount=18)
        with self.assertRaisesRegex(LegacyTransferError, "destination rows changed"):
            transfer_legacy_credits(apply=True)
        self.assertTrue(CreditLot.objects.filter(remaining_amount=18).exists())

    def test_missing_or_added_source_rows_block_rerun(self):
        self.source_ledger()
        transfer_legacy_credits(apply=True)
        self.OldPackage.objects.all().delete()
        with self.assertRaisesRegex(LegacyTransferError, "Source rows differ"):
            transfer_legacy_credits()

    def test_failure_after_initial_insert_rolls_back_entire_import(self):
        self.source_ledger()
        with patch("credits.legacy_transfer._verify", side_effect=RuntimeError("verification failed")):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                transfer_legacy_credits(apply=True)
        self.assertFalse(CreditLot.objects.exists())
        self.assertFalse(CreditTransaction.objects.exists())
        self.assertFalse(LegacyCreditRecord.objects.exists())
        self.assertEqual(self.OldLot.objects.count(), 3)

    def test_already_dropped_rows_are_not_claimed_recoverable(self):
        self.recorder.record_applied(*DROP_MIGRATION)
        with self.assertRaisesRegex(LegacyTransferError, "cannot recover dropped rows"):
            transfer_legacy_credits(apply=True)
        self.assertFalse(LegacyCreditRecord.objects.exists())

    def test_pending_monthly_conversion_blocks_double_conversion_guessing(self):
        self.recorder.record_unapplied(*CONVERSION_MIGRATION)
        with self.assertRaisesRegex(LegacyTransferError, "0004 must already be applied"):
            transfer_legacy_credits(apply=True)

    def test_missing_archive_migration_requires_targeted_setup(self):
        self.recorder.record_unapplied(*TRANSFER_MIGRATION)
        with self.assertRaisesRegex(LegacyTransferError, "targeted credits.0003"):
            transfer_legacy_credits(apply=True)

    def test_expired_rows_are_preserved_without_reactivating_them(self):
        self.source_ledger()
        transfer_legacy_credits(apply=True)
        expired = CreditLot.objects.get(remaining_amount=7)
        self.assertEqual(expired.expires_at, self.when)
        self.assertFalse(expired.is_valid)

    def test_invalid_lot_balance_blocks_all_writes(self):
        self.source_ledger()
        self.OldLot.objects.filter(pk=101).update(remaining_amount=26)
        with self.assertRaisesRegex(LegacyTransferError, "invalid balance"):
            transfer_legacy_credits(apply=True)
        self.assertFalse(CreditLot.objects.exists())

    def test_foreign_user_lot_reference_blocks_all_writes(self):
        self.source_ledger()
        another = get_user_model().objects.create_user(username="another-legacy-user")
        self.OldLot.objects.filter(pk=101).update(user_id=another.pk)
        with self.assertRaisesRegex(LegacyTransferError, "another user"):
            transfer_legacy_credits(apply=True)
        self.assertFalse(CreditLot.objects.exists())

    def test_reserved_metadata_name_requires_review(self):
        self.source_ledger()
        self.OldTransaction.objects.update(metadata={PROVENANCE_KEY: "already exists"})
        with self.assertRaisesRegex(LegacyTransferError, "metadata cannot"):
            transfer_legacy_credits(apply=True)

    def test_empty_database_with_known_legacy_schema_is_safe_noop(self):
        report = transfer_legacy_credits(apply=True)
        self.assertEqual(report["active_credit_balance"], 0)
        self.assertFalse(LegacyCreditRecord.objects.exists())

    def test_command_requires_explicit_paused_writes_confirmation(self):
        with self.assertRaisesRegex(CommandError, "confirm-writes-paused"):
            call_command("transfer_legacy_credits", apply=True, stdout=StringIO())
        self.assertFalse(CreditLot.objects.exists())

    def test_command_dry_run_and_apply_emit_only_summary_counts(self):
        self.source_ledger()
        for apply in (False, True):
            output = StringIO()
            call_command("transfer_legacy_credits", apply=apply, confirm_writes_paused=apply, stdout=output)
            self.assertIn('"active_credit_balance": 23', output.getvalue())
            self.assertNotIn("old-payment-reference", output.getvalue())
            self.assertNotIn(self.user.username, output.getvalue())

    def test_command_redacts_unexpected_driver_errors(self):
        error = "postgresql://private-user:private-password@private-host/db"
        with patch("credits.management.commands.transfer_legacy_credits.transfer_legacy_credits", side_effect=RuntimeError(error)):
            with self.assertRaises(CommandError) as caught:
                call_command("transfer_legacy_credits", stdout=StringIO())
        self.assertNotIn(error, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
