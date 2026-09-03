import logging
from django.db import transaction
from django.utils import timezone
from .models import Achievement, UserAchievement, UserBadge, Badge, LearningEvent, ActivityType
from .notifications import schedule, NotificationType

logger = logging.getLogger(__name__)

# Basic definitions to seed
ACHIEVEMENT_DEFINITIONS = [
    # Quizzes
    {
        "id": "FIRST_QUIZ",
        "name": "First Steps",
        "description": "Complete your first quiz.",
        "category": "QUIZZES",
        "target_metric": "quizzes_completed",
        "target_value": 1,
        "badge_id": "b_first_steps",
        "badge": {
            "name": "First Steps",
            "description": "Took your first step into quizzes.",
            "rarity": "COMMON",
            "icon": "graduation-cap",
        }
    },
    {
        "id": "QUIZ_EXPLORER",
        "name": "Quiz Explorer",
        "description": "Complete 10 quizzes.",
        "category": "QUIZZES",
        "target_metric": "quizzes_completed",
        "target_value": 10,
        "badge_id": "b_quiz_explorer",
        "badge": {
            "name": "Quiz Explorer",
            "description": "You've explored many quizzes.",
            "rarity": "UNCOMMON",
            "icon": "compass",
        }
    },
    {
        "id": "QUIZ_MASTER",
        "name": "Quiz Master",
        "description": "Complete 100 quizzes.",
        "category": "QUIZZES",
        "target_metric": "quizzes_completed",
        "target_value": 100,
        "badge_id": "b_quiz_master",
        "badge": {
            "name": "Quiz Master",
            "description": "A true master of quizzes.",
            "rarity": "RARE",
            "icon": "crown",
        }
    },
    {
        "id": "CERTIFIED_SCHOLAR",
        "name": "Certified Scholar",
        "description": "Pass a formal assessment with at least 50%.",
        "category": "QUIZZES",
        "target_metric": "formal_assessments_passed",
        "target_value": 1,
        "badge_id": "b_certified_scholar",
        "badge": {
            "name": "Certified Scholar",
            "description": "Passed a rigorous formal assessment.",
            "rarity": "EPIC",
            "icon": "award",
        }
    },
    # Flashcards
    {
        "id": "FIRST_REVIEW",
        "name": "First Review",
        "description": "Review your first flashcard.",
        "category": "FLASHCARDS",
        "target_metric": "flashcards_reviewed",
        "target_value": 1,
        "badge_id": "b_first_review",
        "badge": {
            "name": "First Review",
            "description": "Reviewed your first flashcard.",
            "rarity": "COMMON",
            "icon": "book-open",
        }
    },
    {
        "id": "FLASHCARD_100",
        "name": "Flashcard Warrior",
        "description": "Review 100 flashcards.",
        "category": "FLASHCARDS",
        "target_metric": "flashcards_reviewed",
        "target_value": 100,
        "badge_id": "b_flashcard_warrior",
        "badge": {
            "name": "Flashcard Warrior",
            "description": "Fought through 100 flashcards.",
            "rarity": "UNCOMMON",
            "icon": "sword",
        }
    },
    # Streaks (Handled by tracking study sessions)
    {
        "id": "STREAK_3",
        "name": "On Fire",
        "description": "Maintain a 3-day study streak.",
        "category": "STREAKS",
        "target_metric": "current_streak",
        "target_value": 3,
        "badge_id": "b_streak_3",
        "badge": {
            "name": "On Fire",
            "description": "3-day study streak.",
            "rarity": "COMMON",
            "icon": "flame",
        }
    },
    {
        "id": "STREAK_7",
        "name": "Consistency Champion",
        "description": "Maintain a 7-day study streak.",
        "category": "STREAKS",
        "target_metric": "current_streak",
        "target_value": 7,
        "badge_id": "b_streak_7",
        "badge": {
            "name": "Consistency Champion",
            "description": "7-day study streak.",
            "rarity": "UNCOMMON",
            "icon": "calendar-check",
        }
    }
]

def seed_achievements():
    """Ensure all achievement definitions exist in the database."""
    for definition in ACHIEVEMENT_DEFINITIONS:
        badge_data = definition.get("badge")
        badge = None
        if badge_data:
            badge, _ = Badge.objects.update_or_create(
                id=definition["badge_id"],
                defaults={
                    "name": badge_data["name"],
                    "description": badge_data["description"],
                    "category": definition["category"],
                    "rarity": badge_data["rarity"],
                    "icon": badge_data.get("icon", ""),
                }
            )
        
        Achievement.objects.update_or_create(
            id=definition["id"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "category": definition["category"],
                "target_metric": definition["target_metric"],
                "target_value": definition["target_value"],
                "badge": badge,
            }
        )

