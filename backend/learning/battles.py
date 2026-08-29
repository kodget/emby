"""
Brain Battle mechanics.

Everything that decides an outcome lives here rather than in the client:

  * **Scoring is derived, never accepted.** The client sends which option it picked and
    how long it took; the server decides whether that was right and what it is worth.
  * **Answers are recorded per question** with a unique constraint, so replaying a
    submission cannot inflate a score.
  * **The correct answer is stripped** from every question payload sent to a participant
    while the battle is live.
  * **XP flows through the normal ledger**, so battle XP obeys the same daily caps and
    diminishing returns as everything else and cannot be farmed by rematching.
"""

from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from curriculum.models import BattleAnswer, BattleParticipant, BrainBattle

from . import events
from .models import ActivityType

logger = logging.getLogger(__name__)

BASE_POINTS = 100
# Answering quickly is worth up to this much on top, scaled by time remaining.
SPEED_BONUS = 50


class BattleError(Exception):
    def __init__(self, message: str, code: str = "invalid", status: int = 400):
        self.code = code
        self.status = status
        super().__init__(message)


def find_by_code(code: str) -> BrainBattle:
    """Resolve a join code, with messages a student can act on."""
    cleaned = (code or "").strip().upper().replace(" ", "").replace("-", "")
    if not cleaned:
        raise BattleError("Enter a battle code.", code="missing_code")

    battle = BrainBattle.objects.filter(code=cleaned).first()
    if battle is None:
        raise BattleError(
            "No battle with that code. Check it and try again.",
            code="not_found",
            status=404,
        )
    if not battle.is_joinable:
        raise BattleError("That battle has already finished.", code="finished", status=409)
    return battle


@transaction.atomic
def join(user: User, code: str) -> tuple[BrainBattle, BattleParticipant, bool]:
    """Join by code. Re-joining is idempotent so a refresh does not error."""
    battle = find_by_code(code)

    if not (battle.questions or []):
        raise BattleError(
            "This battle has no questions yet. Ask the host to try again.",
            code="no_questions",
            status=409,
        )

    participant, created = BattleParticipant.objects.get_or_create(
        battle=battle, user=user
    )
    return battle, participant, created


def question_payload(battle: BrainBattle, index: int, *, reveal: bool = False) -> dict:
    """One question as a participant may see it.

    `correct_index` and the explanation are withheld until the answer is revealed, so a
    participant cannot read the answer out of the network response.
    """
    questions = battle.questions or []
    if index < 0 or index >= len(questions):
        raise BattleError("No question at that position.", code="out_of_range", status=404)

    raw = questions[index] or {}
    payload = {
        "index": index,
        "total": len(questions),
        "question": raw.get("question") or raw.get("question_text") or "",
        "options": list(raw.get("options") or [])[:4],
        "seconds": battle.time_per_question,
    }
    if reveal:
        payload["correct_index"] = _correct_index(raw)
        payload["explanation"] = raw.get("explanation", "")
    return payload


def _correct_index(raw: dict) -> int | None:
    """Read the correct option, tolerating the shapes the generator has produced."""
    for key in ("correct_index", "correctAnswer", "correct_answer", "answer_index"):
        value = raw.get(key)
        if isinstance(value, int):
            return value
    # Letter form, e.g. "correct_option": "B"
    letter = raw.get("correct_option") or raw.get("correctOption")
    if isinstance(letter, str) and len(letter) == 1 and letter.upper() in "ABCD":
        return "ABCD".index(letter.upper())
    return None


@transaction.atomic
def submit_answer(
    user: User,
    battle: BrainBattle,
    index: int,
    selected_index: int | None,
    seconds_taken: float,
) -> dict:
    """Score one answer server-side and return the reveal."""
    participant = BattleParticipant.objects.select_for_update().filter(
        battle=battle, user=user
    ).first()
    if participant is None:
        raise BattleError("You have not joined this battle.", code="not_joined", status=403)

    questions = battle.questions or []
    if index < 0 or index >= len(questions):
        raise BattleError("No question at that position.", code="out_of_range", status=404)

    if BattleAnswer.objects.filter(participant=participant, question_index=index).exists():
        raise BattleError(
            "You have already answered this question.", code="already_answered", status=409
        )

    raw = questions[index] or {}
    correct_index = _correct_index(raw)
    is_correct = correct_index is not None and selected_index == correct_index

    points = 0
    if is_correct:
        # Full marks for a correct answer, plus a bonus that decays with time used.
        limit = max(1, battle.time_per_question)
        remaining = max(0.0, min(1.0, (limit - max(0.0, seconds_taken)) / limit))
        points = BASE_POINTS + round(SPEED_BONUS * remaining)

    BattleAnswer.objects.create(
        participant=participant,
        question_index=index,
        selected_index=selected_index,
        is_correct=is_correct,
        seconds_taken=max(0.0, seconds_taken),
        points=points,
    )

    participant.answered_count += 1
    participant.correct_count += 1 if is_correct else 0
    participant.score += points
    participant.save(update_fields=["answered_count", "correct_count", "score"])

    return {
        "index": index,
        "correct": is_correct,
        "correct_index": correct_index,
        "explanation": raw.get("explanation", ""),
        "points": points,
        "score": participant.score,
    }


def leaderboard(battle: BrainBattle) -> list[dict]:
    """Standings, computed from recorded answers."""
    rows = (
        BattleParticipant.objects.filter(battle=battle)
        .select_related("user")
        .order_by("-score", "joined_at")
    )
    return [
        {
            "rank": position,
            "user_id": p.user_id,
            "name": (p.user.get_full_name() or p.user.username).strip(),
            "score": p.score,
            "answered": p.answered_count,
            "correct": p.correct_count,
            "accuracy": round(p.accuracy, 3) if p.accuracy is not None else None,
            "is_host": p.user_id == battle.host_id,
        }
        for position, p in enumerate(rows, start=1)
    ]


@transaction.atomic
def finish_for_user(user: User, battle: BrainBattle) -> dict:
    """Close out one participant's run and award XP once.

    XP goes through learning.events like every other activity, so the daily cap and
    diminishing returns apply — replaying battles against the same friend cannot be used
    to farm the leaderboard.
    """
    participant = BattleParticipant.objects.select_for_update().filter(
        battle=battle, user=user
    ).first()
    if participant is None:
        raise BattleError("You have not joined this battle.", code="not_joined", status=403)

    standings = leaderboard(battle)
    rank = next((r["rank"] for r in standings if r["user_id"] == user.id), None)

    if participant.finished_at is None:
        participant.finished_at = timezone.now()
        participant.save(update_fields=["finished_at"])

        duration = int(
            BattleAnswer.objects.filter(participant=participant).aggregate(
                total=__import__("django").db.models.Sum("seconds_taken")
            )["total"]
            or 0
        )
        events.record(
            user,
            ActivityType.BRAIN_BATTLE_COMPLETED,
            subject=battle.linked_subject,
            block=battle.linked_block,
            sub_block=battle.linked_sub_block,
            correct_count=participant.correct_count,
            total_count=participant.answered_count,
            duration_seconds=duration,
            resource_type="brain_battle",
            resource_id=str(battle.id),
            metadata={
                "battle_code": battle.code,
                "rank": rank,
                "participants": len(standings),
                "score": participant.score,
            },
        )

    return {
        "battle_id": battle.id,
        "code": battle.code,
        "your_rank": rank,
        "your_score": participant.score,
        "answered": participant.answered_count,
        "correct": participant.correct_count,
        "accuracy": round(participant.accuracy, 3) if participant.accuracy is not None else None,
        "participants": len(standings),
        "leaderboard": standings,
    }
