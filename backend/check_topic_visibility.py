#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Topic, SubBlock
from django.contrib.auth import get_user_model

User = get_user_model()

# Get your user
user = User.objects.get(email='nexatage@gmail.com')
print(f"User: {user.email}")
print(f"Class Group: {user.class_group if hasattr(user, 'class_group') else 'No class_group attribute'}")

# Get neuroanatomy sub-block
sb = SubBlock.objects.get(id='neuroanatomy')

# Try the visibility filter
from curriculum.views import visible

try:
    visible_topics = visible(Topic, user).filter(sub_block=sb)
    print(f"\nVisible topics to user: {visible_topics.count()}")
    
    for topic in visible_topics[:10]:
        print(f"  - {topic.name}")
except Exception as e:
    print(f"\nError with visible() filter: {e}")

# Check topics directly
all_topics = Topic.objects.filter(sub_block=sb)
print(f"\nAll topics (no filter): {all_topics.count()}")

# Check class_group on topics
for topic in all_topics[:5]:
    slides = topic.slides.all()
    if slides.exists():
        slide = slides.first()
        print(f"\nTopic: {topic.name}")
        print(f"  Slide class_group: {slide.class_group if slide else 'No slide'}")
        print(f"  User can access: {slide.class_group == user.class_group if slide and hasattr(user, 'class_group') else 'Unknown'}")
