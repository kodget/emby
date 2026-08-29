"""
Choosing which questions a student sees.

Once a slide's bank exists, practice must come out of the database rather than calling
the model again — that is what keeps Emby affordable and fast. But reading from the bank
naively means blind `order_by('?')`, which re-shows the same questions and skips others
entirely.

Selection here is a weighted blend rather than a shuffle:

  * **Unseen questions first.** Nothing beats a question the student has never met.
  * **Then rarely seen.** Fewer previous exposures ranks higher.
  * **Missed questions resurface**, but on a delay so they are not repeated in the very
    next session.
  * **Weak areas get more slots** when the student has a weak-area profile.
  * A small random jitter stops the order being identical for the same inputs.

Everything is driven off QuestionExposure, which is written whenever questions are served
and updated when they are answered.
"""

from __future__ import annotations

import logging
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from curriculum.models import QuizQuestion

from .models import QuestionExposure, WeakArea

logger = logging.getLogger(__name__)

# How long a missed question waits before it is eligible to come back.
MISSED_COOLDOWN = timedelta(hours=12)
# A question seen this recently is avoided unless the pool is exhausted.
RECENT_COOLDOWN = timedelta(hours=6)

# Score weights. Higher total score means "show this sooner".
W_UNSEEN = 100.0
W_MISSED = 45.0
W_WEAK_AREA = 25.0
W_STALENESS = 15.0
W_SEEN_PENALTY = 18.0
W_JITTER = 8.0


def _weak_node_ids(user: User) -> set:
    """Sub-block and topic ids the student is currently weak at."""
    rows = WeakArea.objects.filter(user=user, attempted__gte=3, mastery__lt=0.7).values(
        "sub_block_id", "topic_id"
    )
    ids = set()
    for row in rows:
        ids.update(v for v in row.values() if v)
    return ids


def _score(
    question: QuizQuestion,
    exposure: QuestionExposure | None,
    weak_ids: set,
    now,
) -> float:
    score = random.uniform(0, W_JITTER)

    if exposure is None or exposure.times_seen == 0:
        score += W_UNSEEN
    else:
        # Each additional exposure makes a question less valuable, with a floor so an
        # exhausted pool still returns something.
        score -= min(W_SEEN_PENALTY * exposure.times_seen, W_SEEN_PENALTY * 4)

        if exposure.is_weak and exposure.last_incorrect_at:
            # Missed questions are worth revisiting, but not immediately.
            if now - exposure.last_incorrect_at >= MISSED_COOLDOWN:
                score += W_MISSED

        if exposure.last_seen_at:
            days = (now - exposure.last_seen_at).days
            score += min(W_STALENESS, days * 1.5)
            if now - exposure.last_seen_at < RECENT_COOLDOWN:
                score -= W_SEEN_PENALTY * 2

    if weak_ids and (question.sub_block_id in weak_ids):
        score += W_WEAK_AREA

    return score


def select_questions(
    user: User,
    *,
    count: int,
    question_type: str = "mcq",
    subject_id: str | None = None,
    block_id: str | None = None,
    sub_block_id: str | None = None,
    slide_id: str | None = None,
    weak_areas_only: bool = False,
) -> list[QuizQuestion]:
    """Pick `count` questions for this student, preferring ones they have not seen.

    Returns fewer than `count` only when the filtered bank genuinely holds fewer.
    """
    qs = QuizQuestion.objects.filter(question_type=question_type)

    if subject_id:
        qs = qs.filter(subject_id=subject_id)
    if block_id:
        qs = qs.filter(block_id=block_id)
    if sub_block_id:
        qs = qs.filter(sub_block_id=sub_block_id)
    if slide_id:
        qs = qs.filter(source_slide_id=slide_id)

    weak_ids = _weak_node_ids(user)
    if weak_areas_only and weak_ids:
        qs = qs.filter(Q(sub_block_id__in=weak_ids) | Q(subject__weak_areas__user=user)).distinct()

    candidates = list(qs.only(
        "id", "sub_block_id", "subject_id", "block_id", "question_type", "difficulty"
    )[:1200])
    if not candidates:
        return []

    exposures = {
        e.question_id: e
        for e in QuestionExposure.objects.filter(
            user=user, question_id__in=[c.id for c in candidates]
        )
    }

    now = timezone.now()
    ranked = sorted(
        candidates,
        key=lambda q: _score(q, exposures.get(q.id), weak_ids, now),
        reverse=True,
    )
    chosen = ranked[:count]

    # Re-fetch in full: the ranking pass only loaded the columns it needed.
    ids = [q.id for q in chosen]
    by_id = {q.id: q for q in QuizQuestion.objects.filter(id__in=ids)}
    return [by_id[i] for i in ids if i in by_id]


@transaction.atomic
def mark_served(user: User, question_ids: list[str]) -> None:
    """Record that these questions were put in front of the student."""
    if not question_ids:
        return

    now = timezone.now()
    existing = {
        e.question_id: e
        for e in QuestionExposure.objects.select_for_update().filter(
            user=user, question_id__in=question_ids
        )
    }

    to_create = []
    for qid in question_ids:
        exposure = existing.get(qid)
        if exposure is None:
            to_create.append(
                QuestionExposure(user=user, question_id=qid, times_seen=1, last_seen_at=now)
            )
        else:
            exposure.times_seen += 1
            exposure.last_seen_at = now
            exposure.save(update_fields=["times_seen", "last_seen_at", "updated_at"])

    if to_create:
        QuestionExposure.objects.bulk_create(to_create, ignore_conflicts=True)


@transaction.atomic
def mark_answered(user: User, question_id: str, correct: bool) -> None:
    """Record the outcome so weak questions can resurface later."""
    now = timezone.now()
    exposure, _ = QuestionExposure.objects.select_for_update().get_or_create(
        user=user, question_id=question_id, defaults={"times_seen": 1, "last_seen_at": now}
    )
    exposure.times_answered += 1
    if correct:
        exposure.times_correct += 1
        exposure.last_correct_at = now
    else:
        exposure.times_incorrect += 1
        exposure.last_incorrect_at = now
    exposure.save()


def missed_questions(user: User, *, limit: int = 20) -> list[QuizQuestion]:
    """Questions this student has actually got wrong, worst first.

    Used by the "practise your mistakes" flow and by flashcard generation, so both work
    from the same definition of a mistake.
    """
    rows = (
        QuestionExposure.objects.filter(user=user, times_incorrect__gt=0)
        .select_related("question")
        .order_by("-times_incorrect", "last_incorrect_at")[:limit]
    )
    return [r.question for r in rows if r.is_weak]


def coverage(user: User, **filters) -> dict:
    """How much of the available bank this student has seen — real numbers, not a guess."""
    qs = QuizQuestion.objects.all()
    for field, value in filters.items():
        if value:
            qs = qs.filter(**{field: value})

    total = qs.count()
    seen = QuestionExposure.objects.filter(
        user=user, question__in=qs, times_seen__gt=0
    ).count()
    answered = QuestionExposure.objects.filter(
        user=user, question__in=qs, times_answered__gt=0
    ).count()

    return {
        "total": total,
        "seen": seen,
        "unseen": max(0, total - seen),
        "answered": answered,
        "percent_seen": round(seen / total * 100) if total else 0,
    }
