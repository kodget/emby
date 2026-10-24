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

from django.contrib.auth.models import User
from django.utils import timezone

from curriculum.class_access import content_admin, member_class, visible
from . import credits
from .analytics_evidence import Evidence
from .models import AIAction, DashboardMessage

logger = logging.getLogger(__name__)


def _class_scope(user: User) -> dict:
    group = member_class(user)
    return {"version": 2, "class_group": group.pk if group else None, "admin": content_admin(user)}


def cards_due(user: User) -> int:
    from curriculum.models import Flashcard, FlashcardProgress
    return FlashcardProgress.objects.filter(
        user=user, flashcard__in=visible(Flashcard, user).filter(user=user),
        due_date__lte=timezone.now(),
    ).count()


def build_context(user: User) -> dict:
    """The real figures the greeting is written from."""
    evidence = Evidence(user, 7)
    overview = evidence.overview()
    consistency = evidence.consistency()
    weakest = next(iter(evidence.topics()['weakest']), None)
    last_day = max((timezone.localdate(row['at']) for row in evidence.rows), default=None)

    return {
        "class_scope": _class_scope(user),
        "name": (user.first_name or user.username or "").strip(),
        "streak": consistency['current_streak'],
        "sessions_this_week": overview['sessions'],
        "questions_this_week": overview['attempted'],
        "accuracy_this_week": overview['accuracy'],
        "cards_due": cards_due(user),
        "weakest_topic": weakest['label'] if weakest else None,
        "weakest_area_id": weakest['id'] if weakest else None,
        "days_since_last_study": (evidence.today - last_day).days if last_day else None,
        "credits": credits.balance(user),
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
        f"{ {key: value for key, value in context.items() if key != 'credits'} }\n\n"
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

    context = build_context(user)
    cached_context = cached.context if isinstance(cached.context, dict) else {}
    if cached.is_valid and not force:
        # Refresh changed facts without a new provider call/credit charge during
        # the existing six-hour window. Credits can change on greeting generation
        # itself and are not used in the message prompt.
        stable = lambda value: {key: item for key, item in value.items() if key != 'credits'}
        changed = stable(cached_context) != stable(context)
        if changed:
            cached.headline, cached.body = _fallback(context)
            cached.context = context
            cached.save(update_fields=['headline', 'body', 'context'])
        return {
            "headline": cached.headline,
            "body": cached.body,
            "cached": not changed,
            "source": 'fallback_updated' if changed else 'cache',
            "generated_at": cached.generated_at,
            "expires_at": cached.expires_at,
        }

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
