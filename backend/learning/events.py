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
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

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
    ActivityType.FLASHCARD_REVIEWED,
}


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
) -> LearningEvent:
    """Record one learning activity and fan out its consequences.

    Returns the LearningEvent. The XP award, if any, is available as
    `event.xp_awards.first()`.
    """
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
        duration_seconds=max(0, duration_seconds),
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=metadata or {},
        occurred_at=occurred_at or timezone.now(),
    )

    if duration_seconds > 0:
        _add_study_time(user, event.occurred_at.date(), duration_seconds)

    _touch_streak(user, event.occurred_at.date())

    if activity in SCORING_ACTIVITIES and total_count:
        update_weak_areas(event)

    if award_xp:
        try:
            xp.award_for_event(event)
        except Exception:  # noqa: BLE001 - XP must never break the student's action
            logger.exception("XP award failed for event %s", event.id)

    return event


# ---------------------------------------------------------------------------
# Study time and streaks (kept on the existing curriculum models)
# ---------------------------------------------------------------------------
def _add_study_time(user: User, day: date, seconds: int) -> None:
    from curriculum.models import DailyStudySession

    minutes = max(0, round(seconds / 60))
    if minutes <= 0:
        return

    session, created = DailyStudySession.objects.get_or_create(
        user=user, date=day, defaults={"minutes_studied": minutes, "sessions_count": 1}
    )
    if not created:
        session.minutes_studied += minutes
        session.sessions_count += 1
        session.save(update_fields=["minutes_studied", "sessions_count"])

    stats = getattr(user, "stats", None)
    if stats is not None:
        stats.total_study_minutes = (stats.total_study_minutes or 0) + minutes
        stats.save(update_fields=["total_study_minutes", "updated_at"])


def _touch_streak(user: User, day: date) -> None:
    """Advance the study streak, but only once per calendar day."""
    stats = getattr(user, "stats", None)
    if stats is None:
        return

    last = stats.last_activity_date
    if last == day:
        return

    if last == day - timedelta(days=1):
        stats.current_streak = (stats.current_streak or 0) + 1
    else:
        stats.current_streak = 1

    stats.longest_streak = max(stats.longest_streak or 0, stats.current_streak)
    stats.last_activity_date = day
    stats.save(
        update_fields=[
            "current_streak", "longest_streak", "last_activity_date", "updated_at"
        ]
    )


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

        area, created = WeakArea.objects.get_or_create(
            user=event.user, scope=scope, **key,
            defaults={"label": _node_label(node), "mastery": accuracy},
        )

        area.attempted += event.total_count
        area.correct += event.correct_count or 0
        # Exponential moving average: recent practice counts for more than old practice.
        area.mastery = (
            accuracy if created else (1 - MASTERY_ALPHA) * area.mastery + MASTERY_ALPHA * accuracy
        )
        area.label = _node_label(node)
        area.last_practised_at = event.occurred_at
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
    """The nodes a student should revise next."""
    return list(
        WeakArea.objects.filter(user=user, scope=scope, attempted__gt=0)
        .order_by("-priority")[:limit]
    )


def strongest(user: User, *, scope: str = WeakArea.Scope.TOPIC, limit: int = 5):
    return list(
        WeakArea.objects.filter(user=user, scope=scope, attempted__gte=5)
        .order_by("-mastery")[:limit]
    )
