#!/usr/bin/env python
"""Check slide status"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideProcessingStatus, SlideContent

slides = Slide.objects.filter(sub_block__name='Neuroanatomy').order_by('title')

print("\n" + "="*80)
print("NEUROANATOMY SLIDES STATUS")
print("="*80 + "\n")

for slide in slides:
    print(f"📄 {slide.title}")
    print(f"   ID: {slide.id}")
    print(f"   Generation Status: {slide.generation_status}")
    print(f"   File: {slide.file if slide.file else 'No file'}")
    print(f"   Page Count: {slide.page_count}")
    
    # Check processing status
    try:
        proc_status = SlideProcessingStatus.objects.get(slide=slide)
        print(f"   Processing Status: {proc_status.status}")
        print(f"   Content Extracted: {proc_status.content_extracted}")
        if proc_status.error_message:
            print(f"   Error: {proc_status.error_message}")
    except SlideProcessingStatus.DoesNotExist:
        print(f"   Processing Status: No processing record")
    
    # Check content
    try:
        content = SlideContent.objects.get(slide=slide)
        print(f"   Content Extracted: {content.is_extracted}")
        if content.content_data:
            pages = content.content_data.get('pages', [])
            print(f"   Content Pages: {len(pages)}")
    except SlideContent.DoesNotExist:
        print(f"   Content: No content record")
    
    print()

print("="*80)
