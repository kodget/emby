from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models import Q
from .models import CreditLot, CreditTransaction, TransactionType, CreditSource
from accounts.models import SubscriptionTier
from .config import FREE_DAILY_CREDITS, PRO_DAILY_CREDITS
from django.db import transaction

@shared_task
def allocate_daily_credits():
    """
    Runs daily at midnight.
    Grants role-based credits:
      - Class Head: 150 daily (up to 4500 monthly)
      - Material Uploader: 100 daily (up to 3000 monthly)
      - Premium: 60 daily (up to 1800 monthly)
      - Free: 20 daily (up to 600 monthly)
    Unused credits roll over and are not wiped out.
    """
    from .services import CreditManager
    users = User.objects.filter(is_active=True).select_related('profile')
    
    for user in users:
        try:
            CreditManager.ensure_daily_allocation(user)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed allocating daily credits for user %s: %s", user.id, e)

@shared_task
def expiration_cleanup():
    """
    Cleans up any other expired lots (e.g. promotional) and records a transaction.
    (Purchases don't expire based on models config, but if they did we'd handle it here)
    """
    now = timezone.now()
    user_ids = CreditLot.objects.filter(
        remaining_amount__gt=0, expires_at__lte=now
    ).order_by().values_list("user_id", flat=True).distinct()

    for user_id in user_ids.iterator():
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user_id)
            expired_lots = list(CreditLot.objects.select_for_update().filter(
                user=user, remaining_amount__gt=0, expires_at__lte=now
            ).order_by("expires_at", "pk"))
            balance = CreditLot.objects.filter(
                user=user, remaining_amount__gt=0
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            ).aggregate(total=Sum("remaining_amount"))["total"] or 0
            balance += sum(lot.remaining_amount for lot in expired_lots)

            for lot in expired_lots:
                amount = lot.remaining_amount
                lot.remaining_amount = 0
                lot.save(update_fields=["remaining_amount"])

                CreditTransaction.objects.create(
                    user=user,
                    type=TransactionType.EXPIRATION,
                    amount=-amount,
                    balance_before=balance,
                    balance_after=balance - amount,
                    action="EXPIRATION",
                    description=f"Expired {amount} credits from lot {lot.id}",
                )
                balance -= amount
