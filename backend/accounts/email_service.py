"""Observable email delivery and expiring, single-use verification links.

Only the digest and issue time are stored in the existing profile token field.
Compare-and-swap updates enforce resend limits and consumption across workers.
Legacy unbounded tokens must be replaced through the authenticated resend route.
"""

from dataclasses import dataclass
import hashlib
import logging
import math
import secrets
import time
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone

from .models import Profile


logger = logging.getLogger(__name__)
VERIFICATION_SALT = "accounts.email-verification.v1"


@dataclass(frozen=True)
class EmailDelivery:
    status: str
    message: str

    @property
    def sent(self):
        return self.status == "sent"


@dataclass(frozen=True)
class VerificationDelivery(EmailDelivery):
    retry_after: int = 0


def send_transactional_email(subject, body, recipients):
    """Return provider acceptance, never claim console output reached an inbox."""
    recipients = list(dict.fromkeys(address for address in recipients if address))
    backend = settings.EMAIL_BACKEND
    non_delivery_backends = {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    }
    if not settings.DEBUG:
        non_delivery_backends.add("django.core.mail.backends.locmem.EmailBackend")
    if not recipients or backend in non_delivery_backends:
        logger.warning("Email delivery unavailable (recipient_count=%s)", len(recipients))
        return EmailDelivery("unavailable", "Email delivery is temporarily unavailable.")
    try:
        accepted = send_mail(
            subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False,
        )
        if accepted != 1:
            logger.warning("Email provider did not accept the message")
            return EmailDelivery("failed", "The email could not be sent. Please try again later.")
    except Exception as exc:
        # Provider exceptions can contain credentials, recipient addresses or links.
        logger.warning("Email delivery failed (%s)", type(exc).__name__)
        return EmailDelivery("failed", "The email could not be sent. Please try again later.")
    return EmailDelivery("sent", "Email sent. Please check your inbox and spam folder.")


def _cooldown_remaining(stored, now):
    try:
        version, issued_at, digest = stored.split(":", 2)
        if version != "v1" or len(digest) != 64:
            return 0
        cooldown = max(1, int(getattr(settings, "EMAIL_VERIFICATION_RESEND_SECONDS", 60)))
        return max(0, math.ceil(int(issued_at) + cooldown - now))
    except (ValueError, TypeError, AttributeError):
        return 0


def _token_state(token, issued_at):
    return f"v1:{issued_at}:{hashlib.sha256(token.encode()).hexdigest()}"


def account_email_link(path, token):
    """Validate the configured frontend origin before sending an account link."""
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    try:
        parsed_url = urlsplit(frontend_url)
        if (parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc
                or parsed_url.query or parsed_url.fragment or parsed_url.username or parsed_url.password
                or (not settings.DEBUG and parsed_url.scheme != "https")):
            return None
    except ValueError:
        return None
    return f"{frontend_url}{path}?{urlencode({'token': token})}"


def request_email_verification(user):
    """Reserve a delivery attempt without holding a DB lock during SMTP I/O."""
    profile = Profile.objects.select_related("user").get(user_id=user.pk)
    if profile.email_verified:
        return VerificationDelivery("already_verified", "Email already verified.")

    now = time.time()
    retry_after = _cooldown_remaining(profile.email_verification_token, now)
    if retry_after:
        return VerificationDelivery(
            "throttled", f"Please wait {retry_after} seconds before requesting another email.", retry_after,
        )

    if not account_email_link("/verify-email", "validation"):
        logger.error("Email verification requires a valid FRONTEND_URL")
        return VerificationDelivery("unavailable", "Email delivery is temporarily unavailable.")

    token = signing.dumps(
        {"profile": profile.pk, "email": profile.user.email, "nonce": secrets.token_urlsafe(24)},
        salt=VERIFICATION_SALT,
    )
    stored = _token_state(token, int(now))
    reserved = Profile.objects.filter(
        pk=profile.pk, email_verified=False,
        email_verification_token=profile.email_verification_token,
    ).update(email_verification_token=stored, updated_at=timezone.now())
    cooldown = max(1, int(getattr(settings, "EMAIL_VERIFICATION_RESEND_SECONDS", 60)))
    if not reserved:
        profile.refresh_from_db(fields=["email_verified", "email_verification_token"])
        if profile.email_verified:
            return VerificationDelivery("already_verified", "Email already verified.")
        retry_after = _cooldown_remaining(profile.email_verification_token, time.time()) or cooldown
        return VerificationDelivery(
            "throttled", f"Please wait {retry_after} seconds before requesting another email.", retry_after,
        )

    verification_link = account_email_link("/verify-email", token)
    expiry_minutes = math.ceil(max(1, int(getattr(settings, "EMAIL_VERIFICATION_MAX_AGE_SECONDS", 86400))) / 60)
    delivery = send_transactional_email(
        "Verify your email - Emby",
        f"Click this link to verify your email: {verification_link}\n\n"
        f"This single-use link expires in {expiry_minutes} minutes. "
        "If you request another email, use the newest link.\n\n"
        "Email verification does not approve a class-head request.",
        [profile.user.email],
    )
    return VerificationDelivery(delivery.status, delivery.message, cooldown)


def consume_verification_token(token):
    """Consume a valid link once, bound to the account's current email address."""
    if not isinstance(token, str) or not token or len(token) > 2048:
        return False
    try:
        payload = signing.loads(
            token, salt=VERIFICATION_SALT,
            max_age=max(1, int(getattr(settings, "EMAIL_VERIFICATION_MAX_AGE_SECONDS", 86400))),
        )
        if (not isinstance(payload, dict) or type(payload.get("profile")) is not int
                or not isinstance(payload.get("email"), str) or not payload.get("nonce")):
            return False
        profile = Profile.objects.only("email_verification_token").get(
            pk=payload["profile"], user__email=payload["email"], email_verified=False,
        )
        stored = profile.email_verification_token
        version, issued_at, digest = stored.split(":", 2)
        if version != "v1" or not secrets.compare_digest(digest, hashlib.sha256(token.encode()).hexdigest()):
            return False
        return bool(Profile.objects.filter(
            pk=profile.pk, user__email=payload["email"], email_verified=False,
            email_verification_token=stored,
        ).update(email_verified=True, email_verification_token="", updated_at=timezone.now()))
    except (signing.BadSignature, Profile.DoesNotExist, ValueError, TypeError, KeyError):
        return False
