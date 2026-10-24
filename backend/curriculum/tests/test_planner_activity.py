from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as dt_timezone
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import ScheduleItem
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.views import ScheduleItemViewSet
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, LearningEvent, XPAward


class PlannerFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.item = ScheduleItem.objects.create(user=self.user, slide=self.slide,
            title='Read chapter', activity_type='read', scheduled_date=timezone.localdate(), estimated_minutes=180)

    def request(self, action, data=None, method='post'):
        request = getattr(APIRequestFactory(), method)('/api/test/', data or {}, format='json')
        force_authenticate(request, self.user)
        kwargs = {} if action in ('today', 'upcoming', 'list', 'create') else {'pk': self.item.pk}
        return ScheduleItemViewSet.as_view({method: action})(request, **kwargs)


class PlannerActivityTests(PlannerFixture, TestCase):
    def test_checklist_completion_does_not_turn_estimated_minutes_into_study_time(self):
        result = self.request('complete')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertTrue(result.data['completed'])
        event = LearningEvent.objects.get()
        self.assertEqual(event.duration_seconds, 0)
        self.assertEqual(event.metadata['estimated_minutes'], 180)
        self.assertEqual(event.subject, self.slide.subject)
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 0)

    def test_retry_and_untick_retick_do_not_duplicate_activity_or_rewards(self):
        first = self.request('complete')
        reward = XPAward.objects.get()
        self.assertEqual(self.request('complete').data['completed_at'], first.data['completed_at'])
        self.assertFalse(self.request('uncomplete').data['completed'])
        self.assertTrue(self.request('complete').data['completed'])
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(XPAward.objects.get().pk, reward.pk)

    def test_old_planner_estimates_do_not_inflate_reports_or_rewrite_history(self):
        event = LearningEvent.objects.create(user=self.user, activity=ActivityType.PLANNER_TASK_COMPLETED,
            resource_type='schedule_item', resource_id=str(self.item.pk), duration_seconds=10800)
        LearningEvent.objects.create(user=self.user, activity=ActivityType.RESOURCE_STUDIED, duration_seconds=60)
        report = Evidence(self.user, 7).overview()
        self.assertEqual((report['sessions'], report['study_minutes']), (2, 1))
        event.refresh_from_db()
        self.assertEqual(event.duration_seconds, 10800)

    def test_failed_activity_write_rolls_back_checklist_and_can_be_retried(self):
        with patch('learning.events.record', side_effect=RuntimeError('simulated storage failure')):
            with self.assertRaises(RuntimeError):
                self.request('complete')
        self.item.refresh_from_db()
        self.assertFalse(self.item.completed)
        self.assertIsNone(self.item.completed_at)
        self.assertFalse(LearningEvent.objects.exists())
        self.assertEqual(self.request('complete').status_code, 200)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_ordinary_edit_cannot_bypass_the_completion_writer(self):
        response = self.request('partial_update', {'completed': True}, 'patch')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['completed'])
        self.assertFalse(LearningEvent.objects.exists())

    def test_old_class_planner_item_cannot_create_activity(self):
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(self.request('complete').status_code, 404)
        self.assertFalse(LearningEvent.objects.exists())

    def test_today_uses_the_activity_timezone_at_local_midnight(self):
        now = datetime(2026, 10, 21, 23, 30, tzinfo=dt_timezone.utc)
        self.item.scheduled_date = '2026-10-22'; self.item.save()
        with patch('django.utils.timezone.now', return_value=now):
            response = self.request('today', method='get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [self.item.pk])


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class PlannerConcurrencyTests(PlannerFixture, TransactionTestCase):
    def test_simultaneous_completions_share_one_timestamp_event_and_reward(self):
        barrier = Barrier(2)
        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                result = self.request('complete')
                self.assertEqual(result.status_code, 200, result.data)
                return result.data['completed_at']
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(run, range(2)))
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(XPAward.objects.count(), 1)
