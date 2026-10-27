#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, Topic

# Find our uploaded slides by looking for the specific topic IDs we created
sample_topic_id = '300l-medical-student-lecture-diencephalo-588acdf0'

topic = Topic.objects.filter(id=sample_topic_id).first()
if topic:
    print(f"✅ Found our topic: {topic.name}")
    print(f"   ID: {topic.id}")
    print(f"   Sub-block: {topic.sub_block}")
    print(f"   Sub-block ID: {topic.sub_block.id if topic.sub_block else 'None'}")
    print(f"   Block: {topic.sub_block.block if topic.sub_block else 'None'}")
    print(f"   Block ID: {topic.sub_block.block.id if topic.sub_block else 'None'}")
    
    slides = Slide.objects.filter(topic=topic)
    print(f"   Slides: {slides.count()}")
    if slides.exists():
        slide = slides.first()
        print(f"\n   Sample slide:")
        print(f"     Title: {slide.title}")
        print(f"     ID: {slide.id}")
        print(f"     Status: {slide.generation_status}")
        print(f"     Sub-block: {slide.sub_block}")
        print(f"     Block: {slide.block}")
else:
    print("❌ Topic not found!")

# Count all our topics
our_topics = Topic.objects.filter(id__startswith='300l-') | Topic.objects.filter(id__startswith='anatomy-') | Topic.objects.filter(id__startswith='basal-') | Topic.objects.filter(id__startswith='hypothalamus') | Topic.objects.filter(id__startswith='lasucom') | Topic.objects.filter(id__startswith='meninges') | Topic.objects.filter(id__startswith='visual-') | Topic.objects.filter(id__startswith='cerbellum') | Topic.objects.filter(id__startswith='cerebrum') | Topic.objects.filter(id__startswith='dural-') | Topic.objects.filter(id__startswith='limbic-') | Topic.objects.filter(id__startswith='the-ventricular')

print(f"\n\nTotal topics we created: {our_topics.count()}")
for t in our_topics:
    print(f"  - {t.name[:50]} (sub-block: {t.sub_block.id if t.sub_block else 'None'})")
