from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import pymongo
from pymongo import MongoClient
from django.conf import settings
import requests
import os
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()



PAYSTACK_SECRET = settings.PAYSTACK_SECRET_KEY

@require_http_methods(["POST"])
@csrf_exempt
def checkout(request):
    """Initialize Paystack transaction"""
    data = request.POST
    email = data.get('email')
    amount = int(data.get('amount')) * 100  # kobo
    
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "amount": amount,
        "callback_url": os.getenv('PAYSTACK_CALLBACK_URL', 'http://localhost:3000/upgrade-success'),
        "metadata": {"user_id": data.get('user_id', 'user-you')}
    }
    
    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    
    return JsonResponse({
        "status": "success",
        "data": {
            "authorization_url": result['data']['authorization_url'],
            "reference": result['data']['reference'],
            "access_code": result['data']['access_code']
        }
    })

@require_http_methods(["GET"])
def verify(request):
    """Verify payment"""
    reference = request.GET.get('reference')
    if not reference:
        return JsonResponse({"error": "No reference"}, status=400)
    
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
    
    response = requests.get(url, headers=headers)
    result = response.json()
    
    if result['data']['status'] == 'success':
        # Update user subscription in Mongo
        user_id = result['data']['metadata']['user_id']
        db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "subscription.status": "active",
                    "subscription.tier": "premium",
                    "subscription.expiresAt": result['data']['created_at']
                }
            }
        )
        return JsonResponse({"success": True, "message": "Premium activated"})
    
    return JsonResponse({"success": False}, status=400)

@csrf_exempt
def webhook(request):
    """Paystack webhook verification"""
    payload = request.body
    sig_header = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    
    # Verify webhook signature
    h = hmac.new(PAYSTACK_SECRET.encode(), payload, hashlib.sha512)
    hashhex = h.hexdigest()
    
    if hashhex != sig_header:
        return HttpResponse(status=400)
    
    event = request.POST.get('event', '')
    if event == 'charge.success':
        reference = request.POST['data']['reference']
        # Re-verify (idempotent)
        verify(request)
    
    return HttpResponse(status=200)
