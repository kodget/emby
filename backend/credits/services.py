from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import CreditLot, CreditTransaction, TransactionType, CreditSource
from .config import get_action_reserve_credits, TOKENS_PER_CREDIT
from accounts.models import SubscriptionTier

class InsufficientCreditsError(Exception):
    pass

class CreditManager:
    @staticmethod
    def get_user_balance(user, ensure_allocation: bool = True) -> int:
        if ensure_allocation and user and user.is_authenticated:
            try:
                CreditManager.ensure_daily_allocation(user)
            except Exception as e:
                # Log error but don't break balance query
                import logging
                logging.getLogger(__name__).warning("Failed in ensure_daily_allocation: %s", e)

        valid_lots = CreditLot.objects.filter(
            user=user,
            remaining_amount__gt=0
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        return valid_lots.aggregate(total=Sum('remaining_amount'))['total'] or 0

    @staticmethod
    @transaction.atomic
    def ensure_daily_allocation(user) -> int:
        """
        Ensures the user has received their daily credit drop for today.
        Respects role-specific daily allowances and monthly caps with rollover.
        """
        from .config import get_user_credit_tier
        from datetime import timedelta

        daily_amount, monthly_cap, source, tier_name = get_user_credit_tier(user)
        if tier_name == "platinum":
            return 999999

        today = timezone.now().date()
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
            granted_at__date=today
        ).exists()

        if not already_allocated_today:
            # Check how much has been granted this calendar month
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_granted = CreditTransaction.objects.filter(
                user=user,
                type=TransactionType.DAILY_ALLOCATION,
                created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0

            if month_granted < monthly_cap:
                grant_amount = min(daily_amount, monthly_cap - month_granted)
                if grant_amount > 0:
                    current_balance = CreditManager.get_user_balance(user, ensure_allocation=False)

                    # Rollover enabled: credits expire after 60 days, never wiped out daily
                    expires_at = timezone.now() + timedelta(days=60)

                    CreditLot.objects.create(
                        user=user,
                        source=source,
                        original_amount=grant_amount,
                        remaining_amount=grant_amount,
                        expires_at=expires_at
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

        reserve_amount = get_action_reserve_credits(action)
        
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
            description=f"Reserved {reserve_amount} credits for {action}"
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

        reserved_amount = reservation["reserved_amount"]
        action = reservation["action"]
        
        # Calculate actual cost
        actual_cost = max(1, (total_tokens + TOKENS_PER_CREDIT - 1) // TOKENS_PER_CREDIT)
        
        refund_amount = reserved_amount - actual_cost
        
        if refund_amount > 0:
            CreditManager.refund_credits(user, refund_amount, action=f"REFUND_PARTIAL_{action}", description=f"Refunded {refund_amount} unused reserved credits for {action}")
        elif refund_amount < 0:
            # If actual cost exceeded reservation somehow, we should technically deduct more.
            # But let's just log a warning or deduct it if we can. For now, we will deduct the difference if possible.
            extra_needed = -refund_amount
            try:
                CreditManager._deduct_credits(user, extra_needed, action=f"EXTRA_{action}")
            except InsufficientCreditsError:
                # They went negative implicitly. We won't block the result, but their balance goes to 0.
                CreditManager._deduct_credits(user, CreditManager.get_user_balance(user), action=f"EXTRA_{action}_MAX")

    @staticmethod
    @transaction.atomic
    def refund_credits(user, amount: int, action: str = "REFUND", description: str = ""):
        if amount <= 0:
            return
            
        balance_before = CreditManager.get_user_balance(user)
        
        # We can add this back to a generic REFUND lot or create a new lot.
        # Creating a new non-expiring lot is simplest for partial refunds.
        CreditLot.objects.create(
            user=user,
            source=CreditSource.REFUND,
            original_amount=amount,
            remaining_amount=amount,
            expires_at=None # Refunds don't expire for now
        )

        balance_after = balance_before + amount
        
        CreditTransaction.objects.create(
            user=user,
            type=TransactionType.REFUND,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            action=action,
            description=description
        )

    @staticmethod
    @transaction.atomic
    def _deduct_credits(user, amount: int, action: str):
        if amount <= 0:
            return
            
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
