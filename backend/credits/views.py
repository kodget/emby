import requests
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CreditPackage, CreditLot, CreditTransaction, TransactionType, CreditSource
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
    limit = int(request.query_params.get('limit', 50))
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
                    "user_id": request.user.id
                }
            },
            timeout=10
        )
        res.raise_for_status()
        result = res.json()
        if not result.get("status"):
            return Response({"error": result.get("message", "Paystack init failed")}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({
            "authorization_url": result["data"]["authorization_url"],
            "access_code": result["data"]["access_code"],
            "reference": result["data"]["reference"]
        })
    except Exception as e:
        logger.error(f"Paystack init error: {e}")
        return Response({"error": "Failed to connect to payment gateway"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_purchase(request):
    """Verify a Paystack transaction and grant the purchased credits."""
    reference = request.data.get('reference')
    if not reference:
        return Response({"error": "reference is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Prevent double processing
    if CreditTransaction.objects.filter(reference_id=reference).exists():
        return Response({"error": "Transaction already verified"}, status=status.HTTP_400_BAD_REQUEST)
        
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
        
    paystack_data = result.get("data", {})
    if paystack_data.get("status") != "success":
        return Response({"error": f"Payment not successful: {paystack_data.get('status')}"}, status=status.HTTP_400_BAD_REQUEST)
        
    metadata = paystack_data.get("metadata", {})
    if metadata.get("type") != "credit_purchase":
        return Response({"error": "Invalid transaction type"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Make sure user matches (security)
    if str(metadata.get("user_id")) != str(request.user.id):
        return Response({"error": "Payment does not belong to this user"}, status=status.HTTP_403_FORBIDDEN)
        
    package_id = metadata.get("package_id")
    try:
        package = CreditPackage.objects.get(id=package_id)
    except CreditPackage.DoesNotExist:
        return Response({"error": "Credit package no longer exists"}, status=status.HTTP_404_NOT_FOUND)
        
    # Verify amount paid
    expected_kobo = (package.price + EMBY_SERVICE_FEE) * 100
    paid_kobo = int(paystack_data.get("amount", 0))
    if paid_kobo < expected_kobo:
        return Response({"error": "Incomplete payment amount"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Grant credits
    with transaction.atomic():
        # Double check to avoid race condition
        if CreditTransaction.objects.filter(reference_id=reference).exists():
            return Response({"error": "Transaction already verified"}, status=status.HTTP_400_BAD_REQUEST)
            
        balance_before = CreditManager.get_user_balance(request.user)
        
        # Purchased credits never expire based on models config
        CreditLot.objects.create(
            user=request.user,
            source=CreditSource.PURCHASE,
            original_amount=package.credits,
            remaining_amount=package.credits,
            expires_at=None
        )
        
        CreditTransaction.objects.create(
            user=request.user,
            type=TransactionType.PURCHASE,
            amount=package.credits,
            balance_before=balance_before,
            balance_after=balance_before + package.credits,
            action="CREDIT_PURCHASE",
            description=f"Purchased {package.name} ({package.credits} credits)",
            reference_id=reference,
            metadata={"paystack_ref": reference, "package_id": package.id}
        )
        
    return Response({
        "message": "Purchase successful",
        "credits_added": package.credits,
        "new_balance": balance_before + package.credits
    })
