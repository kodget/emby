import json
import logging
from celery import shared_task
from django.conf import settings
from .models import PushSubscription, Notification

logger = logging.getLogger(__name__)


@shared_task
def recover_question_generation_task():
    from .generation_dispatch import recover_generation_jobs
    return recover_generation_jobs()

@shared_task(bind=True, max_retries=5)
def send_push_notification_task(self, notification_id, subscription_ids=None):
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush is not installed. Push notifications will not be sent.")
        return

    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return

    from django.utils import timezone
    if (not notification.user.is_active or notification.status in (
        Notification.Status.CANCELLED, Notification.Status.FAILED,
    ) or notification.scheduled_for > timezone.now()):
        return

    # Check if the user has browser_push_enabled
    prefs = getattr(notification.user, "notification_preference", None)
    from .notifications import PREFERENCE_FIELD
    category = PREFERENCE_FIELD.get(notification.type)
    if not prefs or not prefs.browser_push_enabled or (category and not getattr(prefs, category, True)):
        return

    subscriptions = PushSubscription.objects.filter(user=notification.user, is_active=True)
    if subscription_ids is not None:
        subscriptions = subscriptions.filter(pk__in=subscription_ids)
    if not subscriptions.exists():
        return

    payload = {
        "title": notification.title,
        "body": notification.body,
        "action_url": notification.action_url,
    }

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
    vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "admin@example.com")

    if not vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY is not set. Cannot send push notifications.")
        return

    pending = []
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=vapid_private_key,
                vapid_claims={
                    "sub": f"mailto:{vapid_admin_email}",
                },
            )
        except WebPushException as ex:
            # HTTP error responses can be falsey, including expired subscriptions.
            if ex.response is not None and ex.response.status_code in (404, 410):
                subscription.delete()
            else:
                pending.append(str(subscription.pk))
                logger.warning("Browser push transport failed for subscription %s", subscription.pk)
        except Exception as e:
            pending.append(str(subscription.pk))
            logger.warning("Browser push transport failed (%s)", type(e).__name__)
    if pending:
        # Retry only failed devices, without repeating successful sends in this batch.
        raise self.retry(
            kwargs={'notification_id': str(notification.pk), 'subscription_ids': pending},
            countdown=min(60 * (2 ** self.request.retries), 1800),
            exc=RuntimeError('Browser push delivery is temporarily unavailable.'),
        )

@shared_task
def build_all_notifications_task():
    """Runs the notification engine for all active students."""
    from .notifications import run_for_all
    logger.info("Starting notification sweep...")
    results = run_for_all()
    logger.info("Notification sweep complete: %s", results)


@shared_task
def dispatch_due_notifications_task():
    from .notifications import dispatch_due
    dispatch_due()
