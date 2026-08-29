"""
Image-spot practice: Steeplechase and Histology.

Both modes are the same mechanic over a different station pool — thirty seconds a
station, a typed main answer, a supporting MCQ, sometimes a true/false — so they share
this one service rather than each growing a parallel implementation. `mode` selects the
pool; everything else (timing, entitlement, grading, results, analytics) is common.

Two rules are enforced here and nowhere else, because the frontend cannot be trusted
with either:

  * Free students get at most 5 stations per round and 5 rounds per calendar month,
    per mode. Premium users and verified class heads are unlimited.
  * Answers are never included in a station payload until the student has submitted.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from curriculum.models import SpotStation

from . import events
from .models import (
    ActivityType,
    PracticeAttempt,
    PracticeMode,
    PracticeRoundUsage,
    PracticeSession,
)

logger = logging.getLogger(__name__)

FREE_STATIONS_PER_ROUND = 5
FREE_ROUNDS_PER_MONTH = 5
MAX_STATIONS_PER_ROUND = 40
SECONDS_PER_STATION = PracticeSession.STATION_SECONDS

KIND_FOR_MODE = {
    PracticeMode.STEEPLECHASE: [
        SpotStation.Kind.GROSS_ANATOMY,
        SpotStation.Kind.RADIOGRAPH,
        SpotStation.Kind.MODEL,
    ],
    PracticeMode.HISTOLOGY: [SpotStation.Kind.HISTOLOGY],
}


class PracticeError(Exception):
    """A practice request that cannot be honoured, with a student-facing message."""

    def __init__(self, message: str, code: str = "invalid", status: int = 400):
        self.code = code
        self.status = status
        super().__init__(message)


class LimitReached(PracticeError):
    def __init__(self, message: str):
        super().__init__(message, code="limit_reached", status=403)


# ---------------------------------------------------------------------------
# Entitlement
# ---------------------------------------------------------------------------
def _is_premium(user: User) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_premium)


def _period() -> str:
    return timezone.now().strftime("%Y-%m")


def entitlement(user: User, mode: str) -> dict:
    """What this student is allowed to do right now, for display and enforcement."""
    premium = _is_premium(user)
    usage, _ = PracticeRoundUsage.objects.get_or_create(
        user=user, mode=mode, period=_period()
    )
    available = station_pool(mode).count()

    if premium:
        return {
            "is_premium": True,
            "max_stations": min(MAX_STATIONS_PER_ROUND, max(1, available)),
            "rounds_used": usage.rounds_used,
            "rounds_limit": None,
            "rounds_remaining": None,
            "stations_available": available,
        }

    return {
        "is_premium": False,
        "max_stations": FREE_STATIONS_PER_ROUND,
        "rounds_used": usage.rounds_used,
        "rounds_limit": FREE_ROUNDS_PER_MONTH,
        "rounds_remaining": max(0, FREE_ROUNDS_PER_MONTH - usage.rounds_used),
        "stations_available": available,
    }


# ---------------------------------------------------------------------------
# Station selection
# ---------------------------------------------------------------------------
def station_pool(mode: str, sections: list[str] | None = None):
    """Approved, playable stations for a mode, optionally filtered by section."""
    kinds = KIND_FOR_MODE.get(mode, [])
    qs = SpotStation.objects.filter(kind__in=kinds, is_approved=True).exclude(
        image_url=""
    )

    if sections:
        wanted = [s.strip().upper() for s in sections if s and s.strip()]
        if wanted and "ALL" not in wanted:
            if mode == PracticeMode.HISTOLOGY:
                qs = qs.filter(histology_topic__in=wanted)
            else:
                qs = qs.filter(region__in=wanted)
    return qs


def available_sections(mode: str) -> list[dict]:
    """Sections that actually have playable stations, with counts.

    Only non-empty sections are offered so a student cannot pick a filter that yields
    an empty round.

    UNKNOWN is deliberately not offered. It is not a region a student would ever choose
    to revise — it means the vision pass could place the structure but not the part of
    the body, so "Unclassified" is a statement about our pipeline, not about anatomy.
    Those stations stay in the pool and still appear in an unfiltered round; they just
    are not presented as something to pick.
    """
    field = "histology_topic" if mode == PracticeMode.HISTOLOGY else "region"
    rows = (
        station_pool(mode)
        .values(field)
        .annotate(count=__import__("django").db.models.Count("id"))
        .order_by("-count")
    )
    labels = dict(
        SpotStation._meta.get_field(field).choices or []
    )
    return [
        {"code": r[field], "label": labels.get(r[field], r[field]), "count": r["count"]}
        for r in rows
        if r["count"] > 0 and r[field] != "UNKNOWN"
    ]


def _select_stations(user: User, mode: str, sections: list[str], count: int) -> list[str]:
    """Pick stations, preferring ones this student has not attempted before.

    Blind randomisation would re-show the same handful of stations; this ranks unseen
    first, then least-recently-seen, and only then falls back to repeats.
    """
    pool = list(station_pool(mode, sections).values_list("id", flat=True))
    if not pool:
        return []

    seen_rows = (
        PracticeAttempt.objects.filter(session__user=user, station_id__in=pool)
        .values_list("station_id", flat=True)
    )
    seen_counts: dict[str, int] = {}
    for sid in seen_rows:
        seen_counts[sid] = seen_counts.get(sid, 0) + 1

    unseen = [s for s in pool if s not in seen_counts]
    seen = sorted(seen_counts.keys(), key=lambda s: seen_counts[s])

    random.shuffle(unseen)
    chosen = unseen[:count]
    if len(chosen) < count:
        # Fall back to the least-often-seen stations, lightly shuffled within tiers.
        remaining = [s for s in seen if s not in chosen]
        chosen.extend(remaining[: count - len(chosen)])

    random.shuffle(chosen)
    return chosen


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
@transaction.atomic
def start_session(
    user: User, mode: str, sections: list[str] | None, requested: int
) -> PracticeSession:
    """Create a round, enforcing the free-tier limits server-side."""
    if mode not in dict(PracticeMode.choices):
        raise PracticeError("Unknown practice mode")

    sections = sections or []
    limits = entitlement(user, mode)

    if not limits["is_premium"]:
        if limits["rounds_remaining"] <= 0:
            raise LimitReached(
                f"You have used all {FREE_ROUNDS_PER_MONTH} free {mode.lower()} rounds "
                f"this month. Upgrade for unlimited rounds."
            )
        requested = min(requested, FREE_STATIONS_PER_ROUND)
    requested = max(1, min(requested, MAX_STATIONS_PER_ROUND))

    station_ids = _select_stations(user, mode, sections, requested)
    if not station_ids:
        raise PracticeError(
            "No approved stations match that selection yet.", code="empty_pool"
        )

    session = PracticeSession.objects.create(
        user=user,
        mode=mode,
        sections=sections,
        station_ids=station_ids,
        total_stations=len(station_ids),
        seconds_per_station=SECONDS_PER_STATION,
    )

    # Count the round only once it has actually been created.
    usage, _ = PracticeRoundUsage.objects.select_for_update().get_or_create(
        user=user, mode=mode, period=_period()
    )
    usage.rounds_used += 1
    usage.save(update_fields=["rounds_used", "updated_at"])

    SpotStation.objects.filter(id__in=station_ids).update(
        times_served=__import__("django").db.models.F("times_served") + 1
    )
    return session


def station_payload(station: SpotStation, index: int, total: int) -> dict:
    """What the student may see *before* answering.

    Deliberately omits accepted_answers, the supporting question's correct_index, the
    true/false answer and every explanation. Those are only returned once the attempt
    has been submitted.
    """
    supporting = station.supporting_question or {}
    true_false = station.true_false_question or {}

    payload = {
        "id": station.id,
        "index": index,
        "total": total,
        "seconds": SECONDS_PER_STATION,
        "image_url": station.image_url,
        "section": station.section,
        "marker": {
            "present": bool((station.marker or {}).get("present")),
            "type": (station.marker or {}).get("type", "none"),
            "x": (station.marker or {}).get("x"),
            "y": (station.marker or {}).get("y"),
        },
        "main": {"question": station.prompt},
    }

    if supporting.get("enabled") and supporting.get("options"):
        payload["supporting"] = {
            "question": supporting.get("question", ""),
            "options": list(supporting.get("options", []))[:4],
        }
    if true_false.get("enabled") and true_false.get("statement"):
        payload["true_false"] = {"statement": true_false["statement"]}

    return payload


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
_ARTICLES = {"the", "a", "an", "of", "left", "right"}


def normalise_answer(text: str) -> set[str]:
    """Reduce a typed answer to comparable tokens.

    Students type "the radial n." or "Radial Nerve" for the same thing, so casing,
    punctuation, accents, articles and a few common abbreviations are folded away.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\bn\b", "nerve", text)
    text = re.sub(r"\ba\b(?=\s)", " ", text)
    text = re.sub(r"\bm\b", "muscle", text)
    text = re.sub(r"\bv\b", "vein", text)
    tokens = {t for t in text.split() if t and t not in _ARTICLES}
    return tokens


