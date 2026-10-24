# Credit purchase refund reconciliation

Paystack refunds are completed by support outside this application. The command below
does not contact Paystack or issue a refund; apply mode must only be used after the
provider confirms the full refund.

The command is dry-run by default. It compares the original payment amount with the
purchase snapshot, identifies the purchased credits still available for recovery, and
reports how many have already been spent. Apply mode revokes only the remaining credits,
records the provider refund reference and consumed-credit amount in the ledger, and
cannot make the user's balance negative.

```powershell
Set-Location backend
python manage.py reconcile_credit_purchase_refund `
  --reference PURCHASE_REFERENCE `
  --provider-refund-reference PROVIDER_REFUND_REFERENCE `
  --amount-kobo FULL_AMOUNT_IN_KOBO

python manage.py reconcile_credit_purchase_refund `
  --reference PURCHASE_REFERENCE `
  --provider-refund-reference PROVIDER_REFUND_REFERENCE `
  --amount-kobo FULL_AMOUNT_IN_KOBO `
  --apply --confirm-provider-refund
```

Only full purchase refunds are accepted. Repeating the same confirmed refund is
idempotent; a different refund reference or amount requires manual reconciliation.
