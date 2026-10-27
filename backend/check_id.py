#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Topic, Block, Slide

id_to_check = '300l-medical-student-lecture-diencephalo-588acdf0'

print(f"\nChecking ID: {id_to_check}\n")

# Check if it's a topic
topic = Topic.objects.filter(id=id_to_check).first()
if topic:
    print(f"✅ Found as TOPIC: {topic.name}")
    print(f"   Sub-block: {topic.sub_block}")
    slides = Slide.objects.filter(topic=topic)
    print(f"   Slides: {slides.count()}")
    if slides.exists():
        print(f"   First slide: {slides.first().title}")
        print(f"   Slide ID: {slides.first().id}")
else:
    print("❌ Not found as TOPIC")

# Check if it's a block
block = Block.objects.filter(id=id_to_check).first()
if block:
    print(f"✅ Found as BLOCK: {block.name}")
else:
    print("❌ Not found as BLOCK")

# Check if it's a slide
slide = Slide.objects.filter(id=id_to_check).first()
if slide:
    print(f"✅ Found as SLIDE: {slide.title}")
else:
    print("❌ Not found as SLIDE")

print("\n" + "="*60)
print("The frontend is calling /api/blocks/{id}/ but the ID is a TOPIC!")
print("This is the routing mismatch causing the 404.")
print("="*60)
