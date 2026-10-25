"""Fenced standalone conversions with atomic publication of a complete page set."""
from datetime import timedelta
import logging
from pathlib import Path
import tempfile
import uuid

from django.db import transaction
from django.utils import timezone

from .models import SlideDeck, SlidePage
from .private_media import content_file_url, upload_asset, discard_new_asset

logger = logging.getLogger(__name__)
LEASE = timedelta(hours=2)


class Superseded(Exception):
    pass


@transaction.atomic
def claim(deck_id, token=None):
    deck = SlideDeck.objects.select_for_update().filter(pk=deck_id).first()
    if not deck or deck.processing_status == 'completed' or not deck.class_group_id or not deck.asset_id:
        return None
    # A reserved recovery can be claimed once. An unreserved initial call can only
    # claim a fresh pending record; stale/failed work goes through explicit recovery.
    if token is None:
        if deck.processing_token or deck.processing_status not in ('pending', 'processing'):
            return None
        deck.processing_token = uuid.uuid4()
    elif str(deck.processing_token) != str(token) or deck.processing_lease_until is not None:
        return None
    if not deck.class_group.is_active or deck.asset.class_group_id != deck.class_group_id:
        return None
    deck.processing_status = 'processing'
    deck.processing_error = ''
    deck.processing_lease_until = timezone.now() + LEASE
    deck.save(update_fields=['processing_token', 'processing_status', 'processing_error',
                             'processing_lease_until', 'updated_at'])
    return deck


def owned(deck):
    return SlideDeck.objects.filter(pk=deck.pk, processing_token=deck.processing_token,
        processing_status='processing', asset_id=deck.asset_id, class_group_id=deck.class_group_id,
        class_group__is_active=True)


def heartbeat(deck):
    if not owned(deck).update(processing_lease_until=timezone.now() + LEASE, updated_at=timezone.now()):
        raise Superseded()


def process(deck_id, token=None):
    deck = claim(deck_id, token)
    if deck is None:
        return False
    result, source = None, None
    staged = []
    published = False
    try:
        import requests
        from PIL import Image
        from .services.converter import SlideConverter
        response = requests.get(content_file_url(deck), timeout=60)
        if response.status_code != 200:
            raise RuntimeError('Source download failed.')
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{deck.file_type}') as stream:
            source = Path(stream.name)
            stream.write(response.content)
        heartbeat(deck)
        success, result = SlideConverter.convert_document(str(source), deck.file_type, deck.pk)
        if not success:
            owned(deck).update(processing_status='failed', processing_lease_until=None,
                processing_error=result.get('error') or 'Document processing failed. Please retry processing.',
                updated_at=timezone.now())
            return False
        images, pages = result['slide_images'], result['pages']
        if not images or result['page_count'] != len(images) or len(pages) != len(images):
            raise RuntimeError('Incomplete document render.')
        rows = []
        for number, image_path in enumerate(images, 1):
            heartbeat(deck)
            with Image.open(image_path) as image:
                width, height = image.size
            asset = upload_asset(image_path, class_group=deck.class_group, uploaded_by=deck.uploaded_by,
                resource_type='image', folder=f'emby/deck_pages/{deck.pk}', timeout=60)
            staged.append(asset)
            rows.append(SlidePage(deck=deck, slide_number=number, extracted_text=pages[number-1]['text'],
                                  image='', image_url='', asset=asset, width=width, height=height))
        with transaction.atomic():
            current = SlideDeck.objects.select_for_update().get(pk=deck.pk)
            if (current.processing_token != deck.processing_token or current.processing_status != 'processing'
                    or current.asset_id != deck.asset_id or current.class_group_id != deck.class_group_id
                    or not current.class_group.is_active):
                raise Superseded()
            # Keep previously published pages readable until every replacement is stored.
            # Superseded assets stay registered for a separate reviewed inventory.
            current.pages.all().delete()
            SlidePage.objects.bulk_create(rows)
            current.page_count = len(rows)
            current.text_extraction = {**result['text_extraction'],
                'pages': [{key: value for key, value in page.items() if key != 'text'} for page in pages]}
            current.processing_status = 'completed'
            current.processing_error = ''
            current.processing_lease_until = None
            current.save(update_fields=['page_count', 'text_extraction', 'processing_status',
                                       'processing_error', 'processing_lease_until', 'updated_at'])
            from .document_index import request_index
            request_index(current, force=True)
        published = True
        return True
    except Superseded:
        return False
    except Exception as exc:
        logger.error('Deck processing failed (%s)', type(exc).__name__)
        owned(deck).update(processing_status='failed', processing_lease_until=None,
            processing_error='Document processing failed. Please retry processing.', updated_at=timezone.now())
        return False
    finally:
        if not published:
            for asset in staged:
                try:
                    discard_new_asset(asset)
                except Exception:
                    logger.warning('Unpublished page asset needs storage reconciliation.')
        from .services.document_rendering import cleanup_render
        try:
            cleanup_render(result)
        except Exception:
            logger.warning('Temporary render cleanup failed.')
        if source:
            try:
                source.unlink(missing_ok=True)
            except OSError:
                logger.warning('Temporary source cleanup failed.')
