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
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from curriculum.class_access import scoped_optional_parents, visible
from curriculum.models import Subject, Block, SubBlock, Topic

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


def visible_weak_areas(user: User):
    """Only current-class nodes may contribute names or revision suggestions."""
    parents = {"subject": Subject, "block": Block, "sub_block": SubBlock, "topic": Topic}
    rows = scoped_optional_parents(WeakArea.objects.filter(user=user), user, parents)
    scope_matches = Q()
    for field, model in parents.items():
        scope_matches |= Q(scope=field.upper(), **{field + "__in": visible(model, user)})
    return rows.filter(scope_matches)


def _window(days: int):
    end = timezone.now()
    return end - timedelta(days=days), end


def overview(user: User, days: int = 30) -> dict:
    from .analytics_evidence import Evidence
    return Evidence(user, days).overview()


def improvement(user: User, days: int = 30) -> dict:
    from .analytics_evidence import Evidence
    return Evidence(user, days).improvement()


def daily_activity(user: User, days: int = 30) -> list[dict]:
    from .analytics_evidence import Evidence
    return Evidence(user, days).daily()


def consistency(user: User, days: int = 30) -> dict:
    from .analytics_evidence import Evidence
    return Evidence(user, days).consistency()


def by_assessment(user: User, days: int = 30) -> list[dict]:
    from .analytics_evidence import Evidence
    return Evidence(user, days).by_assessment()


def topic_performance(user: User, limit: int = 8, days: int = 30) -> dict:
    from .analytics_evidence import Evidence
    return Evidence(user, days).topics(limit=limit)


def question_bank(user: User) -> dict:
    """How much of the bank this student has worked through."""
    from .selection import coverage
    return coverage(user, question_type='mcq')


def practice_summary(user: User, days: int = 30, *, since=None, end=None) -> dict:
    """Image-spot practice, per mode."""
    from .analytics_evidence import Evidence
    evidence = Evidence(user, days, now=end)
    if since is not None:
        evidence.window = [r for r in evidence.rows if since <= r['at'] <= evidence.now]
    return evidence.practice_summary()


def full_report(user: User, days: int = 30, *, include_detail: bool = True) -> dict:
    """Everything the analytics screen renders, in one round trip.

    `include_detail` is False for free students: they still get their real headline
    figures and activity, but topic-level analysis is the premium half.
    """
    from .analytics_evidence import Evidence
    evidence = Evidence(user, days)
    report = {
        "generated_at": evidence.now,
        "window_days": days,
        "overview": evidence.overview(),
        "improvement": evidence.improvement(),
        "consistency": evidence.consistency(),
        "daily_activity": evidence.daily(),
        "by_assessment": evidence.by_assessment(),
        "practice": evidence.practice_summary(),
        "include_detail": include_detail,
        "evidence": {"timezone": timezone.get_current_timezone_name(),
                     "period_start": evidence.start, "period_end": evidence.now,
                     "historical_assessments_excluded": evidence.excluded_historical,
                     "historical_image_rounds_excluded_from_accuracy": evidence.historical_image_rounds,
                     "assessments_awaiting_written_grades": evidence.pending_written,
                     "note": "Accuracy covers objective scored items, including unanswered questions. Written marks and self-rated flashcards are separate. Historical assessments and image rounds without saved question versions are excluded from accuracy. Activity uses local calendar days through today; planner estimates are not study time. Study time is recorded elapsed time, not a measure of attention."},
    }

    # Bank coverage is "how much have you seen", not analysis — every student needs it
    # to judge whether practising will even find them new questions, so it is not gated.
    report["question_bank"] = question_bank(user)

    if include_detail:
        report["topics"] = evidence.topics()

    return report
