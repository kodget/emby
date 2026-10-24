import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    CreditPackage, CreditLot, CreditPurchase, CreditTransaction,
    TransactionType, CreditSource,
)
from .services import CreditManager
import logging

logger = logging.getLogger(__name__)

PAYSTACK_SECRET = getattr(settings, "PAYSTACK_SECRET_KEY", "")
PAYSTACK_BASE = "https://api.paystack.co"
EMBY_SERVICE_FEE = 50  # N50 mandatory fee

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balance(request):
    """Get the user's current valid credit balance."""
    return Response({"balance": CreditManager.get_user_balance(request.user)})

DEFAULT_PACKAGES = [
    {"name": "Starter AI Pack", "credits": 500, "price": 800},
    {"name": "Scholar AI Pack", "credits": 1500, "price": 2400},
    {"name": "Power Scholar Pack", "credits": 5000, "price": 7500},
    {"name": "Mastery AI Pack", "credits": 15000, "price": 21000},
]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packages(request):
    """List all active credit packages, auto-seeding default packages if empty."""
    if not CreditPackage.objects.filter(is_active=True).exists():
        for pkg in DEFAULT_PACKAGES:
            CreditPackage.objects.get_or_create(
                name=pkg["name"],
                defaults={"credits": pkg["credits"], "price": pkg["price"], "is_active": True}
            )

    packages = CreditPackage.objects.filter(is_active=True).order_by('price')
    data = [
        {
            "id": p.id,
            "name": p.name,
            "credits": p.credits,
            "price": p.price,
            "total_price": p.price + EMBY_SERVICE_FEE,
            "service_fee": EMBY_SERVICE_FEE
        }
        for p in packages
    ]
    return Response({"packages": data})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    """Get the user's credit transaction history."""
    try:
        limit = min(max(int(request.query_params.get('limit', 50)), 1), 100)
    except (TypeError, ValueError):
        return Response({"error": "limit must be a whole number between 1 and 100"}, status=400)
    transactions = CreditTransaction.objects.filter(user=request.user).order_by('-created_at')[:limit]
    data = [
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "balance_before": t.balance_before,
            "balance_after": t.balance_after,
            "action": t.action,
            "description": t.description,
            "created_at": t.created_at
        }
        for t in transactions
    ]
    return Response({"history": data})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def init_purchase(request):
    """Initialize a Paystack transaction to purchase a credit package."""
    package_id = request.data.get('package_id')
    if not package_id:
        return Response({"error": "package_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        package = CreditPackage.objects.get(id=package_id, is_active=True)
    except CreditPackage.DoesNotExist:
        return Response({"error": "Invalid or inactive credit package"}, status=status.HTTP_404_NOT_FOUND)
    if package.credits <= 0 or package.price <= 0:
        logger.error("Credit package %s has a nonpositive price or credit quantity", package.pk)
        return Response({"error": "Credit package is unavailable"}, status=status.HTTP_409_CONFLICT)
        
    # Total price includes the service fee
    total_price_naira = package.price + EMBY_SERVICE_FEE
    amount_kobo = total_price_naira * 100
    
    # Initialize Paystack
    try:
        res = requests.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}", "Content-Type": "application/json"},
            json={
                "email": request.user.email,
                "amount": amount_kobo,
                "callback_url": getattr(settings, "PAYSTACK_CALLBACK_URL", ""),
                "metadata": {
                    "type": "credit_purchase",
                    "package_id": package.id,
                    "credits": package.credits,
                    "amount_kobo": amount_kobo,
                    "currency": "NGN",
                    "user_id": request.user.id
                }
            },
            timeout=10
        )
        res.raise_for_status()
        result = res.json()
        if not result.get("status"):
            return Response({"error": result.get("message", "Paystack init failed")}, status=status.HTTP_400_BAD_REQUEST)

        provider_data = result.get("data", {})
        reference = provider_data.get("reference")
        if not isinstance(reference, str) or not reference or len(reference) > 100:
            logger.error("Paystack returned an invalid credit purchase reference")
            return Response(
                {"error": "Payment gateway returned an invalid purchase reference"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        CreditPurchase.objects.create(
            reference=reference,
            user=request.user,
            package=package,
            package_id_snapshot=package.pk,
            package_name=package.name,
            credits=package.credits,
            amount_kobo=amount_kobo,
            currency="NGN",
        )
            
        return Response({
            "authorization_url": provider_data["authorization_url"],
            "access_code": provider_data["access_code"],
            "reference": reference
        })
    except Exception as e:
        logger.error(f"Paystack init error: {e}")
        return Response({"error": "Failed to connect to payment gateway"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_purchase(request):
    """Verify a Paystack transaction and grant the purchased credits."""
    reference = request.data.get('reference')
    if not isinstance(reference, str) or not reference or len(reference) > 100:
        return Response({"error": "reference is required"}, status=status.HTTP_400_BAD_REQUEST)

    purchase = CreditPurchase.objects.filter(reference=reference, user=request.user).first()
    if purchase is None:
        return Response({"error": "Unknown credit purchase"}, status=status.HTTP_404_NOT_FOUND)
    if purchase.status == CreditPurchase.Status.CREDITED:
        return Response({
            "message": "Purchase successful",
            "credits_added": purchase.credits,
            "new_balance": CreditManager.get_user_balance(request.user),
        })
    if purchase.status != CreditPurchase.Status.PENDING:
        return Response({"error": "Credit purchase is not eligible for verification"}, status=status.HTTP_409_CONFLICT)
        
    try:
        res = requests.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
            timeout=10
        )
        res.raise_for_status()
        result = res.json()
    except Exception as e:
        logger.error(f"Paystack verify error: {e}")
        return Response({"error": "Failed to verify payment with gateway"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    if not isinstance(result, dict) or not result.get("status"):
        return Response({"error": "Payment gateway could not verify this transaction"}, status=status.HTTP_502_BAD_GATEWAY)
    paystack_data = result.get("data", {})
    if not isinstance(paystack_data, dict):
        return Response({"error": "Payment gateway returned an invalid verification response"}, status=status.HTTP_502_BAD_GATEWAY)
    if paystack_data.get("status") != "success":
        return Response({"error": f"Payment not successful: {paystack_data.get('status')}"}, status=status.HTTP_400_BAD_REQUEST)

    if paystack_data.get("reference") != reference:
        return Response({"error": "Payment reference does not match"}, status=status.HTTP_400_BAD_REQUEST)
        
    metadata = paystack_data.get("metadata", {})
    if not isinstance(metadata, dict):
        return Response({"error": "Payment metadata is invalid"}, status=status.HTTP_400_BAD_REQUEST)
    if metadata.get("type") != "credit_purchase":
        return Response({"error": "Invalid transaction type"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Make sure user matches (security)
    if str(metadata.get("user_id")) != str(request.user.id):
        return Response({"error": "Payment does not belong to this user"}, status=status.HTTP_403_FORBIDDEN)

    if str(metadata.get("package_id")) != str(purchase.package_id_snapshot):
        return Response({"error": "Payment package does not match the purchase"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Verify amount paid
    try:
        paid_kobo = int(paystack_data.get("amount", 0))
    except (TypeError, ValueError):
        paid_kobo = 0
    if paid_kobo != purchase.amount_kobo:
        return Response({"error": "Paid amount does not match the purchase"}, status=status.HTTP_400_BAD_REQUEST)
    if paystack_data.get("currency") != purchase.currency or metadata.get("currency") != purchase.currency:
        return Response({"error": "Payment currency does not match the purchase"}, status=status.HTTP_400_BAD_REQUEST)
    if metadata.get("credits") != purchase.credits or metadata.get("amount_kobo") != purchase.amount_kobo:
        return Response({"error": "Payment entitlement does not match the purchase"}, status=status.HTTP_400_BAD_REQUEST)
        
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        purchase = CreditPurchase.objects.select_for_update().get(pk=purchase.pk)
        if purchase.status == CreditPurchase.Status.CREDITED:
            return Response({
                "message": "Purchase successful",
                "credits_added": purchase.credits,
                "new_balance": CreditManager.get_user_balance(request.user),
            })
        if purchase.status != CreditPurchase.Status.PENDING:
            return Response({"error": "Credit purchase is not eligible for verification"}, status=status.HTTP_409_CONFLICT)

        balance_before = CreditManager.get_user_balance(request.user)
        
        CreditLot.objects.create(
            user=request.user,
            purchase=purchase,
            source=CreditSource.PURCHASE,
            original_amount=purchase.credits,
            remaining_amount=purchase.credits,
            expires_at=None
        )
        
        CreditTransaction.objects.create(
            user=request.user,
            type=TransactionType.PURCHASE,
            amount=purchase.credits,
            balance_before=balance_before,
            balance_after=balance_before + purchase.credits,
            action="CREDIT_PURCHASE",
            description=f"Purchased {purchase.package_name} ({purchase.credits} credits)",
            reference_id=reference,
            metadata={"paystack_ref": reference, "package_id": purchase.package_id_snapshot},
        )

        purchase.status = CreditPurchase.Status.CREDITED
        purchase.provider_transaction_id = str(paystack_data.get("id") or "")
        purchase.verified_at = timezone.now()
        purchase.save(update_fields=["status", "provider_transaction_id", "verified_at"])
        
    return Response({
        "message": "Purchase successful",
        "credits_added": purchase.credits,
        "new_balance": balance_before + purchase.credits
    })
