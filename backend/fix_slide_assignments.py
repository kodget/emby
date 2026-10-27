#!/usr/bin/env python
"""Fix slide subject and block assignments"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide

# Update all neuroanatomy slides to have proper subject and block
slides = Slide.objects.filter(sub_block__name='Neuroanatomy')

print(f"\nFixing {slides.count()} Neuroanatomy slides...")

for slide in slides:
    updates = {}
    
    if not slide.subject and slide.sub_block:
        slide.subject = slide.sub_block.block.subject
        updates['subject'] = True
    
    if not slide.block and slide.sub_block:
        slide.block = slide.sub_block.block
        updates['block'] = True
    
    if updates:
        slide.save()
        print(f"✅ Fixed {slide.title[:50]}: {', '.join(updates.keys())}")
    else:
        print(f"⏭️  {slide.title[:50]}: already has subject and block")

print(f"\n✅ All slides now have subject and block assignments!")
