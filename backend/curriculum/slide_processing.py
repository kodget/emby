"""Owned course conversion attempts; readable page sets publish atomically."""
from datetime import timedelta
import logging
import uuid

from django.db import transaction
from django.utils import timezone

from .models import Slide, SlideContent, SlideProcessingStatus
from .services.document_extraction import source_key, is_complete, ERRORS

logger = logging.getLogger(__name__)
LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 4
ACTIVE_STATES = ('pending', 'processing', 'downloading', 'converting_to_jpg')


class Superseded(Exception):
    pass


@transaction.atomic
def reserve(slide_id, *, manual=False, cutoff=None):
    # All conversion paths lock the source before its status row.
    slide = Slide.objects.select_for_update().filter(pk=slide_id, class_group__is_active=True).first()
    if not slide or (slide.asset_id and slide.asset.class_group_id != slide.class_group_id):
        return None
    state, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
    state = SlideProcessingStatus.objects.select_for_update().get(pk=slide_id)
    now = timezone.now()
    if state.processing_lease_until and state.processing_lease_until > now:
        return None
    if not manual:
        due = state.next_attempt_at is not None and state.next_attempt_at <= now
        stale = state.status in ACTIVE_STATES and (state.started_at or slide.created_at) <= (cutoff or now-LEASE)
        if not (due or stale):
            return None
        if state.processing_attempts >= MAX_ATTEMPTS:
            state.status = 'failed'; state.next_attempt_at = None
            state.processing_lease_until = None
            state.error_message = 'Processing stopped after repeated failures. An uploader can retry.'
            state.save()
            return None
    else:
        # Do not repeatedly replace a newly queued manual request.
        if state.processing_token and state.status in ACTIVE_STATES and state.started_at and state.started_at > now-LEASE:
            return None
        state.processing_attempts = 0
    state.processing_token = uuid.uuid4()
    state.processing_lease_until = None
    state.next_attempt_at = None
    state.status = 'processing'
    state.started_at = now
    state.error_message = ''
    state.processing_progress = {}
    state.save()
    return state.processing_token


@transaction.atomic
def claim(slide_id, token=None):
    slide = Slide.objects.select_for_update().filter(pk=slide_id, class_group__is_active=True).first()
    if slide is None or (slide.asset_id and slide.asset.class_group_id != slide.class_group_id):
        return None
    state, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
    if token is None:
        if state.processing_token or state.status not in ACTIVE_STATES:
            return None
        state.processing_token = uuid.uuid4()
    elif (str(state.processing_token) != str(token) or state.processing_lease_until is not None
          or state.status not in ACTIVE_STATES):
        return None
    if state.processing_attempts >= MAX_ATTEMPTS:
        return None
    state.processing_attempts += 1
    state.processing_lease_until = timezone.now()+LEASE
    state.next_attempt_at = None
    state.status = 'processing'
    state.started_at = timezone.now()
    state.error_message = ''
    state.save()
    return slide, state, source_key(slide)


def owned(state):
    return SlideProcessingStatus.objects.filter(pk=state.pk, processing_token=state.processing_token)


class Progress:
    """Only the owning worker can publish pipeline phase updates."""
    def __init__(self, state):
        self.state = state
        self.status = 'processing'

    def save(self, **kwargs):
        if not owned(self.state).filter(status__in=ACTIVE_STATES).update(status=self.status,
                processing_lease_until=timezone.now()+LEASE):
            raise Superseded()

    def report(self, phase, completed, total):
        if not owned(self.state).filter(status__in=ACTIVE_STATES).update(
                processing_progress={'phase': phase, 'completed': completed, 'total': total},
                processing_lease_until=timezone.now()+LEASE):
            raise Superseded()


def fail(state, detail=''):
    owned(state).filter(status__in=ACTIVE_STATES).update(status='failed', processing_lease_until=None,
        completed_at=timezone.now(), next_attempt_at=timezone.now()+timedelta(minutes=1)
        if state.processing_attempts < MAX_ATTEMPTS else None,
        error_message=detail or ('Slide processing failed. Automatic recovery will retry, or an uploader can retry.'
            if state.processing_attempts < MAX_ATTEMPTS else
            'Processing stopped after repeated failures. An uploader can retry.'))


