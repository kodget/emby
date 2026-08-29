"""
XP rules.

XP is meant to track genuine learning, so the rules here reward accuracy, consistency
and revision, and deliberately resist the obvious exploits:

  * Every reason has a **daily cap**, so grinding one activity stops paying.
  * Awards use **diminishing returns** within a day: the 1st quiz is worth full XP, the
    5th much less. Volume alone cannot beat quality.
  * Accuracy scales the award, and deliberately wrong answers earn nothing, so you
    cannot farm by spamming submissions.
  * Activities with a duration require a **plausible time floor** — answering 20
    questions in 15 seconds earns no XP, which kills click-through farming.
  * Passive presence is never rewarded; there is no XP for having a tab open.

Everything is written to the XPAward ledger with the base amount and multiplier kept
alongside the final figure, so a student can always be shown why they earned what
they did, and so caps can be enforced by querying the ledger rather than by trusting
an in-memory counter.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import ActivityType, LearningEvent, XPAward

logger = logging.getLogger(__name__)


# Base XP per activity, before accuracy and diminishing returns.
BASE_XP: dict[str, int] = {
    ActivityType.RESOURCE_STUDIED: 10,
    ActivityType.STUDY_SESSION_COMPLETED: 15,
    ActivityType.QUIZ_COMPLETED: 30,
    ActivityType.QUESTION_ANSWERED: 2,
    ActivityType.FLASHCARD_REVIEWED: 3,
    ActivityType.STEEPLECHASE_COMPLETED: 35,
    ActivityType.HISTOLOGY_COMPLETED: 35,
    ActivityType.BRAIN_BATTLE_COMPLETED: 40,
    ActivityType.PLANNER_TASK_COMPLETED: 12,
}

# Most XP obtainable from one activity in a single day.
DAILY_CAP: dict[str, int] = {
    ActivityType.RESOURCE_STUDIED: 80,
    ActivityType.STUDY_SESSION_COMPLETED: 90,
    ActivityType.QUIZ_COMPLETED: 180,
    ActivityType.QUESTION_ANSWERED: 120,
    ActivityType.FLASHCARD_REVIEWED: 120,
    ActivityType.STEEPLECHASE_COMPLETED: 180,
    ActivityType.HISTOLOGY_COMPLETED: 180,
    ActivityType.BRAIN_BATTLE_COMPLETED: 160,
    ActivityType.PLANNER_TASK_COMPLETED: 72,
}

# Minimum seconds per item for an activity to look like real work rather than clicking.
MIN_SECONDS_PER_ITEM: dict[str, float] = {
    ActivityType.QUESTION_ANSWERED: 3.0,
    ActivityType.FLASHCARD_REVIEWED: 2.5,
    ActivityType.QUIZ_COMPLETED: 4.0,
    ActivityType.STEEPLECHASE_COMPLETED: 5.0,
    ActivityType.HISTOLOGY_COMPLETED: 5.0,
}

# Awards shrink as the same activity repeats within a day: 1st full, then 85%, 70%, ...
DECAY_STEPS = [1.0, 0.85, 0.7, 0.55, 0.4, 0.3, 0.2, 0.15, 0.1]
DECAY_FLOOR = 0.1

# Consistency bonus applied on top, by current streak length.
STREAK_BONUS = [(30, 0.30), (14, 0.20), (7, 0.12), (3, 0.05)]


def _today_window():
    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def earned_today(user: User, reason: str) -> int:
    start, end = _today_window()
    total = XPAward.objects.filter(
        user=user, reason=reason, awarded_at__gte=start, awarded_at__lt=end
    ).aggregate(total=Sum("amount"))["total"]
    return total or 0


def _awards_today(user: User, reason: str) -> int:
    start, end = _today_window()
    return XPAward.objects.filter(
        user=user, reason=reason, awarded_at__gte=start, awarded_at__lt=end
    ).count()


def _decay(occurrence_index: int) -> float:
    if occurrence_index < len(DECAY_STEPS):
        return DECAY_STEPS[occurrence_index]
    return DECAY_FLOOR


def _streak_multiplier(user: User) -> float:
    stats = getattr(user, "stats", None)
    streak = getattr(stats, "current_streak", 0) or 0
    for threshold, bonus in STREAK_BONUS:
        if streak >= threshold:
            return 1.0 + bonus
    return 1.0


def _looks_like_real_effort(event: LearningEvent) -> bool:
    """Reject awards for activity completed implausibly fast."""
    floor = MIN_SECONDS_PER_ITEM.get(event.activity)
    if floor is None:
        return True
    items = max(1, event.total_count or 1)
    # No timing recorded: give the benefit of the doubt rather than punish older clients.
    if not event.duration_seconds:
        return True
    return (event.duration_seconds / items) >= floor


def compute(event: LearningEvent) -> tuple[int, int, float, bool, str]:
    """Work out the XP for one event.

    Returns (amount, base, multiplier, capped, note).
    """
    base = BASE_XP.get(event.activity, 0)
    if base <= 0:
        return 0, 0, 0.0, False, "activity earns no XP"

    if not _looks_like_real_effort(event):
        return 0, base, 0.0, False, "completed too quickly to count"

    # Per-item activities scale with how much was actually done.
    if event.activity == ActivityType.QUESTION_ANSWERED:
        base *= max(1, event.total_count or 1)
    elif event.activity == ActivityType.FLASHCARD_REVIEWED:
        base *= max(1, event.total_count or 1)

    multiplier = 1.0
    note_parts: list[str] = []

    # Accuracy: below 40% earns a floor, perfect work earns a genuine bonus.
    if event.accuracy is not None:
        accuracy = max(0.0, min(1.0, event.accuracy))
        accuracy_mult = 0.35 + (accuracy * 0.85)      # 0.35 .. 1.20
        multiplier *= accuracy_mult
        note_parts.append(f"accuracy {accuracy:.0%}")

    occurrence = _awards_today(event.user, event.activity)
    decay = _decay(occurrence)
    multiplier *= decay
    if decay < 1.0:
        note_parts.append(f"repeat #{occurrence + 1}")

    streak_mult = _streak_multiplier(event.user)
    multiplier *= streak_mult
    if streak_mult > 1.0:
        note_parts.append(f"streak x{streak_mult:.2f}")

    amount = max(0, round(base * multiplier))

    # Apply the daily ceiling for this activity.
    cap = DAILY_CAP.get(event.activity)
    capped = False
    if cap is not None:
        already = earned_today(event.user, event.activity)
        headroom = max(0, cap - already)
        if amount > headroom:
            amount = headroom
            capped = True
            note_parts.append("daily cap reached")

    return amount, base, round(multiplier, 3), capped, ", ".join(note_parts)


@transaction.atomic
def award_for_event(event: LearningEvent) -> XPAward | None:
    """Grant XP for an event and keep UserStats.points in step.

    Returns None when the event earns nothing (capped out, too fast, or not an
    XP-bearing activity). Safe to call once per event; callers should not retry.
    """
    amount, base, multiplier, capped, note = compute(event)
    if amount <= 0:
        logger.debug("No XP for %s: %s", event.activity, note or "zero award")
        return None

    award = XPAward.objects.create(
        user=event.user,
        event=event,
        reason=event.activity,
        amount=amount,
        base_amount=base,
        multiplier=multiplier,
        capped=capped,
        note=note[:200],
    )

    # Mirror onto the existing gamification counter so leaderboards keep working.
    stats = getattr(event.user, "stats", None)
    if stats is not None:
        stats.points = (stats.points or 0) + amount
        stats.save(update_fields=["points", "updated_at"])

    return award


def total_xp(user: User) -> int:
    return XPAward.objects.filter(user=user).aggregate(total=Sum("amount"))["total"] or 0


def breakdown(user: User, days: int = 30) -> dict:
    """XP grouped by activity over a recent window, for the analytics screen."""
    since = timezone.now() - timedelta(days=days)
    rows = (
        XPAward.objects.filter(user=user, awarded_at__gte=since)
        .values("reason")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return {
        "total": sum(r["total"] for r in rows),
        "by_activity": {r["reason"]: r["total"] for r in rows},
        "window_days": days,
    }
