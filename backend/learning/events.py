"""
The single entry point for recording learning activity.

Every feature calls `record()` when a student does something meaningful. That one call
then fans out to everything downstream:

    record()
      ├── writes a LearningEvent          (the audit trail analytics reads)
      ├── awards XP                       (learning.xp, capped and farm-resistant)
      ├── updates weak areas              (mastery per curriculum node)
      ├── updates the daily study total   (curriculum.DailyStudySession)
      └── advances the streak             (curriculum.UserStats)

Routing it through here is what stops analytics, XP and the weak-area engine from
each inventing their own slightly different definition of "a completed quiz".

Callers should not write XPAward, WeakArea or DailyStudySession directly.
"""

from __future__ import annotations

import logging
from datetime import date

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import xp
from .models import ActivityType, LearningEvent, WeakArea

logger = logging.getLogger(__name__)

# How strongly the newest result moves the mastery estimate. Higher reacts faster.
MASTERY_ALPHA = 0.3
# Activities that represent focused practice and should move mastery.
SCORING_ACTIVITIES = {
    ActivityType.QUIZ_COMPLETED,
    ActivityType.QUESTION_ANSWERED,
    ActivityType.STEEPLECHASE_COMPLETED,
    ActivityType.HISTOLOGY_COMPLETED,
    ActivityType.BRAIN_BATTLE_COMPLETED,
}

COMPLETION_RESOURCES = {'QuizAttempt', 'practice_session', 'brain_battle', 'schedule_item'}


def lock_stats(user):
    """All event/reward writers serialize on the same account row."""
    from curriculum.models import UserStats
    stats, _ = UserStats.objects.get_or_create(user=user)
    stats = UserStats.objects.select_for_update().get(pk=stats.pk)
    # A caller may have cached stats before awarding quiz points with F().
    user.stats = stats
    return stats


@transaction.atomic
def record(
    user: User,
    activity: str,
    *,
    subject=None,
    block=None,
    sub_block=None,
    topic=None,
    correct_count: int = 0,
    total_count: int = 0,
    duration_seconds: int = 0,
    resource_type: str = "",
    resource_id: str = "",
    metadata: dict | None = None,
    occurred_at=None,
    award_xp: bool = True,
    idempotency_key: str = "",
) -> LearningEvent:
    """Record one learning activity and fan out its consequences.

    Returns the LearningEvent. `_record_created` identifies a new write for
    callers updating related progress in the same transaction. The XP award,
    if any, is available as `event.xp_awards.first()`.
    """
    now = timezone.now()
    occurred_at = occurred_at or now
    if activity not in ActivityType.values:
        raise ValidationError('Unknown learning activity.')
    for value in (correct_count, total_count, duration_seconds):
        if type(value) is not int or value < 0 or value > 2147483647:
            raise ValidationError('Activity counts and seconds must be nonnegative whole numbers.')
    if correct_count > total_count:
        raise ValidationError('Correct answers cannot exceed the item count.')
    if timezone.is_naive(occurred_at) or occurred_at > now:
        raise ValidationError('Activity time must be timezone-aware and cannot be in the future.')
    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError('Activity metadata must be an object.')
    resource_id = str(resource_id or '')
    if not isinstance(resource_type, str) or len(resource_type) > 40 or len(resource_id) > 64:
        raise ValidationError('Invalid activity resource identifier.')
    if not isinstance(idempotency_key, str) or len(idempotency_key) > 160:
        raise ValidationError('Invalid activity request identifier.')
    completion = bool(resource_id and resource_type in COMPLETION_RESOURCES)
    if completion:
        idempotency_key = f'{activity}:{resource_type}:{resource_id}'

    lock_stats(user)
    existing = None
    if idempotency_key:
        existing = LearningEvent.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing is None and completion:
        # Historical completions have no key. Do not replay their side effects.
        existing = LearningEvent.objects.filter(user=user, activity=activity,
            resource_type=resource_type, resource_id=resource_id).order_by('created_at', 'pk').first()
    if existing is not None:
        # A completion is an immutable fact. For caller-supplied request keys,
        # reject accidental reuse for a different action instead of losing it.
        if not completion and any(getattr(existing, field) != value for field, value in {
            'activity': activity, 'resource_type': resource_type, 'resource_id': resource_id,
            'correct_count': correct_count, 'total_count': total_count,
            'duration_seconds': duration_seconds, 'metadata': metadata or {},
            'subject_id': getattr(subject, 'pk', None), 'block_id': getattr(block, 'pk', None),
            'sub_block_id': getattr(sub_block, 'pk', None), 'topic_id': getattr(topic, 'pk', None),
        }.items()):
            raise ValidationError('This activity request identifier was already used for different data.')
        existing._record_created = False
        return existing

    accuracy = (correct_count / total_count) if total_count else None

    event = LearningEvent.objects.create(
        user=user,
        activity=activity,
        subject=subject,
        block=block,
        sub_block=sub_block,
        topic=topic,
        correct_count=correct_count,
        total_count=total_count,
        accuracy=accuracy,
        duration_seconds=duration_seconds,
        resource_type=resource_type,
        resource_id=resource_id,
        idempotency_key=idempotency_key,
        xp_processed=not award_xp,
        metadata=metadata or {},
        occurred_at=occurred_at,
    )

    if duration_seconds > 0:
        _add_study_time(user, timezone.localdate(event.occurred_at), duration_seconds)

    _touch_streak(user, refresh_day=timezone.localdate(occurred_at))

    if activity in SCORING_ACTIVITIES and total_count:
        update_weak_areas(event)

    if award_xp:
        try:
            with transaction.atomic():
                xp.award_for_event(event)
        except Exception:  # noqa: BLE001 - XP must never break the student's action
            logger.exception("XP award failed for event %s", event.id)

    try:
        from .gamification import AchievementEngine
        with transaction.atomic():
            AchievementEngine.evaluate_event(event)
    except Exception:
        logger.exception("Gamification engine failed for event %s", event.id)

    event._record_created = True
    return event


