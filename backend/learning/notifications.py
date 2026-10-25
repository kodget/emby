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
  * **Delivery has an outbox.** In-app notices remain available during transport
    outages; due notices are retried and browser push honours opt-in preferences.
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
    NotificationType.EXAM_COUNTDOWN: "academic_enabled",
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
    hour = timezone.localtime(when).hour
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
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
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
    # Serialize the daily budget as well as the dedupe constraint for this account.
    User.objects.select_for_update().get(pk=user.pk)
    prefs = _prefs(user)

    field = PREFERENCE_FIELD.get(type_)
    if field and not getattr(prefs, field, True):
        return None

    if _sent_today(user) >= max(0, prefs.max_per_day):
        logger.debug("Daily notification budget reached for %s", user.id)
        return None

    when = _next_allowed_time(prefs, when or timezone.now())

    # The day is part of the key, so a daily reminder is raised at most once per day.
    key = dedupe_key or f"{type_}:{timezone.localdate()}"

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
        
        # Delivery failures must never roll back an announcement or study action.
        transaction.on_commit(lambda: dispatch_notification(notification.pk))
        return notification
    except IntegrityError:
        # The unique constraint on (user, dedupe_key) did its job.
        return None


def dispatch_notification(notification_id):
    """Retryable outbox: persist first, dispatch only when due, keep failures pending."""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from .tasks import send_push_notification_task
    try:
        with transaction.atomic():
            notification = Notification.objects.select_for_update().filter(
                pk=notification_id, dispatched_at__isnull=True, scheduled_for__lte=timezone.now(),
                status__in=[Notification.Status.SCHEDULED, Notification.Status.DELIVERED],
            ).first()
            if notification is None:
                return
            async_to_sync(get_channel_layer().group_send)(
                f'user_{notification.user_id}_notifications', {
                    'type': 'notification_message', 'message': {
                        'id': str(notification.pk), 'type': notification.type,
                        'title': notification.title, 'body': notification.body,
                        'priority': notification.priority, 'action_url': notification.action_url,
                        'created_at': notification.created_at.isoformat(),
                    },
                })
            send_push_notification_task.delay(str(notification.pk))
            notification.dispatched_at = timezone.now()
            notification.save(update_fields=['dispatched_at'])
    except Exception:
        logger.exception('Notification delivery is pending for %s', notification_id)


def dispatch_due():
    ids = Notification.objects.filter(dispatched_at__isnull=True, scheduled_for__lte=timezone.now(),
        status__in=[Notification.Status.SCHEDULED, Notification.Status.DELIVERED]).values_list('pk', flat=True)[:500]
    for notification_id in list(ids):
        dispatch_notification(notification_id)


def announce_to_class(announcement):
    for user in User.objects.filter(is_active=True, profile__class_group_id=announcement.class_group_id).iterator():
        schedule(user, NotificationType.HEAD_ANNOUNCEMENT, announcement.title,
                 announcement.content, action_url='/class/announcements',
                 dedupe_key=f'announcement:{announcement.pk}:{announcement.updated_at.isoformat()}')


# ---------------------------------------------------------------------------
# The rules — what is actually worth saying
# ---------------------------------------------------------------------------
def build_for_user(user: User) -> list[Notification]:
    """Work out this student's notifications for right now."""
    from curriculum.models import Flashcard, FlashcardProgress, ScheduleItem
    from curriculum.class_access import visible, member_class
    from accounts.models import ExamCountdown
    from django.db.models import Exists, OuterRef, Q

    created: list[Notification] = []
    now = timezone.now()
    today = timezone.localdate(now)

    group = member_class(user)
    if group:
        for exam in ExamCountdown.objects.filter(class_group=group, exam_date__gte=today,
                                                 exam_date__lte=today + timedelta(days=7)):
            days = (exam.exam_date - today).days
            if days not in (0, 1, 3, 7):
                continue
            n = schedule(user, NotificationType.EXAM_COUNTDOWN,
                f'{exam.title}: ' + ('today' if days == 0 else f'in {days} day' + ('s' if days != 1 else '')),
                f"{exam.exam_date:%d %b}" + (f" at {exam.exam_time:%H:%M}" if exam.exam_time else ''),
                action_url='/class/exams', dedupe_key=f'exam:{exam.pk}:{exam.exam_date}:{days}')
            if n:
                created.append(n)

    # --- flashcards actually due -------------------------------------------------
    progress = FlashcardProgress.objects.filter(user=user, flashcard_id=OuterRef('pk'))
    cards = visible(Flashcard, user).annotate(
        reviewed=Exists(progress), due_for_user=Exists(progress.filter(due_date__lte=now)),
    ).filter(Q(reviewed=False) | Q(due_for_user=True))
    due = cards.count()
    if due:
        overdue = FlashcardProgress.objects.filter(
            user=user, flashcard__in=cards, due_date__lte=now - timedelta(days=1)
        ).count()
        card = cards.order_by('?').first()
        n = schedule(
            user,
            NotificationType.FLASHCARDS_DUE,
            f"{due} flashcard{'s' if due != 1 else ''} ready for review",
            f"Quick recall: {card.front[:350]}",
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
    from .analytics_evidence import Evidence
    evidence = Evidence(user, 30, now=now)
    streak = evidence.consistency()['current_streak']
    last = max((timezone.localdate(row['at']) for row in evidence.rows), default=None)
    if streak >= 2 and last and last < today and timezone.localtime(now).hour >= 17:
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
    weakest = next((row for row in evidence.topics(scope='SUB_BLOCK', limit=None)['weakest']
                    if row['attempted'] >= 8 and row['mastery'] < .55), None)
    if weakest:
        iso_year, iso_week, _ = today.isocalendar()
        n = schedule(
            user,
            NotificationType.WEAK_AREA,
            f"{weakest['label']} needs another pass",
            f"You're at {round(weakest['mastery'] * 100)}% there. A focused round would help.",
            action_url="/analytics",
            dedupe_key=f"weak_area:{weakest['id']}:{iso_year}-{iso_week}",
            payload={"area_id": weakest['id']},
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

    Called when the in-app list serves it. Enqueuing browser push alone does not
    establish that a device received the notification.
    """
    if notification.status != Notification.Status.SCHEDULED:
        return
    notification.status = Notification.Status.DELIVERED
    notification.delivered_at = timezone.now()
    notification.save(update_fields=["status", "delivered_at"])
