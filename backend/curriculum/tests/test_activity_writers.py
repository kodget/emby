"""Activity retries, reward atomicity and dashboard evidence; no provider calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models import F, Sum
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import DailyStudySession, UserStats
from curriculum.tests.test_bank_recovery import BankFixture
from learning import dashboard, events, views, xp
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, DashboardMessage, LearningEvent, WeakArea, XPAward


class ActivityWriterTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 10, 19, 23, 30, tzinfo=dt_timezone.utc)
        clock = patch('django.utils.timezone.now', return_value=self.now)
        clock.start(); self.addCleanup(clock.stop)
        # Field defaults retain the original callable when the model is imported.
        # Freeze that callable too, so these calendar tests work on any real date.
        award_clock = patch.object(XPAward._meta.get_field('awarded_at'), '_get_default', lambda: self.now)
        award_clock.start(); self.addCleanup(award_clock.stop)

    def record(self, **kwargs):
        data = dict(user=self.user, activity=ActivityType.QUESTION_ANSWERED,
            subject=self.slide.subject, correct_count=2, total_count=3, duration_seconds=20)
        data.update(kwargs)
        return events.record(**data)

    def test_completion_retry_has_one_event_reward_study_and_weak_area_update(self):
        first = self.record(resource_type='practice_session', resource_id='one')
        points = self.user.stats.points
        with patch('learning.gamification.AchievementEngine.evaluate_event') as achievements:
            second = self.record(resource_type='practice_session', resource_id='one')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(XPAward.objects.count(), 1)
        self.assertEqual(WeakArea.objects.get().attempted, 3)
        self.assertEqual(DailyStudySession.objects.get().sessions_count, 1)
        self.user.stats.refresh_from_db()
        self.assertEqual(self.user.stats.points, points)
        achievements.assert_not_called()

    def test_retry_of_pre_migration_completion_does_not_replay_rewards(self):
        old = LearningEvent.objects.create(user=self.user, activity=ActivityType.QUESTION_ANSWERED,
            resource_type='practice_session', resource_id='old', total_count=3, correct_count=2)
        self.assertEqual(self.record(resource_type='practice_session', resource_id='old').pk, old.pk)
        self.assertFalse(XPAward.objects.exists())
        self.assertFalse(DailyStudySession.objects.exists())

    def test_explicit_request_key_rejects_changed_payload_but_allows_other_users(self):
        first = self.record(idempotency_key='read-1', award_xp=False)
        self.assertEqual(self.record(idempotency_key='read-1', award_xp=False).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.record(idempotency_key='read-1', duration_seconds=21)
        other = User.objects.create_user('separate-activity-user')
        self.record(user=other, subject=None, idempotency_key='read-1', award_xp=False)
        self.assertEqual(LearningEvent.objects.count(), 2)

    def test_database_rejects_duplicate_nonblank_key_without_restricting_historical_rows(self):
        self.record(idempotency_key='unique', award_xp=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LearningEvent.objects.create(user=self.user, activity=ActivityType.RESOURCE_STUDIED,
                                         idempotency_key='unique')
        self.record(award_xp=False); self.record(award_xp=False)
        self.assertEqual(LearningEvent.objects.count(), 3)

    def test_invalid_activity_data_writes_no_events_or_rewards(self):
        for bad in [dict(correct_count=4), dict(total_count=-1), dict(duration_seconds=-1),
                    dict(duration_seconds=True), dict(total_count=1.5), dict(metadata=[]),
                    dict(activity='unknown'), dict(occurred_at=self.now+timedelta(seconds=1)),
                    dict(occurred_at=self.now.replace(tzinfo=None)), dict(idempotency_key='x'*161)]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.record(**bad)
        self.assertFalse(LearningEvent.objects.exists())
        self.assertFalse(XPAward.objects.exists())

    def test_three_short_sessions_accumulate_one_minute_on_the_local_date(self):
        for _ in range(3):
            self.record(award_xp=False)
        day = DailyStudySession.objects.get()
        self.assertEqual(day.date.isoformat(), '2026-10-20')
        self.assertEqual((day.minutes_studied, day.sessions_count), (1, 3))
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 1)

    def test_out_of_order_backfill_bridges_streak_without_moving_last_day_backwards(self):
        for offset in (0, 2, 1, 10):
            self.record(occurred_at=self.now-timedelta(days=offset), award_xp=False)
        stats = UserStats.objects.get(user=self.user)
        self.assertEqual((stats.current_streak, stats.longest_streak), (3, 3))
        self.assertEqual(stats.last_activity_date, timezone.localdate(self.now))
        self.assertEqual(stats.active_streak, 3)

    def test_future_or_expired_cached_streak_is_inactive_and_local_yesterday_is_active(self):
        stats, _ = UserStats.objects.get_or_create(user=self.user)
        stats.current_streak = 8
        for offset, expected in ((-1, 8), (-2, 0), (1, 0)):
            stats.last_activity_date = timezone.localdate(self.now)+timedelta(days=offset)
            self.assertEqual(stats.active_streak, expected)

    def test_flashcard_self_rating_does_not_update_objective_weak_areas(self):
        self.record(activity=ActivityType.FLASHCARD_REVIEWED, award_xp=False)
        self.assertFalse(WeakArea.objects.exists())

    def test_xp_uses_fresh_stats_and_retries_return_the_same_award(self):
        stats, _ = UserStats.objects.get_or_create(user=self.user)
        self.user.stats = stats  # Deliberately cache before another award.
        UserStats.objects.filter(pk=stats.pk).update(points=F('points') + 100)
        event = self.record()
        award = XPAward.objects.get(event=event)
        self.assertEqual(xp.award_for_event(event).pk, award.pk)
        stats.refresh_from_db()
        self.assertEqual(stats.points, 100+award.amount)
        self.assertEqual(XPAward.objects.count(), 1)

    def test_zero_award_decision_is_durable_even_after_the_daily_cap_resets(self):
        XPAward.objects.create(user=self.user, reason=ActivityType.QUESTION_ANSWERED,
                              amount=120, base_amount=120, multiplier=1)
        event = self.record()
        self.assertFalse(XPAward.objects.filter(event=event).exists())
        with patch('django.utils.timezone.now', return_value=self.now+timedelta(days=1)):
            self.assertIsNone(xp.award_for_event(event))
        event.refresh_from_db()
        self.assertTrue(event.xp_processed)

    def test_disabled_xp_cannot_be_awarded_by_a_later_retry(self):
        event = self.record(award_xp=False)
        self.assertIsNone(xp.award_for_event(event))
        self.assertFalse(XPAward.objects.exists())

    def test_daily_xp_cap_uses_local_midnight(self):
        before = XPAward.objects.create(user=self.user, reason=ActivityType.QUESTION_ANSWERED,
                                        amount=100, base_amount=100, multiplier=1)
        XPAward.objects.filter(pk=before.pk).update(awarded_at=self.now-timedelta(hours=1))
        self.assertEqual(xp.earned_today(self.user, ActivityType.QUESTION_ANSWERED), 0)
        self.record()
        self.assertGreater(xp.earned_today(self.user, ActivityType.QUESTION_ANSWERED), 0)

    def test_failed_xp_write_rolls_back_its_ledger_and_preserves_activity_transaction(self):
        def fail(event):
            XPAward.objects.create(user=event.user, event=event, reason=event.activity,
                                  amount=100, base_amount=100, multiplier=1)
            LearningEvent.objects.filter(pk=event.pk).update(xp_processed=True)
            raise IntegrityError('simulated database failure')
        with patch('learning.events.xp.award_for_event', side_effect=fail), self.assertLogs('learning.events', level='ERROR'):
            event = self.record()
        event.refresh_from_db()
        self.assertFalse(event.xp_processed)
        self.assertFalse(XPAward.objects.exists())
        self.assertTrue(DailyStudySession.objects.exists())
        self.assertIsNotNone(xp.award_for_event(event))

    def test_failed_achievement_write_is_rolled_back_without_poisoning_activity(self):
        def fail(event):
            UserStats.objects.filter(user=event.user).update(points=999)
            raise IntegrityError('simulated achievement failure')
        with patch('learning.gamification.AchievementEngine.evaluate_event', side_effect=fail), self.assertLogs('learning.events', level='ERROR'):
            event = self.record(award_xp=False)
        self.assertTrue(LearningEvent.objects.filter(pk=event.pk).exists())
        self.assertEqual(UserStats.objects.get(user=self.user).points, 0)

    @patch('learning.dashboard.credits.balance', return_value={'remaining': 10})
    def test_dashboard_matches_report_and_updates_cached_facts_without_provider_cost(self, balance):
        self.record(award_xp=False)
        context = dashboard.build_context(self.user)
        report = Evidence(self.user, 7).overview()
        self.assertEqual(context['sessions_this_week'], report['sessions'])
        self.assertEqual(context['questions_this_week'], report['attempted'])
        self.assertEqual(context['accuracy_this_week'], report['accuracy'])
        cached = DashboardMessage.objects.create(user=self.user, context=context,
            headline='Old', body='Old evidence', expires_at=self.now+timedelta(hours=1))
        expiry = cached.expires_at
        self.record(award_xp=False, total_count=10, correct_count=10)
        with patch('learning.dashboard._generate') as generate:
            result = dashboard.get_message(self.user)
            self.assertFalse(result['cached'])
            self.assertEqual(result['source'], 'fallback_updated')
            self.assertTrue(dashboard.get_message(self.user)['cached'])
        generate.assert_not_called()
        cached.refresh_from_db()
        self.assertEqual(cached.expires_at, expiry)
        self.assertEqual(cached.context['questions_this_week'], 13)
        self.assertIsNone(cached.context['weakest_topic'])

    def test_dashboard_stat_rail_does_not_read_stale_streak_counter(self):
        self.record(award_xp=False)
        UserStats.objects.filter(user=self.user).update(current_streak=999)
        req = APIRequestFactory().get('/api/test/')
        force_authenticate(req, self.user)
        with patch('learning.views.credits.balance', return_value={}), patch(
                'learning.views.practice.entitlement', return_value={}), patch(
                'learning.views.selection.coverage', return_value={}):
            response = views.dashboard_snapshot(req)
        self.assertEqual(response.data['streak'], 1)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class ActivityConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user('concurrent-activity')
        UserStats.objects.get_or_create(user=self.user)

    def race(self, worker, count=2):
        barrier = Barrier(count)
        def run(index):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                return worker(user, index)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(run, range(count)))

    def test_simultaneous_completion_creates_only_one_event_and_award(self):
        def work(user, index):
            return events.record(user, ActivityType.BRAIN_BATTLE_COMPLETED,
                resource_type='brain_battle', resource_id='one', correct_count=3,
                total_count=3, duration_seconds=60).pk
        result = self.race(work)
        self.assertEqual(result[0], result[1])
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(XPAward.objects.count(), 1)
        self.assertEqual(DailyStudySession.objects.get().minutes_studied, 1)
        self.assertEqual(UserStats.objects.get(user=self.user).points, XPAward.objects.get().amount)

    def test_simultaneous_distinct_events_preserve_points_minutes_and_daily_cap(self):
        def work(user, index):
            return events.record(user, ActivityType.QUESTION_ANSWERED,
                idempotency_key=f'work-{index}', correct_count=50, total_count=50, duration_seconds=180).pk
        self.race(work, 3)
        total = XPAward.objects.aggregate(total=Sum('amount'))['total']
        self.assertEqual(total, 120)
        stats = UserStats.objects.get(user=self.user)
        self.assertEqual(stats.points, total)
        self.assertEqual(stats.total_study_minutes, 9)
        self.assertEqual(DailyStudySession.objects.get().sessions_count, 3)

    def test_simultaneous_reward_retries_share_one_saved_decision(self):
        event = LearningEvent.objects.create(user=self.user, activity=ActivityType.RESOURCE_STUDIED)
        def work(user, index):
            saved = LearningEvent.objects.get(pk=event.pk)
            saved.user = user
            return xp.award_for_event(saved).pk
        result = self.race(work)
        self.assertEqual(result[0], result[1])
        self.assertEqual(XPAward.objects.count(), 1)

    def test_simultaneous_manual_log_replays_count_once(self):
        import uuid
        from curriculum.views import log_study_time
        request_id = str(uuid.uuid4())
        def work(user, index):
            request = APIRequestFactory().post('/api/test/',
                {'minutes': 5, 'request_id': request_id}, format='json')
            force_authenticate(request, user)
            response = log_study_time(request)
            self.assertEqual(response.status_code, 200, response.data)
            return response.data['total_overall']
        self.assertEqual(self.race(work), [5, 5])
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(DailyStudySession.objects.get().minutes_studied, 5)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 5)
        self.assertFalse(XPAward.objects.exists())
