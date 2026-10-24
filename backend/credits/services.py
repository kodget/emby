import logging

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import CreditLot, CreditTransaction, TransactionType, CreditSource
from .config import get_action_reserve_credits, TOKENS_PER_CREDIT
from accounts.models import SubscriptionTier

class InsufficientCreditsError(Exception):
    pass


logger = logging.getLogger(__name__)


def _lock_user(user):
    User.objects.select_for_update().get(pk=user.pk)


def _credit_balance(user, *, now=None):
    now = now or timezone.now()
    valid_lots = CreditLot.objects.filter(
        user=user, remaining_amount__gt=0
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return valid_lots.aggregate(total=Sum("remaining_amount"))["total"] or 0


class CreditManager:
    @staticmethod
    def get_user_balance(user, ensure_allocation: bool = True) -> int:
        if ensure_allocation and user and user.is_authenticated:
            if user.profile.subscription_tier == SubscriptionTier.PLATINUM:
                return 999999
            CreditManager.ensure_daily_allocation(user)

        return _credit_balance(user)

    @staticmethod
    @transaction.atomic
    def ensure_daily_allocation(user) -> int:
        """
        Ensures the user has received their daily credit drop for today.
        Respects role-specific daily allowances and monthly caps with rollover.
        """
        from .config import get_user_credit_tier
        from datetime import timedelta

        _lock_user(user)
        daily_amount, monthly_cap, source, tier_name = get_user_credit_tier(user)
        if tier_name == "platinum":
            return 999999

        now = timezone.now()
        local_now = timezone.localtime(now)
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        daily_sources = [
            CreditSource.DAILY_FREE,
            CreditSource.DAILY_PRO,
            CreditSource.DAILY_CLASS_HEAD,
            CreditSource.DAILY_MATERIAL_UPLOADER,
        ]

        # Check if user already got an allocation today
        already_allocated_today = CreditLot.objects.filter(
            user=user,
            source__in=daily_sources,
            granted_at__gte=today_start,
            granted_at__lt=tomorrow_start,
        ).exists()

        if not already_allocated_today:
            # Check how much has been granted this calendar month
            month_granted = CreditTransaction.objects.filter(
                user=user,
                type=TransactionType.DAILY_ALLOCATION,
                created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0

            if month_granted < monthly_cap:
                grant_amount = min(daily_amount, monthly_cap - month_granted)
                if grant_amount > 0:
                    current_balance = _credit_balance(user, now=now)

                    # Rollover enabled: credits expire after 60 days, never wiped out daily
                    expires_at = now + timedelta(days=60)

                    CreditLot.objects.create(
                        user=user,
                        source=source,
                        original_amount=grant_amount,
                        remaining_amount=grant_amount,
                        granted_at=now,
                        expires_at=expires_at,
                    )

                    CreditTransaction.objects.create(
                        user=user,
                        type=TransactionType.DAILY_ALLOCATION,
                        amount=grant_amount,
                        balance_before=current_balance,
                        balance_after=current_balance + grant_amount,
                        action="DAILY_DROP",
                        description=f"Granted {grant_amount} daily credits ({tier_name.replace('_', ' ').title()} tier, rollover enabled)"
                    )
        return CreditManager.get_user_balance(user, ensure_allocation=False)

    @staticmethod
    @transaction.atomic
    def reserve_credits(user, action: str, reference_id: str = "") -> dict:
        """
        Reserves estimated credits for an AI action.
        Returns a dict: {"reservation_id": ..., "reserved_amount": ...}
        """
        if user.profile.subscription_tier == SubscriptionTier.PLATINUM:
            # Platinum users don't need real deductions, but we'll record a 0 cost transaction or just allow it.
            return {"reservation_id": reference_id or "plat_res", "reserved_amount": 0}

        CreditManager.ensure_daily_allocation(user)
        reserve_amount = get_action_reserve_credits(action)
        _lock_user(user)

        if reference_id:
            existing = CreditTransaction.objects.select_for_update().filter(
                user=user,
                type=TransactionType.AI_USAGE,
                reference_id=reference_id,
            ).first()
            if existing:
                if existing.action != f"RESERVE_{action}":
                    raise ValueError("This credit reference was already used for a different action.")
                return {
                    "reservation_id": str(existing.pk),
                    "reserved_amount": abs(existing.amount),
                    "action": action,
                }
        
        # Lock lots for this user to prevent race conditions
        valid_lots = list(CreditLot.objects.filter(
            user=user,
            remaining_amount__gt=0
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_for_update().order_by('expires_at')) # FEFO: oldest expiring first (nulls last in postgres usually, but let's be careful. In SQLite nulls are first or last depending on config. Actually, let's sort properly)

        # In Python, we can sort to ensure expiring lots are first, and non-expiring are last
        valid_lots.sort(key=lambda x: (x.expires_at is None, x.expires_at))

        total_available = sum(lot.remaining_amount for lot in valid_lots)
        if total_available < reserve_amount:
            raise InsufficientCreditsError(f"Insufficient credits. Required: {reserve_amount}, Available: {total_available}")

        balance_before = total_available
        remaining_to_deduct = reserve_amount

        for lot in valid_lots:
            if remaining_to_deduct <= 0:
                break
            deduction = min(lot.remaining_amount, remaining_to_deduct)
            lot.remaining_amount -= deduction
            lot.save(update_fields=['remaining_amount'])
            remaining_to_deduct -= deduction

        balance_after = balance_before - reserve_amount

        txn = CreditTransaction.objects.create(
            user=user,
            type=TransactionType.AI_USAGE,
            amount=-reserve_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            action=f"RESERVE_{action}",
            reference_id=reference_id,
            description=f"Reserved {reserve_amount} credits for {action}",
            metadata={"settlement_status": "RESERVED"},
        )

        return {"reservation_id": str(txn.id), "reserved_amount": reserve_amount, "action": action}

    @staticmethod
    @transaction.atomic
    def commit_usage(user, reservation: dict, total_tokens: int):
        """
        Calculates exact cost from tokens, refunds any unused reserved credits.
        """
        if user.profile.subscription_tier == SubscriptionTier.PLATINUM:
            return

        if type(total_tokens) is not int or total_tokens < 0:
            raise ValueError("total_tokens must be a nonnegative integer.")

        _lock_user(user)
        try:
            reserve_txn = CreditTransaction.objects.select_for_update().get(
                pk=reservation["reservation_id"],
                user=user,
                type=TransactionType.AI_USAGE,
                action=f"RESERVE_{reservation['action']}",
            )
        except (CreditTransaction.DoesNotExist, KeyError) as exc:
            raise ValueError("Unknown credit reservation.") from exc
        if reservation.get("reserved_amount") != abs(reserve_txn.amount):
            raise ValueError("Credit reservation amount does not match the ledger.")

        metadata = reserve_txn.metadata or {}
        if metadata.get("settlement_status", "RESERVED") != "RESERVED":
            return
        reserved_amount = abs(reserve_txn.amount)
        action = reservation["action"]
        
        # Calculate actual cost
        actual_cost = max(1, (total_tokens + TOKENS_PER_CREDIT - 1) // TOKENS_PER_CREDIT)
        
        refund_amount = reserved_amount - actual_cost
        
        if refund_amount > 0:
            CreditManager._issue_refund(
                user,
                refund_amount,
                action=f"REFUND_PARTIAL_{action}",
                description=f"Refunded {refund_amount} unused reserved credits for {action}",
                reference_id=f"refund:{reserve_txn.pk}",
                metadata={"reservation_id": str(reserve_txn.pk)},
            )
        elif refund_amount < 0:
            extra_needed = -refund_amount
            available = _credit_balance(user)
            collected = min(extra_needed, available)
            if collected:
                CreditManager._deduct_credits(user, collected, action=f"EXTRA_{action}")
            if collected < extra_needed:
                logger.warning(
                    "Credit usage exceeded reservation for user %s by %s credits",
                    user.pk,
                    extra_needed - collected,
                )

        reserve_txn.metadata = {
            **metadata,
            "settlement_status": "COMMITTED",
            "total_tokens": total_tokens,
            "actual_cost": actual_cost,
        }
        if refund_amount < 0:
            reserve_txn.metadata["uncollected_credits"] = max(0, -refund_amount - collected)
        reserve_txn.save(update_fields=["metadata"])

    @staticmethod
    @transaction.atomic
    def refund_credits(
        user, amount: int, action: str = "REFUND", description: str = "",
        reservation_id: str = "",
    ):
        if type(amount) is not int or amount < 0:
            raise ValueError("Refund amount must be a nonnegative integer.")
        if amount == 0:
            return
        if not reservation_id:
            raise ValueError("A credit reservation is required for refunds.")

        _lock_user(user)
        try:
            reservation = CreditTransaction.objects.select_for_update().get(
                pk=reservation_id,
                user=user,
                type=TransactionType.AI_USAGE,
                action__startswith="RESERVE_",
            )
        except CreditTransaction.DoesNotExist as exc:
            raise ValueError("Unknown credit reservation.") from exc
        metadata = reservation.metadata or {}
        if metadata.get("settlement_status", "RESERVED") != "RESERVED":
            return
        if amount != abs(reservation.amount):
            raise ValueError("A reservation must be refunded in full.")

        CreditManager._issue_refund(
            user,
            amount,
            action=action,
            description=description,
            reference_id=f"refund:{reservation_id}" if reservation_id else "",
            metadata={"reservation_id": reservation_id},
        )
        reservation.metadata = {
            **(reservation.metadata or {}),
            "settlement_status": "REFUNDED",
            "refund_amount": amount,
        }
        reservation.save(update_fields=["metadata"])

    @staticmethod
    def _issue_refund(
        user, amount: int, *, action: str, description: str,
        reference_id: str = "", metadata: dict | None = None,
    ):
        balance_before = _credit_balance(user)
        CreditLot.objects.create(
            user=user,
            source=CreditSource.REFUND,
            original_amount=amount,
            remaining_amount=amount,
            expires_at=None,
        )

        balance_after = balance_before + amount
        CreditTransaction.objects.create(
            user=user,
            type=TransactionType.REFUND,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            action=action,
            reference_id=reference_id,
            description=description,
            metadata=metadata or {},
        )

    @staticmethod
    @transaction.atomic
    def _deduct_credits(user, amount: int, action: str):
        if amount <= 0:
            return
        _lock_user(user)
        valid_lots = list(CreditLot.objects.filter(
            user=user,
            remaining_amount__gt=0
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_for_update())
        
        valid_lots.sort(key=lambda x: (x.expires_at is None, x.expires_at))
        
        total_available = sum(lot.remaining_amount for lot in valid_lots)
        if total_available < amount:
            raise InsufficientCreditsError(f"Insufficient credits.")

        balance_before = total_available
        remaining_to_deduct = amount

        for lot in valid_lots:
            if remaining_to_deduct <= 0:
                break
            deduction = min(lot.remaining_amount, remaining_to_deduct)
            lot.remaining_amount -= deduction
            lot.save(update_fields=['remaining_amount'])
            remaining_to_deduct -= deduction
            
        CreditTransaction.objects.create(
            user=user,
            type=TransactionType.AI_USAGE,
            amount=-amount,
            balance_before=balance_before,
            balance_after=balance_before - amount,
            action=action
        )
