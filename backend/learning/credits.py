"""
AI credit accounting.

The backend is the only authority on how many credits a student has. Every AI action
goes through `spend()`, which:

  1. locks the student's account row,
  2. rolls the monthly period over if it has expired,
  3. re-grants the correct allowance for the student's current tier,
  4. refuses the action if the balance is insufficient,
  5. writes a RESERVED usage row and increments `used` inside the same transaction.

Because step 1 takes `SELECT ... FOR UPDATE`, two AI requests racing on the same account
serialise, so a student with one credit left cannot spend it twice. The reservation is
settled afterwards: `charge()` confirms it, `refund()` gives the credit back when the
provider failed before doing any billable work.

Typical use:

    with spend(user, AIAction.GENERATE_MCQ, resource_id=slide.id) as usage:
        result = call_the_model()
        usage.model_used = llm.primary_model()

The context manager charges on a clean exit and refunds on an exception, so no caller
has to remember to settle.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Iterator

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import AIAction, AICreditAccount, AIUsageEvent

logger = logging.getLogger(__name__)


class InsufficientCredits(Exception):
    """Raised when a student cannot afford an AI action."""

    def __init__(self, required: int, remaining: int):
        self.required = required
        self.remaining = remaining
        super().__init__(
            f"This needs {required} AI credit(s) but only {remaining} remain."
        )


# What each action costs. Generation is dearer than chat because it produces a whole
# question set from a long document; grading and dashboard copy are cheap.
COSTS: dict[str, int] = {
    AIAction.CHAT: 1,
    AIAction.EXPLAIN: 1,
    AIAction.RESOURCES: 1,
    AIAction.DASHBOARD_MESSAGE: 1,
    AIAction.GRADE_THEORY: 2,
    AIAction.GENERATE_FLASHCARDS: 3,
    AIAction.STUDY_PLAN: 3,
    AIAction.BATTLE_QUESTIONS: 4,
    AIAction.GENERATE_THEORY: 5,
    AIAction.GENERATE_MCQ: 8,
}
DEFAULT_COST = 1


def cost_of(action: str) -> int:
    return COSTS.get(action, DEFAULT_COST)


def _allowance_for(user: User) -> tuple[int, str]:
    """The monthly credit grant for a user's current entitlement."""
    profile = getattr(user, "profile", None)
    if profile is not None and profile.is_premium:
        return AICreditAccount.PREMIUM_MONTHLY_CREDITS, "premium"
    return AICreditAccount.FREE_MONTHLY_CREDITS, "free"


def get_account(user: User) -> AICreditAccount:
    """Fetch (creating if needed) a student's account, rolling the period if due."""
    account, _ = AICreditAccount.objects.get_or_create(user=user)
    if account.is_expired or account.allocated == 0:
        _roll_period(account, user)
    return account


def _roll_period(account: AICreditAccount, user: User) -> None:
    allowance, tier = _allowance_for(user)
    account.allocated = allowance
    account.used = 0
    account.tier_at_grant = tier
    account.period_started = timezone.now()
    account.save(update_fields=["allocated", "used", "tier_at_grant", "period_started", "updated_at"])


def balance(user: User) -> dict:
    """Everything the frontend needs to render the credit meter."""
    account = get_account(user)
    return {
        "allocated": account.allocated,
        "used": account.used,
        "remaining": account.remaining,
        "tier": account.tier_at_grant,
        "period_started": account.period_started,
        "period_ends": account.period_ends,
    }


@transaction.atomic
def reserve(
    user: User,
    action: str,
    *,
    credits: int | None = None,
    resource_type: str = "",
    resource_id: str = "",
    idempotency_key: str = "",
) -> AIUsageEvent:
    """Atomically check the balance and hold the credits for an action.

    Raises InsufficientCredits without writing anything if the student cannot afford it.
    """
    required = credits if credits is not None else cost_of(action)

    if idempotency_key:
        existing = AIUsageEvent.objects.filter(
            user=user, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return existing

    # Lock the row so concurrent AI requests cannot both pass the check below.
    account = (
        AICreditAccount.objects.select_for_update().filter(user=user).first()
    )
    if account is None:
        AICreditAccount.objects.get_or_create(user=user)
        account = AICreditAccount.objects.select_for_update().get(user=user)

    if account.is_expired or account.allocated == 0:
        _roll_period(account, user)

    if account.remaining < required:
        raise InsufficientCredits(required, account.remaining)

    account.used += required
    account.save(update_fields=["used", "updated_at"])

    return AIUsageEvent.objects.create(
        user=user,
        action=action,
        credits=required,
        status=AIUsageEvent.Status.RESERVED,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def charge(usage: AIUsageEvent, *, model_used: str = "", provider: str = "") -> None:
    """Confirm a reservation: the provider did the work, so the credits are spent."""
    if usage.status != AIUsageEvent.Status.RESERVED:
        return
    usage.status = AIUsageEvent.Status.CHARGED
    usage.settled_at = timezone.now()
    if model_used:
        usage.model_used = model_used
    if provider:
        usage.provider = provider
    usage.save(update_fields=["status", "settled_at", "model_used", "provider"])


@transaction.atomic
def refund(usage: AIUsageEvent, *, error: str = "") -> None:
    """Return reserved credits after a failure that produced nothing billable."""
    if usage.status != AIUsageEvent.Status.RESERVED:
        return

    account = AICreditAccount.objects.select_for_update().filter(user=usage.user).first()
    if account is not None:
        account.used = max(0, account.used - usage.credits)
        account.save(update_fields=["used", "updated_at"])

    usage.status = AIUsageEvent.Status.FAILED if error else AIUsageEvent.Status.REFUNDED
    usage.error = error[:2000]
    usage.settled_at = timezone.now()
    usage.save(update_fields=["status", "error", "settled_at"])


@contextlib.contextmanager
def spend(
    user: User,
    action: str,
    *,
    credits: int | None = None,
    resource_type: str = "",
    resource_id: str = "",
    idempotency_key: str = "",
) -> Iterator[AIUsageEvent]:
    """Reserve credits, run the block, then charge on success or refund on failure.

    Raises InsufficientCredits before the block runs if the student cannot afford it.
    """
    usage = reserve(
        user,
        action,
        credits=credits,
        resource_type=resource_type,
        resource_id=resource_id,
        idempotency_key=idempotency_key,
    )
    # An idempotent replay of an already-settled action must not run the body again.
    if usage.status != AIUsageEvent.Status.RESERVED:
        yield usage
        return

    try:
        yield usage
    except Exception as exc:  # noqa: BLE001 - refund then re-raise
        refund(usage, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        charge(usage, model_used=usage.model_used, provider=usage.provider)


def history(user: User, limit: int = 50) -> list[dict]:
    """Recent AI spending, for the account screen."""
    rows = AIUsageEvent.objects.filter(user=user).order_by("-created_at")[:limit]
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "action_label": row.get_action_display(),
            "credits": row.credits,
            "status": row.status,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]
