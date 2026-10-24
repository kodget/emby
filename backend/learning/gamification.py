import logging
from django.db import transaction
from django.db.models import Sum
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
    """Central engine for deriving achievement progress from learning records."""
    
    @classmethod
    def evaluate_event(cls, event: LearningEvent):
        """Refresh from the ledger; reprocessing the same event cannot add progress twice."""
        cls.recalculate_user(event.user)

    @classmethod
    @transaction.atomic
    def recalculate_user(cls, user):
        """Rebuild progress from recorded events and current streak without inventing activity."""
        from curriculum.models import UserStats

        stats, _ = UserStats.objects.get_or_create(user=user)
        stats = UserStats.objects.select_for_update().get(pk=stats.pk)
        events = LearningEvent.objects.filter(user=user)
        quiz_events = events.filter(activity=ActivityType.QUIZ_COMPLETED)
        flashcard_events = events.filter(activity=ActivityType.FLASHCARD_REVIEWED)

        formal_passes = 0
        for accuracy, metadata in quiz_events.filter(
            metadata__exam_type="formal"
        ).values_list("accuracy", "metadata"):
            if metadata.get("theory_grading_pending"):
                continue
            percentage = metadata.get("final_percentage")
            if percentage is None:
                percentage = (accuracy or 0) * 100
            if percentage >= 50:
                formal_passes += 1

        metrics = {
            "quizzes_completed": quiz_events.count(),
            "formal_assessments_passed": formal_passes,
            "flashcards_reviewed": (
                flashcard_events.aggregate(total=Sum("total_count"))["total"] or 0
            ) + flashcard_events.filter(total_count=0).count(),
            "current_streak": stats.active_streak,
        }

        for achievement in Achievement.objects.filter(is_active=True):
            progress = min(max(metrics.get(achievement.target_metric, 0), 0), achievement.target_value)
            user_achievement, _ = UserAchievement.objects.select_for_update().get_or_create(
                user=user, achievement=achievement
            )
            if user_achievement.is_completed:
                continue

            if user_achievement.progress != progress:
                user_achievement.progress = progress
                user_achievement.save(update_fields=["progress", "updated_at"])

            if progress >= achievement.target_value:
                cls._unlock_achievement(user_achievement)

    @classmethod
    def _unlock_achievement(cls, user_achievement: UserAchievement):
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
