"""
Brain Battle mechanics.

Everything that decides an outcome lives here rather than in the client:

  * **Scoring is derived, never accepted.** The client sends which option it picked; the
    server decides whether it was right and measures elapsed time itself.
  * **Answers are recorded per question** with a unique constraint, so replaying a
    submission cannot inflate a score.
  * **The correct answer is stripped** from every question payload sent to a participant
    while the battle is live.
  * **XP flows through the normal ledger**, so battle XP obeys the same daily caps and
    diminishing returns as everything else and cannot be farmed by rematching.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from curriculum.models import BattleAnswer, BattleParticipant, BrainBattle

from . import events
from .models import ActivityType

MAX_ANSWER_POINTS = 1000


class BattleError(Exception):
    def __init__(self, message: str, code: str = "invalid", status: int = 400):
        self.code = code
        self.status = status
        super().__init__(message)


def find_by_code(code: str, *, allow_active: bool = False) -> BrainBattle:
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
    if battle.status == "completed":
        raise BattleError("That battle has already finished.", code="finished", status=409)
    if not battle.is_joinable and not (allow_active and battle.status == "active"):
        raise BattleError(
            "That battle has started and no longer accepts new players.",
            code="started",
            status=409,
        )
    return battle


@transaction.atomic
def join(user: User, code: str) -> tuple[BrainBattle, BattleParticipant, bool]:
    """Join by code. Re-joining is idempotent so a refresh does not error."""
    battle = find_by_code(code, allow_active=True)
    battle = BrainBattle.objects.select_for_update().get(pk=battle.pk)
    existing = BattleParticipant.objects.filter(battle=battle, user=user).first()
    if battle.status == "active":
        if existing is not None:
            return battle, existing, False
        raise BattleError(
            "That battle has started and no longer accepts new players.",
            code="started",
            status=409,
        )
    if not battle.is_joinable:
        raise BattleError(
            "That battle has already started. Rejoin from your battle list.",
            code="started",
            status=409,
        )

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


@transaction.atomic
def advance_question(host: User, battle_id: int) -> dict | None:
    """Start the first question or advance after the current answer is revealed."""
    battle = BrainBattle.objects.select_for_update().filter(pk=battle_id).first()
    if battle is None:
        raise BattleError("Battle not found.", code="not_found", status=404)
    if battle.host_id != host.id:
        raise BattleError("Only the host can advance this battle.", code="forbidden", status=403)
    questions = battle.questions or []
    if not questions:
        raise BattleError("This battle has no questions.", code="no_questions", status=409)
    if battle.status == "completed":
        raise BattleError("This battle has already finished.", code="finished", status=409)

    now = timezone.now()
    if battle.status == "scheduled":
        battle.status = "active"
        battle.start_time = now
        battle.current_question_index = 0
    elif battle.current_question_index < 0:
        battle.current_question_index = 0
    elif battle.current_question_revealed_at is None:
        raise BattleError(
            "Reveal the current answer before continuing.",
            code="awaiting_reveal",
            status=409,
        )
    else:
        battle.current_question_index += 1

    if battle.current_question_index >= len(questions):
        battle.status = "completed"
        battle.current_question_started_at = None
        battle.current_question_revealed_at = None
        battle.save(update_fields=[
            "status", "current_question_index", "current_question_started_at",
            "current_question_revealed_at",
        ])
        _complete_participants(battle)
        return None

    battle.current_question_started_at = now
    battle.current_question_revealed_at = None
    battle.save(update_fields=[
        "status", "start_time", "current_question_index",
        "current_question_started_at", "current_question_revealed_at",
    ])
    return {
        **question_payload(battle, battle.current_question_index),
        "remaining_ms": max(1, battle.time_per_question) * 1000,
    }


@transaction.atomic
def reveal_current_answer(host: User, battle_id: int) -> dict:
    """Reveal the active question once and prevent further submissions."""
    battle = BrainBattle.objects.select_for_update().filter(pk=battle_id).first()
    if battle is None:
        raise BattleError("Battle not found.", code="not_found", status=404)
    if battle.host_id != host.id:
        raise BattleError("Only the host can reveal answers.", code="forbidden", status=403)
    if (
        battle.status != "active"
        or battle.current_question_index < 0
        or battle.current_question_index >= len(battle.questions or [])
    ):
        raise BattleError("There is no active question to reveal.", code="not_active", status=409)

    if battle.current_question_revealed_at is None:
        battle.current_question_revealed_at = timezone.now()
        battle.save(update_fields=["current_question_revealed_at"])
    question = (battle.questions or [])[battle.current_question_index] or {}
    return {
        "correct_index": _correct_index(question),
        "explanation": question.get("explanation", ""),
    }


@transaction.atomic
def end_battle(host: User, battle_id: int) -> None:
    """Complete a battle; repeated host requests are harmless."""
    battle = BrainBattle.objects.select_for_update().filter(pk=battle_id).first()
    if battle is None:
        raise BattleError("Battle not found.", code="not_found", status=404)
    if battle.host_id != host.id:
        raise BattleError("Only the host can end this battle.", code="forbidden", status=403)
    if battle.status == "completed":
        return
    was_active = battle.status == "active"
    battle.status = "completed"
    battle.current_question_started_at = None
    battle.current_question_revealed_at = None
    battle.save(update_fields=[
        "status", "current_question_started_at", "current_question_revealed_at",
    ])
    if was_active:
        _complete_participants(battle)


def question_payload(battle: BrainBattle, index: int, *, reveal: bool = False) -> dict:
    """One question as a participant may see it.

    `correct_index` and the explanation are withheld until the answer is revealed, so a
    participant cannot read the answer out of the network response.
    """
    questions = battle.questions or []
    if index < 0 or index >= len(questions):
        raise BattleError("No question at that position.", code="out_of_range", status=404)
    if battle.status != "active":
        raise BattleError("This battle has no active question.", code="not_active", status=409)
    if index != battle.current_question_index:
        raise BattleError(
            "Only the current question is available.",
            code="not_current",
            status=409,
        )
    if reveal and battle.current_question_revealed_at is None:
        raise BattleError("The host has not revealed this answer.", code="not_revealed", status=409)

    raw = questions[index] or {}
    payload = {
        "index": index,
        "total": len(questions),
        "question": raw.get("question") or raw.get("question_text") or "",
        "options": list(raw.get("options") or [])[:4],
        "seconds": max(1, battle.time_per_question),
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
) -> dict:
    """Persist and score one answer from server timing, never client timing."""
    battle = BrainBattle.objects.select_for_update().filter(pk=battle.pk).first()
    if battle is None:
        raise BattleError("Battle not found.", code="not_found", status=404)
    participant = BattleParticipant.objects.select_for_update().filter(
        battle=battle, user=user
    ).first()
    if participant is None:
        raise BattleError("You have not joined this battle.", code="not_joined", status=403)

    questions = battle.questions or []
    if index < 0 or index >= len(questions):
        raise BattleError("No question at that position.", code="out_of_range", status=404)

    previous = BattleAnswer.objects.filter(
        participant=participant, question_index=index
    ).first()
    if previous is not None:
        return {
            "index": index,
            "correct": previous.is_correct,
            "points": previous.points,
            "score": participant.score,
            "replayed": True,
        }

    if participant.finished_at is not None:
        raise BattleError("Your battle run is already finished.", code="finished", status=409)
    if (
        battle.status != "active"
        or index != battle.current_question_index
        or battle.current_question_revealed_at is not None
    ):
        raise BattleError("This question is no longer accepting answers.", code="closed", status=409)
    if battle.current_question_started_at is None:
        battle.current_question_started_at = battle.start_time or timezone.now()
        battle.save(update_fields=["current_question_started_at"])

    limit = max(1, battle.time_per_question)
    elapsed = max(
        0.0,
        (timezone.now() - battle.current_question_started_at).total_seconds(),
    )
    if elapsed > limit:
        raise BattleError("The time for this question has expired.", code="time_expired", status=409)

    raw = questions[index] or {}
    correct_index = _correct_index(raw)
    options = list(raw.get("options") or [])[:4]
    if (
        type(selected_index) is not int
        or selected_index < 0
        or selected_index >= len(options)
    ):
        raise BattleError("Choose a valid answer option.", code="invalid_answer")
    is_correct = correct_index is not None and selected_index == correct_index

    points = 0
    if is_correct:
        remaining = max(0.0, min(1.0, (limit - elapsed) / limit))
        points = int(MAX_ANSWER_POINTS * remaining)

    BattleAnswer.objects.create(
        participant=participant,
        question_index=index,
        selected_index=selected_index,
        is_correct=is_correct,
        seconds_taken=elapsed,
        points=points,
    )

    participant.answered_count += 1
    participant.correct_count += 1 if is_correct else 0
    participant.score += points
    participant.save(update_fields=["answered_count", "correct_count", "score"])

    return {
        "index": index,
        "correct": is_correct,
        "points": points,
        "score": participant.score,
        "replayed": False,
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


def _complete_participants(battle: BrainBattle) -> None:
    for user in User.objects.filter(battle_participations__battle=battle).iterator():
        finish_for_user(user, battle)


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
    if battle.status != "completed":
        raise BattleError("This battle has not finished yet.", code="not_finished", status=409)

    standings = leaderboard(battle)
    rank = next((r["rank"] for r in standings if r["user_id"] == user.id), None)

    if participant.finished_at is None:
        participant.finished_at = timezone.now()
        participant.save(update_fields=["finished_at"])

        duration = int(
            BattleAnswer.objects.filter(participant=participant).aggregate(
                total=Sum("seconds_taken")
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
