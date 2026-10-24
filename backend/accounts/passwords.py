"""Expiring password links, with serialized consumption and bounded resends."""
import hashlib
import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .email_service import account_email_link, send_transactional_email, _token_state
from .models import Profile

SALT = "accounts.password-reset.v1"
RESET_MESSAGE = (
    "If an eligible account matches this email, we'll attempt to send a reset link. "
    "Check your inbox and spam folder. You can try again after one minute."
)


def request_password_reset(email):
    # Historical duplicate email addresses require account reconciliation;
    # never arbitrarily choose which account gets a password reset.
    users = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
    if len(users) != 1:
        return
    user = users[0]
    profile = Profile.objects.filter(user=user).first()
    if not profile:
        return
    now = time.time()
    cooldown = max(1, int(getattr(settings, "PASSWORD_RESET_RESEND_SECONDS", 60)))
    try:
        version, issued, _ = profile.password_reset_token.split(":", 2)
        if version == "v1" and now < int(issued) + cooldown:
            return
    except (TypeError, ValueError):
        pass
    lifetime = max(1, int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600)))
    token = signing.dumps({
        "profile": profile.pk, "email": user.email,
        "password_state": user.get_session_auth_hash(), "nonce": secrets.token_urlsafe(24),
    }, salt=SALT)
    link = account_email_link("/reset-password", token)
    if not link:
        return
    reserved = Profile.objects.filter(pk=profile.pk, password_reset_token=profile.password_reset_token).update(
        password_reset_token=_token_state(token, int(now)),
        password_reset_token_expires=timezone.now() + timedelta(seconds=lifetime),
        updated_at=timezone.now(),
    )
    if reserved:
        send_transactional_email(
            "Password Reset - Emby",
            f"Reset your password: {link}\n\nThis single-use link expires in {lifetime // 60} minutes. "
            "Use only the newest link. If you did not request a reset, you can ignore this email.",
            [user.email],
        )


@transaction.atomic
def reset_password_with_token(token, new_password):
    invalid = ValidationError({"error": "Invalid, expired or already-used reset link. Request a new one."})
    if not isinstance(token, str) or not token or len(token) > 2048:
        raise invalid
    if not isinstance(new_password, str) or not new_password:
        raise ValidationError({"error": "A new password is required."})
    try:
        data = signing.loads(token, salt=SALT, max_age=max(1, int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600))))
        if not isinstance(data, dict) or type(data.get("profile")) is not int:
            raise invalid
        profile = Profile.objects.select_for_update().select_related("user").get(pk=data["profile"])
        user = profile.user
        _, _, digest = profile.password_reset_token.split(":", 2)
        if (not user.is_active or user.email != data.get("email")
                or not secrets.compare_digest(user.get_session_auth_hash(), str(data.get("password_state", "")))
                or not profile.password_reset_token_expires
                or profile.password_reset_token_expires <= timezone.now()
                or not secrets.compare_digest(digest, hashlib.sha256(token.encode()).hexdigest())):
            raise invalid
    except (signing.BadSignature, Profile.DoesNotExist, ValueError, TypeError):
        raise invalid from None
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"error": " ".join(exc.messages)}) from None
    user.set_password(new_password)
    user.save(update_fields=["password"])
    profile.password_reset_token = ""
    profile.password_reset_token_expires = None
    profile.save(update_fields=["password_reset_token", "password_reset_token_expires", "updated_at"])

