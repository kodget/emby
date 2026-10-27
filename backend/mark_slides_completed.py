#!/usr/bin/env python
"""Mark slides with extracted content as completed"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent, SlideProcessingStatus

# Find slides that have content but are still in "indexing" status
slides_to_update = []

for slide in Slide.objects.filter(sub_block__name='Neuroanatomy'):
    try:
        content = SlideContent.objects.get(slide=slide)
        proc_status = SlideProcessingStatus.objects.get(slide=slide)
        
        if content.is_extracted and content.content_data and content.content_data.get('pages'):
            if proc_status.status in ('indexing', 'generating_quizzes'):
                slides_to_update.append((slide, proc_status))
    except (SlideContent.DoesNotExist, SlideProcessingStatus.DoesNotExist):
        pass

print(f"\n📋 Found {len(slides_to_update)} slides to mark as completed\n")

for slide, proc_status in slides_to_update:
    print(f"✅ Marking '{slide.title}' as completed")
    proc_status.status = 'completed'
    proc_status.content_extracted = True
    proc_status.save()
    
    # Also update slide generation status
    slide.generation_status = 'completed'
    slide.save(update_fields=['generation_status'])

print(f"\n✅ All slides marked as completed and should now be readable!")
