from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.serializers import ProfileSerializer, ClassMemberSerializer
from accounts.views import get_class_members
from curriculum import views as curriculum_views
from curriculum.models import Block, SubBlock, Topic, QuizAttempt, QuizAttemptResponse, UserStats, QuizQuestion
from curriculum.serializers import UserStatsSerializer
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.tests.test_mock_attempts import MockFixture
from learning import analytics, views, selection
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, LearningEvent, WeakArea, QuestionExposure


class ProgressSurfaceTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.block = Block.objects.create(id='progress-block', name='Upper limb', subject=self.slide.subject)
        self.sub = SubBlock.objects.create(id='progress-sub', name='Hand', block=self.block)
        self.topic = Topic.objects.create(id='progress-topic', name='Bones', block=self.block, sub_block=self.sub)
        self.stats, _ = UserStats.objects.get_or_create(user=self.user)
        UserStats.objects.filter(pk=self.stats.pk).update(current_streak=999, longest_streak=999,
            total_study_minutes=999, quizzes_taken=999, slides_completed=999, last_activity_date=timezone.localdate())
        self.stats.refresh_from_db()
        self.user.stats = self.stats

    def event(self, **changes):
        data = dict(user=self.user, activity=ActivityType.QUESTION_ANSWERED, topic=self.topic,
                    correct_count=1, total_count=4, duration_seconds=20, occurred_at=self.now)
        data.update(changes)
        return LearningEvent.objects.create(**data)

    def request(self, handler, data=None, action=None):
        request = APIRequestFactory().get('/api/test/', data or {})
        force_authenticate(request, self.user)
        return handler.as_view({'get': action})(request) if action else handler(request)

    def test_profile_roster_stats_and_badges_share_evidence_streaks_without_rewriting_caches(self):
        for offset in (0, 1, 2):
            self.event(occurred_at=self.now-timedelta(days=offset))
        self.user.profile.streak = 777
        self.user.profile.save()
        self.assertEqual(ProfileSerializer(self.user.profile).data['streak'], 3)
        self.assertEqual(ClassMemberSerializer(self.user.profile).data['streak_days'], 3)
        stats = UserStatsSerializer(self.stats).data
        self.assertEqual(stats['current_streak'], 3)
        self.assertEqual(stats['longest_streak'], 3)
        self.assertEqual(stats['total_study_minutes'], 1)
        self.assertEqual(stats['quizzes_taken'], 0)
        self.assertEqual(stats['slides_completed'], 0)
        self.assertEqual(self.request(views.gamification_profile).data['current_streak'], 3)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.total_study_minutes, 999)

    def test_stats_serializer_reuses_one_evidence_read_and_rejects_client_counters(self):
        with patch('learning.progress_evidence.Evidence', wraps=Evidence) as evidence:
            serializer = UserStatsSerializer(self.stats)
            serializer.data
        evidence.assert_called_once()
        change = UserStatsSerializer(self.stats, data={'points': 100000, 'rank': 1,
            'total_study_minutes': 123, 'current_streak': 55, 'public_profile': False}, partial=True)
        self.assertTrue(change.is_valid(), change.errors)
        change.save()
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.points, 0)
        self.assertEqual(self.stats.total_study_minutes, 999)
        self.assertFalse(self.stats.public_profile)
        request = APIRequestFactory().post('/api/test/', {'points': 500}, format='json')
        force_authenticate(request, self.user)
        response = curriculum_views.UserStatsViewSet.as_view({'post': 'award_points'})(request)
        self.assertEqual(response.status_code, 403)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.points, 0)

    def test_weak_area_period_ignores_lifetime_cache_and_excludes_strong_results(self):
        WeakArea.objects.create(user=self.user, scope='TOPIC', topic=self.topic,
                                label='Wrong cache', attempted=900, correct=0, mastery=0)
        self.event(total_count=10, correct_count=10)
        self.event(total_count=100, correct_count=0, occurred_at=self.now-timedelta(days=60))
        response = self.request(views.weak_areas, {'scope': 'TOPIC', 'days': 30}).data
        self.assertEqual(response['weakest'], [])
        self.assertEqual(response['strongest'][0]['label'], 'Bones')
        self.assertEqual(response['strongest'][0]['attempted'], 10)
        self.assertTrue(response['has_data'])
        older = self.request(views.weak_areas, {'scope': 'TOPIC', 'days': 90}).data
        self.assertEqual(older['weakest'][0]['attempted'], 110)
        self.assertEqual(older['strongest'], [])

    def test_topic_evidence_rolls_up_to_each_requested_authorized_parent(self):
        self.event()
        for scope, label in [('TOPIC', 'Bones'), ('SUB_BLOCK', 'Hand'), ('BLOCK', 'Upper limb'), ('SUBJECT', 'Anatomy')]:
            result = self.request(views.weak_areas, {'scope': scope}).data
            self.assertEqual(result['tracked_nodes'], 1)
            self.assertEqual(result['weakest'][0]['label'], label)
            self.assertEqual(result['weakest'][0]['attempted'], 4)
        self.assertEqual(self.request(views.weak_areas, {'scope': 'nonsense'}).status_code, 400)

    def test_sparse_evidence_is_neither_a_strength_nor_a_weakness(self):
        self.event(correct_count=0, total_count=2)
        result = self.request(views.weak_areas).data
        self.assertEqual(result['weakest'], [])
        self.assertEqual(result['strongest'], [])
        self.assertFalse(result['has_data'])

    def test_saved_results_drive_completed_count_and_recommendations_not_stale_answers(self):
        attempt = QuizAttempt.objects.create(id='progress-snapshot', user=self.user, exam_type='mock',
            snapshot_class=self.user.profile.class_group, status='submitted', submitted_at=self.now,
            question_ids=['a', 'b'], question_snapshots=[{'id': key, 'question_type': 'mcq', 'correct_option': 'B'} for key in ('a', 'b')],
            subject=self.slide.subject, analysis_data={'insights': ['Invented old prediction']})
        QuizAttemptResponse.objects.create(attempt=attempt, snapshot_question_id='a', selected_option='A', is_correct=True)
        QuizAttempt.objects.create(id='unverified-history', user=self.user, exam_type='practice',
                                  status='submitted', submitted_at=self.now+timedelta(seconds=1))
        self.assertEqual(UserStatsSerializer(self.stats).data['quizzes_taken'], 1)
        result = self.request(curriculum_views.ai_study_recommendations).data
        self.assertEqual(result['missed_count'], 2)
        self.assertIsNone(result['insights'])

    def test_class_roster_rank_is_local_deterministic_and_uses_evidence_streak(self):
        peer = User.objects.create_user('roster-peer')
        peer.profile.class_group = self.user.profile.class_group; peer.profile.save()
        UserStats.objects.update_or_create(user=peer, defaults={'points': 20, 'rank': 999})
        UserStats.objects.filter(pk=self.stats.pk).update(points=20, rank=888)
        self.event()
        response = self.request(get_class_members)
        self.assertEqual([row['user']['id'] for row in response.data], [self.user.pk, peer.pk])
        self.assertEqual([row['rank'] for row in response.data], [1, 2])
        self.assertEqual([row['streak_days'] for row in response.data], [1, 0])

    def test_class_roster_streak_queries_are_batched_and_match_activity_evidence(self):
        self.event(occurred_at=self.now)
        with CaptureQueriesContext(connection) as single_member:
            self.request(get_class_members)

        peers = []
        for index in range(6):
            peer = User.objects.create_user(f'roster-batch-{index}')
            peer.profile.class_group = self.user.profile.class_group
            peer.profile.save()
            peers.append(peer)
        for offset in (0, 1, 2):
            LearningEvent.objects.create(
                user=peers[0], activity=ActivityType.QUESTION_ANSWERED,
                correct_count=1, total_count=1, duration_seconds=0,
                occurred_at=self.now - timedelta(days=offset),
            )
        LearningEvent.objects.create(
            user=peers[1], activity=ActivityType.QUESTION_ANSWERED,
            correct_count=1, total_count=1, duration_seconds=0,
            occurred_at=self.now - timedelta(days=3),
        )

        with CaptureQueriesContext(connection) as class_roster:
            response = self.request(get_class_members)

        self.assertLessEqual(len(class_roster), len(single_member) + 2)
        by_user = {row['user']['id']: row['streak_days'] for row in response.data}
        for user in [self.user, *peers]:
            expected = Evidence(user, 7, now=self.now).consistency()['current_streak']
            self.assertEqual(by_user[user.pk], expected)

    def test_class_roster_collapses_large_activity_history_to_local_activity_days(self):
        LearningEvent.objects.bulk_create([
            LearningEvent(
                user=self.user,
                activity=ActivityType.QUESTION_ANSWERED,
                correct_count=1,
                total_count=1,
                duration_seconds=0,
                occurred_at=self.now - timedelta(days=index % 3),
            )
            for index in range(10000)
        ])

        with CaptureQueriesContext(connection) as queries:
            response = self.request(get_class_members)

        event_queries = [
            query['sql'] for query in queries
            if LearningEvent._meta.db_table.lower() in query['sql'].lower()
        ]
        self.assertTrue(event_queries)
        self.assertTrue(any('DISTINCT' in query.upper() for query in event_queries))
        self.assertEqual(response.data[0]['streak_days'], 3)


