"""Atomic course-reader checkpoints, compatible with legacy minute clients."""
from django.db import transaction
from rest_framework import serializers

from .class_access import require_visible
from .models import Slide, UserProgress, CourseReadingCheckpoint


class CheckpointInput(serializers.Serializer):
    slide_id = serializers.CharField()
    current_page = serializers.IntegerField(min_value=1)
    seconds = serializers.IntegerField(min_value=0, max_value=300, required=False)
    time_spent_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False)
    request_id = serializers.UUIDField(required=False)

    def validate(self, values):
        if 'seconds' in values:
            if 'time_spent_minutes' in values:
                raise serializers.ValidationError('Send seconds or minutes, not both.')
            if 'request_id' not in values:
                raise serializers.ValidationError('Seconds checkpoints require a request identifier.')
        return values


@transaction.atomic
def save(user, data):
    from learning import events
    from learning.models import ActivityType
    form = CheckpointInput(data=data)
    form.is_valid(raise_exception=True)
    values = form.validated_data
    slide = require_visible(Slide, user, values['slide_id'])
    page = values['current_page']
    seconds = values.get('seconds', values.get('time_spent_minutes', 0) * 60)
    request_id = values.get('request_id')
    events.lock_stats(user)
    if request_id:
        prior = CourseReadingCheckpoint.objects.filter(user=user, request_id=request_id).first()
        if prior:
            if (prior.slide_id, prior.current_page, prior.seconds) != (slide.pk, page, seconds):
                raise serializers.ValidationError('This reading request was already used for different data.')
            return UserProgress.objects.get(user=user, slide=slide)
    if slide.page_count < 1:
        raise serializers.ValidationError('Choose a page from a processed document.')
    if page > slide.page_count:
        raise serializers.ValidationError({'code': 'reading_page_unavailable',
                                           'detail': 'That page is no longer available in this document.'})
    if seconds:
        event = events.record(user, ActivityType.RESOURCE_STUDIED,
            subject=slide.subject, block=slide.block, sub_block=slide.sub_block, topic=slide.topic,
            duration_seconds=seconds, resource_type='slide', resource_id=str(slide.pk),
            idempotency_key=f'reading:{request_id}' if request_id else '',
            metadata={'page': page}, award_xp=False)
        # Legacy minute requests may already have a ledger entry but no receipt.
        if not event._record_created:
            return UserProgress.objects.get(user=user, slide=slide)
    if request_id:
        CourseReadingCheckpoint.objects.create(user=user, slide=slide, request_id=request_id,
                                               current_page=page, seconds=seconds)
    progress, _ = UserProgress.objects.get_or_create(user=user, slide=slide)
    minutes, remainder = divmod(progress.reading_seconds_remainder + seconds, 60)
    progress.time_spent_minutes += minutes
    progress.reading_seconds_remainder = remainder
    progress.current_page = page
    progress.total_pages = slide.page_count
    progress.completed = page == slide.page_count
    progress.save()
    return progress
