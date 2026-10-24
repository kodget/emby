from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
import json
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from curriculum.models import UserStats, DailyStudySession
from curriculum.tests.test_bank_recovery import BankFixture
from learning import events
from learning.activity_reconciliation import plan, apply
from learning.models import ActivityType, LearningEvent, XPAward, ActivityCacheReconciliation


class ReconciliationFixture(BankFixture):
    def event(self, **changes):
        data = dict(user=self.user, activity=ActivityType.RESOURCE_STUDIED, duration_seconds=30)
        data.update(changes)
        return LearningEvent.objects.create(**data)

    def stale(self):
        UserStats.objects.update_or_create(user=self.user, defaults=dict(points=417, rank=8,
            total_study_minutes=900, current_streak=99, longest_streak=99))
        DailyStudySession.objects.create(user=self.user, date=timezone.localdate(), minutes_studied=900, sessions_count=99)
        self.event(); self.event()


class ActivityReconciliationTests(ReconciliationFixture, TestCase):
    def test_preview_is_read_only_stable_and_shows_exact_changes(self):
        self.stale()
        with CaptureQueriesContext(connection) as queries:
            result = plan(self.user)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in queries))
        self.assertEqual(result['fingerprint'], plan(self.user)['fingerprint'])
        self.assertTrue(result['dry_run'])
        self.assertEqual(result['before']['stats']['total_study_minutes'], 900)
        self.assertEqual(result['after']['stats']['total_study_minutes'], 1)
        self.assertFalse(ActivityCacheReconciliation.objects.exists())

    def test_apply_preserves_source_history_rewards_points_and_previous_cache_values(self):
        self.stale()
        event = LearningEvent.objects.first()
        XPAward.objects.create(user=self.user, event=event, reason=event.activity, amount=10, base_amount=10, multiplier=1)
        source = list(LearningEvent.objects.values())
        rewards = list(XPAward.objects.values())
        reviewed = plan(self.user)
        result = apply(self.user, reviewed['fingerprint'])
        self.assertTrue(result['applied'])
        stats = UserStats.objects.get(user=self.user)
        self.assertEqual((stats.points, stats.rank, stats.total_study_minutes, stats.current_streak), (417, 8, 1, 1))
        self.assertEqual(DailyStudySession.objects.get().sessions_count, 2)
        receipt = ActivityCacheReconciliation.objects.get()
        self.assertEqual(receipt.before, reviewed['before'])
        self.assertEqual(receipt.after, reviewed['after'])
        self.assertEqual(list(LearningEvent.objects.values()), source)
        self.assertEqual(list(XPAward.objects.values()), rewards)

    def test_cache_only_days_are_zeroed_without_inventing_events_or_deleting_rows(self):
        day = DailyStudySession.objects.create(user=self.user, date=timezone.localdate()-timedelta(days=5),
                                               minutes_studied=99, sessions_count=12)
        apply(self.user, plan(self.user)['fingerprint'])
        day.refresh_from_db()
        self.assertEqual((day.minutes_studied, day.sessions_count), (0, 0))
        self.assertFalse(LearningEvent.objects.exists())
        self.assertFalse(XPAward.objects.exists())
        self.assertEqual(ActivityCacheReconciliation.objects.get().before['daily'][day.date.isoformat()]['minutes_studied'], 99)

    def test_changed_evidence_invalidates_approval_even_before_another_whole_minute(self):
        self.stale(); reviewed = plan(self.user)
        self.event(duration_seconds=1)
        with self.assertRaises(ValidationError): apply(self.user, reviewed['fingerprint'])
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 900)
        self.assertFalse(ActivityCacheReconciliation.objects.exists())

    def test_changed_membership_or_cache_invalidates_approval(self):
        self.stale(); reviewed = plan(self.user)
        UserStats.objects.filter(user=self.user).update(total_study_minutes=901)
        with self.assertRaises(ValidationError): apply(self.user, reviewed['fingerprint'])
        reviewed = plan(self.user)
        self.user.profile.class_group = None; self.user.profile.save()
        with self.assertRaises(ValidationError): apply(self.user, reviewed['fingerprint'])
        self.assertFalse(ActivityCacheReconciliation.objects.exists())

    def test_failed_apply_rolls_back_receipt_and_all_cache_changes(self):
        self.stale(); reviewed = plan(self.user)
        with patch('learning.activity_reconciliation.DailyStudySession.objects.update_or_create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError): apply(self.user, reviewed['fingerprint'])
        self.assertEqual(plan(self.user)['fingerprint'], reviewed['fingerprint'])
        self.assertFalse(ActivityCacheReconciliation.objects.exists())

    def test_replay_returns_receipt_without_overwriting_subsequent_activity(self):
        self.stale(); reviewed = plan(self.user)
        apply(self.user, reviewed['fingerprint'])
        events.record(self.user, ActivityType.RESOURCE_STUDIED, duration_seconds=60, award_xp=False)
        before = plan(self.user)
        self.assertTrue(apply(self.user, reviewed['fingerprint'])['already_applied'])
        self.assertEqual(plan(self.user), before)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 2)
        self.assertEqual(ActivityCacheReconciliation.objects.count(), 1)

    def test_new_stats_and_cross_day_fractions_remain_correct_after_new_activity(self):
        now = timezone.now()
        self.event(duration_seconds=30, occurred_at=now-timedelta(days=1))
        self.event(duration_seconds=30, occurred_at=now)
        self.assertFalse(UserStats.objects.exists())
        apply(self.user, plan(self.user)['fingerprint'])
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        events.record(self.user, ActivityType.RESOURCE_STUDIED, duration_seconds=30, award_xp=False)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        self.assertEqual(DailyStudySession.objects.get(user=self.user, date=timezone.localdate()).minutes_studied, 1)
        self.assertFalse(plan(self.user)['changes'])

    def test_invalid_future_and_duplicate_completion_history_stays_preserved_but_excluded(self):
        for _ in range(2):
            self.event(activity=ActivityType.BRAIN_BATTLE_COMPLETED, resource_type='brain_battle', resource_id='same', duration_seconds=60)
        self.event(duration_seconds=999, occurred_at=timezone.now()+timedelta(days=1))
        self.event(duration_seconds=-1)
        reviewed = plan(self.user)
        self.assertEqual(reviewed['after']['stats']['total_study_minutes'], 1)
        apply(self.user, reviewed['fingerprint'])
        self.assertEqual(LearningEvent.objects.count(), 4)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)

    def test_a_new_review_can_repair_cache_values_that_drift_back_to_the_original_state(self):
        self.stale(); original = plan(self.user)
        apply(self.user, original['fingerprint'])
        UserStats.objects.filter(user=self.user).update(**original['before']['stats'])
        for day, values in original['before']['daily'].items():
            DailyStudySession.objects.filter(user=self.user, date=day).update(**values)
        reviewed = plan(self.user)
        self.assertNotEqual(reviewed['fingerprint'], original['fingerprint'])
        apply(self.user, reviewed['fingerprint'])
        self.assertEqual(ActivityCacheReconciliation.objects.count(), 2)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)

    def test_zero_duration_new_activity_updates_sessions_without_adding_minutes(self):
        self.stale(); apply(self.user, plan(self.user)['fingerprint'])
        events.record(self.user, ActivityType.PLANNER_TASK_COMPLETED, resource_type='schedule_item',
                      resource_id='planned', duration_seconds=0, award_xp=False)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        self.assertEqual(DailyStudySession.objects.get(user=self.user).sessions_count, 3)
        self.assertFalse(plan(self.user)['changes'])

    def test_command_requires_one_explicit_user_and_exact_reviewed_fingerprint(self):
        self.stale(); output = StringIO()
        call_command('reconcile_activity', '--user-id', str(self.user.pk), stdout=output)
        reviewed = json.loads(output.getvalue())
        self.assertTrue(reviewed['dry_run'])
        for args in (['--apply'], ['--apply', '--expected-fingerprint', 'bad'],
                     ['--expected-fingerprint', reviewed['fingerprint']]):
            with self.assertRaises(CommandError):
                call_command('reconcile_activity', '--user-id', str(self.user.pk), *args, stdout=StringIO())
        call_command('reconcile_activity', '--user-id', str(self.user.pk), '--apply',
                     '--expected-fingerprint', reviewed['fingerprint'], stdout=StringIO())
        self.assertEqual(ActivityCacheReconciliation.objects.count(), 1)
        with self.assertRaises(CommandError):
            call_command('reconcile_activity', '--user-id', '999999999', stdout=StringIO())


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class ActivityReconciliationConcurrencyTests(ReconciliationFixture, TransactionTestCase):
    def test_two_simultaneous_applies_have_one_receipt(self):
        self.stale(); reviewed = plan(self.user); barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                return apply(user, reviewed['fingerprint'])
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
        self.assertEqual(sum(row['applied'] for row in results), 1)
        self.assertEqual(ActivityCacheReconciliation.objects.count(), 1)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)

    def test_apply_and_new_activity_cannot_overwrite_each_other(self):
        self.stale(); reviewed = plan(self.user); barrier = Barrier(2)
        def run(kind):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                if kind == 'apply':
                    try: return apply(user, reviewed['fingerprint'])
                    except ValidationError: return {'stale': True}
                events.record(user, ActivityType.RESOURCE_STUDIED, duration_seconds=60, award_xp=False)
                return {'written': True}
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, ['apply', 'write']))
        self.assertTrue(results[1]['written'])
        # If the writer won, the old plan must be rejected and a fresh review applied.
        if results[0].get('stale'):
            apply(self.user, plan(self.user)['fingerprint'])
        self.assertEqual(LearningEvent.objects.count(), 3)
        self.assertEqual(ActivityCacheReconciliation.objects.count(), 1)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 2)
        self.assertEqual(DailyStudySession.objects.get(user=self.user).sessions_count, 3)


