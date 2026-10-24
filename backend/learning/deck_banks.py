"""Explicit standalone-deck association with the existing curriculum bank workflow."""
import uuid
import hashlib
import json

from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied

from curriculum.class_access import require_visible
from curriculum.content_permissions import can_reprocess_upload
from curriculum.hierarchy import validate_ancestry
from curriculum.models import SlideDeck, Slide, SlideContent, Subject, Block, SubBlock, Topic
from curriculum.services.document_extraction import source_key
from .bank_sources import bank_status
from .generation_dispatch import request_generation


def deck_version(deck):
    value = [deck.pk, deck.class_group_id, deck.asset_id, str(deck.original_file or ''),
             deck.file_type, deck.processing_status, deck.page_count, deck.text_extraction,
             list(deck.pages.order_by('slide_number').values_list('slide_number', 'extracted_text', 'asset_id'))]
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def deck_bank_status(deck, user):
    allowed = can_reprocess_upload(user, deck)
    slide = deck.curriculum_slide
    if not slide:
        return {'slide_id': None, 'can_generate': allowed, 'needs_assignment': True,
                'question_bank': None}
    if slide.class_group_id != deck.class_group_id:
        raise ValidationError('This document association needs administrator repair.')
    require_visible(Slide, user, slide.pk)
    return {'slide_id': slide.pk, 'can_generate': allowed, 'needs_assignment': False,
            'subject': slide.subject_id, 'block': slide.block_id,
            'question_bank': bank_status(slide)}


@transaction.atomic
def prepare_deck_bank(deck_id, user, payload):
    # Deck requests serialize before entering the established Slide -> job lock order.
    deck = SlideDeck.objects.select_for_update().get(pk=deck_id)
    if not can_reprocess_upload(user, deck):
        raise PermissionDenied('Only the uploader or an approved class head can prepare these questions.')
    if deck.processing_status != 'completed':
        raise ValidationError('Wait for this document to finish processing before preparing questions.')
    force = payload.get('force', False)
    if type(force) is not bool:
        raise ValidationError({'force': 'Use true or false.'})
    allowed = {'subject', 'block', 'sub_block', 'topic', 'force'}
    if set(payload) - allowed:
        raise ValidationError('Only curriculum selections and the retry flag are accepted.')
    parents = {}
    for name, model in [('subject', Subject), ('block', Block), ('sub_block', SubBlock), ('topic', Topic)]:
        if name in payload:
            parents[name] = require_visible(model, user, payload[name]) if payload[name] else None
    if deck.curriculum_slide_id:
        slide = Slide.objects.select_for_update().get(pk=deck.curriculum_slide_id)
        if slide.class_group_id != deck.class_group_id:
            raise ValidationError('This document association needs administrator repair.')
        if any(getattr(slide, name + '_id') != (value.pk if value else None) for name, value in parents.items()):
            raise ValidationError('This document is already assigned. Changing its curriculum requires a hierarchy migration.')
    else:
        parents = validate_ancestry(parents)
        if parents['subject'].class_group_id != deck.class_group_id:
            raise ValidationError('Choose a course belonging to this document’s class.')
        if deck.asset_id and deck.asset.class_group_id != deck.class_group_id:
            raise ValidationError('This document asset needs administrator repair.')
        # page_count=0 avoids the creation signal queuing before the verified cache exists.
        slide = Slide.objects.create(
            id=f'deck_source_{uuid.uuid4().hex}', title=deck.title, file_type=deck.file_type,
            file=deck.original_file if not deck.asset_id else '',
            asset=deck.asset, class_group=deck.class_group, uploaded_by=deck.uploaded_by,
            page_count=0, **parents,
        )
    if deck.asset_id and deck.asset.class_group_id != deck.class_group_id:
        raise ValidationError('This document asset needs administrator repair.')
    slide.asset = deck.asset
    slide.file = deck.original_file if not deck.asset_id else ''
    slide.file_type = deck.file_type
    slide.title = deck.title
    slide.save(update_fields=['asset', 'file', 'file_type', 'title', 'updated_at'])
    metadata = {p['page_number']: p for p in deck.text_extraction.get('pages', [])}
    pages = []
    for page in deck.pages.order_by('slide_number'):
        if page.asset_id and page.asset.class_group_id != deck.class_group_id:
            raise ValidationError('A document page asset needs administrator repair.')
        pages.append({**metadata.get(page.slide_number, {}), 'page_number': page.slide_number,
                      'text': page.extracted_text, 'asset_id': str(page.asset_id) if page.asset_id else None,
                      'image_url': (page.image_url or (page.image.url if page.image else '')) if not page.asset_id else '',
                      'width': page.width, 'height': page.height})
    manifest = {key: value for key, value in deck.text_extraction.items() if key != 'pages'}
    manifest['source_key'] = source_key(slide)
    previous = SlideContent.objects.filter(slide=slide).first()
    version = deck_version(deck)
    if not previous or previous.content_data.get('standalone_version') != version:
        SlideContent.objects.update_or_create(slide=slide, defaults={'is_extracted': True,
            'content_data': {'pages': pages, 'total_pages': deck.page_count, 'text_extraction': manifest,
                             'standalone_version': version}})
    Slide.objects.filter(pk=slide.pk).update(page_count=deck.page_count)
    slide.page_count = deck.page_count
    deck.curriculum_slide = slide
    deck.save(update_fields=['curriculum_slide', 'updated_at'])
    queued = request_generation(slide, force=force)
    return queued, deck_bank_status(deck, user)
