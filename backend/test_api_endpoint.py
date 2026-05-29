"""
Test the AI API endpoints directly
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide
from curriculum.views import get_textbook_suggestions
from curriculum.content_extractor import get_slide_full_text
from django.test import RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 60)
print("TESTING AI API ENDPOINT")
print("=" * 60)

# Get a slide
slide = Slide.objects.first()
print(f"\nSlide ID: {slide.id}")
print(f"Title: {slide.title}")
print(f"Subject: {slide.subject.name if slide.subject else 'None'}")

# Get file URL
file_url = None
if slide.file:
    file_url = slide.file.url
elif slide.file_url:
    file_url = slide.file_url

print(f"File URL: {file_url}")

# Try to extract content
if file_url:
    print(f"\nExtracting content from {slide.file_type}...")
    content = get_slide_full_text(file_url, slide.file_type or 'pdf')
    print(f"Content length: {len(content)} characters")
    print(f"Content preview: {content[:300] if content else 'EMPTY!'}")
else:
    print("NO FILE URL!")

# Create a test request
factory = RequestFactory()
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.first()

print(f"\nTest user: {user.username}")
print(f"Is premium: {getattr(user.profile, 'is_premium', False) if hasattr(user, 'profile') else 'No profile'}")

# Create request
request = factory.post('/api/ai/textbook-suggestions/', {'slide_id': slide.id})
request.user = user

print("\nCalling get_textbook_suggestions view...")
try:
    response = get_textbook_suggestions(request)
    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.data}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
