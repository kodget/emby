"""Clean up expired daily credit lots.

Daily lots expire 30 days after allocation. This command:
1. Finds all expired daily lots with remaining credits
2. Sets their remaining_amount to 0
3. Creates EXPIRATION transactions for audit trail
4. Logs the cleanup

Run daily via Celery beat or cron.

    python manage.py expire_credits
    python manage.py expire_credits --before=2026-09-01
    python manage.py expire_credits --dry-run
"""

from datetime import datetime
from typing import List, Dict

from django.core.management.base import BaseCommand
from django.utils import timezone

from learning import credits as credit_service


class Command(BaseCommand):
    help = "Clean up expired daily credit lots"

    def add_arguments(self, parser):
        parser.add_argument(
            "--before",
            help="Expire lots expiring before this date (YYYY-MM-DD). Defaults to now.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be expired without making changes",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of lots to expire (for testing)",
        )

    def handle(self, *args, **options):
        # Parse before date
        before = None
        if options["before"]:
            try:
                before = datetime.fromisoformat(options["before"]).date()
                before = timezone.make_aware(
                    datetime.combine(before, datetime.min.time())
                )
            except ValueError:
                self.stderr.write(f"Invalid date format: {options['before']}. Use YYYY-MM-DD.")
                return
        else:
            before = timezone.now()

        self.stdout.write(f"Cleaning up credits expiring before {before}...")

        if options["dry_run"]:
            # Simulate finding expired lots
            expired_lots = credit_service.CreditLot.objects.filter(
                expires_at__lte=before,
                remaining_amount__gt=0,
                is_daily=True,
            ).select_related("user")
            
            if options["limit"]:
                expired_lots = expired_lots[:options["limit"]]

            count = expired_lots.count()
            total_credits = sum(lot.remaining_amount for lot in expired_lots)

            self.stdout.write(f"DRY RUN: Would expire {count} lots totaling {total_credits} credits")
            
            for lot in expired_lots[:10]:  # Show first 10
                self.stdout.write(
                    f"  {lot.user.email or lot.user.username}: "
                    f"{lot.remaining_amount} credits ({lot.source}) "
                    f"expired {lot.expires_at.date()}"
                )
            
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more lots")

            self.stdout.write(self.style.WARNING("DRY RUN — no changes were made"))
            return

        # Actual expiration
        count, expired_data = credit_service.expire_old_credits(before)
        
        if options["limit"] and count > options["limit"]:
            expired_data = expired_data[:options["limit"]]
            count = len(expired_data)

        total_credits = sum(item["amount"] for item in expired_data)

        self.stdout.write(f"Expired {count} lots totaling {total_credits} credits")
        
        for item in expired_data[:10]:  # Show first 10
            self.stdout.write(
                f"  User {item['user_id']}: {item['amount']} credits ({item['source']}) "
                f"expired {item['expires_at'].date() if item['expires_at'] else 'N/A'}"
            )
        
        if count > 10:
            self.stdout.write(f"  ... and {count - 10} more lots")

        self.stdout.write(
            self.style.SUCCESS(f"✓ Successfully expired {count} credit lots")
        )