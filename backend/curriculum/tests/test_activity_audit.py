import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from curriculum.models import UserStats, DailyStudySession, QuizAttempt
from curriculum.tests.test_bank_recovery import BankFixture
from learning.activity_audit import report
from learning.models import ActivityType, LearningEvent, WeakArea, XPAward


class ActivityAuditTests(BankFixture, TestCase):
    def event(self, **changes):
        values = dict(user=self.user, activity=ActivityType.RESOURCE_STUDIED, duration_seconds=30)
        values.update(changes)
        return LearningEvent.objects.create(**values)

    def test_audit_reports_cache_differences_and_duplicates_without_writing(self):
        UserStats.objects.update_or_create(user=self.user, defaults={'points': 123, 'current_streak': 99,
            'longest_streak': 99, 'total_study_minutes': 900})
        DailyStudySession.objects.create(user=self.user, date=timezone.localdate(), minutes_studied=900)
        self.event(); self.event()
        for _ in range(2):
            event = self.event(activity=ActivityType.BRAIN_BATTLE_COMPLETED, resource_type='brain_battle',
                resource_id='duplicate', total_count=3, correct_count=2, duration_seconds=60)
            WeakArea.objects.create(user=self.user, scope='SUBJECT', subject=self.slide.subject,
                label='Historical cache', attempted=3, correct=2)
        for _ in range(2):
            XPAward.objects.create(user=self.user, event=event, reason=event.activity, amount=10,
                                  base_amount=10, multiplier=1)
        self.event(correct_count=2, total_count=1)
        self.event(occurred_at=timezone.now()+timedelta(days=2))
        with CaptureQueriesContext(connection) as queries:
            result = report(self.user)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in queries))
        self.assertTrue(result['dry_run'])
        self.assertEqual(result['observed']['study_minutes'], 2)
        self.assertEqual(result['observed']['sessions'], 3)
        self.assertEqual(result['cached']['study_minutes'], 900)
        for field in ('duplicate_completion_rows', 'duplicate_weak_area_rows', 'duplicate_reward_rows',
                      'future_activity_rows', 'invalid_activity_rows'):
            self.assertEqual(result[field], 1, field)
        self.assertEqual(len(result['daily_differences']), 1)
        self.assertEqual(UserStats.objects.get(user=self.user).points, 123)
        self.assertEqual(LearningEvent.objects.count(), 6)

    def test_audit_distinguishes_historical_attempts_from_missing_completion_events(self):
        for pk, snapshots in [('old', []), ('saved', [{'id': 'q', 'question_type': 'mcq', 'correct_option': 'A'}])]:
            QuizAttempt.objects.create(id=pk, user=self.user, exam_type='mock',
                subject=self.slide.subject, snapshot_class=self.slide.class_group if snapshots else None,
                question_snapshots=snapshots, question_ids=[q['id'] for q in snapshots],
                status='submitted', submitted_at=timezone.now())
        result = report(self.user)
        self.assertEqual(result['historical_assessments_without_snapshots'], 1)
        self.assertEqual(result['saved_assessments_without_completion_event'], 1)
        self.event(activity=ActivityType.QUIZ_COMPLETED, resource_type='QuizAttempt', resource_id='saved')
        self.assertEqual(report(self.user)['saved_assessments_without_completion_event'], 0)

    def test_command_audits_only_explicit_users_and_has_no_apply_mode(self):
        output = StringIO()
        call_command('audit_activity', '--user-id', str(self.user.pk), stdout=output)
        result = json.loads(output.getvalue())
        self.assertTrue(result['dry_run'])
        self.assertEqual([row['user_id'] for row in result['reports']], [self.user.pk])
        self.assertIsNone(result['reports'][0]['cached'])
        with self.assertRaises(CommandError):
            call_command('audit_activity', '--user-id', '999999999', stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('audit_activity', '--user-id', str(self.user.pk), '--apply', stdout=StringIO())
