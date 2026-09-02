"""
Cross-cutting learning infrastructure.

Emby already models *content* (slides, questions, flashcards, battles) inside the
`curriculum` app. What it lacked was a single place to answer questions that span all of
those features:

    "How many AI credits does this student have left?"
    "What is this student actually weak at?"
    "Has this student seen this question before?"
    "How much XP has this action already earned today?"
    "What should we remind this student about, and when?"

Those questions were previously either unanswerable or recomputed differently in each
feature. This app holds the shared answer, and every feature writes into it rather than
keeping its own private tally.

The organising idea is `LearningEvent`: one row per meaningful thing a student did.
Analytics, XP, weak-area detection and study-time tracking are all derived from that
single stream, so they can never disagree with each other.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------
class ActivityType(models.TextChoices):
    """Every kind of learning activity Emby can record."""

    RESOURCE_STUDIED = "RESOURCE_STUDIED", "Resource studied"
    STUDY_SESSION_COMPLETED = "STUDY_SESSION_COMPLETED", "Study session completed"
    QUIZ_COMPLETED = "QUIZ_COMPLETED", "Quiz completed"
    QUESTION_ANSWERED = "QUESTION_ANSWERED", "Question answered"
    FLASHCARD_REVIEWED = "FLASHCARD_REVIEWED", "Flashcard reviewed"
    STEEPLECHASE_COMPLETED = "STEEPLECHASE_COMPLETED", "Steeplechase completed"
    HISTOLOGY_COMPLETED = "HISTOLOGY_COMPLETED", "Histology completed"
    BRAIN_BATTLE_COMPLETED = "BRAIN_BATTLE_COMPLETED", "Brain battle completed"
    PLANNER_TASK_COMPLETED = "PLANNER_TASK_COMPLETED", "Planner task completed"


class PracticeMode(models.TextChoices):
    """Image-based practice modes that share session, timer and scoring logic."""

    STEEPLECHASE = "STEEPLECHASE", "Steeplechase"
    HISTOLOGY = "HISTOLOGY", "Histology"


# ---------------------------------------------------------------------------
# AI CREDITS
# ---------------------------------------------------------------------------
class AICreditAccount(models.Model):
    """A student's AI allowance for the current billing period.

    The backend is the only source of truth. The frontend displays `remaining` but can
    never set it: every spend goes through `learning.credits.spend()`, which takes a row
    lock so two concurrent AI requests cannot both pass the same balance check.
    """

    FREE_MONTHLY_CREDITS = 60
    PREMIUM_MONTHLY_CREDITS = 1500

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="ai_credits")

    allocated = models.IntegerField(default=FREE_MONTHLY_CREDITS)
    used = models.IntegerField(default=0)

    # Credits reset monthly; this marks the start of the window `allocated` applies to.
    period_started = models.DateTimeField(default=timezone.now)
    tier_at_grant = models.CharField(max_length=20, default="free")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI credit account"

    def __str__(self) -> str:
        return f"{self.user.username}: {self.remaining}/{self.allocated} credits"

    @property
    def remaining(self) -> int:
        return max(0, self.allocated - self.used)

    @property
    def period_ends(self):
        return self.period_started + timedelta(days=30)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.period_ends


class AIAction(models.TextChoices):
    """AI actions and, implicitly, what they cost. See credits.COSTS."""

    CHAT = "CHAT", "Tutor chat message"
    EXPLAIN = "EXPLAIN", "Explain selection"
    GENERATE_MCQ = "GENERATE_MCQ", "Generate MCQs"
    GENERATE_THEORY = "GENERATE_THEORY", "Generate theory questions"
    GENERATE_FLASHCARDS = "GENERATE_FLASHCARDS", "Generate flashcards"
    GRADE_THEORY = "GRADE_THEORY", "Grade a theory answer"
    RESOURCES = "RESOURCES", "Suggest resources"
    STUDY_PLAN = "STUDY_PLAN", "Build a study plan"
    DASHBOARD_MESSAGE = "DASHBOARD_MESSAGE", "Dashboard message"
    BATTLE_QUESTIONS = "BATTLE_QUESTIONS", "Brain battle questions"


class AIUsageEvent(models.Model):
    """An auditable record of every AI action, successful or not.

    Rows are written *before* the provider call (status=RESERVED) and settled afterwards.
    A failed call is refunded and marked FAILED, so students are never charged for an
    error, while the reservation still prevents concurrent requests from overspending.
    """

    class Status(models.TextChoices):
        RESERVED = "RESERVED", "Reserved"
        CHARGED = "CHARGED", "Charged"
        REFUNDED = "REFUNDED", "Refunded"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_usage")

    action = models.CharField(max_length=32, choices=AIAction.choices)
    credits = models.IntegerField(default=1)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESERVED)

    # Free-form pointer to whatever the action was about (slide id, attempt id, ...).
    resource_type = models.CharField(max_length=40, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)

    # Set by callers that must not double-charge on retry.
    idempotency_key = models.CharField(max_length=100, blank=True, db_index=True)

    model_used = models.CharField(max_length=80, blank=True)
    provider = models.CharField(max_length=40, blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "action"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_ai_usage_idempotency_key",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} {self.action} -{self.credits} ({self.status})"


# ---------------------------------------------------------------------------
# UNIFIED LEARNING ACTIVITY STREAM
# ---------------------------------------------------------------------------
class LearningEvent(models.Model):
    """One meaningful learning action.

    Analytics, XP, streaks, weak areas and study time all read from this table, which is
    why they stay consistent. Features append here; nothing recomputes from scratch.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="learning_events")

    activity = models.CharField(max_length=40, choices=ActivityType.choices)

    # Curriculum context, denormalised so analytics never needs a join-heavy walk.
    subject = models.ForeignKey(
        "curriculum.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    block = models.ForeignKey(
        "curriculum.Block", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sub_block = models.ForeignKey(
        "curriculum.SubBlock", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    topic = models.ForeignKey(
        "curriculum.Topic", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # What happened, in whatever terms the activity uses.
    correct_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    accuracy = models.FloatField(null=True, blank=True)  # 0..1
    duration_seconds = models.IntegerField(default=0)

    # Pointer back to the concrete record (quiz attempt, battle, session, ...).
    resource_type = models.CharField(max_length=40, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "-occurred_at"]),
            models.Index(fields=["user", "activity", "-occurred_at"]),
            models.Index(fields=["user", "subject"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} {self.activity} @ {self.occurred_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# XP
# ---------------------------------------------------------------------------
class XPAward(models.Model):
    """A single XP grant, always traceable to the event that earned it.

    Keeping a ledger (rather than only incrementing UserStats.points) is what makes XP
    auditable and farm-resistant: daily caps and diminishing returns are enforced by
    querying what this user has already earned today for the same reason.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="xp_awards")
    event = models.ForeignKey(
        LearningEvent, on_delete=models.CASCADE, related_name="xp_awards", null=True, blank=True
    )

    reason = models.CharField(max_length=40, choices=ActivityType.choices)
    amount = models.IntegerField()

    # What the uncapped award would have been, for transparency in the UI.
    base_amount = models.IntegerField(default=0)
    multiplier = models.FloatField(default=1.0)
    capped = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)

    awarded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-awarded_at"]
        indexes = [
            models.Index(fields=["user", "-awarded_at"]),
            models.Index(fields=["user", "reason", "-awarded_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} +{self.amount} XP ({self.reason})"


# ---------------------------------------------------------------------------
# QUESTION EXPOSURE  (drives non-repetitive question selection)
# ---------------------------------------------------------------------------
class QuestionExposure(models.Model):
    """Per-student history for a single question.

    Question selection reads this to prefer unseen questions, then rarely-seen ones, and
    to resurface questions the student actually got wrong.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="question_exposure")
    question = models.ForeignKey(
        "curriculum.QuizQuestion", on_delete=models.CASCADE, related_name="exposure"
    )

    times_seen = models.IntegerField(default=0)
    times_answered = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)
    times_incorrect = models.IntegerField(default=0)

    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_correct_at = models.DateTimeField(null=True, blank=True)
    last_incorrect_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "question"]
        indexes = [
            models.Index(fields=["user", "last_seen_at"]),
            models.Index(fields=["user", "times_seen"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} × {self.question_id} (seen {self.times_seen})"

    @property
    def accuracy(self) -> float | None:
        if not self.times_answered:
            return None
        return self.times_correct / self.times_answered

    @property
    def is_weak(self) -> bool:
        """True when the student has answered this and gets it wrong more often than not."""
        acc = self.accuracy
        return acc is not None and acc < 0.5


# ---------------------------------------------------------------------------
# WEAK AREAS
# ---------------------------------------------------------------------------
class WeakArea(models.Model):
    """A rolling mastery estimate for one curriculum node, for one student.

    Updated incrementally from LearningEvent, so reading, quizzes, steeplechase,
    histology, flashcards and battles all feed the same picture of what a student
    struggles with.
    """

    class Scope(models.TextChoices):
        SUBJECT = "SUBJECT", "Subject"
        BLOCK = "BLOCK", "Block"
        SUB_BLOCK = "SUB_BLOCK", "Sub-block"
        TOPIC = "TOPIC", "Topic"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="weak_areas")

    scope = models.CharField(max_length=12, choices=Scope.choices)
    # Exactly one of these is set, matching `scope`.
    subject = models.ForeignKey(
        "curriculum.Subject", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    block = models.ForeignKey(
        "curriculum.Block", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    sub_block = models.ForeignKey(
        "curriculum.SubBlock", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    topic = models.ForeignKey(
        "curriculum.Topic", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )

    # Denormalised label so the UI can render history even if a node is later removed.
    label = models.CharField(max_length=200, blank=True)

    attempted = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)

    # 0..1 exponential moving average of accuracy — recent performance counts for more.
    mastery = models.FloatField(default=0.0)
    # Higher means "revise this sooner".
    priority = models.FloatField(default=0.0, db_index=True)

    last_practised_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority"]
        indexes = [
            models.Index(fields=["user", "-priority"]),
            models.Index(fields=["user", "scope"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope", "subject", "block", "sub_block", "topic"],
                name="unique_weak_area_node_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.label or self.scope} ({self.mastery:.0%})"

    @property
    def accuracy(self) -> float | None:
        if not self.attempted:
            return None
        return self.correct / self.attempted


# ---------------------------------------------------------------------------
# IMAGE-SPOT PRACTICE  (shared by Steeplechase and Histology)
# ---------------------------------------------------------------------------
class PracticeSession(models.Model):
    """One timed run through a set of image stations.

    Steeplechase and Histology are the same mechanic over a different station pool, so
    they share this model, its timer rules, its entitlement checks and its analytics
    rather than each growing a parallel implementation.
    """

    STATION_SECONDS = 30

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="practice_sessions")

    mode = models.CharField(max_length=20, choices=PracticeMode.choices)
    # Region / topic filters the student chose, e.g. ["UPPER_LIMB", "THORAX"].
    sections = models.JSONField(default=list, blank=True)

    # Ordered station ids, fixed at creation so refreshes cannot reroll the session.
    station_ids = models.JSONField(default=list)
    seconds_per_station = models.IntegerField(default=STATION_SECONDS)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    total_stations = models.IntegerField(default=0)
    main_correct = models.IntegerField(default=0)
    supporting_correct = models.IntegerField(default=0)
    true_false_correct = models.IntegerField(default=0)
    score = models.FloatField(default=0.0)      # 0..1 overall
    timed_out_count = models.IntegerField(default=0)

    # Per-section breakdown computed at completion.
    section_breakdown = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "mode", "-started_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} {self.mode} ({self.total_stations} stations)"


class PracticeAttempt(models.Model):
    """A student's answers at one station within a session."""

    session = models.ForeignKey(
        PracticeSession, on_delete=models.CASCADE, related_name="attempts"
    )
    station = models.ForeignKey(
        "curriculum.SpotStation", on_delete=models.CASCADE, related_name="attempts"
    )
    order = models.IntegerField(default=0)

    # Main question — free text, graded by normalised comparison against accepted answers.
    main_answer = models.TextField(blank=True)
    main_correct = models.BooleanField(null=True, blank=True)

    supporting_choice = models.IntegerField(null=True, blank=True)
    supporting_correct = models.BooleanField(null=True, blank=True)

    true_false_answer = models.BooleanField(null=True, blank=True)
    true_false_correct = models.BooleanField(null=True, blank=True)

    seconds_taken = models.IntegerField(default=0)
    timed_out = models.BooleanField(default=False)

    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["session", "station"]
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.session_id} #{self.order} — {self.station_id}"


class PracticeRoundUsage(models.Model):
    """Monthly round counter used to enforce the free-tier limit server-side.

    Free students get 5 rounds a month per mode; premium users and verified class heads
    are never counted here. Kept as its own row (rather than derived from PracticeSession)
    so the allowance is cheap to read on every page load.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="practice_usage")
    mode = models.CharField(max_length=20, choices=PracticeMode.choices)
    period = models.CharField(max_length=7)  # "YYYY-MM"
    rounds_used = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "mode", "period"]

    def __str__(self) -> str:
        return f"{self.user.username} {self.mode} {self.period}: {self.rounds_used}"


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
class NotificationType(models.TextChoices):
    # Existing
    FLASHCARDS_DUE = "FLASHCARDS_DUE", "Flashcards due"
    FLASHCARDS_MISSED = "FLASHCARDS_MISSED", "Missed flashcards"
    PLANNER_UPCOMING = "PLANNER_UPCOMING", "Planned session starting"
    PLANNER_MISSED = "PLANNER_MISSED", "Planned session missed"
    STUDY_GOAL = "STUDY_GOAL", "Daily study goal"
    STREAK_AT_RISK = "STREAK_AT_RISK", "Streak at risk"
    WEAK_AREA = "WEAK_AREA", "Weak area needs revision"
    QUESTIONS_READY = "QUESTIONS_READY", "Generated questions ready"
    BATTLE_INVITE = "BATTLE_INVITE", "Brain battle invitation"
    
    # New - Academic
    NEW_QUIZ_AVAILABLE = "NEW_QUIZ", "New Quiz Available"
    QUIZ_COMPLETED = "QUIZ_COMPLETED", "Quiz Completed"
    QUIZ_RESULT = "QUIZ_RESULT", "Quiz Result Available"
    NEW_PAST_QUESTION = "NEW_PAST_Q", "New Past Question"
    NEW_FLASHCARD_SET = "NEW_FLASH_SET", "New Flashcard Set"
    STUDY_GOAL_COMPLETED = "GOAL_COMPLETED", "Study Goal Completed"
    
    # New - Class/Community
    NEW_SLIDES = "NEW_SLIDES", "New Slides Uploaded"
    SLIDE_UPDATED = "SLIDE_UPDATED", "Slide Updated"
    NEW_MATERIAL = "NEW_MATERIAL", "New Class Material"
    CLASS_ANNOUNCEMENT = "CLASS_ANNOUNCEMENT", "Class Announcement"
    HEAD_ANNOUNCEMENT = "HEAD_ANNOUNCEMENT", "Class Head Announcement"
    
    # New - Social
    NEW_COMMENT = "NEW_COMMENT", "New Comment"
    COMMENT_REPLY = "COMMENT_REPLY", "Comment Reply"
    POST_LIKED = "POST_LIKED", "Post Liked"
    POST_COMMENTED = "POST_COMMENTED", "Post Commented"
    MENTIONED = "MENTIONED", "Mentioned"
    NEW_FOLLOWER = "NEW_FOLLOWER", "New Follower"
    
    # New - System
    ACCOUNT_SECURITY = "ACCOUNT_SECURITY", "Account Security"
    WELCOME = "WELCOME", "Welcome"
    SYSTEM_MSG = "SYSTEM_MSG", "System Announcement"
    MAINTENANCE = "MAINTENANCE", "Maintenance"
    FEATURE_UPDATE = "FEATURE_UPDATE", "Feature Update"
    
    # Gamification additional
    LEADERBOARD_CHANGE = "LEADERBOARD_CHANGE", "Leaderboard Changed"
    ACHIEVEMENT = "ACHIEVEMENT", "Achievement Unlocked"
    BADGE_EARNED = "BADGE_EARNED", "Badge Earned"
    STREAK_MILESTONE = "STREAK_MILESTONE", "Streak Milestone"
    COMPETITION_START = "COMPETITION_START", "Competition Started"
    COMPETITION_END = "COMPETITION_END", "Competition Ending"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"

class Notification(models.Model):
    """An in-app notification.

    `dedupe_key` is what stops Emby nagging: a reminder of the same kind, for the same
    thing, on the same day is written once. Delivery status is recorded honestly — a row
    is only marked delivered when a transport actually accepted it.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")

    type = models.CharField(max_length=32, choices=NotificationType.choices)
    priority = models.CharField(max_length=12, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    # Where tapping the notification should take the student.
    action_url = models.CharField(max_length=300, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    scheduled_for = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    delivered_at = models.DateTimeField(null=True, blank=True)

    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    dedupe_key = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_for"]
        indexes = [
            models.Index(fields=["user", "read", "-scheduled_for"]),
            models.Index(fields=["status", "scheduled_for"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"],
                condition=~models.Q(dedupe_key=""),
                name="unique_notification_dedupe_key",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.title}"


class NotificationPreference(models.Model):
    """Per-student control over what Emby is allowed to send, and when."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preference"
    )

    academic_enabled = models.BooleanField(default=True)
    community_enabled = models.BooleanField(default=True)
    system_enabled = models.BooleanField(default=True)
    
    flashcards_enabled = models.BooleanField(default=True)
    planner_enabled = models.BooleanField(default=True)
    study_goal_enabled = models.BooleanField(default=True)
    streak_enabled = models.BooleanField(default=True)
    weak_area_enabled = models.BooleanField(default=True)

    browser_push_enabled = models.BooleanField(default=False)
    push_subscription = models.JSONField(default=dict, blank=True)

    # No notifications are scheduled inside this window (local time).
    quiet_hours_start = models.IntegerField(default=22)  # 22:00
    quiet_hours_end = models.IntegerField(default=7)     # 07:00

    max_per_day = models.IntegerField(default=4)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} notification preferences"


class PushSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    
    endpoint = models.URLField(max_length=500)
    p256dh = models.CharField(max_length=100)
    auth = models.CharField(max_length=100)
    
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'endpoint']

    def __str__(self):
        return f"PushSubscription for {self.user.username}"


# ---------------------------------------------------------------------------
# BACKGROUND QUESTION GENERATION
# ---------------------------------------------------------------------------
class QuestionGenerationJob(models.Model):
    """Tracks the one-off bulk question generation for an uploaded slide.

    A slide gets 50 MCQs and 10 theory questions generated once, in the background.
    This row is what makes that safe and observable:

      * `OneToOne` on the slide means a second job can never be created for the same
        slide, so two workers racing on the same upload cannot double-generate,
      * the status field lets the uploader see progress instead of guessing,
      * counts and `attempts` make a failed run retryable without duplicating whatever
        the previous run already saved.
    """

    TARGET_MCQ = 50
    TARGET_THEORY = 10
    MAX_ATTEMPTS = 3

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partially generated"
        FAILED = "failed", "Failed"

    slide = models.OneToOneField(
        "curriculum.Slide", on_delete=models.CASCADE, related_name="generation_job"
    )

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    mcq_target = models.IntegerField(default=TARGET_MCQ)
    theory_target = models.IntegerField(default=TARGET_THEORY)
    mcq_generated = models.IntegerField(default=0)
    theory_generated = models.IntegerField(default=0)

    attempts = models.IntegerField(default=0)
    error = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.slide_id}: {self.mcq_generated}/{self.mcq_target} MCQ ({self.status})"

    @property
    def is_complete(self) -> bool:
        return (
            self.mcq_generated >= self.mcq_target
            and self.theory_generated >= self.theory_target
        )

    @property
    def progress_percent(self) -> int:
        total_target = max(1, self.mcq_target + self.theory_target)
        return min(100, round(
            (self.mcq_generated + self.theory_generated) / total_target * 100
        ))

    @property
    def can_retry(self) -> bool:
        return self.status in {self.Status.FAILED, self.Status.PARTIAL} and (
            self.attempts < self.MAX_ATTEMPTS
        )


# ---------------------------------------------------------------------------
# CACHED AI DASHBOARD MESSAGE
# ---------------------------------------------------------------------------
class DashboardMessage(models.Model):
    """The personalised dashboard greeting, cached so reloads don't re-bill the AI.

    A message stays valid for six hours; the dashboard endpoint regenerates only once it
    has expired, which turns an unbounded per-pageview cost into at most four calls per
    student per day.
    """

    TTL_HOURS = 6

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="dashboard_message"
    )

    headline = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    # Snapshot of the stats the message was written from, for debugging drift.
    context = models.JSONField(default=dict, blank=True)

    generated_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.user.username}: {self.headline[:40]}"

    @property
    def is_valid(self) -> bool:
        return bool(self.body) and timezone.now() < self.expires_at

    def refresh_expiry(self) -> None:
        self.generated_at = timezone.now()
        self.expires_at = self.generated_at + timedelta(hours=self.TTL_HOURS)


# ---------------------------------------------------------------------------
# GAMIFICATION
# ---------------------------------------------------------------------------
class BadgeCategory(models.TextChoices):
    ACADEMIC = "ACADEMIC", "Academic"
    QUIZZES = "QUIZZES", "Quizzes"
    FLASHCARDS = "FLASHCARDS", "Flashcards"
    STUDY_CONSISTENCY = "STUDY_CONSISTENCY", "Study Consistency"
    STREAKS = "STREAKS", "Streaks"
    MASTERY = "MASTERY", "Mastery"
    IMPROVEMENT = "IMPROVEMENT", "Improvement"
    COMMUNITY = "COMMUNITY", "Community"
    CONTRIBUTION = "CONTRIBUTION", "Contribution"
    SPECIAL = "SPECIAL", "Special"


class BadgeRarity(models.TextChoices):
    COMMON = "COMMON", "Common"
    UNCOMMON = "UNCOMMON", "Uncommon"
    RARE = "RARE", "Rare"
    EPIC = "EPIC", "Epic"
    LEGENDARY = "LEGENDARY", "Legendary"


class Badge(models.Model):
    """A visual reward representing a meaningful accomplishment."""

    id = models.CharField(primary_key=True, max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=BadgeCategory.choices)
    rarity = models.CharField(max_length=20, choices=BadgeRarity.choices, default=BadgeRarity.COMMON)
    
    icon = models.CharField(max_length=100, blank=True, help_text="Lucide icon name or emoji")
    image_url = models.URLField(blank=True)
    
    is_active = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False, help_text="True if this should be a secret until unlocked")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "rarity", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.rarity})"


class Achievement(models.Model):
    """A specific measurable accomplishment that awards a badge."""

    id = models.CharField(primary_key=True, max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=BadgeCategory.choices)
    
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True, related_name="achievements")
    
    target_metric = models.CharField(max_length=100, help_text="Metric tracked (e.g. 'quizzes_completed')")
    target_value = models.IntegerField(default=1)
    
    is_active = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "target_value", "name"]

    def __str__(self) -> str:
        return f"{self.name}: {self.target_metric} = {self.target_value}"


class UserBadge(models.Model):
    """Tracks the badges earned by a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    
    earned_at = models.DateTimeField(default=timezone.now, db_index=True)
    source_achievement = models.ForeignKey(Achievement, on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ["user", "badge"]
        ordering = ["-earned_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.badge.name}"


class UserAchievement(models.Model):
    """Tracks a user's progress towards an achievement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="achievements")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    
    progress = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "achievement"]
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_completed"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.achievement.name} ({self.progress}/{self.achievement.target_value})"

    @property
    def percentage(self) -> int:
        if not self.achievement.target_value:
            return 100 if self.is_completed else 0
        return min(100, int((self.progress / self.achievement.target_value) * 100))
