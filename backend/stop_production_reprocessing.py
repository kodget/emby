#!/usr/bin/env python
"""Stop production from reprocessing slides with memory errors"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideProcessingStatus
from django.utils import timezone

# Slides that keep failing on production due to memory
problem_slides = ['slide_53c6d7d67a8a', 'slide_b5e870a1c1da']  # CEREBRUM, Dural venous

print("\nStopping production reprocessing for memory-error slides...")

for slide_id in problem_slides:
    try:
        slide = Slide.objects.get(id=slide_id)
        proc_status = SlideProcessingStatus.objects.get(slide=slide)
        
        print(f"\n{slide.title}")
        print(f"  Current status: {proc_status.status}")
        print(f"  Attempts: {proc_status.processing_attempts}")
        
        # Mark as failed with clear message and no retry
        proc_status.status = 'failed'
        proc_status.error_message = 'Production server has insufficient memory. Processed locally instead.'
        proc_status.next_attempt_at = None  # Don't retry
        proc_status.processing_lease_until = None
        proc_status.completed_at = timezone.now()
        proc_status.save()
        
        print(f"  ✅ Marked as failed (no retry)")
        
    except (Slide.DoesNotExist, SlideProcessingStatus.DoesNotExist) as e:
        print(f"  ⚠️  Not found: {e}")

print(f"\n✅ Production will stop trying to process these slides!")
