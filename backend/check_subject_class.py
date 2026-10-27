#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Subject
from django.contrib.auth import get_user_model

User = get_user_model()

# Get user
user = User.objects.get(email='nexatage@gmail.com')
print(f"User: {user.email}")

if hasattr(user, 'profile') and user.profile:
    user_class = user.profile.class_group
    print(f"User class_group: {user_class}")
    print(f"User class_group ID: {user_class.id if user_class else 'None'}")
else:
    print("User has no profile!")
    user_class = None

# Get subject
subject = Subject.objects.get(name='Anatomy')
print(f"\nSubject: {subject.name}")
print(f"Subject class_group: {subject.class_group}")
print(f"Subject class_group ID: {subject.class_group.id if subject.class_group else 'None'}")

if subject.class_group and user_class:
    print(f"\nMatch: {subject.class_group.id == user_class.id}")
else:
    print(f"\n❌ MISMATCH: Subject or User has no class_group!")

print("\n" + "="*60)
if subject.class_group != user_class:
    print("PROBLEM: The Subject class_group doesn't match user's class_group!")
    print(f"Need to update Subject class_group from {subject.class_group} to {user_class}")
