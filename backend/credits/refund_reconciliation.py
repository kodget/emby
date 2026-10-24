"""Manual reconciliation of provider-confirmed credit-purchase refunds."""

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import CreditLot, CreditPurchase, CreditSource, CreditTransaction, TransactionType
from .services import _credit_balance


class RefundReconciliationError(Exception):
    pass


def reconcile_purchase_refund(
    reference: str,
    provider_refund_reference: str,
    amount_kobo: int,
    *,
    apply: bool = False,
) -> dict:
    if not isinstance(reference, str) or not reference or len(reference) > 100:
        raise RefundReconciliationError("A valid purchase reference is required.")
    if (
        not isinstance(provider_refund_reference, str)
        or not provider_refund_reference
        or len(provider_refund_reference) > 100
    ):
        raise RefundReconciliationError("A valid provider refund reference is required.")
    if type(amount_kobo) is not int or amount_kobo <= 0:
        raise RefundReconciliationError("Refund amount must be a positive integer in kobo.")

    try:
        purchase = CreditPurchase.objects.select_related("user").get(reference=reference)
    except CreditPurchase.DoesNotExist as exc:
        raise RefundReconciliationError("Unknown credit purchase.") from exc

    if purchase.status == CreditPurchase.Status.REFUNDED:
        if (
            purchase.provider_refund_reference == provider_refund_reference
            and purchase.refunded_amount_kobo == amount_kobo
        ):
            return _report(purchase, apply=apply, already_reconciled=True)
        raise RefundReconciliationError("This purchase was already reconciled with another refund.")
    if purchase.status != CreditPurchase.Status.CREDITED:
        raise RefundReconciliationError("Only credited purchases can be reconciled as refunded.")
    if amount_kobo != purchase.amount_kobo:
        raise RefundReconciliationError("Only full purchase refunds are supported.")
    if CreditPurchase.objects.filter(
        provider_refund_reference=provider_refund_reference
    ).exists():
        raise RefundReconciliationError("This provider refund reference was already used.")

    lot = CreditLot.objects.filter(
        user=purchase.user, purchase=purchase, source=CreditSource.PURCHASE
    ).first()
    if lot is None:
        raise RefundReconciliationError("Purchase credit lot is missing; reconcile manually.")

    report = _report(purchase, lot=lot, apply=apply, already_reconciled=False)
    if not apply:
        return report

    with transaction.atomic():
        User.objects.select_for_update().get(pk=purchase.user_id)
        purchase = CreditPurchase.objects.select_for_update().get(pk=purchase.pk)
        if purchase.status == CreditPurchase.Status.REFUNDED:
            if (
                purchase.provider_refund_reference == provider_refund_reference
                and purchase.refunded_amount_kobo == amount_kobo
            ):
                return _report(purchase, apply=True, already_reconciled=True)
            raise RefundReconciliationError("This purchase was already reconciled with another refund.")
        if purchase.status != CreditPurchase.Status.CREDITED:
            raise RefundReconciliationError("Only credited purchases can be reconciled as refunded.")
        if CreditPurchase.objects.filter(
            provider_refund_reference=provider_refund_reference
        ).exclude(pk=purchase.pk).exists():
            raise RefundReconciliationError("This provider refund reference was already used.")

        lot = CreditLot.objects.select_for_update().get(
            user=purchase.user, purchase=purchase, source=CreditSource.PURCHASE
        )
        balance_before = _credit_balance(purchase.user)
        recovered_credits = lot.remaining_amount
        already_spent_credits = max(0, lot.original_amount - recovered_credits)

        lot.remaining_amount = 0
        lot.save(update_fields=["remaining_amount"])
        purchase.status = CreditPurchase.Status.REFUNDED
        purchase.provider_refund_reference = provider_refund_reference
        purchase.refunded_amount_kobo = amount_kobo
        purchase.refunded_at = timezone.now()
        purchase.save(update_fields=[
            "status", "provider_refund_reference", "refunded_amount_kobo", "refunded_at"
        ])

        CreditTransaction.objects.create(
            user=purchase.user,
            type=TransactionType.REFUND,
            amount=-recovered_credits,
            balance_before=balance_before,
            balance_after=balance_before - recovered_credits,
            action="PURCHASE_REFUND_RECONCILIATION",
            reference_id=provider_refund_reference,
            description="Reconciled provider-confirmed credit purchase refund.",
            metadata={
                "purchase_reference": purchase.reference,
                "provider_refund_reference": provider_refund_reference,
                "refunded_amount_kobo": amount_kobo,
                "recovered_credits": recovered_credits,
                "already_spent_credits": already_spent_credits,
            },
        )

        report = _report(
            purchase,
            lot=lot,
            apply=True,
            already_reconciled=False,
            recovered_credits=recovered_credits,
            already_spent_credits=already_spent_credits,
            balance_after=balance_before - recovered_credits,
        )
        return report


def _report(
    purchase,
    *,
    lot=None,
    apply: bool,
    already_reconciled: bool,
    recovered_credits=None,
    already_spent_credits=None,
    balance_after=None,
) -> dict:
    lot = lot or CreditLot.objects.filter(purchase=purchase).first()
    available = lot.remaining_amount if lot else 0
    if (
        purchase.status == CreditPurchase.Status.REFUNDED
        and recovered_credits is None
    ):
        refund_entry = CreditTransaction.objects.filter(
            user=purchase.user,
            type=TransactionType.REFUND,
            action="PURCHASE_REFUND_RECONCILIATION",
            reference_id=purchase.provider_refund_reference,
        ).first()
        if refund_entry:
            recovered_credits = refund_entry.metadata.get("recovered_credits", 0)
            already_spent_credits = refund_entry.metadata.get("already_spent_credits", 0)
            balance_after = refund_entry.balance_after
    return {
        "reference": purchase.reference,
        "status": purchase.status,
        "refunded_amount_kobo": purchase.amount_kobo,
        "credits_to_recover": available if recovered_credits is None else recovered_credits,
        "credits_already_spent": (
            max(0, purchase.credits - available)
            if already_spent_credits is None else already_spent_credits
        ),
        "balance_after": balance_after,
        "apply": apply,
        "already_reconciled": already_reconciled,
    }
