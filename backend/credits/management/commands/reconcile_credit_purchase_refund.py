"""Dry-run-first reconciliation for provider-confirmed credit purchase refunds."""

import json

from django.core.management.base import BaseCommand, CommandError

from credits.refund_reconciliation import (
    RefundReconciliationError,
    reconcile_purchase_refund,
)


class Command(BaseCommand):
    help = "Dry-run or reconcile a provider-confirmed full credit-purchase refund."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--reference", required=True, help="Original credit purchase reference.")
        parser.add_argument(
            "--provider-refund-reference",
            required=True,
            help="Refund reference returned by the payment provider.",
        )
        parser.add_argument("--amount-kobo", required=True, type=int)
        parser.add_argument("--apply", action="store_true", help="Apply the ledger reconciliation.")
        parser.add_argument(
            "--confirm-provider-refund",
            action="store_true",
            help="Confirm the provider has already completed the refund.",
        )

    def handle(self, *args, **options):
        if options["apply"] and not options["confirm_provider_refund"]:
            raise CommandError(
                "Apply requires --confirm-provider-refund. This command does not issue Paystack refunds."
            )
        try:
            result = reconcile_purchase_refund(
                options["reference"],
                options["provider_refund_reference"],
                options["amount_kobo"],
                apply=options["apply"],
            )
        except RefundReconciliationError as exc:
            raise CommandError(str(exc)) from None
        except Exception:
            raise CommandError(
                "Credit refund reconciliation failed; any database writes were rolled back."
            ) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