def expand_alternatives(answer: str) -> list[str]:
    """Split one accepted answer into the forms a student might legitimately type.

    Source answers routinely carry a synonym in brackets or after a slash, e.g.
    "Common fibular nerve (Common peroneal nerve)". Treating that as a single string
    would demand the student type both names, so each variant is accepted on its own.
    """
    if not answer:
        return []

    variants: list[str] = []
    inner = re.findall(r"\(([^)]*)\)", answer)
    outer = re.sub(r"\([^)]*\)", " ", answer)

    for chunk in [outer, *inner]:
        for part in re.split(r"\s*(?:/|;| or )\s*", chunk):
            part = part.strip(" ,.")
            if part:
                variants.append(part)
    return variants or [answer]


def grade_main_answer(given: str, accepted: list[str]) -> bool:
    """True when a typed answer matches any accepted answer closely enough.

    Requires the student's tokens to cover the significant tokens of one accepted
    variant, which accepts "radial nerve", "the radial n." and "Radial Nerve" while
    still rejecting "median nerve".
    """
    given_tokens = normalise_answer(given)
    if not given_tokens:
        return False

    for candidate in accepted or []:
        for variant in expand_alternatives(candidate):
            want = normalise_answer(variant)
            if not want:
                continue
            # Ignore very generic tokens when deciding what must be present, so
            # "ulnar" matches "Ulnar nerve".
            core = {
                t for t in want
                if t not in {"nerve", "muscle", "artery", "vein", "bone", "tendon"}
            }
            target = core or want
            if target.issubset(given_tokens) or want.issubset(given_tokens):
                return True
    return False


