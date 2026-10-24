"""Explicit operator tool; intentionally not called by deployment hooks."""

import json

from django.core.management.base import BaseCommand, CommandError

from credits.legacy_transfer import LegacyTransferError, transfer_legacy_credits


class Command(BaseCommand):
    help = "Dry-run a conservative legacy credit transfer; see docs/LEGACY_CREDIT_TRANSFER.md."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")
        parser.add_argument("--apply", action="store_true", help="Atomically copy and verify; never delete sources.")
        parser.add_argument("--confirm-writes-paused", action="store_true", help="Confirm all web, worker, scheduler and admin writes are paused through final migration.")

    def handle(self, *args, **options):
        if options["apply"] and not options["confirm_writes_paused"]:
            raise CommandError("Apply requires --confirm-writes-paused. Pause every writer and complete a backup/staging rehearsal first.")
        try:
            result = transfer_legacy_credits(database=options["database"], apply=options["apply"])
        except LegacyTransferError as exc:
            raise CommandError(str(exc)) from None
        except Exception:
            # Database exceptions may include credentials or row contents.
            raise CommandError("Legacy credit inspection or transfer failed. Any writes were rolled back. Check database access and schema privately; no raw database error is printed.") from None
        self.stdout.write(json.dumps(result, sort_keys=True))
