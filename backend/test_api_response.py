#!/usr/bin/env python
"""Test what the API actually returns for a topic"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Topic, Slide
from django.contrib.auth import get_user_model
from curriculum.views import visible

User = get_user_model()

# Get user
user = User.objects.get(email='nexatage@gmail.com')

# Get a topic
topic = Topic.objects.filter(name__icontains='Hypothalamus').first()
if not topic:
    print("Topic not found!")
    exit(1)

print(f"Topic: {topic.name}")
print(f"Topic ID: {topic.id}")
print(f"Sub-block: {topic.sub_block}")

# Check if topic is visible to user
visible_topics = visible(Topic, user).filter(id=topic.id)
print(f"\nTopic visible to user: {visible_topics.exists()}")

# Get slides for this topic
slides = Slide.objects.filter(topic=topic)
print(f"\nSlides in topic (direct query): {slides.count()}")

# Get slides using visible filter
visible_slides = visible(Slide, user).filter(topic=topic)
print(f"Slides visible to user: {visible_slides.count()}")

if visible_slides.exists():
    for slide in visible_slides:
        print(f"\n  Slide: {slide.title}")
        print(f"    ID: {slide.id}")
        print(f"    Status: {slide.generation_status}")
        print(f"    Pages: {slide.page_count}")
        print(f"    Class group: {slide.class_group}")
        print(f"    File: {slide.file}")
else:
    print("\n❌ NO VISIBLE SLIDES!")
    
    # Debug why
    if slides.exists():
        slide = slides.first()
        print(f"\nSlide exists but not visible:")
        print(f"  Slide class_group: {slide.class_group}")
        print(f"  User class_group: {user.profile.class_group if hasattr(user, 'profile') and user.profile else 'None'}")
        print(f"  Match: {slide.class_group == user.profile.class_group if hasattr(user, 'profile') and user.profile and slide.class_group else 'No'}")

print(f"\n" + "="*60)
print(f"Expected API endpoint:")
print(f"GET /api/curriculum/slides/?topic={topic.id}")
print(f"Should return {visible_slides.count()} slide(s)")
