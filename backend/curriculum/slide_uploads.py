"""Upload validation and dispatch, independent of AI provider availability."""
import logging
from datetime import timedelta
from django.utils import timezone
from zipfile import BadZipFile, ZipFile

from rest_framework.exceptions import APIException, ValidationError
from backend.task_dispatch import dispatch_task

from .models import SlideProcessingStatus

logger = logging.getLogger(__name__)
MAX_SLIDE_BYTES = 100 * 1024 * 1024
SLIDE_TYPES = {'pdf', 'ppt', 'pptx', 'docx'}


def topic_for_upload(validated_data):
    """Use the upload title as its Learn topic within this exact module/submodule.

    Called inside the upload transaction, so a failed original save cannot leave
    an empty topic. The module lock also serializes simultaneous matching titles.
    Explicit legacy topic selections retain their existing ownership and links.
    """
    import uuid
    from .models import Block, Topic
    if validated_data.get('topic') is not None:
        return validated_data['topic']
    block = validated_data['block']
    Block.objects.select_for_update().get(pk=block.pk)
    title = validated_data['title'].strip()
    sub_block = validated_data.get('sub_block')
    topic = Topic.objects.filter(block=block, sub_block=sub_block, name__iexact=title).order_by('pk').first()
    if topic is None:
        topic = Topic.objects.create(id=f'topic_{uuid.uuid4().hex}', name=title,
                                     block=block, sub_block=sub_block)
    return topic


class UploadTooLarge(APIException):
    status_code = 413
    default_detail = 'File too large. Maximum size is 100 MB.'


def validate_slide_file(upload):
    extension = upload.name.rsplit('.', 1)[-1].lower()
    if extension not in SLIDE_TYPES:
        raise ValidationError({'file': 'Supported formats: PDF, PPT, PPTX and DOCX.'})
    if upload.size > MAX_SLIDE_BYTES:
        raise UploadTooLarge()
    if upload.size == 0:
        raise ValidationError({'file': 'File is empty.'})
    try:
        upload.seek(0)
        head = upload.read(16)
        valid = False
        if extension == 'pdf':
            valid = head.startswith(b'%PDF-')
        elif extension == 'ppt':
            valid = head.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
        else:
            # A ZIP header alone cannot distinguish Word, PowerPoint and an arbitrary archive.
            try:
                with ZipFile(upload) as archive:
                    names = set(archive.namelist())
                    main = 'ppt/presentation.xml' if extension == 'pptx' else 'word/document.xml'
                    valid = '[Content_Types].xml' in names and main in names
            except (BadZipFile, OSError, ValueError):
                valid = False
        if not valid:
            raise ValidationError({'file': 'File content does not match its extension.'})
    finally:
        upload.seek(0)
    return extension


def dispatch_slide_processing(slide_id, token=None):
    """Keep the successfully stored original available when dispatch fails."""
    try:
        from .tasks import process_slide_task
        task = dispatch_task(process_slide_task, slide_id, token=str(token)) if token else dispatch_task(process_slide_task, slide_id)
        return task
    except Exception as exc:
        SlideProcessingStatus.objects.filter(
            slide_id=slide_id, processing_token=token, processing_lease_until__isnull=True,
            status__in=('pending', 'processing')
        ).update(
            status='failed',
            next_attempt_at=timezone.now()+timedelta(minutes=1),
            error_message='Original file saved. Processing could not be queued; automatic recovery will retry.',
        )
        logger.warning('Slide dispatch failed (%s)', type(exc).__name__)
        return None


def dispatch_standalone_deck_processing(deck_id, token=None):
    """Queue new or recovered standalone conversions after the original commits."""
    try:
        from .tasks import process_standalone_deck_task
        return dispatch_task(process_standalone_deck_task, deck_id, str(token) if token else None)
    except Exception as exc:
        from .models import SlideDeck
        SlideDeck.objects.filter(pk=deck_id, processing_token=token,
            processing_lease_until__isnull=True, processing_status__in=('pending', 'processing')).update(
            processing_status='failed',
            next_attempt_at=timezone.now()+timedelta(minutes=1),
            processing_error='Original file saved. Processing could not be queued; automatic recovery will retry.',
        )
        logger.warning('Standalone deck dispatch failed (%s)', type(exc).__name__)
