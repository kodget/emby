#!/usr/bin/env python
"""Check slide access permissions"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide
from django.contrib.auth import get_user_model

User = get_user_model()

# Get a neuroanatomy slide
slide = Slide.objects.filter(sub_block__name='Neuroanatomy').first()

print(f"\nSlide: {slide.title}")
print(f"  ID: {slide.id}")
print(f"  Class Group: {slide.class_group}")
print(f"  Class Group Active: {slide.class_group.is_active if slide.class_group else 'N/A'}")
print(f"  File in Cloudinary: {slide.file}")

# Check your user
user = User.objects.filter(email='nexatage@gmail.com').first()
if user:
    print(f"\nYour User: {user.email}")
    print(f"  User ID: {user.id}")
    if hasattr(user, 'class_group') and user.class_group:
        print(f"  Your Class Group: {user.class_group}")
        print(f"  Match: {user.class_group == slide.class_group}")
    else:
        print(f"  No class_group field on user")

# Check if slide would be visible using the visibility filter
from curriculum.views import visible
try:
    visible_slide = visible(Slide, user).filter(id=slide.id).first()
    if visible_slide:
        print(f"\n✅ Slide IS visible to user via visible() filter")
    else:
        print(f"\n❌ Slide is NOT visible to user via visible() filter")
except Exception as e:
    print(f"\n❌ Error checking visibility: {e}")
