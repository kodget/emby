"""
Signal handlers for quiz system integration.

Handles automatic question generation when slides are processed.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Slide, SlidePage
from .tasks import generate_questions_task

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Slide)
def trigger_question_generation_on_slide_save(sender, instance, created, **kwargs):
    """
    Trigger question generation when a slide is newly created or updated.
    
    Only triggers for slides that have been successfully processed and have content.
    Implements task 17.1: Create post_save signal handler for slide processing.
    """
    # Only process slides that are newly created and fully processed
    if not created:
        return
        
    # Check if slide has content (page_count > 0 indicates successful processing)
    if instance.page_count <= 0:
        logger.info(f"Skipping question generation for slide {instance.id} - no pages processed yet")
        return
    
    # Check if slide has subject/topic information for better question generation
    if not instance.subject:
        logger.info(f"Skipping question generation for slide {instance.id} - no subject assigned")
        return
        
    logger.info(f"Triggering question generation for slide {instance.id}: {instance.title}")
    
    # Queue async question generation task
    # Default to 3 MCQs and 1 theory question for newly processed slides
    try:
        generate_questions_task.delay(
            slide_id=str(instance.id),
            mcq_count=3,
            theory_count=1,
            difficulty='medium'
        )
        logger.info(f"Queued question generation task for slide {instance.id}")
    except Exception as e:
        logger.error(f"Failed to queue question generation for slide {instance.id}: {e}")


@receiver(post_save, sender=SlidePage)
def trigger_question_generation_on_page_completion(sender, instance, created, **kwargs):
    """
    Trigger question generation when the last page of a slide deck is processed.
    
    This ensures questions are generated only after all slide content is available.
    """
    if not created:
        return
        
    slide = instance.slide_deck
    if not slide:
        return
        
    # Check if this is the last page being processed
    total_pages = slide.page_count
    processed_pages = slide.pages.count()
    
    if processed_pages >= total_pages and total_pages > 0:
        logger.info(f"All pages processed for slide {slide.id}, triggering question generation")
        
        # Check if questions already exist for this slide to avoid duplicates
        from .models import QuizQuestion
        existing_questions = QuizQuestion.objects.filter(
            source_slide=slide
        ).exists()
        
        if existing_questions:
            logger.info(f"Questions already exist for slide {slide.id}, skipping generation")
            return
            
        # Queue question generation
        try:
            generate_questions_task.delay(
                slide_id=str(slide.id),
                mcq_count=4,  # Slightly more questions for completed slide decks
                theory_count=2,
                difficulty='medium'
            )
            logger.info(f"Queued question generation task for completed slide {slide.id}")
        except Exception as e:
            logger.error(f"Failed to queue question generation for completed slide {slide.id}: {e}")