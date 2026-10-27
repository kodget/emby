#!/usr/bin/env python
"""Test API access to slides"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent, SlideProcessingStatus
from django.contrib.auth import get_user_model

User = get_user_model()

# Get user and slide
user = User.objects.filter(email='nexatage@gmail.com').first()
slide = Slide.objects.filter(sub_block__name='Neuroanatomy', page_count__gt=0).first()

print(f"\nAPI Access Test for: {slide.title}")
print(f"Slide ID: {slide.id}")
print(f"URL would be: /api/curriculum/slides/{slide.id}/content/")

# Simulate the API view logic
try:
    from curriculum.views import visible
    slide_check = visible(Slide, user).get(id=slide.id)
    print(f"✅ Slide found via visible() filter")
except Slide.DoesNotExist:
    print(f"❌ Slide NOT found via visible() filter - would return 404")
    exit()

# Check content
slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
cached_pages = slide_content.content_data.get('pages', []) if slide_content.content_data else []

print(f"\nContent Check:")
print(f"  is_extracted: {slide_content.is_extracted}")
print(f"  has pages: {len(cached_pages) > 0}")
print(f"  page count: {len(cached_pages)}")

if slide_content.is_extracted and cached_pages:
    print(f"\n✅ Would return 200 OK with {len(cached_pages)} pages")
else:
    # Check processing status
    from curriculum.slide_processing import ACTIVE_STATES
    processing = SlideProcessingStatus.objects.filter(slide=slide).first()
    
    if processing:
        print(f"\nProcessing Status: {processing.status}")
        print(f"  In ACTIVE_STATES: {processing.status in ACTIVE_STATES}")
        print(f"  In ACTIVE + failed: {processing.status in (*ACTIVE_STATES, 'failed')}")
        
        if processing.status in (*ACTIVE_STATES, 'failed'):
            failed = processing.status == 'failed' and not processing.next_attempt_at
            if failed:
                print(f"\n❌ Would return 409 (conflict) - processing failed")
            else:
                print(f"\n⏳ Would return 202 (processing) - not ready yet")
        else:
            print(f"\n🤔 Status '{processing.status}' not in ACTIVE_STATES, would try legacy render")
    else:
        print(f"\n🤔 No processing status, would try legacy render")
