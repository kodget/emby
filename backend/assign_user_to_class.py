#!/usr/bin/env python
"""Assign user to the class group"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import ClassGroup, Profile

User = get_user_model()

# Get your user
user = User.objects.get(email='nexatage@gmail.com')
print(f"User: {user.email}")

# Get the class group
class_group = ClassGroup.objects.get(id=1)  # LASUCOM INVICTUS
print(f"Class Group: {class_group}")

# Check if user has a profile
try:
    profile = user.profile
    print(f"User already has profile")
    print(f"  Current class_group: {profile.class_group}")
except Profile.DoesNotExist:
    # Create profile
    profile = Profile.objects.create(
        user=user,
        class_group=class_group,
        class_role='student'
    )
    print(f"✅ Created new profile for user")

# Update class group
if profile.class_group != class_group:
    profile.class_group = class_group
    profile.is_active = True
    profile.save()
    print(f"✅ Updated user's class_group to: {class_group}")
else:
    print(f"✅ User already in correct class_group")

print(f"\n✅ User is now assigned to class group!")
print(f"User should now be able to see all Anatomy materials.")
