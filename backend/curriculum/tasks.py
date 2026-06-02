"""
Celery tasks for async slide processing

FLOW:
1. File uploaded to Cloudinary (in upload_views.py)
2. Celery task triggered (this file)
3. Pipeline: ANY FILE → PPTX → PDF → IMAGES
4. Images stored in Cloudinary  
5. Frontend displays images
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_slide_task(self, slide_id: str):
    """
    Async task to process a slide after upload
    
    PIPELINE: ANY FILE → PPTX → PDF → IMAGES
    
    Args:
        slide_id: ID of the slide to process
        
    Returns:
        dict: Processing results
    """
    from .models import Slide, SlideProcessingStatus, SlideContent
    from .services.slide_conversion_pipeline import SlideConversionPipeline
    import cloudinary.uploader
    
    try:
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            logger.error(f"Slide {slide_id} not found")
            return {'success': False, 'error': 'Slide not found'}
        
        # Get Cloudinary URL
        cloudinary_url = slide.file_url if slide.file_url else (slide.file.url if slide.file else None)
        if not cloudinary_url:
            logger.error(f"Slide {slide_id} has no file URL")
            return {'success': False, 'error': 'No file URL found'}
        
        # Update status to processing
        status_obj, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
        status_obj.status = 'processing'
        status_obj.started_at = timezone.now()
        status_obj.error_message = ''
        status_obj.save()
        
        logger.info(f"=== STARTING SLIDE PROCESSING ===")
        logger.info(f"Slide ID: {slide_id}")
        logger.info(f"Title: {slide.title}")
        logger.info(f"File URL: {cloudinary_url}")
        logger.info(f"File Type: {slide.file_type}")
        
        # Run the conversion pipeline
        result = SlideConversionPipeline.process_slide(
            cloudinary_url=cloudinary_url,
            slide_id=slide_id,
            original_file_type=slide.file_type or 'pdf'
        )
        
        # Handle result
        if result['success']:
            logger.info(f"✓ Pipeline completed successfully")
            
            # Update slide page count
            slide.page_count = result['page_count']
            slide.save(update_fields=['page_count'])
            
            # Store images in Cloudinary and get URLs
            logger.info(f"Uploading {len(result['image_paths'])} images to Cloudinary...")
            pages = []  # frontend shape: [{page_number, image_url, width, height}]

            for idx, image_path in enumerate(result['image_paths'], 1):
                try:
                    cloudinary_result = cloudinary.uploader.upload(
                        image_path,
                        folder=f"emby/slides/{slide_id}",
                        public_id=f"page_{idx:04d}",
                        resource_type='image',
                        format='jpg',
                        quality='auto:best',
                        timeout=60
                    )
                    # Store in the shape ReaderContent expects:
                    # page.image_url, page.page_number, page.width, page.height
                    pages.append({
                        'page_number': idx,
                        'image_url': cloudinary_result['secure_url'],
                        'width': cloudinary_result.get('width', 1280),
                        'height': cloudinary_result.get('height', 960),
                    })
                    logger.info(f"✓ Uploaded page {idx} to Cloudinary")
                except Exception as e:
                    logger.error(f"Failed to upload page {idx}: {e}")

            # Store in database — shape that get_slide_content returns directly
            slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
            slide_content.content_data = {
                'text': result.get('text_content', ''),
                'pages': pages,
                'total_pages': len(pages),   # get_slide_content reads this key
                'page_count': len(pages),
            }
            slide_content.is_extracted = True
            slide_content.extracted_at = timezone.now()
            slide_content.save()
            
            # Update processing status
            status_obj.status = 'completed'
            status_obj.completed_at = timezone.now()
            status_obj.error_message = ''
            status_obj.save()
            
            logger.info(f"✓✓✓ SLIDE {slide_id} SUCCESSFULLY PROCESSED ✓✓✓")
            logger.info(f"    Pages: {result['page_count']}")
            logger.info(f"    Images uploaded to Cloudinary")
            logger.info(f"    Page count updated")
            
            return {
                'success': True,
                'slide_id': slide_id,
                'page_count': result['page_count'],
                'image_urls': pages
            }
        
        else:
            # Pipeline failed
            error_message = result.get('error', 'Unknown error')
            logger.error(f"✗ Pipeline failed: {error_message}")
            
            status_obj.status = 'failed'
            status_obj.error_message = error_message
            status_obj.completed_at = timezone.now()
            status_obj.save()
            
            return {
                'success': False,
                'slide_id': slide_id,
                'error': error_message
            }
        
    except Exception as e:
        logger.error(f"Task error for slide {slide_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        try:
            status_obj = SlideProcessingStatus.objects.get(slide_id=slide_id)
            status_obj.status = 'failed'
            status_obj.error_message = str(e)
            status_obj.completed_at = timezone.now()
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
