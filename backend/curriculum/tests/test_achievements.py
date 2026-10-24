from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from learning import events
from learning.gamification import AchievementEngine, seed_achievements
from learning.models import (
    Achievement, ActivityType, LearningEvent, Notification, UserAchievement, UserBadge,
)
from curriculum.models import UserStats


class AchievementEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("achievement-student")
        push_task = patch("learning.tasks.send_push_notification_task.delay")
        push_task.start()
        self.addCleanup(push_task.stop)
        seed_achievements()

    def add_event(self, activity, *, correct=0, total=0, metadata=None):
        return LearningEvent.objects.create(
            user=self.user,
            activity=activity,
            correct_count=correct,
            total_count=total,
            accuracy=correct / total if total else None,
            metadata=metadata or {},
        )

    def progress(self, achievement_id):
        return UserAchievement.objects.get(
            user=self.user, achievement_id=achievement_id
        )

    def test_quiz_replay_rebuilds_progress_and_awards_badge_and_notifications_once(self):
        event = events.record(
            user=self.user,
            activity=ActivityType.QUIZ_COMPLETED,
            correct_count=1,
            total_count=1,
            award_xp=False,
        )
        AchievementEngine.evaluate_event(event)

        first_quiz = self.progress("FIRST_QUIZ")
        self.assertEqual((first_quiz.progress, first_quiz.is_completed), (1, True))
        self.assertEqual(UserBadge.objects.filter(user=self.user, badge_id="b_first_steps").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    def test_quiz_and_flashcard_thresholds_come_from_saved_event_counts(self):
        for _ in range(9):
            self.add_event(ActivityType.QUIZ_COMPLETED, correct=1, total=1)
        self.add_event(ActivityType.FLASHCARD_REVIEWED, total=99)
        self.add_event(ActivityType.FLASHCARD_REVIEWED)
        AchievementEngine.recalculate_user(self.user)

        self.assertEqual(self.progress("QUIZ_EXPLORER").progress, 9)
        self.assertFalse(self.progress("QUIZ_EXPLORER").is_completed)
        self.assertEqual(self.progress("FLASHCARD_100").progress, 100)
        self.assertTrue(self.progress("FLASHCARD_100").is_completed)

        self.add_event(ActivityType.QUIZ_COMPLETED, correct=1, total=1)
        AchievementEngine.recalculate_user(self.user)
        self.assertTrue(self.progress("QUIZ_EXPLORER").is_completed)
        self.assertEqual(self.progress("QUIZ_MASTER").progress, 10)

        for _ in range(89):
            self.add_event(ActivityType.QUIZ_COMPLETED, correct=1, total=1)
        AchievementEngine.recalculate_user(self.user)
        self.assertEqual(self.progress("QUIZ_MASTER").progress, 99)
        self.assertFalse(self.progress("QUIZ_MASTER").is_completed)

        self.add_event(ActivityType.QUIZ_COMPLETED, correct=1, total=1)
        AchievementEngine.recalculate_user(self.user)
        self.assertTrue(self.progress("QUIZ_MASTER").is_completed)

    def test_formal_pass_requires_final_score_of_at_least_fifty_percent(self):
        self.add_event(
            ActivityType.QUIZ_COMPLETED, correct=1, total=2,
            metadata={"exam_type": "formal"},
        )
        self.add_event(
            ActivityType.QUIZ_COMPLETED, correct=2, total=4,
            metadata={"exam_type": "formal"},
        )
        self.add_event(
            ActivityType.QUIZ_COMPLETED, correct=4, total=4,
            metadata={"exam_type": "formal", "theory_grading_pending": True},
        )
        AchievementEngine.recalculate_user(self.user)

        passed = self.progress("CERTIFIED_SCHOLAR")
        self.assertEqual((passed.progress, passed.is_completed), (1, True))

        pending = LearningEvent.objects.get(metadata__theory_grading_pending=True)
        pending.metadata.update(theory_grading_pending=False, final_percentage=49)
        pending.save(update_fields=["metadata"])
        AchievementEngine.recalculate_user(self.user)
        self.assertEqual(self.progress("CERTIFIED_SCHOLAR").progress, 1)

    def test_streak_progress_can_fall_but_earned_milestone_is_preserved(self):
        stats = UserStats.objects.create(
            user=self.user,
            current_streak=3,
            last_activity_date=timezone.localdate(),
        )
        AchievementEngine.recalculate_user(self.user)
        self.assertTrue(self.progress("STREAK_3").is_completed)
        self.assertEqual(self.progress("STREAK_7").progress, 3)

        stats.current_streak = 0
        stats.last_activity_date = timezone.localdate() - timedelta(days=3)
        stats.save(update_fields=["current_streak", "last_activity_date"])
        AchievementEngine.recalculate_user(self.user)

        self.assertTrue(self.progress("STREAK_3").is_completed)
        self.assertEqual(self.progress("STREAK_7").progress, 0)

    def test_seed_command_is_repeatable_and_preserves_catalog_thresholds(self):
        original = list(Achievement.objects.order_by("id").values_list(
            "id", "target_metric", "target_value"
        ))
        call_command("seed_gamification", stdout=StringIO())
        call_command("seed_gamification", stdout=StringIO())
        repeated = list(Achievement.objects.order_by("id").values_list(
            "id", "target_metric", "target_value"
        ))

        self.assertEqual(repeated, original)
        self.assertEqual(len(repeated), 8)