# ---------------------------------------------------------------------------
# Study time and streaks (kept on the existing curriculum models)
# ---------------------------------------------------------------------------
def _add_study_time(user: User, day: date, seconds: int) -> None:
    from curriculum.models import DailyStudySession

    # Carry sub-minute work across events. Preserve existing legacy minute totals
    # until an explicit reconciliation, rather than silently replacing history.
    total_seconds = LearningEvent.objects.filter(user=user, occurred_at__date=day,
        duration_seconds__gte=0).aggregate(total=Sum('duration_seconds'))['total'] or 0
    minutes = total_seconds // 60 - (total_seconds - seconds) // 60

    session, created = DailyStudySession.objects.get_or_create(
        user=user, date=day, defaults={"minutes_studied": minutes, "sessions_count": 1}
    )
    if not created:
        session.minutes_studied += minutes
        session.sessions_count += 1
        session.save(update_fields=["minutes_studied", "sessions_count"])

    stats = getattr(user, "stats", None)
    if stats is not None:
        type(stats).objects.filter(pk=stats.pk).update(
            total_study_minutes=F('total_study_minutes') + minutes, updated_at=timezone.now())
        stats.refresh_from_db()


def _touch_streak(user: User, refresh_day=None) -> None:
    """Refresh date-ordered evidence while the caller holds the user's stats lock."""
    stats = getattr(user, "stats", None)
    if stats is None:
        return

    from .analytics_evidence import Evidence
    evidence = Evidence(user, 7)
    consistency = evidence.consistency()
    stats.current_streak = consistency['current_streak']
    stats.longest_streak = consistency['longest_streak']
    stats.last_activity_date = max((timezone.localdate(row['at']) for row in evidence.rows), default=None)
    stats.save(
        update_fields=[
            "current_streak", "longest_streak", "last_activity_date", "updated_at"
        ]
    )
    from .activity_reconciliation import refresh_reconciled_time
    refresh_reconciled_time(user, stats, evidence, refresh_day)



