from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile, UserRole


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Create profile when user is created"""
    if created:
        Profile.objects.create(
            user=instance,
            role=UserRole.STUDENT  # default role
        )
