"""
Signals for automatic slide processing after upload
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Slide

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Slide)
def auto_process_slide_after_upload(sender, instance, created, **kwargs):
    """
    Automatically queue slides for processing after they are created.
    
    Processing includes:
    1. Download from Cloudinary
    2. Extract text content
    3. Generate RAG embeddings
    4. Convert and render if needed
    
    Runs asynchronously using Celery to avoid blocking the upload.
    """
    # Only process if the slide has a file
    if not instance.file and not instance.file_url:
        logger.info(f"Slide {instance.id} has no file, skipping processing")
        return
    
    # Only process newly created slides (not updates)
    if not created:
        logger.info(f"Slide {instance.id} updated, skipping auto-processing")
        return
    
    # Import here to avoid circular imports
    from .tasks import process_slide_task
    
    # Queue the task asynchronously
    try:
        logger.info(f"Queuing slide {instance.id} for async processing: {instance.title}")
        task = process_slide_task.delay(instance.id)
        logger.info(f"✓ Slide {instance.id} queued successfully (task_id: {task.id})")
        
    except Exception as e:
        logger.error(f"Failed to queue slide {instance.id} for processing: {e}")
        import traceback
        traceback.print_exc()
