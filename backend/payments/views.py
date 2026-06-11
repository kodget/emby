"""
Paystack payment endpoints (PRD §7.3).

Postgres-native: subscription state lives on accounts.Profile and every
transaction is recorded in accounts.PaymentTransaction. The webhook is the
source of truth for activating/renewing premium server-side.
"""

import json
import hmac
import hashlib
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

PAYSTACK_SECRET = settings.PAYSTACK_SECRET_KEY
PAYSTACK_BASE = "https://api.paystack.co"


def _activate_premium(transaction):
    """Mark a transaction successful and extend the user's premium window."""
    from accounts.models import Profile, SubscriptionTier

    if transaction.status == "success":
        return  # idempotent — already processed

    transaction.status = "success"
    transaction.verified_at = timezone.now()
    transaction.save(update_fields=["status", "verified_at"])

    profile = Profile.objects.filter(user=transaction.user).first()
    if profile:
        base = profile.subscription_expires_at
        if not base or base < timezone.now():
            base = timezone.now()
        profile.subscription_tier = SubscriptionTier.PREMIUM
        profile.subscription_expires_at = base + timedelta(days=30 * transaction.subscription_months)
        profile.save(update_fields=["subscription_tier", "subscription_expires_at"])


@require_http_methods(["POST"])
@csrf_exempt
def checkout(request):
    """Initialize a Paystack transaction and record it."""
    from accounts.models import PaymentTransaction

    data = request.POST or json.loads(request.body or "{}")
    email = data.get("email")
    try:
        amount_naira = int(data.get("amount", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid amount"}, status=400)

    if not email or amount_naira <= 0:
        return JsonResponse({"error": "email and a positive amount are required"}, status=400)

    months = int(data.get("months", 1))
    resp = requests.post(
        f"{PAYSTACK_BASE}/transaction/initialize",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}", "Content-Type": "application/json"},
        json={
            "email": email,
            "amount": amount_naira * 100,  # kobo
            "callback_url": settings.PAYSTACK_CALLBACK_URL,
            "metadata": {"user_id": data.get("user_id"), "months": months},
        },
        timeout=20,
    )
    result = resp.json()
    if not result.get("status"):
        return JsonResponse({"error": result.get("message", "Paystack init failed")}, status=400)

    pdata = result["data"]
    if request.user.is_authenticated:
        PaymentTransaction.objects.create(
            user=request.user,
            reference=pdata["reference"],
            amount=amount_naira,
            subscription_months=months,
            status="pending",
        )

    return JsonResponse({
        "status": "success",
        "data": {
            "authorization_url": pdata["authorization_url"],
            "reference": pdata["reference"],
            "access_code": pdata["access_code"],
        },
    })


@require_http_methods(["GET"])
def verify(request):
    """Verify a payment by reference and activate premium on success."""
    from accounts.models import PaymentTransaction

    reference = request.GET.get("reference")
    if not reference:
        return JsonResponse({"error": "No reference"}, status=400)

    resp = requests.get(
        f"{PAYSTACK_BASE}/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
        timeout=20,
    )
    result = resp.json()
    if not result.get("status"):
        return JsonResponse({"success": False, "error": result.get("message")}, status=400)

    if result["data"]["status"] == "success":
        transaction = PaymentTransaction.objects.filter(reference=reference).first()
        if transaction:
            _activate_premium(transaction)
        return JsonResponse({"success": True, "message": "Premium activated"})

    return JsonResponse({"success": False}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    """Paystack webhook — the server-side source of truth (PRD §7.3)."""
    from accounts.models import PaymentTransaction

    payload = request.body
    sig_header = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")

    expected = hmac.new(PAYSTACK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, sig_header):
        logger.warning("Rejected Paystack webhook with bad signature")
        return HttpResponse(status=401)

    try:
        event = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    if event.get("event") == "charge.success":
        reference = event.get("data", {}).get("reference")
        transaction = PaymentTransaction.objects.filter(reference=reference).first()
        if transaction:
            _activate_premium(transaction)
            logger.info(f"Premium activated via webhook for {reference}")

    return HttpResponse(status=200)
