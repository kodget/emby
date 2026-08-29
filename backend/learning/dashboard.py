"""
The personalised dashboard greeting.

This message used to be regenerated on every page load, which meant an AI call — and a
different message — each time a student refreshed. It is now generated at most once
every six hours and served from cache in between, so a day of heavy use costs at most
four calls instead of dozens, and the message stays stable while the student reads it.

The copy is grounded in the student's real numbers (streak, recent accuracy, cards due,
weakest topic). If the model is unavailable the fallback is still built from those same
numbers rather than being generic filler.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from . import credits, events
from .models import AIAction, DashboardMessage, LearningEvent, WeakArea

logger = logging.getLogger(__name__)


def build_context(user: User) -> dict:
    """The real figures the greeting is written from."""
    from curriculum.models import FlashcardProgress

    stats = getattr(user, "stats", None)
    since = timezone.now() - timedelta(days=7)

    recent = LearningEvent.objects.filter(user=user, occurred_at__gte=since)
    attempted = sum(e.total_count for e in recent)
    correct = sum(e.correct_count for e in recent)

    weakest = (
        WeakArea.objects.filter(user=user, attempted__gte=3)
        .order_by("-priority")
        .first()
    )

    return {
        "name": (user.first_name or user.username or "").strip(),
        "streak": getattr(stats, "current_streak", 0) or 0,
        "sessions_this_week": recent.count(),
        "questions_this_week": attempted,
        "accuracy_this_week": round(correct / attempted, 2) if attempted else None,
        "cards_due": FlashcardProgress.objects.filter(
            user=user, due_date__lte=timezone.now()
        ).count(),
        "weakest_topic": weakest.label if weakest else None,
        "days_since_last_study": (
            (timezone.now().date() - stats.last_activity_date).days
            if stats and stats.last_activity_date
            else None
        ),
    }


def _fallback(context: dict) -> tuple[str, str]:
    """A grounded message for when the model is unavailable or out of credit."""
    name = context["name"].split(" ")[0] if context["name"] else ""
    streak = context["streak"]
    due = context["cards_due"]

    headline = f"{name}, ready to study?" if name else "Ready to study?"

    parts: list[str] = []
    if streak >= 2:
        parts.append(f"You're on a {streak}-day streak.")
    elif context["days_since_last_study"] and context["days_since_last_study"] > 2:
        parts.append("It's been a few days — a short session is enough to restart.")

    if due:
        parts.append(f"{due} flashcard{'s' if due != 1 else ''} due for review.")
    if context["weakest_topic"]:
        parts.append(f"{context['weakest_topic']} could use another pass.")

    if not parts:
        parts.append("Pick a slide or start a quick quiz to get going.")

    return headline, " ".join(parts)


def _generate(user: User, context: dict) -> tuple[str, str]:
    """Ask the model for a short, specific greeting, charging one AI credit."""
    from curriculum import llm

    prompt = (
        "You are Emby, a study companion for Nigerian medical students. Write a short "
        "dashboard greeting for this student, grounded ONLY in the figures below.\n\n"
        f"{context}\n\n"
        "Return JSON with two fields:\n"
        '  "headline": at most 8 words, warm, may use their first name.\n'
        '  "body": one or two sentences, at most 40 words, naming something concrete '
        "from the figures and suggesting one next action.\n\n"
        "Do not invent numbers. Do not be saccharine or use exclamation marks. If the "
        "student has been away, be encouraging rather than guilt-inducing."
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["headline", "body"],
        "properties": {
            "headline": {"type": "string"},
            "body": {"type": "string"},
        },
    }

    with credits.spend(user, AIAction.DASHBOARD_MESSAGE, resource_type="dashboard"):
        data = llm.chat_json(
            [{"role": "user", "content": prompt}],
            json_schema=schema,
            schema_name="dashboard_message",
            max_tokens=300,
            temperature=0.7,
        )

    if not isinstance(data, dict) or not data.get("body"):
        raise ValueError("model returned no usable message")
    return str(data.get("headline") or "").strip(), str(data["body"]).strip()


def get_message(user: User, *, force: bool = False) -> dict:
    """Return the cached greeting, regenerating only when it has expired.

    Never raises: a failure here must not take down the dashboard, so any problem falls
    back to the grounded local message.
    """
    cached, _ = DashboardMessage.objects.get_or_create(user=user)

    if cached.is_valid and not force:
        return {
            "headline": cached.headline,
            "body": cached.body,
            "cached": True,
            "generated_at": cached.generated_at,
            "expires_at": cached.expires_at,
        }

    context = build_context(user)

    try:
        headline, body = _generate(user, context)
        source = "ai"
    except credits.InsufficientCredits:
        headline, body = _fallback(context)
        source = "fallback_no_credits"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Dashboard message generation failed for %s: %s", user.id, exc)
        headline, body = _fallback(context)
        source = "fallback_error"

    cached.headline = headline[:200]
    cached.body = body
    cached.context = context
    cached.refresh_expiry()
    cached.save()

    return {
        "headline": cached.headline,
        "body": cached.body,
        "cached": False,
        "source": source,
        "generated_at": cached.generated_at,
        "expires_at": cached.expires_at,
    }
