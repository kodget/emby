#!/usr/bin/env python
"""Final status of neuroanatomy uploads"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide

slides = Slide.objects.filter(sub_block__id='neuroanatomy').order_by('title')

print("\n" + "="*70)
print("NEUROANATOMY SLIDES - FINAL STATUS")
print("="*70 + "\n")

completed = 0
pending = 0
failed = 0

for slide in slides:
    status_icon = {
        'completed': '✅',
        'pending': '⏳',
        'in_progress': '🔄',
        'failed': '❌'
    }.get(slide.generation_status, '❓')
    
    print(f"{status_icon} {slide.title[:50]:<50} {slide.generation_status:>12} ({slide.page_count} pages)")
    
    if slide.generation_status == 'completed':
        completed += 1
    elif slide.generation_status == 'pending':
        pending += 1
    elif slide.generation_status == 'failed':
        failed += 1

print("\n" + "="*70)
print(f"SUMMARY: {completed} completed | {pending} pending | {failed} failed | Total: {slides.count()}")
print("="*70)

print("\n📝 NEXT STEPS:")
if pending > 0:
    print(f"  - Wait for {pending} slide(s) to finish processing")
if failed > 0:
    print(f"  - {failed} slide(s) failed (likely PPTX timeout - need PDF conversion)")
print(f"  - {completed} slides are ready to read!")
print("\n🌐 Try accessing: https://emby-sigma.vercel.app/courses/anatomy")
print("   Navigate to: Anatomy → Third block → Neuroanatomy → [any topic]")
