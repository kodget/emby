"""
Quiz/Examination System - Subscription Enforcement

This module provides the SubscriptionLimiter service class that centralizes 
all subscription tier checks and quota enforcement for the quiz system.
"""

from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User


class SubscriptionLimiter:
    """
    Single authoritative place for all tier checks and limits.
    
    Reads subscription status from UserProfile; never trusts frontend data.
    Enforces server-side limits for security.
    """
    
    # Question limits per tier
    MCQ_LIMIT_FREE = 5
    MCQ_LIMIT_PREMIUM = 100
    THEORY_LIMIT_FREE = 1
    THEORY_LIMIT_PREMIUM = 10
    
    @staticmethod
    def is_premium(user):
        """
        Check if user has premium access.
        
        Returns True if:
        - subscription_tier == 'premium'
        - OR (role == 'class_head' AND class_head_verified == True)
        
        Reads from UserProfile; never trusts frontend payload.
        """
        if not user or not user.is_authenticated:
            return False
            
        if not hasattr(user, 'profile'):
            return False
            
        profile = user.profile
        
        # Premium subscription tier
        if hasattr(profile, 'subscription_tier') and profile.subscription_tier == 'premium':
            return True
            
        # Verified class head gets premium access
        if (hasattr(profile, 'role') and profile.role == 'class_head' and 
            hasattr(profile, 'class_head_verified') and profile.class_head_verified):
            return True
            
        # Also check the legacy is_premium field if it exists
        if hasattr(profile, 'is_premium') and profile.is_premium:
            return True
            
        return False
    
    @staticmethod
    def check_limits(user, num_mcq, num_theory):
        """
        Validate subscription limits for quiz configuration.
        
        Raises PermissionDenied with descriptive message if limits exceeded.
        
        Args:
            user: Authenticated user
            num_mcq: Number of MCQ questions requested
            num_theory: Number of theory questions requested
            
        Raises:
            PermissionDenied: If limits are exceeded
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required")
            
        is_premium = SubscriptionLimiter.is_premium(user)
        
        # Set limits based on tier
        if is_premium:
            mcq_limit = SubscriptionLimiter.MCQ_LIMIT_PREMIUM
            theory_limit = SubscriptionLimiter.THEORY_LIMIT_PREMIUM
        else:
            mcq_limit = SubscriptionLimiter.MCQ_LIMIT_FREE
            theory_limit = SubscriptionLimiter.THEORY_LIMIT_FREE
        
        # Check MCQ limits
        if num_mcq > mcq_limit:
            tier_name = "Premium" if is_premium else "Free"
            raise PermissionDenied(
                f"{tier_name} tier allows up to {mcq_limit} MCQ questions. "
                f"You requested {num_mcq}. " +
                ("" if is_premium else "Upgrade to Premium for more questions.")
            )
        
        # Check theory limits  
        if num_theory > theory_limit:
            tier_name = "Premium" if is_premium else "Free"
            raise PermissionDenied(
                f"{tier_name} tier allows up to {theory_limit} theory questions. "
                f"You requested {num_theory}. " +
                ("" if is_premium else "Upgrade to Premium for more questions.")
            )
        
        # Check total questions for free tier (additional constraint)
        if not is_premium and (num_mcq + num_theory) > 6:
            raise PermissionDenied(
                f"Free tier allows up to 6 total questions. "
                f"You requested {num_mcq + num_theory}. Upgrade to Premium for unlimited questions."
            )
    
    @staticmethod
    def premium_feature(user, feature_name):
        """
        Check if user can access a premium feature.
        
        Args:
            user: Authenticated user
            feature_name: Name of the feature being accessed
            
        Raises:
            PermissionDenied: If user doesn't have premium access
        """
        if not SubscriptionLimiter.is_premium(user):
            raise PermissionDenied(
                f"Premium access required for {feature_name}. "
                "Upgrade to Premium to unlock advanced features."
            )
    
    @staticmethod
    def can_create_concurrent_attempts(user):
        """
        Check if user can have multiple concurrent quiz attempts.
        
        Free tier: 1 concurrent attempt
        Premium tier: unlimited concurrent attempts
        """
        return SubscriptionLimiter.is_premium(user)