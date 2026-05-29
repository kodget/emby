"""
Celery tasks for async slide processing
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_slide_task(self, slide_id: str):
    """
    Async task to process a slide after upload
    
    Args:
        slide_id: ID of the slide to process
        
    Returns:
        dict: Processing results
    """
    from .models import Slide, SlideProcessingStatus
    from .services.slide_processor import SlideProcessor
    
    try:
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            logger.error(f"Slide {slide_id} not found")
            return {'success': False, 'error': 'Slide not found'}
        
        # Update status to processing
        status_obj, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
        status_obj.status = 'processing'
        status_obj.started_at = timezone.now()
        status_obj.error_message = ''
        status_obj.save()
        
        logger.info(f"Starting async processing for slide {slide_id}: {slide.title}")
        
        # Process the slide
        result = SlideProcessor.process_slide(slide)
        
        # Update status based on result
        if result['success']:
            status_obj.status = 'completed'
            status_obj.completed_at = timezone.now()
            status_obj.content_extracted = result.get('content_extracted', False)
            status_obj.rag_processed = result.get('rag_processed', False)
            logger.info(f"✓ Slide {slide_id} processed successfully")
        else:
            status_obj.status = 'failed'
            status_obj.error_message = result.get('error', 'Unknown error')
            logger.error(f"✗ Slide {slide_id} processing failed: {status_obj.error_message}")
        
        status_obj.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Task error for slide {slide_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        try:
            status_obj = SlideProcessingStatus.objects.get(slide_id=slide_id)
            status_obj.status = 'failed'
            status_obj.error_message = str(e)
            status_obj.save()
        except:
            pass
        
        # Retry the task
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for slide {slide_id}")
            return {'success': False, 'error': f'Max retries exceeded: {str(e)}'}


@shared_task
def process_multiple_slides_task(slide_ids: list):
    """
    Process multiple slides in batch
    
    Args:
        slide_ids: List of slide IDs to process
        
    Returns:
        dict: Summary of results
    """
    results = {
        'total': len(slide_ids),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    for slide_id in slide_ids:
        try:
            result = process_slide_task.delay(slide_id)
            results['details'].append({
                'slide_id': slide_id,
                'task_id': result.id,
                'status': 'queued'
            })
        except Exception as e:
            logger.error(f"Failed to queue slide {slide_id}: {e}")
            results['failed'] += 1
            results['details'].append({
                'slide_id': slide_id,
                'status': 'error',
                'error': str(e)
            })
    
    return results


@shared_task
def cleanup_old_temp_files():
    """
    Periodic task to clean up old temporary files
    """
    import os
    import shutil
    import tempfile
    from datetime import datetime, timedelta
    
    temp_dir = tempfile.gettempdir()
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    cleaned = 0
    for item in os.listdir(temp_dir):
        if item.startswith('slide_') or item.startswith('slides_'):
            item_path = os.path.join(temp_dir, item)
            try:
                if os.path.isdir(item_path):
                    # Check modification time
                    mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                    if mtime < cutoff_time:
                        shutil.rmtree(item_path, ignore_errors=True)
                        cleaned += 1
                        logger.info(f"Cleaned up old temp directory: {item_path}")
            except Exception as e:
                logger.error(f"Error cleaning {item_path}: {e}")
    
    logger.info(f"Cleanup complete: removed {cleaned} old temp directories")
    return {'cleaned': cleaned}
