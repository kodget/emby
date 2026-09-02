from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class CreditSource(models.TextChoices):
    DAILY_FREE = "DAILY_FREE", "Daily Free Allocation"
    DAILY_PRO = "DAILY_PRO", "Daily Pro Allocation"
    DAILY_CLASS_HEAD = "DAILY_CLASS_HEAD", "Daily Class Head Allocation"
    DAILY_MATERIAL_UPLOADER = "DAILY_MATERIAL_UPLOADER", "Daily Material Uploader Allocation"
    PURCHASE = "PURCHASE", "Purchased Credits"
    ADMIN = "ADMIN", "Admin Adjustment"
    PROMOTIONAL = "PROMOTIONAL", "Promotional"
    REFUND = "REFUND", "Refund"

class TransactionType(models.TextChoices):
    AI_USAGE = "AI_USAGE", "AI Usage"
    DAILY_ALLOCATION = "DAILY_ALLOCATION", "Daily Allocation"
    PURCHASE = "PURCHASE", "Purchase"
    REFUND = "REFUND", "Refund"
    EXPIRATION = "EXPIRATION", "Expiration"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT", "Admin Adjustment"

class CreditPackage(models.Model):
    name = models.CharField(max_length=100)
    credits = models.IntegerField()
    price = models.IntegerField(help_text="Base price in Naira (excluding N100 fee)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.credits} credits"

class CreditLot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_lots')
    source = models.CharField(max_length=50, choices=CreditSource.choices)
    original_amount = models.IntegerField()
    remaining_amount = models.IntegerField()
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Null for non-expiring credits (e.g. purchases)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'remaining_amount', 'expires_at']),
        ]

    def __str__(self):
        return f"Lot {self.id} for {self.user.username}: {self.remaining_amount}/{self.original_amount} ({self.source})"

    @property
    def is_valid(self):
        if self.remaining_amount <= 0:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

class CreditTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_transactions')
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.IntegerField(help_text="Positive for additions, negative for deductions")
    balance_before = models.IntegerField()
    balance_after = models.IntegerField()
    action = models.CharField(max_length=100, blank=True, help_text="e.g. CHAT, GENERATE_MCQ")
    reference_id = models.CharField(max_length=100, blank=True, help_text="Used for idempotency, e.g. request ID or payment ref")
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'reference_id']),
        ]
        
    def __str__(self):
        return f"{self.user.username} {self.type} {self.amount} ({self.action})"
