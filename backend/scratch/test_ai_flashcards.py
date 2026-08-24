import os
import sys
import django

# Setup Django environment
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from curriculum.models import Slide, SlideContent, Flashcard, FlashcardProgress
from curriculum.tasks import generate_ai_flashcards_from_slide_task

User = get_user_model()

def test_flashcard_generation():
    print("Testing AI Flashcard Generation...")
    
    # 1. Get or create a test user
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(username='test_flash_user', email='test@example.com', password='password123')
        print(f"Created user {user.username}")
    else:
        print(f"Using user {user.username}")

    # 2. Get a slide that has content
    slide_content = SlideContent.objects.filter(content_data__has_key='text').first()
    if not slide_content:
        print("No slide with text content found. Creating a dummy slide and content...")
        from curriculum.models import Subject, Block, SubBlock, Topic
        subject = Subject.objects.first() or Subject.objects.create(name='Test Subject')
        block = Block.objects.first() or Block.objects.create(subject=subject, name='Test Block', order=1)
        sub_block = SubBlock.objects.first() or SubBlock.objects.create(block=block, name='Test SubBlock', order=1)
        topic = Topic.objects.first() or Topic.objects.create(sub_block=sub_block, name='Test Topic', order=1)
        
        slide = Slide.objects.create(
            topic=topic,
            subject=subject,
            block=block,
            sub_block=sub_block,
            title='Test Slide',
            page_count=1,
            order=1
        )
        slide_content = SlideContent.objects.create(
            slide=slide,
            content_data={
                'text': 'The brachial plexus is a network of nerves that sends signals from your spinal cord to your shoulder, arm and hand. A brachial plexus injury occurs when these nerves are stretched, compressed, or in the most serious cases, ripped apart or torn away from the spinal cord. It is formed by the anterior rami of cervical spinal nerves C5, C6, C7 and C8, and the first thoracic spinal nerve, T1.'
            }
        )
        print("Dummy slide created.")
    
    slide = slide_content.slide
    print(f"Using slide {slide.id} with title {slide.title}")
    
    # Count before
    # Count before
    count_before = Flashcard.objects.filter(user=user, source='ai_generated').count()
    print(f"Flashcards for user before: {count_before}")

    # 3. Call the task synchronously
    print("Running task...")
    result = generate_ai_flashcards_from_slide_task(slide.id, user.id, 2)
    print(f"Task result: {result}")

    # 4. Count after
    count_after = Flashcard.objects.filter(user=user, source='ai_generated').count()
    print(f"Flashcards for user after: {count_after}")
    
    if count_after > count_before:
        print("SUCCESS! Flashcards were generated and saved.")
        new_cards = Flashcard.objects.filter(user=user, source='ai_generated').order_by('-created_at')[:result.get('generated_count', 0)]
        for c in new_cards:
            print(f" - Q: {c.front}")
            print(f"   A: {c.back}")
    else:
        print("FAILED: No new flashcards created.")

if __name__ == '__main__':
    test_flashcard_generation()
