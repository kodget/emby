from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
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
    with transaction.atomic():
        expired_lots = CreditLot.objects.filter(
            remaining_amount__gt=0,
            expires_at__lte=timezone.now()
        )
        
        for lot in expired_lots:
            # We must be careful to calculate balance correctly per user
            balance_before = sum(l.remaining_amount for l in CreditLot.objects.filter(
                user=lot.user, 
                remaining_amount__gt=0
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))) + lot.remaining_amount
            
            amount = lot.remaining_amount
            lot.remaining_amount = 0
            lot.save(update_fields=['remaining_amount'])
            
            CreditTransaction.objects.create(
                user=lot.user,
                type=TransactionType.EXPIRATION,
                amount=-amount,
                balance_before=balance_before,
                balance_after=balance_before - amount,
                action="EXPIRATION",
                description=f"Expired {amount} credits from lot {lot.id}"
            )