def process(slide_id, *, token=None, local_file_path=None):
    claim_result = claim(slide_id, token)
    if claim_result is None:
        return {'success': False, 'skipped': True, 'slide_id': slide_id}
    slide, state, original_source = claim_result
    result, staged, published = None, [], False
    try:
        from .private_media import content_file_url, upload_asset
        from .services.slide_conversion_pipeline import SlideConversionPipeline
        from PIL import Image
        progress = Progress(state)
        result = SlideConversionPipeline.process_slide(cloudinary_url=local_file_path or content_file_url(slide),
            slide_id=slide_id, original_file_type=slide.file_type or 'pdf', status_obj=progress)
        if not result['success']:
            # The pipeline returns predefined safe messages, never raw provider exceptions.
            fail(state, result.get('error', ''))
            return {'success': False, 'slide_id': slide_id,
                    'error': result.get('error') or 'Slide processing failed. Please retry.',
                    'error_code': result.get('error_code', 'render_failed')}
        if not result['image_paths'] or len(result['image_paths']) != result['page_count'] or len(result['pages']) != result['page_count']:
            raise RuntimeError('Incomplete render.')
        pages = []
        for number, path in enumerate(result['image_paths'], 1):
            progress.report('storing_pages', number-1, result['page_count'])
            with Image.open(path) as image:
                width, height = image.size
            asset = upload_asset(path, class_group=slide.class_group, uploaded_by=slide.uploaded_by,
                folder=f'emby/slides/{slide_id}', resource_type='image', format='jpg', quality='auto:best', timeout=60)
            staged.append(asset)
            pages.append({**result['pages'][number-1], 'page_number': number, 'asset_id': str(asset.pk),
                          'width': width, 'height': height})
        with transaction.atomic():
            current = Slide.objects.select_for_update().get(pk=slide_id)
            locked = SlideProcessingStatus.objects.select_for_update().get(pk=slide_id)
            if (locked.processing_token != state.processing_token or locked.status not in ACTIVE_STATES
                    or current.class_group_id != slide.class_group_id or not current.class_group.is_active
                    or source_key(current) != original_source):
                raise Superseded()
            content, _ = SlideContent.objects.get_or_create(slide=current)
            extraction = {**result['text_extraction'], 'source_key': original_source}
            content.content_data = {**(content.content_data or {}), 'text': result.get('text_content', ''),
                'text_extraction': extraction, 'pages': pages, 'total_pages': len(pages), 'page_count': len(pages)}
            complete = is_complete(content.content_data)
            content.is_extracted = True
            content.extraction_error = ''
            content.extracted_at = timezone.now()
            content.save()
            current.page_count = len(pages)
            current.generation_status = 'in_progress'
            current.save(update_fields=['page_count', 'generation_status'])
            locked.status = 'generating_quizzes' if complete else 'indexing'
            locked.content_extracted = complete
            locked.processing_lease_until = locked.next_attempt_at = None
            locked.completed_at = timezone.now()
            locked.error_message = ''
            locked.save()
            from .document_index import request_index
            request_index(current, force=True)
            if complete:
                # Persist the durable generation request inside publication; its broker send is on_commit.
                from learning.generation_dispatch import request_generation
                queued = request_generation(current)
                if not queued:
                    from learning.models import QuestionGenerationJob as Job
                    job = Job.objects.filter(slide=current).first()
                    if job and (job.status == Job.Status.COMPLETED or
                            (job.status in {Job.Status.FAILED, Job.Status.PARTIAL} and job.attempts >= Job.MAX_ATTEMPTS)):
                        # Re-rendering unchanged bytes must not leave an already
                        # finished bank displaying "generating" indefinitely.
                        done = job.status == Job.Status.COMPLETED
                        current.generation_status = 'completed' if done else 'failed'
                        current.save(update_fields=['generation_status'])
                        locked.status = 'completed' if done else 'failed'
                        locked.error_message = '' if done else job.error
                        locked.save(update_fields=['status', 'error_message'])
        published = True
        return {'success': True, 'reading_ready': True, 'ai_ready': complete,
                'slide_id': slide_id, 'page_count': len(pages), 'image_urls': pages,
                'text_extraction': extraction, 'page_errors': extraction.get('error_counts', {})}
    except Superseded:
        return {'success': False, 'skipped': True, 'slide_id': slide_id}
    except Exception as exc:
        logger.warning('Slide conversion failed (%s)', type(exc).__name__)
        fail(state)
        return {'success': False, 'slide_id': slide_id, 'error': 'Slide processing failed. Please retry.'}
    finally:
        if not published:
            from .private_media import discard_new_asset
            for asset in staged:
                try:
                    discard_new_asset(asset)
                except Exception:
                    logger.warning('Unpublished slide page requires storage reconciliation.')
        from .services.document_rendering import cleanup_render
        try:
            cleanup_render(result)
        except Exception:
            logger.warning('Temporary render cleanup failed.')