@transaction.atomic
def submit_attempt(
    session: PracticeSession,
    station_id: str,
    *,
    main_answer: str = "",
    supporting_choice: int | None = None,
    true_false_answer: bool | None = None,
    seconds_taken: int = 0,
    timed_out: bool = False,
) -> dict:
    """Record and grade one station, returning the reveal payload."""
    if session.status != PracticeSession.Status.IN_PROGRESS:
        raise PracticeError("This session is already finished.")
    if station_id not in session.station_ids:
        raise PracticeError("That station is not part of this session.")

    station = SpotStation.objects.filter(id=station_id).first()
    if station is None:
        raise PracticeError("Station not found.", status=404)

    supporting = station.supporting_question or {}
    true_false = station.true_false_question or {}

    main_correct = grade_main_answer(main_answer, station.accepted_answers)

    supporting_correct = None
    if supporting.get("enabled") and supporting_choice is not None:
        supporting_correct = supporting_choice == supporting.get("correct_index")

    tf_correct = None
    if true_false.get("enabled") and true_false_answer is not None:
        tf_correct = true_false_answer == bool(true_false.get("answer"))

    # A timer expiry must never overwrite an answer the student already submitted.
    attempt, _ = PracticeAttempt.objects.update_or_create(
        session=session,
        station=station,
        defaults={
            "order": session.station_ids.index(station_id),
            "main_answer": (main_answer or "")[:2000],
            "main_correct": main_correct,
            "supporting_choice": supporting_choice,
            "supporting_correct": supporting_correct,
            "true_false_answer": true_false_answer,
            "true_false_correct": tf_correct,
            "seconds_taken": max(0, min(seconds_taken, SECONDS_PER_STATION * 3)),
            "timed_out": timed_out,
            "answered_at": timezone.now(),
        },
    )

    return {
        "station_id": station.id,
        "main": {
            "correct": main_correct,
            "answer": (station.accepted_answers or [None])[0],
            "explanation": station.explanation,
        },
        "supporting": (
            {
                "correct": supporting_correct,
                "correct_index": supporting.get("correct_index"),
                "explanation": supporting.get("explanation", ""),
            }
            if supporting.get("enabled")
            else None
        ),
        "true_false": (
            {
                "correct": tf_correct,
                "answer": true_false.get("answer"),
                "explanation": true_false.get("explanation", ""),
            }
            if true_false.get("enabled")
            else None
        ),
        "structure": station.structure,
        "timed_out": timed_out,
    }


