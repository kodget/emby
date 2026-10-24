"""Class-head transitions share one class-row lock and durable notifications."""
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound

from .models import Profile, ClassGroup, ClassRole
from .email_service import send_transactional_email
from .permissions import has_platform_admin_access


def _locked_profile(user_id):
    try:
        # Lock ordering is always class then profile for review and request paths.
        group_id = Profile.objects.values_list("class_group_id", flat=True).get(user_id=user_id)
        if not group_id:
            raise ValidationError("Join an active class before requesting class-head approval.")
        group = ClassGroup.objects.select_for_update().get(pk=group_id)
        profile = Profile.objects.select_for_update().select_related("user").get(user_id=user_id)
    except (Profile.DoesNotExist, ClassGroup.DoesNotExist):
        raise NotFound("Class head profile not found.") from None
    if profile.class_group_id != group.pk:
        raise ValidationError("Your class changed. Refresh and try again.")
    if profile.class_role != ClassRole.CLASS_HEAD:
        raise ValidationError("Only class-head applicants can request or receive approval.")
    if not group.is_active or not profile.user.is_active:
        raise ValidationError("The account and class must both be active.")
    profile.class_group = group
    return profile, group


def _request_key(profile):
    return f"class-head-request:{profile.pk}:{profile.class_head_request_version}"


@transaction.atomic
def validate_reactivation(user_id, is_active):
    """Admin account activation must not become a fourth approved head."""
    if not is_active or not user_id or User.objects.filter(pk=user_id, is_active=True).exists():
        return
    profile = Profile.objects.filter(user_id=user_id, class_role=ClassRole.CLASS_HEAD,
                                     class_head_verified=True).first()
    if not profile or not profile.class_group_id:
        return
    group = ClassGroup.objects.select_for_update().get(pk=profile.class_group_id)
    active_heads = Profile.objects.filter(class_group=group, class_role=ClassRole.CLASS_HEAD,
                                          class_head_verified=True, user__is_active=True).exclude(pk=profile.pk).count()
    if active_heads >= 3:
        raise ValidationError("This class already has 3 active approved heads. Review membership before reactivation.")


def _notify_admins(profile):
    from learning.models import Notification, NotificationType, NotificationPriority
    now = timezone.now()
    for administrator in User.objects.filter(is_active=True).filter(Q(profile__platform_role='admin') | Q(is_superuser=True)):
        Notification.objects.get_or_create(
            user=administrator, dedupe_key=_request_key(profile),
            defaults={
                "type": NotificationType.ACCOUNT_SECURITY, "priority": NotificationPriority.HIGH,
                "title": "Class-head request awaiting review",
                "body": f"{profile.user.get_full_name() or profile.user.username} requested approval for {profile.class_group}.",
                "action_url": "/admin", "scheduled_for": now,
                "status": Notification.Status.DELIVERED, "delivered_at": now,
                "payload": {"kind": "class_head_request", "user_id": profile.user_id,
                            "profile_id": profile.pk, "state": "pending"},
            },
        )


@transaction.atomic
def request_review(user_id):
    profile, group = _locked_profile(user_id)
    if profile.class_head_verified:
        return profile, False
    is_new = not profile.class_head_verification_requested or profile.class_head_request_version == 0
    if is_new:
        profile.class_head_request_version += 1
        profile.class_head_verification_requested = True
        profile.class_head_rejection_reason = ""
        profile.class_head_reviewed_at = None
        profile.class_head_reviewed_by = None
        profile.save(update_fields=["class_head_request_version", "class_head_verification_requested",
                                   "class_head_rejection_reason", "class_head_reviewed_at",
                                   "class_head_reviewed_by", "updated_at"])
    # Also makes a retry useful if a new administrator has since been appointed.
    _notify_admins(profile)
    return profile, is_new


@transaction.atomic
def review_class_head(*, actor, user_id, approved, rejection_reason=""):
    if not has_platform_admin_access(actor):
        raise PermissionDenied("Admin permission required.")
    if type(approved) is not bool:
        raise ValidationError({"approved": "Provide a JSON boolean (true or false)."})
    if not isinstance(rejection_reason, str) or len(rejection_reason) > 2000:
        raise ValidationError({"rejection_reason": "Provide a reason of at most 2000 characters."})
    reason = rejection_reason.strip()
    if not approved and not reason:
        raise ValidationError({"rejection_reason": "Explain why the request was rejected."})
    profile, group = _locked_profile(user_id)
    if approved and profile.class_head_verified:
        group.class_heads.add(profile.user)
        return profile, False
    if not approved and not profile.class_head_verification_requested and not profile.class_head_verified:
        if profile.class_head_rejection_reason:
            return profile, False
        raise ValidationError("There is no pending class-head request to reject.")
    if approved and not profile.class_head_verification_requested:
        raise ValidationError("The applicant must submit a request before approval.")
    if approved:
        active_heads = Profile.objects.filter(
            class_group=group, class_role=ClassRole.CLASS_HEAD,
            class_head_verified=True, user__is_active=True,
        ).exclude(pk=profile.pk).count()
        if active_heads >= 3:
            raise ValidationError("This class already has the maximum of 3 active approved class heads.")
    profile.class_head_verified = approved
    profile.class_head_verification_requested = False
    profile.class_head_rejection_reason = "" if approved else reason
    profile.class_head_reviewed_at = timezone.now()
    profile.class_head_reviewed_by = actor
    profile.save(update_fields=["class_head_verified", "class_head_verification_requested",
                               "class_head_rejection_reason", "class_head_reviewed_at",
                               "class_head_reviewed_by", "updated_at"])
    if approved:
        group.class_heads.add(profile.user)
    else:
        group.class_heads.remove(profile.user)

    from learning.models import Notification, NotificationType, NotificationPriority
    state = "approved" if approved else "rejected"
    Notification.objects.filter(dedupe_key=_request_key(profile)).update(
        read=True, read_at=timezone.now(),
        payload={"kind": "class_head_request", "user_id": profile.user_id,
                 "profile_id": profile.pk, "state": state, "reviewed_by": actor.pk},
    )
    message = (f"Your class-head request was approved. Your class code is {group.code}."
               if approved else f"Your class-head request was rejected. Reason: {reason}")
    Notification.objects.get_or_create(
        user=profile.user, dedupe_key=f"{_request_key(profile)}:{state}",
        defaults={"type": NotificationType.ACCOUNT_SECURITY, "priority": NotificationPriority.HIGH,
                  "title": f"Class-head request {state}", "body": message,
                  "action_url": "/dashboard" if approved else "/verification-pending",
                  "status": Notification.Status.DELIVERED, "delivered_at": timezone.now(),
                  "payload": {"kind": "class_head_decision", "state": state}},
    )
    transaction.on_commit(lambda: send_transactional_email(
        f"Class-head request {state} - Emby", message, [profile.user.email],
    ))
    return profile, True
