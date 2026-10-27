#!/usr/bin/env python
"""Test slide API response"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent, SlideProcessingStatus
from curriculum.slide_processing import ACTIVE_STATES

# Get a processed slide
slide = Slide.objects.filter(
    sub_block__name='Neuroanatomy',
    page_count__gt=0
).first()

if not slide:
    print("No processed slides found!")
else:
    print(f"\n📄 Testing slide: {slide.title}")
    print(f"   ID: {slide.id}")
    print(f"   Page Count: {slide.page_count}")
    
    # Check processing status
    try:
        proc_status = SlideProcessingStatus.objects.get(slide=slide)
        print(f"   Processing Status: {proc_status.status}")
        print(f"   Is in ACTIVE_STATES: {proc_status.status in ACTIVE_STATES}")
        print(f"   Is in ACTIVE_STATES + 'failed': {proc_status.status in (*ACTIVE_STATES, 'failed')}")
    except SlideProcessingStatus.DoesNotExist:
        print(f"   No processing status record")
    
    # Check content
    try:
        content = SlideContent.objects.get(slide=slide)
        print(f"   Content is_extracted: {content.is_extracted}")
        if content.content_data:
            pages = content.content_data.get('pages', [])
            print(f"   Content has {len(pages)} pages")
            print(f"\n   ✅ Should be READABLE (has content)")
        else:
            print(f"   ⚠️  Content data is empty")
    except SlideContent.DoesNotExist:
        print(f"   ❌ No content record")

print(f"\nACTIVE_STATES = {ACTIVE_STATES}")
