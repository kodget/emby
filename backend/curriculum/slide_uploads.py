"""Upload validation and dispatch, independent of AI provider availability."""
import logging
from zipfile import BadZipFile, ZipFile

from rest_framework.exceptions import APIException, ValidationError

from .models import SlideProcessingStatus

logger = logging.getLogger(__name__)
MAX_SLIDE_BYTES = 100 * 1024 * 1024
SLIDE_TYPES = {'pdf', 'ppt', 'pptx', 'docx'}


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
        task = process_slide_task.delay(slide_id, token=str(token)) if token else process_slide_task.delay(slide_id)
        return task
    except Exception as exc:
        SlideProcessingStatus.objects.filter(
            slide_id=slide_id, processing_token=token, processing_lease_until__isnull=True,
            status__in=('pending', 'processing')
        ).update(
            status='failed',
            error_message='Original file saved, but processing could not be queued. Contact an administrator to retry processing.',
        )
        logger.warning('Slide dispatch failed (%s)', type(exc).__name__)
        return None


def dispatch_standalone_deck_processing(deck_id, token):
    """Queue recovery for a standalone deck whose synchronous request was interrupted."""
    try:
        from .tasks import process_standalone_deck_task
        process_standalone_deck_task.delay(deck_id, str(token))
    except Exception as exc:
        from .models import SlideDeck
        SlideDeck.objects.filter(pk=deck_id, processing_token=token,
            processing_lease_until__isnull=True, processing_status='processing').update(
            processing_status='failed',
            processing_error='Document processing could not be queued. An administrator can retry processing.',
        )
        logger.warning('Standalone deck dispatch failed (%s)', type(exc).__name__)
