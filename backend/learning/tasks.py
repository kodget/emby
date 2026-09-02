import json
import logging
from celery import shared_task
from django.conf import settings
from .models import PushSubscription, Notification

logger = logging.getLogger(__name__)

@shared_task
def send_push_notification_task(notification_id):
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush is not installed. Push notifications will not be sent.")
        return

    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return

    if not notification.user:
        return

    # Check if the user has browser_push_enabled
    prefs = getattr(notification.user, "notification_preferences", None)
    if prefs and not prefs.browser_push_enabled:
        return

    subscriptions = PushSubscription.objects.filter(user=notification.user)
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
            logger.error("WebPush failed: %s", repr(ex))
            # If the subscription is no longer valid, we can delete it
            if ex.response and ex.response.status_code in (404, 410):
                subscription.delete()
        except Exception as e:
            logger.error("Failed to send push notification: %s", str(e))

@shared_task
def build_all_notifications_task():
    """Runs the notification engine for all active students."""
    from .notifications import run_for_all
    logger.info("Starting notification sweep...")
    results = run_for_all()
    logger.info("Notification sweep complete: %s", results)

