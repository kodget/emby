from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import QuizAttempt, QuizAttemptResponse, UserStats
from curriculum.tests.test_bank_recovery import BankFixture
from learning.analytics import full_report
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, LearningEvent, WeakArea
from learning.views import analytics_report


class AnalyticsEvidenceTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        # Just after local midnight on October 20, still October 19 in UTC.
        self.now = datetime(2026, 10, 19, 23, 30, tzinfo=dt_timezone.utc)

    def event(self, **kwargs):
        values = dict(user=self.user, activity=ActivityType.RESOURCE_STUDIED, occurred_at=self.now,
                      duration_seconds=20)
        values.update(kwargs)
        return LearningEvent.objects.create(**values)

    def attempt(self, pk='saved', **kwargs):
        questions = [dict(id=f'q{i}', question_type='mcq', correct_option='B',
                          coverage_key='course:bank-subject', coverage_name='Anatomy') for i in range(3)]
        values = dict(id=pk, user=self.user, exam_type='mock', snapshot_class=self.user.profile.class_group,
                      subject=self.slide.subject, question_ids=[q['id'] for q in questions],
                      question_snapshots=questions, status='submitted', submitted_at=self.now,
                      mcq_total=3, mcq_score=999, overall_percentage=999)
        values.update(kwargs)
        attempt = QuizAttempt.objects.create(**values)
        QuizAttempt.objects.filter(pk=pk).update(started_at=self.now-timedelta(minutes=5))
        attempt.refresh_from_db()
        return attempt

    def report(self, days=7, detail=True):
        with patch('django.utils.timezone.now', return_value=self.now):
            return full_report(self.user, days, include_detail=detail)

    def test_calendar_window_includes_today_excludes_future_and_aggregates_short_sessions(self):
        self.event(); self.event()
        self.event(occurred_at=self.now+timedelta(minutes=1), duration_seconds=999)
        self.event(occurred_at=datetime(2026, 10, 13, 22, 59, tzinfo=dt_timezone.utc), duration_seconds=999)
        report = self.report()
        self.assertEqual(len(report['daily_activity']), 7)
        self.assertEqual(report['daily_activity'][0]['date'], '2026-10-14')
        self.assertEqual(report['daily_activity'][-1]['date'], '2026-10-20')
        self.assertEqual(report['daily_activity'][-1]['minutes'], .67)
        self.assertEqual(report['overview']['study_minutes'], .67)
        self.assertTrue(report['overview']['has_data'])
        self.assertIsNone(report['overview']['accuracy'])
        self.assertEqual(report['overview']['sessions'], 2)
        self.assertEqual(report['consistency']['active_days'], 1)

    def test_saved_answers_override_corrupt_counters_and_duplicate_events(self):
        attempt = self.attempt()
        QuizAttemptResponse.objects.create(attempt=attempt, snapshot_question_id='q0', selected_option='B', is_correct=False)
        QuizAttemptResponse.objects.create(attempt=attempt, snapshot_question_id='q1', selected_option='A', is_correct=True)
        for _ in range(2):
            self.event(activity=ActivityType.QUIZ_COMPLETED, resource_type='QuizAttempt', resource_id=attempt.pk,
                       correct_count=100, total_count=100, duration_seconds=1000)
        report = self.report()
        self.assertEqual(report['overview']['attempted'], 3)
        self.assertEqual(report['overview']['correct'], 1)
        self.assertEqual(report['overview']['sessions'], 1)
        self.assertEqual(report['overview']['study_minutes'], 5)
        self.assertEqual(report['by_assessment'][0]['label'], 'Mock exams')
        self.assertEqual(report['topics']['scope'], 'SUBJECT')
        self.assertEqual(report['topics']['weakest'][0]['accuracy'], .333)
        self.assertEqual(report['topics']['strongest'], [])
        self.assertEqual(LearningEvent.objects.count(), 2)  # Reporting is read-only.

    def test_historical_and_unsubmitted_attempts_are_not_scored_and_theory_is_not_a_fake_zero(self):
        self.attempt('historical', question_snapshots=[], snapshot_class=None, question_ids=[])
        self.attempt('active', status='in_progress')
        self.attempt('written', question_ids=['written'], question_snapshots=[dict(id='written', question_type='theory')],
                     theory_total=1, theory_grading_pending=True)
        report = self.report()
        self.assertEqual(report['overview']['attempted'], 0)
        self.assertIsNone(report['overview']['accuracy'])
        self.assertEqual(report['overview']['sessions'], 1)
        self.assertEqual(report['evidence']['historical_assessments_excluded'], 1)
        self.assertEqual(report['evidence']['assessments_awaiting_written_grades'], 1)

    def test_repeated_completions_deduplicate_but_repeated_reading_remains_activity(self):
        for _ in range(2):
            self.event(activity=ActivityType.BRAIN_BATTLE_COMPLETED, resource_type='brain_battle',
                       resource_id='battle1', total_count=4, correct_count=2)
            self.event(resource_type='slide', resource_id=self.slide.pk)
        report = self.report()
        self.assertEqual(report['overview']['sessions'], 3)
        self.assertEqual(report['overview']['attempted'], 4)

    def test_invalid_counts_future_events_and_self_ratings_cannot_inflate_accuracy(self):
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=1, correct_count=2)
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=-1)
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=1, duration_seconds=-5)
        self.event(activity=ActivityType.FLASHCARD_REVIEWED, total_count=1, correct_count=1)
        report = self.report()
        self.assertEqual(report['overview']['sessions'], 1)
        self.assertIsNone(report['overview']['accuracy'])
        self.assertIsNone(report['by_assessment'][0]['accuracy'])

    def test_streaks_come_from_evidence_in_local_date_order_not_stale_cached_stats(self):
        UserStats.objects.get_or_create(user=self.user)
        UserStats.objects.filter(user=self.user).update(current_streak=999, longest_streak=999)
        for offset in (0, 1, 2, 5, 6):
            self.event(occurred_at=self.now-timedelta(days=offset))
        report = self.report()
        self.assertEqual(report['consistency']['current_streak'], 3)
        self.assertEqual(report['consistency']['longest_streak'], 3)
        self.assertEqual(report['consistency']['active_days'], 5)
        self.assertLessEqual(report['consistency']['active_rate'], 1)

    def test_topic_window_does_not_reuse_lifetime_cache_or_label_good_results_as_weak(self):
        WeakArea.objects.create(user=self.user, scope='SUBJECT', subject=self.slide.subject,
                                label='OLD CACHE', attempted=900, correct=0, mastery=0)
        self.event(activity=ActivityType.QUESTION_ANSWERED, subject=self.slide.subject,
                   correct_count=10, total_count=10)
        self.event(activity=ActivityType.QUESTION_ANSWERED, subject=self.slide.subject,
                   correct_count=0, total_count=100, occurred_at=self.now-timedelta(days=90))
        report = self.report()
        self.assertEqual(report['topics']['weakest'], [])
        self.assertEqual(report['topics']['strongest'][0]['attempted'], 10)
        self.assertEqual(report['topics']['strongest'][0]['label'], 'Anatomy')

    def test_foreign_class_and_other_users_do_not_enter_report(self):
        from accounts.models import ClassGroup
        from curriculum.models import Subject
        from django.contrib.auth.models import User
        other = ClassGroup.objects.create(school=self.user.profile.class_group.school, set_name='Other', code='000222')
        foreign = Subject.objects.create(id='other-subject', name='PRIVATE SUBJECT', class_group=other)
        self.event(activity=ActivityType.QUESTION_ANSWERED, subject=foreign, total_count=100, correct_count=100)
        self.event(user=User.objects.create_user('other-student'), total_count=500, correct_count=500)
        self.attempt(snapshot_class=other, subject=foreign)
        report = self.report()
        self.assertEqual(report['overview']['sessions'], 0)
        self.assertNotIn('PRIVATE SUBJECT', str(report))

    def test_trend_uses_weighted_counts_and_requires_both_halves(self):
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=10, correct_count=5, occurred_at=self.now-timedelta(days=5))
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=9, correct_count=9)
        self.assertEqual(self.report()['improvement']['direction'], 'insufficient_data')
        self.event(activity=ActivityType.QUESTION_ANSWERED, total_count=1, correct_count=0)
        trend = self.report()['improvement']
        self.assertEqual(trend['direction'], 'up')
        self.assertEqual(trend['change'], .4)

    def test_free_api_reports_evidence_without_premium_topics_and_normalizes_bad_period(self):
        self.event()
        request = APIRequestFactory().get('/api/learning/analytics/', {'days': 'bad'})
        force_authenticate(request, self.user)
        with patch('django.utils.timezone.now', return_value=self.now):
            response = analytics_report(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['window_days'], 30)
        self.assertNotIn('topics', response.data)
        self.assertIn('evidence', response.data)
        self.assertEqual(response.data['evidence']['timezone'], 'Africa/Lagos')