class AchievementEngine:
    """Central engine for evaluating achievements based on learning events."""
    
    @classmethod
    def evaluate_event(cls, event: LearningEvent):
        """Hooked into learning.events.record() to fan out progress."""
        
        updates = {}
        
        # 1. Determine which metrics just incremented
        if event.activity == ActivityType.QUIZ_COMPLETED:
            updates["quizzes_completed"] = 1
            if event.metadata and event.metadata.get("exam_type") == "formal":
                if event.correct_count is not None and event.total_count is not None and event.total_count > 0:
                    score = event.correct_count / event.total_count
                    if score >= 0.5:
                        updates["formal_assessments_passed"] = 1
        elif event.activity == ActivityType.FLASHCARD_REVIEWED:
            # Using total_count from LearningEvent (number of cards reviewed)
            updates["flashcards_reviewed"] = event.total_count or 1
            
        # Add a check for streak updates
        # Streak updates happen in `_touch_streak` inside events.py, we can read it from user stats
        stats = getattr(event.user, "stats", None)
        if stats and stats.current_streak > 0:
            updates["current_streak"] = stats.current_streak

        if not updates:
            return

        # 2. Update achievements that match these metrics
        # Only active achievements that the user hasn't completed yet
        for metric, increment in updates.items():
            if metric == "current_streak":
                cls._process_absolute_metric(event.user, metric, increment, event)
            else:
                cls._process_incremental_metric(event.user, metric, increment, event)

    @classmethod
    def _process_incremental_metric(cls, user, metric, increment, event):
        """Update progress for additive metrics (e.g., quizzes_completed)."""
        achievements = Achievement.objects.filter(target_metric=metric, is_active=True)
        
        for ach in achievements:
            # Get or create progress
            with transaction.atomic():
                # Lock the row to prevent race conditions from concurrent quiz completions
                user_ach, created = UserAchievement.objects.select_for_update().get_or_create(
                    user=user, achievement=ach
                )
                
                if user_ach.is_completed:
                    continue
                
                user_ach.progress += increment
                user_ach.save(update_fields=["progress", "updated_at"])
                
                if user_ach.progress >= ach.target_value:
                    cls._unlock_achievement(user_ach, event)
                    
    @classmethod
    def _process_absolute_metric(cls, user, metric, current_value, event):
        """Update progress for absolute metrics (e.g., streak)."""
        achievements = Achievement.objects.filter(target_metric=metric, is_active=True)
        
        for ach in achievements:
            with transaction.atomic():
                user_ach, created = UserAchievement.objects.select_for_update().get_or_create(
                    user=user, achievement=ach
                )
                
                if user_ach.is_completed:
                    continue
                
                # For streaks, progress is just the current streak, bounded by target
                new_progress = min(current_value, ach.target_value)
                if new_progress != user_ach.progress:
                    user_ach.progress = new_progress
                    user_ach.save(update_fields=["progress", "updated_at"])
                
                if user_ach.progress >= ach.target_value:
                    cls._unlock_achievement(user_ach, event)

    @classmethod
    def _unlock_achievement(cls, user_achievement: UserAchievement, event: LearningEvent):
        """Handle the actual unlocking and notification creation."""
        user_achievement.is_completed = True
        user_achievement.completed_at = timezone.now()
        user_achievement.save(update_fields=["is_completed", "completed_at", "updated_at"])
        
        ach = user_achievement.achievement
        user = user_achievement.user
        
        # Log unlock
        logger.info(f"User {user.username} unlocked achievement {ach.id}")
        
        # Award badge if applicable
        if ach.badge:
            UserBadge.objects.get_or_create(
                user=user,
                badge=ach.badge,
                defaults={
                    "source_achievement": ach,
                    "earned_at": timezone.now()
                }
            )
            
            # Badge Notification
            schedule(
                user=user,
                type_=NotificationType.BADGE_EARNED,
                title="New Badge Earned!",
                body=f"You earned the {ach.badge.name} badge.",
                action_url="/achievements",
                payload={"badge_id": ach.badge.id, "icon": ach.badge.icon, "rarity": ach.badge.rarity},
                dedupe_key=f"badge_{ach.badge.id}"
            )
            
        # Achievement Notification
        schedule(
            user=user,
            type_=NotificationType.ACHIEVEMENT,
            title="Achievement Unlocked!",
            body=f"You earned the {ach.name} achievement.",
            action_url="/achievements",
            payload={"achievement_id": ach.id},
            dedupe_key=f"ach_{ach.id}"
        )
