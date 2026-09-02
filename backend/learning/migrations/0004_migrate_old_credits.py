"""Data migration: convert old AICreditAccount monthly credits to new CreditLot system.

For each user with an AICreditAccount:
1. If they have remaining credits > 0, create a purchased lot (no expiry) with those credits
2. Create today's daily allocation (10 free / 60 premium)
"""

from django.db import migrations
from django.utils import timezone


def migrate_old_credits_to_lots(apps, schema_editor):
    CreditLot = apps.get_model('learning', 'CreditLot')
    CreditTransaction = apps.get_model('learning', 'CreditTransaction')
    AICreditAccount = apps.get_model('learning', 'AICreditAccount')
    
    # These are TextChoices values from models.py
    CREDIT_LOT_SOURCE = {
        'DAILY_FREE': 'DAILY_FREE',
        'DAILY_PRO': 'DAILY_PRO', 
        'PURCHASE': 'PURCHASE',
        'ADMIN': 'ADMIN',
        'PROMOTIONAL': 'PROMOTIONAL',
        'REFUND': 'REFUND',
    }
    
    CREDIT_TRANSACTION_TYPE = {
        'DAILY_ALLOCATION': 'DAILY_ALLOCATION',
        'AI_USAGE': 'AI_USAGE',
        'PURCHASE': 'PURCHASE',
        'REFUND': 'REFUND',
        'ADMIN_ADJUSTMENT': 'ADMIN_ADJUSTMENT',
        'EXPIRATION': 'EXPIRATION',
    }
    
    # Get all users with AICreditAccount
    accounts = AICreditAccount.objects.select_related('user').all()
    
    migrated_count = 0
    total_credits_migrated = 0
    
    for account in accounts:
        user = account.user
        
        # 1. Migrate remaining monthly credits as purchased credits (no expiry)
        remaining = max(0, account.allocated - account.used)
        if remaining > 0:
            # Create purchased lot for remaining credits
            purchased_lot = CreditLot.objects.create(
                user=user,
                source=CREDIT_LOT_SOURCE['PURCHASE'],
                original_amount=remaining,
                remaining_amount=remaining,
                granted_at=timezone.now(),
                expires_at=None,  # purchased credits never expire
                purchase_reference='MIGRATION_FROM_OLD_MONTHLY',
            )
            
            # Record transaction
            CreditTransaction.objects.create(
                user=user,
                type=CREDIT_TRANSACTION_TYPE['ADMIN_ADJUSTMENT'],
                amount=remaining,
                balance_before=0,
                balance_after=0,
                lot_breakdown=[{
                    'lot_id': str(purchased_lot.id),
                    'amount': remaining,
                    'source': CREDIT_LOT_SOURCE['PURCHASE'],
                    'expires_at': None,
                }],
                description=f'Migrated {remaining} credits from old monthly system',
                metadata={'migration': True, 'from_monthly_account': True}
            )
            
            total_credits_migrated += remaining
        
        # 2. Create today's daily allocation based on user's tier
        # Check user profile via related name
        try:
            profile = user.profile
            is_premium = profile.is_premium
        except:
            is_premium = False
        
        daily_amount = 60 if is_premium else 10
        source = CREDIT_LOT_SOURCE['DAILY_PRO'] if is_premium else CREDIT_LOT_SOURCE['DAILY_FREE']
        
        # Check if today's allocation already exists (shouldn't, but safe)
        today = timezone.now().date()
        existing_today = CreditLot.objects.filter(
            user=user,
            source=source,
            allocation_date=today,
        ).exists()
        
        if not existing_today:
            expires_at = timezone.now() + timezone.timedelta(days=30)
            daily_lot = CreditLot.objects.create(
                user=user,
                source=source,
                original_amount=daily_amount,
                remaining_amount=daily_amount,
                granted_at=timezone.now(),
                expires_at=expires_at,
                allocation_date=today,
            )
            
            # Record transaction
            CreditTransaction.objects.create(
                user=user,
                type=CREDIT_TRANSACTION_TYPE['DAILY_ALLOCATION'],
                amount=daily_amount,
                balance_before=0,
                balance_after=0,
                lot_breakdown=[{
                    'lot_id': str(daily_lot.id),
                    'source': source,
                    'amount': daily_amount,
                    'expires_at': expires_at.isoformat(),
                }],
                description=f'Initial daily allocation after migration',
                metadata={'migration': True, 'initial_daily': True}
            )
        
        migrated_count += 1
    
    print(f"[+] Migrated {migrated_count} users, {total_credits_migrated} total credits")


def reverse_migration(apps, schema_editor):
    """Reverse migration: delete all CreditLot and CreditTransaction records."""
    CreditLot = apps.get_model('learning', 'CreditLot')
    CreditTransaction = apps.get_model('learning', 'CreditTransaction')
    
    lot_count = CreditLot.objects.count()
    transaction_count = CreditTransaction.objects.count()
    
    CreditTransaction.objects.all().delete()
    CreditLot.objects.all().delete()
    
    print(f"[-] Reversed migration: deleted {lot_count} lots and {transaction_count} transactions")


class Migration(migrations.Migration):
    dependencies = [
        ('learning', '0003_creditpackage_alter_aicreditaccount_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_old_credits_to_lots, reverse_migration),
    ]