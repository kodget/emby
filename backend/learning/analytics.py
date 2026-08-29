"""
Analytics computed from what students actually did.

Every figure here is derived from recorded activity — LearningEvent, DailyStudySession,
PracticeSession, QuestionExposure, WeakArea and the flashcard review log. Nothing is
illustrative, and where there is not enough evidence to answer a question the response
says so rather than filling the gap with a plausible-looking number.

The shape is organised around what a student actually wants to know:

    Am I improving?      -> trend, accuracy over consecutive windows
    What am I weak at?   -> topic performance, from the weak-area engine
    How consistent am I? -> active days, streak, study minutes
    Where did it happen? -> per-assessment-type breakdown
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .models import (
    ActivityType,
    LearningEvent,
    PracticeMode,
    PracticeSession,
    QuestionExposure,
    WeakArea,
)

logger = logging.getLogger(__name__)

# Below this many answered items, accuracy is too noisy to present as a trend.
MIN_ITEMS_FOR_TREND = 10
MIN_ITEMS_FOR_ACCURACY = 5


def _window(days: int):
    end = timezone.now()
    return end - timedelta(days=days), end


def overview(user: User, days: int = 30) -> dict:
    """Headline performance for the period, with an honest empty state."""
    since, _ = _window(days)
    events = LearningEvent.objects.filter(user=user, occurred_at__gte=since)

    totals = events.aggregate(
        attempted=Sum("total_count"),
        correct=Sum("correct_count"),
        seconds=Sum("duration_seconds"),
        sessions=Count("id"),
    )
    attempted = totals["attempted"] or 0
    correct = totals["correct"] or 0

    return {
        "window_days": days,
        "has_data": attempted >= MIN_ITEMS_FOR_ACCURACY,
        "attempted": attempted,
        "correct": correct,
        "incorrect": max(0, attempted - correct),
        "accuracy": round(correct / attempted, 3) if attempted else None,
        "sessions": totals["sessions"] or 0,
        "study_minutes": round((totals["seconds"] or 0) / 60),
    }


def improvement(user: User, days: int = 30) -> dict:
    """Compare the most recent half of the window against the earlier half.

    Returns `direction: "insufficient_data"` rather than a fake 0% when either half is
    too thin to compare — a trend drawn from three questions is noise, not progress.
    """
    since, now = _window(days)
    midpoint = since + (now - since) / 2

    def slice_accuracy(start, end):
        agg = LearningEvent.objects.filter(
            user=user, occurred_at__gte=start, occurred_at__lt=end
        ).aggregate(attempted=Sum("total_count"), correct=Sum("correct_count"))
        attempted = agg["attempted"] or 0
        if attempted < MIN_ITEMS_FOR_TREND:
            return None, attempted
        return (agg["correct"] or 0) / attempted, attempted

    earlier, earlier_n = slice_accuracy(since, midpoint)
    recent, recent_n = slice_accuracy(midpoint, now)

    if earlier is None or recent is None:
        return {
            "direction": "insufficient_data",
            "earlier_accuracy": earlier,
            "recent_accuracy": recent,
            "earlier_items": earlier_n,
            "recent_items": recent_n,
            "change": None,
            "note": (
                f"At least {MIN_ITEMS_FOR_TREND} answered questions in each half of the "
                f"period are needed before a trend means anything."
            ),
        }

    change = recent - earlier
    direction = "up" if change > 0.02 else "down" if change < -0.02 else "flat"
    return {
        "direction": direction,
        "earlier_accuracy": round(earlier, 3),
        "recent_accuracy": round(recent, 3),
        "earlier_items": earlier_n,
        "recent_items": recent_n,
        "change": round(change, 3),
    }


def daily_activity(user: User, days: int = 30) -> list[dict]:
    """One row per day, including days with nothing — gaps are the point of the chart."""
    from curriculum.models import DailyStudySession

    since, now = _window(days)
    rows = {
        r.date: r
        for r in DailyStudySession.objects.filter(user=user, date__gte=since.date())
    }

    out = []
    for offset in range(days):
        day = (since + timedelta(days=offset)).date()
        row = rows.get(day)
        out.append(
            {
                "date": day.isoformat(),
                "minutes": row.minutes_studied if row else 0,
                "sessions": row.sessions_count if row else 0,
            }
        )
    return out


def consistency(user: User, days: int = 30) -> dict:
    """How regularly this student shows up."""
    from curriculum.models import DailyStudySession

    since, _ = _window(days)
    rows = DailyStudySession.objects.filter(
        user=user, date__gte=since.date(), minutes_studied__gt=0
    )
    active_days = rows.count()
    stats = getattr(user, "stats", None)

    return {
        "active_days": active_days,
        "window_days": days,
        "active_rate": round(active_days / days, 3) if days else 0,
        "current_streak": getattr(stats, "current_streak", 0) or 0,
        "longest_streak": getattr(stats, "longest_streak", 0) or 0,
        "total_minutes": rows.aggregate(total=Sum("minutes_studied"))["total"] or 0,
        "average_minutes_per_active_day": (
            round((rows.aggregate(total=Sum("minutes_studied"))["total"] or 0) / active_days)
            if active_days
            else 0
        ),
    }


def by_assessment(user: User, days: int = 30) -> list[dict]:
    """Performance split by what kind of practice it was."""
    since, _ = _window(days)
    labels = {
        ActivityType.QUIZ_COMPLETED: "Quizzes",
        ActivityType.STEEPLECHASE_COMPLETED: "Steeplechase",
        ActivityType.HISTOLOGY_COMPLETED: "Histology",
        ActivityType.BRAIN_BATTLE_COMPLETED: "Brain Battle",
        ActivityType.FLASHCARD_REVIEWED: "Flashcards",
        ActivityType.QUESTION_ANSWERED: "Practice questions",
    }

    rows = (
        LearningEvent.objects.filter(
            user=user, occurred_at__gte=since, activity__in=labels.keys(), total_count__gt=0
        )
        .values("activity")
        .annotate(
            attempted=Sum("total_count"),
            correct=Sum("correct_count"),
            sessions=Count("id"),
            seconds=Sum("duration_seconds"),
        )
    )

    return [
        {
            "activity": r["activity"],
            "label": labels[r["activity"]],
            "sessions": r["sessions"],
            "attempted": r["attempted"],
            "correct": r["correct"],
            "accuracy": round((r["correct"] or 0) / r["attempted"], 3) if r["attempted"] else None,
            "minutes": round((r["seconds"] or 0) / 60),
        }
        for r in sorted(rows, key=lambda r: -(r["attempted"] or 0))
    ]


def topic_performance(user: User, limit: int = 8) -> dict:
    """Strongest and weakest curriculum nodes, from the shared weak-area engine."""

    def serialise(area: WeakArea) -> dict:
        return {
            "label": area.label,
            "scope": area.scope,
            "attempted": area.attempted,
            "correct": area.correct,
            "accuracy": round(area.accuracy, 3) if area.accuracy is not None else None,
            "mastery": round(area.mastery, 3),
            "priority": area.priority,
            "last_practised_at": area.last_practised_at,
        }

    # Require real evidence before calling anything a strength or a weakness.
    graded = WeakArea.objects.filter(user=user, attempted__gte=3)

    # Report a single scope rather than mixing levels: listing "Upper Limb" beside
    # "Anatomy" invites the reader to compare a topic with the subject that contains it.
    # The finest scope that has data is the most actionable, so prefer that.
    scope = None
    for candidate in (
        WeakArea.Scope.TOPIC,
        WeakArea.Scope.SUB_BLOCK,
        WeakArea.Scope.BLOCK,
        WeakArea.Scope.SUBJECT,
    ):
        if graded.filter(scope=candidate).exists():
            scope = candidate
            break

    if scope is None:
        return {"weakest": [], "strongest": [], "tracked_nodes": 0, "scope": None}

    at_scope = graded.filter(scope=scope)

    # A node is only a *strength* if it is genuinely strong. Sorting by mastery alone
    # meant that with few tracked topics the weakest one still appeared under
    # "Strongest", which is worse than showing nothing.
    STRENGTH_FLOOR = 0.75
    strongest = at_scope.filter(mastery__gte=STRENGTH_FLOOR).order_by("-mastery")[:limit]

    return {
        "scope": scope,
        "weakest": [serialise(a) for a in at_scope.order_by("-priority")[:limit]],
        "strongest": [serialise(a) for a in strongest],
        "tracked_nodes": at_scope.count(),
    }


def question_bank(user: User) -> dict:
    """How much of the bank this student has worked through."""
    from curriculum.models import QuizQuestion

    total = QuizQuestion.objects.count()
    exposure = QuestionExposure.objects.filter(user=user)
    seen = exposure.filter(times_seen__gt=0).count()
    answered = exposure.filter(times_answered__gt=0).count()
    missed = exposure.filter(times_incorrect__gt=0).count()

    return {
        "total": total,
        "seen": seen,
        "unseen": max(0, total - seen),
        "answered": answered,
        "missed": missed,
        "percent_seen": round(seen / total * 100) if total else 0,
    }


def practice_summary(user: User, days: int = 30) -> dict:
    """Image-spot practice, per mode."""
    since, _ = _window(days)
    out = {}
    for mode, _label in PracticeMode.choices:
        rows = PracticeSession.objects.filter(
            user=user,
            mode=mode,
            status=PracticeSession.Status.COMPLETED,
            completed_at__gte=since,
        )
        count = rows.count()
        out[mode] = {
            "rounds": count,
            "stations": rows.aggregate(n=Sum("total_stations"))["n"] or 0,
            "average_accuracy": (
                round(rows.aggregate(a=Avg("score"))["a"] or 0, 3) if count else None
            ),
            "timed_out": rows.aggregate(n=Sum("timed_out_count"))["n"] or 0,
        }
    return out


def full_report(user: User, days: int = 30, *, include_detail: bool = True) -> dict:
    """Everything the analytics screen renders, in one round trip.

    `include_detail` is False for free students: they still get their real headline
    figures and activity, but topic-level analysis is the premium half.
    """
    report = {
        "generated_at": timezone.now(),
        "window_days": days,
        "overview": overview(user, days),
        "improvement": improvement(user, days),
        "consistency": consistency(user, days),
        "daily_activity": daily_activity(user, days),
        "by_assessment": by_assessment(user, days),
        "practice": practice_summary(user, days),
        "include_detail": include_detail,
    }

    # Bank coverage is "how much have you seen", not analysis — every student needs it
    # to judge whether practising will even find them new questions, so it is not gated.
    report["question_bank"] = question_bank(user)

    if include_detail:
        report["topics"] = topic_performance(user)

    return report
