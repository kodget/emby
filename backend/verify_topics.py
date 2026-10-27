#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import SubBlock, Topic, Slide

# Get the neuroanatomy sub-block
sb = SubBlock.objects.get(id='neuroanatomy')
print(f"\nSub-block: {sb.name} (ID: {sb.id})")
print(f"Block: {sb.block.name} (ID: {sb.block.id})")
print(f"Block Subject: {sb.block.subject.name}")

# Check topics
topics = Topic.objects.filter(sub_block=sb)
print(f"\nTopics under this sub-block: {topics.count()}")
for topic in topics:
    slides = Slide.objects.filter(topic=topic)
    print(f"  - {topic.name} (ID: {topic.id}, Slides: {slides.count()})")

# Check slides
slides = Slide.objects.filter(sub_block=sb)
print(f"\nTotal slides in sub-block: {slides.count()}")

# Check if slides have topics assigned
slides_with_topic = slides.filter(topic__isnull=False)
slides_without_topic = slides.filter(topic__isnull=True)
print(f"Slides WITH topic: {slides_with_topic.count()}")
print(f"Slides WITHOUT topic: {slides_without_topic.count()}")

if slides_without_topic.exists():
    print("\nSlides without topics:")
    for slide in slides_without_topic[:5]:
        print(f"  - {slide.title}")

# Show recent topics created
recent_topics = Topic.objects.filter(sub_block=sb).order_by('-created_at')[:5]
print(f"\nMost recent topics:")
for topic in recent_topics:
    print(f"  - {topic.name} (created: {topic.created_at})")