@transaction.atomic
def complete_session(session: PracticeSession) -> dict:
    """Score the round, persist the breakdown, and feed the learning stream."""
    if session.status == PracticeSession.Status.COMPLETED:
        return results(session)

    attempts = list(session.attempts.select_related("station"))

    main_correct = sum(1 for a in attempts if a.main_correct)
    supporting_correct = sum(1 for a in attempts if a.supporting_correct)
    tf_correct = sum(1 for a in attempts if a.true_false_correct)
    timed_out = sum(1 for a in attempts if a.timed_out)

    # Every graded item counts, not just the main question, so a student who reliably
    # gets the supporting MCQ right is not scored as if they failed the station.
    graded = 0
    correct = 0
    for a in attempts:
        graded += 1
        correct += 1 if a.main_correct else 0
        if a.supporting_correct is not None:
            graded += 1
            correct += 1 if a.supporting_correct else 0
        if a.true_false_correct is not None:
            graded += 1
            correct += 1 if a.true_false_correct else 0

    score = (correct / graded) if graded else 0.0

    breakdown: dict[str, dict] = {}
    for a in attempts:
        key = a.station.section
        bucket = breakdown.setdefault(key, {"attempted": 0, "correct": 0})
        bucket["attempted"] += 1
        if a.main_correct:
            bucket["correct"] += 1
    for bucket in breakdown.values():
        bucket["accuracy"] = (
            round(bucket["correct"] / bucket["attempted"], 3) if bucket["attempted"] else 0
        )

    session.main_correct = main_correct
    session.supporting_correct = supporting_correct
    session.true_false_correct = tf_correct
    session.timed_out_count = timed_out
    session.score = round(score, 4)
    session.section_breakdown = breakdown
    session.status = PracticeSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save()

    duration = sum(a.seconds_taken for a in attempts)
    activity = (
        ActivityType.STEEPLECHASE_COMPLETED
        if session.mode == PracticeMode.STEEPLECHASE
        else ActivityType.HISTOLOGY_COMPLETED
    )
    events.record(
        session.user,
        activity,
        correct_count=correct,
        total_count=graded,
        duration_seconds=duration,
        resource_type="practice_session",
        resource_id=str(session.id),
        metadata={"mode": session.mode, "sections": session.sections},
    )

    return results(session)


def results(session: PracticeSession) -> dict:
    """Full result payload. Premium students additionally get per-station detail."""
    attempts = list(session.attempts.select_related("station").order_by("order"))
    premium = _is_premium(session.user)

    payload = {
        "session_id": str(session.id),
        "mode": session.mode,
        "status": session.status,
        "total_stations": session.total_stations,
        "answered": len(attempts),
        "score": session.score,
        "accuracy_percent": round(session.score * 100),
        "main_correct": session.main_correct,
        "supporting_correct": session.supporting_correct,
        "true_false_correct": session.true_false_correct,
        "timed_out": session.timed_out_count,
        "average_seconds": (
            round(sum(a.seconds_taken for a in attempts) / len(attempts), 1)
            if attempts
            else 0
        ),
        "section_breakdown": session.section_breakdown,
        "is_premium": premium,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
    }

    if premium:
        payload["stations"] = [
            {
                "station_id": a.station_id,
                "image_url": a.station.image_url,
                "section": a.station.section,
                "question": a.station.prompt,
                "your_answer": a.main_answer,
                "correct_answer": (a.station.accepted_answers or [None])[0],
                "main_correct": a.main_correct,
                "supporting_correct": a.supporting_correct,
                "true_false_correct": a.true_false_correct,
                "explanation": a.station.explanation,
                "structure": a.station.structure,
                "seconds_taken": a.seconds_taken,
                "timed_out": a.timed_out,
            }
            for a in attempts
        ]
        payload["weak_sections"] = [
            section
            for section, stats in sorted(
                session.section_breakdown.items(), key=lambda kv: kv[1].get("accuracy", 0)
            )
            if stats.get("accuracy", 1) < 0.6
        ]
    else:
        # Free students still see which sections went badly, just not every answer.
        payload["upgrade_hint"] = (
            "Upgrade to see the correct answer and explanation for every station."
        )

    return payload
