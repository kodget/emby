from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassGroup, School
from credits.config import (
    CLASS_HEAD_DAILY_CREDITS, CLASS_HEAD_MONTHLY_CAP, FREE_DAILY_CREDITS,
    FREE_MONTHLY_CAP, MATERIAL_UPLOADER_DAILY_CREDITS,
    MATERIAL_UPLOADER_MONTHLY_CAP, PRO_DAILY_CREDITS, PRO_MONTHLY_CAP,
    get_user_credit_tier,
)
from credits import views
from credits.models import (
    CreditLot, CreditPackage, CreditPurchase, CreditSource, CreditTransaction,
    TransactionType,
)
from credits.services import CreditManager, InsufficientCreditsError
from credits.tasks import expiration_cleanup


class CreditAccountingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("credit-student", email="student@example.test")

    def add_lot(self, amount=10, *, source=CreditSource.PURCHASE, expires_at=None):
        return CreditLot.objects.create(
            user=self.user,
            source=source,
            original_amount=amount,
            remaining_amount=amount,
            expires_at=expires_at,
        )

    def api(self, view, method, path, payload):
        request = getattr(APIRequestFactory(), method)(path, payload, format="json")
        force_authenticate(request, self.user)
        return view(request)

    def test_reservation_retry_and_usage_settlement_are_idempotent(self):
        self.add_lot()
        with patch.object(CreditManager, "ensure_daily_allocation", return_value=10), patch(
            "credits.services.get_action_reserve_credits", return_value=3
        ):
            reservation = CreditManager.reserve_credits(self.user, "CHAT", "request-1")
            replay = CreditManager.reserve_credits(self.user, "CHAT", "request-1")

        self.assertEqual(replay, reservation)
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 7)
        self.assertEqual(
            CreditTransaction.objects.filter(type=TransactionType.AI_USAGE).count(), 1
        )

        CreditManager.commit_usage(self.user, reservation, 1000)
        CreditManager.commit_usage(self.user, reservation, 1000)
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 9)
        self.assertEqual(
            CreditTransaction.objects.filter(type=TransactionType.REFUND).count(), 1
        )
        self.assertEqual(
            CreditTransaction.objects.get(pk=reservation["reservation_id"]).metadata[
                "settlement_status"
            ],
            "COMMITTED",
        )

    def test_failed_action_refund_is_applied_once_and_cannot_exceed_reservation(self):
        self.add_lot()
        with patch.object(CreditManager, "ensure_daily_allocation", return_value=10), patch(
            "credits.services.get_action_reserve_credits", return_value=3
        ):
            reservation = CreditManager.reserve_credits(self.user, "CHAT")

        CreditManager.refund_credits(
            self.user, 3, action="REFUND_CHAT_ERROR",
            reservation_id=reservation["reservation_id"],
        )
        CreditManager.refund_credits(
            self.user, 3, action="REFUND_CHAT_ERROR",
            reservation_id=reservation["reservation_id"],
        )
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 10)
        self.assertEqual(CreditTransaction.objects.filter(type=TransactionType.REFUND).count(), 1)

        with patch.object(CreditManager, "ensure_daily_allocation", return_value=10), patch(
            "credits.services.get_action_reserve_credits", return_value=3
        ):
            another = CreditManager.reserve_credits(self.user, "CHAT")
        with self.assertRaises(ValueError):
            CreditManager.refund_credits(
                self.user, 4, reservation_id=another["reservation_id"]
            )

    def test_first_reservation_grants_daily_allowance_and_platinum_balance_is_unlimited(self):
        reservation = CreditManager.reserve_credits(self.user, "CHAT")
        self.assertEqual(reservation["reserved_amount"], 1)
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 19)

        self.user.profile.subscription_tier = "platinum"
        self.user.profile.save(update_fields=["subscription_tier"])
        self.assertEqual(CreditManager.get_user_balance(self.user), 999999)
        CreditManager.refund_credits(self.user, 0, reservation_id="plat_res")

    def test_confirmed_tier_allowances_and_expired_premium_downgrade(self):
        profile = self.user.profile
        self.assertEqual(
            get_user_credit_tier(self.user)[:2], (FREE_DAILY_CREDITS, FREE_MONTHLY_CAP)
        )

        profile.subscription_tier = "premium"
        profile.subscription_expires_at = timezone.now() + timedelta(days=1)
        profile.save(update_fields=["subscription_tier", "subscription_expires_at"])
        self.assertEqual(
            get_user_credit_tier(self.user)[:2], (PRO_DAILY_CREDITS, PRO_MONTHLY_CAP)
        )

        profile.subscription_expires_at = timezone.now() - timedelta(seconds=1)
        profile.save(update_fields=["subscription_expires_at"])
        self.assertEqual(
            get_user_credit_tier(self.user)[:2], (FREE_DAILY_CREDITS, FREE_MONTHLY_CAP)
        )

        profile.subscription_tier = "free"
        profile.class_role = "material_uploader"
        profile.save(update_fields=["subscription_tier", "class_role"])
        self.assertEqual(
            get_user_credit_tier(self.user)[:2],
            (MATERIAL_UPLOADER_DAILY_CREDITS, MATERIAL_UPLOADER_MONTHLY_CAP),
        )

        school = School.objects.create(name="Credit policy school")
        group = ClassGroup.objects.create(school=school, set_name="Year 2", code="728194")
        profile.class_role = "class_head"
        profile.class_head_verified = True
        profile.class_group = group
        profile.save(update_fields=["class_role", "class_head_verified", "class_group"])
        self.assertEqual(
            get_user_credit_tier(self.user)[:2],
            (CLASS_HEAD_DAILY_CREDITS, CLASS_HEAD_MONTHLY_CAP),
        )
        profile.class_head_verified = False
        profile.save(update_fields=["class_head_verified"])
        self.assertEqual(
            get_user_credit_tier(self.user)[:2], (FREE_DAILY_CREDITS, FREE_MONTHLY_CAP)
        )

    def test_daily_grant_uses_configured_local_date_and_is_idempotent(self):
        first_run = datetime(2026, 10, 31, 23, 30, tzinfo=dt_timezone.utc)
        next_local_day = datetime(2026, 11, 1, 23, 30, tzinfo=dt_timezone.utc)

        with timezone.override("Africa/Lagos"), patch(
            "credits.services.timezone.now", return_value=first_run
        ):
            self.assertEqual(CreditManager.ensure_daily_allocation(self.user), 20)
            self.assertEqual(CreditManager.ensure_daily_allocation(self.user), 20)
            lot = CreditLot.objects.get(user=self.user)
            self.assertEqual(lot.expires_at, first_run + timedelta(days=60))

        with timezone.override("Africa/Lagos"), patch(
            "credits.services.timezone.now", return_value=next_local_day
        ):
            self.assertEqual(CreditManager.ensure_daily_allocation(self.user), 40)

        self.assertEqual(
            CreditTransaction.objects.filter(type=TransactionType.DAILY_ALLOCATION).count(), 2
        )

    def test_spending_uses_soonest_expiring_lot_before_nonexpiring_purchases(self):
        now = timezone.now()
        expiring = self.add_lot(
            2, source=CreditSource.DAILY_FREE, expires_at=now + timedelta(days=1)
        )
        purchased = self.add_lot(3)
        with patch.object(CreditManager, "ensure_daily_allocation", return_value=5), patch(
            "credits.services.get_action_reserve_credits", return_value=3
        ):
            CreditManager.reserve_credits(self.user, "CHAT")

        expiring.refresh_from_db()
        purchased.refresh_from_db()
        self.assertEqual(expiring.remaining_amount, 0)
        self.assertEqual(purchased.remaining_amount, 2)

    def test_daily_grant_monthly_cap_uses_local_month_boundary(self):
        allocation = CreditTransaction.objects.create(
            user=self.user,
            type=TransactionType.DAILY_ALLOCATION,
            amount=20,
            balance_before=0,
            balance_after=20,
            action="DAILY_DROP",
        )
        CreditTransaction.objects.filter(pk=allocation.pk).update(
            created_at=datetime(2026, 10, 31, 23, 30, tzinfo=dt_timezone.utc)
        )
        now = datetime(2026, 10, 31, 23, 45, tzinfo=dt_timezone.utc)
        with timezone.override("Africa/Lagos"), patch(
            "credits.services.timezone.now", return_value=now
        ), patch(
            "credits.config.get_user_credit_tier",
            return_value=(20, 25, CreditSource.DAILY_FREE, "free"),
        ):
            self.assertEqual(CreditManager.ensure_daily_allocation(self.user), 5)

    def test_expiry_cleanup_records_multiple_lot_balances_and_replays_safely(self):
        expired_at = timezone.now() - timedelta(seconds=1)
        self.add_lot(5, source=CreditSource.PROMOTIONAL, expires_at=expired_at)
        self.add_lot(7, source=CreditSource.DAILY_FREE, expires_at=expired_at)
        self.add_lot(3)

        expiration_cleanup()
        expiration_cleanup()

        expirations = list(
            CreditTransaction.objects.filter(type=TransactionType.EXPIRATION).order_by("id")
        )
        self.assertEqual(len(expirations), 2)
        self.assertEqual(
            [(row.amount, row.balance_before, row.balance_after) for row in expirations],
            [(-5, 15, 10), (-7, 10, 3)],
        )
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 3)

    def test_provider_refund_reconciliation_is_dry_run_first_audited_and_never_negative(self):
        purchase = CreditPurchase.objects.create(
            reference="purchase-to-refund",
            user=self.user,
            package_id_snapshot=7,
            package_name="Purchased pack",
            credits=10,
            amount_kobo=85000,
            status=CreditPurchase.Status.CREDITED,
        )
        purchased_lot = self.add_lot(10)
        purchased_lot.purchase = purchase
        purchased_lot.remaining_amount = 4
        purchased_lot.save(update_fields=["purchase", "remaining_amount"])
        self.add_lot(3)

        args = [
            "--reference", purchase.reference,
            "--provider-refund-reference", "provider-refund-1",
            "--amount-kobo", "85000",
        ]
        dry_run = StringIO()
        call_command("reconcile_credit_purchase_refund", *args, stdout=dry_run)
        self.assertIn('"apply": false', dry_run.getvalue())
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 7)
        self.assertFalse(CreditTransaction.objects.filter(action="PURCHASE_REFUND_RECONCILIATION").exists())

        with self.assertRaisesRegex(CommandError, "confirm-provider-refund"):
            call_command(
                "reconcile_credit_purchase_refund", *args, apply=True, stdout=StringIO()
            )
        output = StringIO()
        call_command(
            "reconcile_credit_purchase_refund", *args, apply=True,
            confirm_provider_refund=True, stdout=output,
        )
        self.assertIn('"credits_to_recover": 4', output.getvalue())
        self.assertIn('"credits_already_spent": 6', output.getvalue())
        self.assertIn('"balance_after": 3', output.getvalue())

        purchase.refresh_from_db()
        purchased_lot.refresh_from_db()
        self.assertEqual(purchase.status, CreditPurchase.Status.REFUNDED)
        self.assertEqual(purchase.refunded_amount_kobo, 85000)
        self.assertEqual(purchased_lot.remaining_amount, 0)
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 3)
        transaction = CreditTransaction.objects.get(action="PURCHASE_REFUND_RECONCILIATION")
        self.assertEqual((transaction.amount, transaction.balance_before, transaction.balance_after), (-4, 7, 3))
        self.assertEqual(transaction.metadata["already_spent_credits"], 6)

        repeated = StringIO()
        call_command(
            "reconcile_credit_purchase_refund", *args, apply=True,
            confirm_provider_refund=True, stdout=repeated,
        )
        self.assertIn('"already_reconciled": true', repeated.getvalue())
        self.assertIn('"credits_already_spent": 6', repeated.getvalue())
        self.assertIn('"credits_to_recover": 4', repeated.getvalue())
        self.assertEqual(CreditTransaction.objects.filter(action="PURCHASE_REFUND_RECONCILIATION").count(), 1)

    def test_purchase_intent_snapshots_package_and_verification_is_exact_and_idempotent(self):
        package = CreditPackage.objects.create(name="Starter", credits=500, price=800)
        initialization = {
            "status": True,
            "data": {
                "authorization_url": "https://pay.example.test/authorize",
                "access_code": "access-1",
                "reference": "credit-payment-1",
            },
        }
        with patch("credits.views.requests.post", return_value=Mock(
            raise_for_status=Mock(), json=Mock(return_value=initialization)
        )):
            response = self.api(views.init_purchase, "post", "/purchase/", {"package_id": package.pk})

        self.assertEqual(response.status_code, 200)
        purchase = CreditPurchase.objects.get(reference="credit-payment-1")
        package.credits = 700
        package.price = 1000
        package.save(update_fields=["credits", "price"])

        verified = {
            "status": True,
            "data": {
                "status": "success",
                "reference": "credit-payment-1",
                "id": 991,
                "amount": 85000,
                "currency": "NGN",
                "metadata": {
                    "type": "credit_purchase",
                    "user_id": self.user.pk,
                    "package_id": package.pk,
                    "credits": 500,
                    "amount_kobo": 85000,
                    "currency": "NGN",
                },
            },
        }
        with patch("credits.views.requests.get", return_value=Mock(
            raise_for_status=Mock(), json=Mock(return_value=verified)
        )) as verify:
            response = self.api(
                views.verify_purchase, "post", "/verify-purchase/",
                {"reference": "credit-payment-1"},
            )
            self.assertEqual(response.status_code, 200)
            replay = self.api(
                views.verify_purchase, "post", "/verify-purchase/",
                {"reference": "credit-payment-1"},
            )

        self.assertEqual(replay.status_code, 200)
        self.assertEqual(response.data["credits_added"], 500)
        self.assertEqual(CreditLot.objects.get(source=CreditSource.PURCHASE).original_amount, 500)
        self.assertEqual(CreditTransaction.objects.filter(type=TransactionType.PURCHASE).count(), 1)
        self.assertEqual(verify.call_count, 1)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, CreditPurchase.Status.CREDITED)

    def test_purchase_rejects_amount_or_currency_mismatch_without_granting_credits(self):
        purchase = CreditPurchase.objects.create(
            reference="payment-invalid",
            user=self.user,
            package_id_snapshot=4,
            package_name="Snapshot",
            credits=500,
            amount_kobo=85000,
        )
        verification = {
            "status": "success",
            "reference": purchase.reference,
            "amount": 85000,
            "currency": "NGN",
            "metadata": {
                "type": "credit_purchase",
                "user_id": self.user.pk,
                "package_id": 4,
                "credits": 500,
                "amount_kobo": 85000,
                "currency": "NGN",
            },
        }
        for changed_field, changed_value in (("amount", 85001), ("currency", "USD")):
            payload = {"status": True, "data": {**verification, changed_field: changed_value}}
            with self.subTest(field=changed_field), patch(
                "credits.views.requests.get",
                return_value=Mock(raise_for_status=Mock(), json=Mock(return_value=payload)),
            ):
                response = self.api(
                    views.verify_purchase, "post", "/verify-purchase/",
                    {"reference": purchase.reference},
                )
                self.assertEqual(response.status_code, 400)

        self.assertFalse(CreditLot.objects.exists())
        self.assertFalse(CreditTransaction.objects.filter(type=TransactionType.PURCHASE).exists())
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, CreditPurchase.Status.PENDING)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks required")
class CreditReservationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("concurrent-credit-student")
        CreditLot.objects.create(
            user=self.user,
            source=CreditSource.DAILY_FREE,
            original_amount=1,
            remaining_amount=1,
            granted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=1),
        )

    def race(self, reference_ids):
        barrier = Barrier(len(reference_ids))

        def reserve(reference_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                try:
                    return CreditManager.reserve_credits(user, "CHAT", reference_id)["reservation_id"]
                except InsufficientCreditsError:
                    return "insufficient"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(reference_ids)) as pool:
            return list(pool.map(reserve, reference_ids))

    def test_simultaneous_distinct_reservations_cannot_spend_one_credit_twice(self):
        with patch("credits.services.get_action_reserve_credits", return_value=1):
            results = self.race(["parallel-a", "parallel-b"])

        self.assertEqual(results.count("insufficient"), 1)
        self.assertEqual(
            CreditTransaction.objects.filter(
                type=TransactionType.AI_USAGE, action="RESERVE_CHAT"
            ).count(),
            1,
        )
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 0)

    def test_simultaneous_replay_of_one_reference_returns_one_reservation(self):
        with patch("credits.services.get_action_reserve_credits", return_value=1):
            results = self.race(["parallel-same", "parallel-same"])

        self.assertEqual(results[0], results[1])
        self.assertEqual(
            CreditTransaction.objects.filter(
                type=TransactionType.AI_USAGE, action="RESERVE_CHAT"
            ).count(),
            1,
        )
        self.assertEqual(CreditManager.get_user_balance(self.user, ensure_allocation=False), 0)
