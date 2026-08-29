"""Build due notifications for every student.

Run on a schedule (Celery beat, cron, or a hosted scheduler). The command is idempotent:
dedupe keys and the per-student daily budget mean running it more often simply produces
fewer new rows, never duplicates.

    python manage.py send_notifications
    python manage.py send_notifications --user demo@emby.app
    python manage.py send_notifications --dry-run
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from learning import notifications


class Command(BaseCommand):
    help = "Create the notifications that are due right now"

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Limit to one username or email")
        parser.add_argument("--limit", type=int, help="Cap how many users are processed")
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would be created, write nothing"
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["user"]:
                user = (
                    User.objects.filter(username=options["user"]).first()
                    or User.objects.filter(email=options["user"]).first()
                )
                if user is None:
                    self.stderr.write(f"No such user: {options['user']}")
                    return
                made = notifications.build_for_user(user)
                result = {"users_notified": 1 if made else 0, "notifications_created": len(made)}
                for n in made:
                    self.stdout.write(f"  {n.type}: {n.title}")
            else:
                result = notifications.run_for_all(limit=options.get("limit"))

            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("dry run — rolled back"))

        self.stdout.write(
            self.style.SUCCESS(
                f"{result['notifications_created']} notification(s) for "
                f"{result['users_notified']} student(s)"
            )
        )
