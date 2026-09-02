"""Allocate daily AI credits for all active users.

This command runs daily (via Celery beat, cron, or scheduler) to grant:
- 10 credits to FREE users
- 60 credits to PREMIUM users

Each daily allocation is a separate CreditLot that expires in 30 days.
Idempotent: running twice on the same day creates nothing extra.

    python manage.py allocate_daily_credits
    python manage.py allocate_daily_credits --date=2026-09-02
    python manage.py allocate_daily_credits --user=demo@emby.app
    python manage.py allocate_daily_credits --limit=100 --dry-run
"""

from datetime import date
from typing import Dict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from learning import credits as credit_service
from learning.models import CreditLotSource


class Command(BaseCommand):
    help = "Allocate daily AI credits for active users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="Allocation date (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--user",
            help="Process only this user (username or email)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of users to process",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be allocated without writing",
        )
        parser.add_argument(
            "--skip-existing-check",
            action="store_true",
            help="Force allocation even if user already has today's lot (debug only)",
        )

    def handle(self, *args, **options):
        # Parse date
        if options["date"]:
            try:
                allocation_date = date.fromisoformat(options["date"])
            except ValueError:
                self.stderr.write(f"Invalid date format: {options['date']}. Use YYYY-MM-DD.")
                return
        else:
            allocation_date = timezone.now().date()

        # Get user(s)
        if options["user"]:
            user = (
                User.objects.filter(username=options["user"]).first()
                or User.objects.filter(email=options["user"]).first()
            )
            if user is None:
                self.stderr.write(f"No such user: {options['user']}")
                return
            users = [user]
        else:
            # Active users (have logged in within last 90 days)
            cutoff = timezone.now() - timezone.timedelta(days=90)
            users_qs = User.objects.filter(
                last_login__gte=cutoff,
                is_active=True,
            ).order_by("id")
            
            if options["limit"]:
                users_qs = users_qs[:options["limit"]]
            
            users = list(users_qs)

        if not users:
            self.stdout.write("No active users found.")
            return

        # Statistics
        stats: Dict[str, int] = {
            "processed": 0,
            "allocated": 0,
            "free": 0,
            "premium": 0,
            "already_allocated": 0,
            "errors": 0,
        }

        self.stdout.write(
            f"Allocating daily credits for {len(users)} user(s) on {allocation_date}..."
        )

        for user in users:
            stats["processed"] += 1

            # Determine tier
            profile = getattr(user, "profile", None)
            is_premium = bool(profile and profile.is_premium)
            tier = "premium" if is_premium else "free"
            source = CreditLotSource.DAILY_PRO if is_premium else CreditLotSource.DAILY_FREE

            # Check if already allocated today
            if not options["skip_existing_check"]:
                already_exists = credit_service.CreditLot.objects.filter(
                    user=user,
                    source=source,
                    allocation_date=allocation_date,
                ).exists()
                if already_exists:
                    stats["already_allocated"] += 1
                    continue

            try:
                if options["dry_run"]:
                    amount = 60 if is_premium else 10
                    self.stdout.write(
                        f"  DRY RUN: Would allocate {amount} credits to {user.email or user.username} ({tier})"
                    )
                    stats["allocated"] += 1
                    stats["premium" if is_premium else "free"] += 1
                else:
                    with transaction.atomic():
                        created_lots = credit_service.allocate_daily_credits(user, allocation_date)
                        if created_lots:
                            lot = created_lots[0]
                            stats["allocated"] += 1
                            stats["premium" if is_premium else "free"] += 1
                            self.stdout.write(
                                f"  Allocated {lot.original_amount} credits to "
                                f"{user.email or user.username} ({tier})"
                            )
                        else:
                            stats["already_allocated"] += 1

            except Exception as exc:
                stats["errors"] += 1
                self.stderr.write(
                    f"  ERROR for {user.email or user.username}: {exc}"
                )
                if not options["dry_run"]:
                    import traceback
                    self.stderr.write(traceback.format_exc())

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DAILY CREDIT ALLOCATION SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Date:          {allocation_date}")
        self.stdout.write(f"Users processed:  {stats['processed']}")
        self.stdout.write(f"New allocations:  {stats['allocated']}")
        self.stdout.write(f"  - Free users:   {stats['free']} × 10 credits")
        self.stdout.write(f"  - Premium users: {stats['premium']} × 60 credits")
        self.stdout.write(f"Already allocated today: {stats['already_allocated']}")
        self.stdout.write(f"Errors:           {stats['errors']}")
        
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDRY RUN — no changes were saved"))
        else:
            total_credits = (stats['free'] * 10) + (stats['premium'] * 60)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully allocated {total_credits} total credits to {stats['allocated']} users"
                )
            )