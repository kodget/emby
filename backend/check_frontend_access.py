#!/usr/bin/env python
"""Check what the frontend should see"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, Topic, SubBlock

# Check topics
subblock = SubBlock.objects.filter(name='Neuroanatomy').first()
if not subblock:
    print("ERROR: Neuroanatomy sub-block not found!")
    exit(1)

print(f"\nSub-block: {subblock.name} (ID: {subblock.id})")
print(f"Block: {subblock.block}")
print(f"Subject: {subblock.block.subject}")

topics = Topic.objects.filter(sub_block=subblock)
print(f"\nTopics under Neuroanatomy: {topics.count()}")

for topic in topics:
    slides = Slide.objects.filter(topic=topic)
    print(f"\n  Topic: {topic.name}")
    print(f"    ID: {topic.id}")
    print(f"    Slides: {slides.count()}")
    
    for slide in slides:
        print(f"      - {slide.title[:40]} (status: {slide.generation_status})")

# Check what happens when we try to list slides directly
print(f"\n\nDirect slide query (sub_block filter):")
slides = Slide.objects.filter(sub_block=subblock)
print(f"  Found {slides.count()} slides")

print(f"\n\nDirect slide query (topic filter, first topic):")
first_topic = topics.first()
if first_topic:
    slides = Slide.objects.filter(topic=first_topic)
    print(f"  Topic: {first_topic.name}")
    print(f"  Found {slides.count()} slides")
    if slides.exists():
        slide = slides.first()
        print(f"  Sample slide ID: {slide.id}")
        print(f"  Material ID for frontend: {slide.id}")
