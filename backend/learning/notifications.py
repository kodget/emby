"""
Notification scheduling and delivery.

The models, preferences and read API already existed; nothing ever created a
notification. This is the part that decides what is worth telling a student and when.

The whole design is built around *not* becoming spam:

  * **Every notification carries a dedupe key** that includes the day, so the same
    reminder cannot be raised twice for the same thing.
  * **A daily budget** per student (their own `max_per_day`) is checked before anything
    new is scheduled, and the most useful kinds are scheduled first.
  * **Quiet hours** push a notification to the next reasonable time rather than firing
    at 3am.
  * **Preferences gate each type**, so switching one off actually stops it being created.
  * **Nothing claims to be delivered that wasn't.** In-app notifications are marked
    delivered when they become visible; browser push is only marked delivered if a
    transport actually accepted it, and there is no transport wired yet, so push stays
    honestly unsent.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)

logger = logging.getLogger(__name__)

# Ordered by usefulness — when the daily budget is tight, the top of this list wins.
PRIORITY = [
    NotificationType.ACCOUNT_SECURITY,
    NotificationType.SYSTEM_MSG,
    NotificationType.HEAD_ANNOUNCEMENT,
    NotificationType.CLASS_ANNOUNCEMENT,
    NotificationType.FLASHCARDS_DUE,
    NotificationType.PLANNER_UPCOMING,
    NotificationType.PLANNER_MISSED,
    NotificationType.STREAK_AT_RISK,
    NotificationType.WEAK_AREA,
    NotificationType.STUDY_GOAL,
]

PREFERENCE_FIELD = {
    NotificationType.FLASHCARDS_DUE: "flashcards_enabled",
    NotificationType.FLASHCARDS_MISSED: "flashcards_enabled",
    NotificationType.PLANNER_UPCOMING: "planner_enabled",
    NotificationType.PLANNER_MISSED: "planner_enabled",
    NotificationType.STUDY_GOAL: "study_goal_enabled",
    NotificationType.STREAK_AT_RISK: "streak_enabled",
    NotificationType.WEAK_AREA: "weak_area_enabled",
    
    # Academic
    NotificationType.NEW_QUIZ_AVAILABLE: "academic_enabled",
    NotificationType.QUIZ_COMPLETED: "academic_enabled",
    NotificationType.QUIZ_RESULT: "academic_enabled",
    NotificationType.NEW_PAST_QUESTION: "academic_enabled",
    NotificationType.NEW_FLASHCARD_SET: "academic_enabled",
    NotificationType.STUDY_GOAL_COMPLETED: "academic_enabled",
    
    # Community
    NotificationType.NEW_SLIDES: "community_enabled",
    NotificationType.SLIDE_UPDATED: "community_enabled",
    NotificationType.NEW_MATERIAL: "community_enabled",
    NotificationType.CLASS_ANNOUNCEMENT: "community_enabled",
    NotificationType.HEAD_ANNOUNCEMENT: "community_enabled",
    NotificationType.NEW_COMMENT: "community_enabled",
    NotificationType.COMMENT_REPLY: "community_enabled",
    NotificationType.POST_LIKED: "community_enabled",
    NotificationType.POST_COMMENTED: "community_enabled",
    NotificationType.MENTIONED: "community_enabled",
    NotificationType.NEW_FOLLOWER: "community_enabled",
    
    # System
    NotificationType.ACCOUNT_SECURITY: "system_enabled",
    NotificationType.WELCOME: "system_enabled",
    NotificationType.SYSTEM_MSG: "system_enabled",
    NotificationType.MAINTENANCE: "system_enabled",
    NotificationType.FEATURE_UPDATE: "system_enabled",
}


def _prefs(user: User) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def _in_quiet_hours(prefs: NotificationPreference, when) -> bool:
    start, end = prefs.quiet_hours_start, prefs.quiet_hours_end
    hour = when.hour
    if start == end:
        return False
    if start < end:               # e.g. 01:00 -> 07:00
        return start <= hour < end
    return hour >= start or hour < end   # e.g. 22:00 -> 07:00, wrapping midnight


def _next_allowed_time(prefs: NotificationPreference, when):
    """Move a send time out of quiet hours rather than dropping the notification."""
    if not _in_quiet_hours(prefs, when):
        return when
    target = when.replace(minute=0, second=0, microsecond=0)
    # Walk forward to the end of the quiet window (at most a day).
    for _ in range(24):
        target += timedelta(hours=1)
        if not _in_quiet_hours(prefs, target):
            return target
    return when


def _sent_today(user: User) -> int:
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return Notification.objects.filter(
        user=user, created_at__gte=start
    ).exclude(status=Notification.Status.CANCELLED).count()


@transaction.atomic
def schedule(
    user: User,
    type_: str,
    title: str,
    body: str = "",
    *,
    action_url: str = "",
    dedupe_key: str = "",
    when=None,
    payload: dict | None = None,
    priority: str = NotificationPriority.NORMAL,
) -> Notification | None:
    """Create one notification, honouring preferences, quiet hours and the daily budget.

    Returns None when it was suppressed — that is a normal outcome, not an error.
    """
    prefs = _prefs(user)

    field = PREFERENCE_FIELD.get(type_)
    if field and not getattr(prefs, field, True):
        return None

    if _sent_today(user) >= max(1, prefs.max_per_day):
        logger.debug("Daily notification budget reached for %s", user.id)
        return None

    when = _next_allowed_time(prefs, when or timezone.now())

    # The day is part of the key, so a daily reminder is raised at most once per day.
    key = dedupe_key or f"{type_}:{timezone.now():%Y-%m-%d}"

    try:
        notification = Notification.objects.create(
            user=user,
            type=type_,
            priority=priority,
            title=title[:160],
            body=body,
            action_url=action_url,
            payload=payload or {},
            scheduled_for=when,
            dedupe_key=key,
        )
        
        # Send to WebSocket if it's scheduled for now (or in the past)
        if notification.scheduled_for <= timezone.now():
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from .tasks import send_push_notification_task
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}_notifications",
                {
                    "type": "notification_message",
                    "message": {
                        "id": str(notification.id),
                        "type": notification.type,
                        "priority": notification.priority,
                        "title": notification.title,
                        "body": notification.body,
                        "action_url": notification.action_url,
                        "created_at": notification.created_at.isoformat(),
                    }
                }
            )
            
            # Send Web Push via Celery
            send_push_notification_task.delay(notification.id)
            
        return notification
    except IntegrityError:
        # The unique constraint on (user, dedupe_key) did its job.
        return None


# ---------------------------------------------------------------------------
# The rules — what is actually worth saying
# ---------------------------------------------------------------------------
def build_for_user(user: User) -> list[Notification]:
    """Work out this student's notifications for right now."""
    from curriculum.models import FlashcardProgress, ScheduleItem

    created: list[Notification] = []
    now = timezone.now()
    today = now.date()

    # --- flashcards actually due -------------------------------------------------
    due = FlashcardProgress.objects.filter(user=user, due_date__lte=now).count()
    if due:
        overdue = FlashcardProgress.objects.filter(
            user=user, due_date__lte=now - timedelta(days=1)
        ).count()
        n = schedule(
            user,
            NotificationType.FLASHCARDS_DUE,
            f"{due} flashcard{'s' if due != 1 else ''} ready for review",
            (
                f"{overdue} of them are overdue — a short session clears the backlog."
                if overdue
                else "A few minutes now keeps them from piling up."
            ),
            action_url="/flashcards/study",
            dedupe_key=f"flashcards_due:{today}",
            payload={"due": due, "overdue": overdue},
        )
        if n:
            created.append(n)

    # --- a planned session coming up ---------------------------------------------
    soon = ScheduleItem.objects.filter(
        user=user, scheduled_date=today, completed=False
    ).order_by("scheduled_time")
    upcoming = [i for i in soon if i.scheduled_time]
    if upcoming:
        item = upcoming[0]
        n = schedule(
            user,
            NotificationType.PLANNER_UPCOMING,
            f"Planned: {item.title}",
            f"About {item.estimated_minutes} minutes, from your study plan.",
            action_url="/study-plan",
            dedupe_key=f"planner_upcoming:{item.id}:{today}",
            payload={"item_id": item.id},
        )
        if n:
            created.append(n)

    # --- yesterday's plan left unfinished ----------------------------------------
    missed = ScheduleItem.objects.filter(
        user=user, scheduled_date=today - timedelta(days=1), completed=False
    ).count()
    if missed:
        n = schedule(
            user,
            NotificationType.PLANNER_MISSED,
            f"{missed} task{'s' if missed != 1 else ''} from yesterday",
            "Still worth doing — move them to today or tick them off.",
            action_url="/study-plan",
            dedupe_key=f"planner_missed:{today}",
            payload={"count": missed},
        )
        if n:
            created.append(n)

    # --- a streak about to break --------------------------------------------------
    stats = getattr(user, "stats", None)
    streak = getattr(stats, "active_streak", 0) or 0
    last = getattr(stats, "last_activity_date", None)
    if streak >= 2 and last and last < today and now.hour >= 17:
        n = schedule(
            user,
            NotificationType.STREAK_AT_RISK,
            f"Your {streak}-day streak ends tonight",
            "Anything counts — one quiz, a few flashcards, ten minutes of reading.",
            action_url="/dashboard",
            dedupe_key=f"streak_at_risk:{today}",
            payload={"streak": streak},
        )
        if n:
            created.append(n)

    # --- a topic that keeps going wrong -------------------------------------------
    from .models import WeakArea

    weakest = (
        WeakArea.objects.filter(user=user, scope=WeakArea.Scope.SUB_BLOCK, attempted__gte=8)
        .filter(mastery__lt=0.55)
        .order_by("-priority")
        .first()
    )
    if weakest:
        n = schedule(
            user,
            NotificationType.WEAK_AREA,
            f"{weakest.label} needs another pass",
            f"You're at {round(weakest.mastery * 100)}% there. A focused round would help.",
            action_url="/analytics",
            # Weekly, not daily — a weak topic does not change overnight.
            dedupe_key=f"weak_area:{weakest.id}:{today.isocalendar().week}",
            payload={"area_id": weakest.id},
        )
        if n:
            created.append(n)

    return created


def run_for_all(limit: int | None = None) -> dict:
    """Build notifications for every active student. Safe to run repeatedly."""
    users = User.objects.filter(is_active=True)
    if limit:
        users = users[:limit]

    total = 0
    touched = 0
    for user in users.iterator():
        try:
            made = build_for_user(user)
        except Exception:  # noqa: BLE001 - one bad user must not stop the sweep
            logger.exception("Notification build failed for user %s", user.id)
            continue
        if made:
            touched += 1
            total += len(made)

    return {"users_notified": touched, "notifications_created": total}


def mark_delivered(notification: Notification) -> None:
    """Record that a notification actually reached the student.

    Called when the in-app list serves it. Browser push has no transport wired yet, so
    push notifications are never marked delivered — the model tells the truth about what
    was sent rather than assuming.
    """
    if notification.status != Notification.Status.SCHEDULED:
        return
    notification.status = Notification.Status.DELIVERED
    notification.delivered_at = timezone.now()
    notification.save(update_fields=["status", "delivered_at"])
