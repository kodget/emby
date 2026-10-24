"""Serialize matching upload intents and replay their saved, authorized result."""
import hashlib
import json
import logging
import uuid

from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from .models import UploadReceipt

logger = logging.getLogger(__name__)


class UploadConflict(APIException):
    status_code = 409
    default_detail = 'This upload request was already used for a different document. Select the file again.'


class UploadGone(APIException):
    status_code = 410
    default_detail = 'The document from this upload is no longer available. Select the file again to upload it.'


class StorageUnavailable(APIException):
    status_code = 502
    default_detail = 'File storage is unavailable. Please try again.'


def execute_upload(*, user, request_id, kind, metadata, upload, create, queryset):
    """create(staged) returns the new model; staged holds only this attempt's assets.

    The receipt and content commit together. A provider crash can still leave an
    orphan outside the database; the offline inventory reports those for review.
    Older clients without a request ID keep their existing one-request behavior.
    """
    receipt = None
    if request_id is not None:
        try:
            request_id = uuid.UUID(str(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({'request_id': 'Use a valid upload request ID.'})
        digest = hashlib.sha256(json.dumps([kind, metadata], sort_keys=True, default=str).encode())
        try:
            upload.seek(0)
            for chunk in upload.chunks():
                digest.update(chunk)
        finally:
            upload.seek(0)
        fingerprint = digest.hexdigest()
        receipt, _ = UploadReceipt.objects.get_or_create(user=user, request_id=request_id,
            defaults={'kind': kind, 'fingerprint': fingerprint})
    staged = []
    try:
        with transaction.atomic():
            if receipt:
                receipt = UploadReceipt.objects.select_for_update().get(pk=receipt.pk)
                if receipt.kind != kind or receipt.fingerprint != fingerprint:
                    raise UploadConflict()
                if receipt.completed:
                    target_id = receipt.slide_id if kind == 'slide' else receipt.deck_id
                    target = queryset.filter(pk=target_id).first() if target_id else None
                    if target is None:
                        raise UploadGone()
                    return target, True
            result = create(staged)
            if receipt:
                setattr(receipt, kind, result)
                receipt.completed = True
                receipt.save(update_fields=[kind, 'completed'])
        return result, False
    except Exception:
        # Run after rollback; never discard a published reference after an ambiguous commit.
        from .private_media import discard_new_asset
        for asset in staged:
            try:
                discard_new_asset(asset)
            except Exception:
                logger.warning('Upload compensation requires storage reconciliation.')
        raise
