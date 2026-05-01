from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string


# -------------------------
# SUBSCRIPTION TIERS
# -------------------------
class SubscriptionTier(models.TextChoices):
    FREE = "free", "Free"
    PREMIUM = "premium", "Premium"
    CLASS_HEAD = "class_head", "Class Head (Full Access)"


# -------------------------
# USER ROLES
# -------------------------
class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    BRAINSTORMER = "brainstormer", "Brainstormer"
    CLASS_HEAD = "class_head", "Class Head"
    MATERIAL_UPLOADER = "material_uploader", "Material Uploader"


# -------------------------
# SCHOOL & CLASS
# -------------------------
class School(models.Model):
    """School/Institution"""
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    """Class group managed by class head"""
    code = models.CharField(max_length=6, unique=True, db_index=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    set_name = models.CharField(max_length=100)  # e.g., "2024/2025", "Year 3"
    
    # Multiple class heads (max 3)
    class_heads = models.ManyToManyField(User, related_name='managed_classes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['school', 'set_name']

    def __str__(self):
        return f"{self.school.name} - {self.set_name} ({self.code})"

    @staticmethod
    def generate_code():
        """Generate unique 6-digit class code"""
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not ClassGroup.objects.filter(code=code).exists():
                return code
    
    def add_class_head(self, user):
        """Add class head (max 3)"""
        if self.class_heads.count() >= 3:
            raise ValueError("Maximum 3 class heads per class")
        self.class_heads.add(user)
    
    def is_class_head(self, user):
        """Check if user is a class head"""
        return self.class_heads.filter(id=user.id).exists()


# -------------------------
# USER PROFILE
# -------------------------
class Profile(models.Model):
    """Extended user profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Basic info
    photo_url = models.URLField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices)
    
    # School & Class
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    set_name = models.CharField(max_length=100, blank=True)
    class_group = models.ForeignKey(ClassGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    
    # Subscription
    subscription_tier = models.CharField(max_length=20, choices=SubscriptionTier.choices, default=SubscriptionTier.FREE)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Onboarding
    onboarding_completed = models.BooleanField(default=False)
    
    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    
    # Password reset
    password_reset_token = models.CharField(max_length=100, blank=True)
    password_reset_token_expires = models.DateTimeField(null=True, blank=True)
    
    # Class head verification (manual approval by admin)
    class_head_verified = models.BooleanField(default=False)
    class_head_verification_requested = models.BooleanField(default=False)
    class_head_rejection_reason = models.TextField(blank=True)
    
    # Gamification
    streak = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    @property
    def is_premium(self):
        """Check if user has active premium subscription"""
        # Class heads get full access automatically
        if self.role == UserRole.CLASS_HEAD and self.class_head_verified:
            return True
        
        if self.subscription_tier == SubscriptionTier.FREE:
            return False
        if self.subscription_expires_at and self.subscription_expires_at < timezone.now():
            return False
        return True

    @property
    def is_class_head(self):
        return self.role == UserRole.CLASS_HEAD and self.class_head_verified
    
    @property
    def can_access_app(self):
        """Check if user can access the app"""
        # Class heads must be verified
        if self.role == UserRole.CLASS_HEAD:
            return self.class_head_verified
        # Other users can access immediately
        return True


# -------------------------
# ONBOARDING RESPONSES
# -------------------------
class OnboardingQuestion(models.Model):
    """Onboarding questions"""
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=[
        ('text', 'Text'),
        ('choice', 'Multiple Choice'),
        ('select', 'Dropdown'),
    ])
    options = models.JSONField(default=list, blank=True)  # For choice/select types
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.question_text


class OnboardingResponse(models.Model):
    """User's onboarding answers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='onboarding_responses')
    question = models.ForeignKey(OnboardingQuestion, on_delete=models.CASCADE)
    answer = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.username} - {self.question.question_text[:50]}"


# -------------------------
# ANNOUNCEMENTS
# -------------------------
class Announcement(models.Model):
    """Class announcements by class head"""
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='announcements')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.class_group.code} - {self.title}"


# -------------------------
# EXAM COUNTDOWNS
# -------------------------
class ExamCountdown(models.Model):
    """Exam countdowns managed by class heads"""
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='exam_countdowns')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    title = models.CharField(max_length=200)  # e.g., "MBBS Final Exam", "Physiology In-Course"
    exam_date = models.DateField()
    exam_time = models.TimeField(null=True, blank=True)
    
    # Optional details
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=100, blank=True)  # e.g., "Physiology", "Anatomy"
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['exam_date']

    def __str__(self):
        return f"{self.class_group.code} - {self.title} ({self.exam_date})"
    
    @property
    def days_remaining(self):
        """Calculate days remaining until exam"""
        from datetime import date
        delta = self.exam_date - date.today()
        return delta.days


# -------------------------
# PAYMENT HISTORY
# -------------------------
class PaymentTransaction(models.Model):
    """Track premium subscription payments"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    
    # Paystack details
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], default='pending')
    
    # Subscription details
    subscription_months = models.IntegerField(default=1)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.reference} - {self.status}"
