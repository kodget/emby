"""Authorized, atomic reading checkpoints; passive reading never issues XP."""
from django.db import transaction
from rest_framework import serializers

from .models import DeckReadingProgress, DeckReadingCheckpoint


class CheckpointInput(serializers.Serializer):
    current_page = serializers.IntegerField(min_value=1)
    seconds = serializers.IntegerField(min_value=0, max_value=300)
    request_id = serializers.UUIDField()


def payload(user, deck):
    progress = DeckReadingProgress.objects.filter(user=user, deck=deck).first()
    return {'deck_id': deck.pk,
            'current_page': min(progress.current_page, max(1, deck.page_count)) if progress else 1,
            'total_seconds': progress.total_seconds if progress else 0,
            'completed': bool(progress and deck.processing_status == 'completed'
                              and deck.page_count > 0 and progress.current_page >= deck.page_count),
            'updated_at': progress.updated_at if progress else None}


@transaction.atomic
def save(user, deck, data):
    from learning import events
    from learning.models import ActivityType
    form = CheckpointInput(data=data)
    form.is_valid(raise_exception=True)
    values = form.validated_data
    page, seconds = values['current_page'], values['seconds']
    events.lock_stats(user)
    prior = DeckReadingCheckpoint.objects.filter(user=user, request_id=values['request_id']).first()
    if prior:
        if (prior.deck_id, prior.current_page, prior.seconds) != (deck.pk, page, seconds):
            raise serializers.ValidationError('This reading request was already used for different data.')
        return payload(user, deck)  # A late retry must not move the reader backwards.
    if deck.processing_status != 'completed' or deck.page_count < 1:
        raise serializers.ValidationError('Choose a page from a processed document.')
    if page > deck.page_count or not deck.pages.filter(slide_number=page).exists():
        raise serializers.ValidationError({'code': 'reading_page_unavailable',
                                           'detail': 'That page is no longer available in this document.'})
    DeckReadingCheckpoint.objects.create(user=user, deck=deck, **values)
    progress, _ = DeckReadingProgress.objects.get_or_create(user=user, deck=deck)
    progress.current_page = page
    progress.total_seconds += seconds
    progress.completed = page == deck.page_count
    progress.save()
    if seconds:
        events.record(user, ActivityType.RESOURCE_STUDIED, duration_seconds=seconds,
            resource_type='standalone_deck', resource_id=str(deck.pk),
            idempotency_key=f'deck-reading:{values["request_id"]}', metadata={'page': page}, award_xp=False)
    return payload(user, deck)