# ---------------------------------------------------------------------------
# Weak areas
# ---------------------------------------------------------------------------
def update_weak_areas(event: LearningEvent) -> list[WeakArea]:
    """Fold one event's result into the mastery estimate for each curriculum node.

    An event tagged with a topic also updates its sub-block, block and subject, so a
    student's weakness shows up at whatever level the UI wants to display.
    """
    if not event.total_count:
        return []

    accuracy = (event.correct_count or 0) / event.total_count

    # Each scope keys only on nodes at or above its own level; the finer fields are left
    # null. Without that, a block-scope row would be keyed on the sub-block that produced
    # it and become a duplicate of the sub-block row rather than an aggregate across all
    # sub-blocks in that block.
    nodes = [
        (
            WeakArea.Scope.TOPIC,
            event.topic,
            {"subject": event.subject, "block": event.block,
             "sub_block": event.sub_block, "topic": event.topic},
        ),
        (
            WeakArea.Scope.SUB_BLOCK,
            event.sub_block,
            {"subject": event.subject, "block": event.block,
             "sub_block": event.sub_block, "topic": None},
        ),
        (
            WeakArea.Scope.BLOCK,
            event.block,
            {"subject": event.subject, "block": event.block,
             "sub_block": None, "topic": None},
        ),
        (
            WeakArea.Scope.SUBJECT,
            event.subject,
            {"subject": event.subject, "block": None,
             "sub_block": None, "topic": None},
        ),
    ]

    updated: list[WeakArea] = []
    for scope, node, key in nodes:
        if node is None:
            continue

        # record() holds the account lock. Nullable legacy composite keys may
        # contain duplicates: adopt one row without adding uncertain old totals.
        canonical_key = f'{scope}:{node.pk}'
        area = WeakArea.objects.filter(user=event.user, canonical_key=canonical_key).first()
        created = False
        if area is None:
            area = WeakArea.objects.filter(user=event.user, scope=scope, canonical_key__isnull=True,
                                           **key).order_by('-updated_at', '-pk').first()
            if area is None:
                area = WeakArea(user=event.user, scope=scope, **key, mastery=accuracy)
                created = True
            area.canonical_key = canonical_key

        area.attempted += event.total_count
        area.correct += event.correct_count or 0
        # Exponential moving average: recent practice counts for more than old practice.
        area.mastery = (
            accuracy if created else (1 - MASTERY_ALPHA) * area.mastery + MASTERY_ALPHA * accuracy
        )
        area.label = _node_label(node)
        area.last_practised_at = max(area.last_practised_at, event.occurred_at) if area.last_practised_at else event.occurred_at
        area.priority = _priority(area)
        area.save()
        updated.append(area)

    return updated


def _node_label(node) -> str:
    """The node's own name, without its parents.

    Curriculum models' `__str__` includes the parent chain ("Anatomy - Block 1 - Upper
    Limb"), which reads badly in a list of topics where the parent is already implied.
    """
    return str(getattr(node, "name", None) or node)[:200]


def _priority(area: WeakArea) -> float:
    """How urgently this node needs revision, in 0..1-ish.

    Weakness dominates, staleness adds to it, and a node with very little evidence is
    damped so a single unlucky quiz cannot dominate a student's revision list.
    """
    weakness = 1.0 - max(0.0, min(1.0, area.mastery))

    days_stale = 0.0
    if area.last_practised_at:
        days_stale = (timezone.now() - area.last_practised_at).days
    staleness = min(1.0, days_stale / 21.0)

    confidence = min(1.0, area.attempted / 12.0)

    return round((weakness * 0.7 + staleness * 0.3) * confidence, 4)


def weakest(user: User, *, scope: str = WeakArea.Scope.TOPIC, limit: int = 5):
    """Current, authorized objective evidence; legacy EMA rows are diagnostic only."""
    from .analytics_evidence import Evidence
    return Evidence(user, 30).topics(scope=scope, limit=limit)['weakest']


def strongest(user: User, *, scope: str = WeakArea.Scope.TOPIC, limit: int = 5):
    from .analytics_evidence import Evidence
    return Evidence(user, 30).topics(scope=scope, limit=limit)['strongest']