from curriculum.tests.test_deck_practice import PracticeFixture
from curriculum.tests.test_image_practice_evidence import ImageFixture
from curriculum.tests.test_planner_activity import PlannerFixture


class ReconciledPracticeTests(PracticeFixture, TestCase):
    def test_real_practice_submission_uses_saved_attempt_time_after_reconciliation(self):
        from curriculum.models import QuizAttempt
        apply(self.user, plan(self.user)['fingerprint'])
        attempt = self.create()
        QuizAttempt.objects.filter(pk=attempt['id']).update(started_at=timezone.now()-timedelta(seconds=90))
        self.api('answer', {'question_id': attempt['question_ids'][0], 'selected_option': 'B'}, attempt['id'])
        result = self.api('submit', pk=attempt['id'])
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        self.assertEqual(DailyStudySession.objects.get(user=self.user).sessions_count, 1)
        self.assertFalse(plan(self.user)['changes'])


class ReconciledImageTests(ImageFixture, TestCase):
    def test_real_image_completion_uses_saved_round_evidence(self):
        from learning.practice import complete_session
        apply(self.user, plan(self.user)['fingerprint'])
        session = self.start()
        self.answer(session, seconds_taken=20)
        complete_session(session)
        self.assertEqual(DailyStudySession.objects.get(user=self.user).sessions_count, 1)
        self.assertFalse(plan(self.user)['changes'])


class ReconciledPlannerTests(PlannerFixture, TestCase):
    def test_real_planner_completion_records_a_session_without_estimated_time(self):
        apply(self.user, plan(self.user)['fingerprint'])
        result = self.request('complete')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 0)
        self.assertEqual(DailyStudySession.objects.get(user=self.user).sessions_count, 1)
        self.assertFalse(plan(self.user)['changes'])