class BankCoverageTests(MockFixture, TestCase):
    def test_coverage_matches_usable_mcqs_and_ignores_held_invalid_and_theory_rows(self):
        questions = list(QuizQuestion.objects.filter(question_type='mcq').order_by('pk'))
        held, broken, seen = questions[:3]
        held.needs_review = True; held.save()
        broken.option_b = broken.option_a; broken.save()
        for q in (held, broken, seen):
            QuestionExposure.objects.create(user=self.user, question=q, times_seen=1, times_answered=1, times_incorrect=1)
        report = analytics.question_bank(self.user)
        self.assertEqual(report, {'total': 13, 'seen': 1, 'unseen': 12, 'answered': 1, 'missed': 1, 'percent_seen': 8})
        self.assertEqual(report, selection.coverage(self.user, question_type='mcq'))
        self.assertEqual(sum(len(pool['mcq']) for pool in __import__('curriculum.mock_attempts', fromlist=['pools']).pools(
            self.user, {'subject': self.slide.subject}).values()), 13)

    def test_stale_generated_bank_and_old_exposure_do_not_count_as_available(self):
        question = QuizQuestion.objects.filter(question_type='mcq').first()
        QuestionExposure.objects.create(user=self.user, question=question, times_seen=20)
        self.slide.file_url = 'https://storage.invalid/replaced.pdf'; self.slide.save()
        self.assertEqual(analytics.question_bank(self.user)['total'], 0)
        self.assertEqual(analytics.question_bank(self.user)['seen'], 0)

    def test_duplicate_saved_stems_count_once_and_preserve_seen_status(self):
        question = QuizQuestion.objects.filter(question_type='mcq').first()
        question.pk = 'duplicate'; question.save(force_insert=True)
        QuestionExposure.objects.create(user=self.user, question=question, times_seen=1)
        bank = analytics.question_bank(self.user)
        self.assertEqual(bank['total'], 15)
        self.assertEqual(bank['seen'], 1)

    def test_coverage_excludes_bad_source_ancestry_and_held_manual_rows(self):
        self.manual('held-manual', needs_review=True)
        other = SubBlock.objects.create(id='other-sub', name='Other', block=self.block)
        self.manual('wrong-source', source_slide=self.slide, sub_block=other)
        self.assertEqual(analytics.question_bank(self.user)['total'], 15)

    def test_deck_practice_availability_also_excludes_invalid_saved_question(self):
        question = QuizQuestion.objects.filter(question_type='mcq', difficulty='medium').first()
        question.correct_option = 'X'; question.save()
        result = self.api('practice_options', {'slide': self.slide.pk}, method='get').data
        self.assertEqual(result['available']['medium'], 4)
