from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import SpotStation
from curriculum.tests.test_bank_recovery import BankFixture
from learning import practice, views
from learning.analytics import full_report
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, LearningEvent, PracticeAttempt, PracticeMode, PracticeSession, PracticeRoundUsage, XPAward


class ImageFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.station = SpotStation.objects.create(id='image-one', is_shared=True, is_approved=True,
            prompt='Identify this structure', image_url='/test.jpg', accepted_answers=['ulnar nerve'],
            supporting_question={'enabled': True, 'question': 'Choose', 'options': ['A', 'B'], 'correct_index': 1},
            true_false_question={'enabled': True, 'statement': 'Statement', 'answer': False})

    def start(self):
        return practice.start_session(self.user, PracticeMode.STEEPLECHASE, [], 5)

    def answer(self, session, **kwargs):
        values = dict(main_answer='ulnar', supporting_choice=1, true_false_answer=False, seconds_taken=20)
        values.update(kwargs)
        return practice.submit_attempt(session, self.station.pk, **values)


class ImagePracticeEvidenceTests(ImageFixture, TestCase):
    def test_catalogue_edits_do_not_change_presented_questions_grading_or_reveal(self):
        session = self.start()
        self.station.prompt = 'Changed question'
        self.station.accepted_answers = ['median nerve']
        self.station.supporting_question = {'enabled': False}
        self.station.true_false_question = {'enabled': False}
        self.station.save()
        req = APIRequestFactory().get('/api/test/')
        force_authenticate(req, self.user)
        payload = views.practice_station(req, session.pk, 0).data
        self.assertEqual(payload['main']['question'], 'Identify this structure')
        self.assertNotIn('accepted_answers', payload)
        self.assertNotIn('correct_index', payload['supporting'])
        reveal = self.answer(session)
        self.assertTrue(reveal['main']['correct'])
        self.assertEqual(reveal['main']['answer'], 'ulnar nerve')
        self.assertTrue(reveal['true_false']['correct'])
        self.assertEqual(practice.complete_session(session)['score'], 1)

    def test_skipped_questions_and_stations_are_in_the_denominator(self):
        SpotStation.objects.create(id='image-two', is_shared=True, is_approved=True,
            prompt='Second', image_url='/second.jpg', accepted_answers=['heart'])
        session = self.start()
        self.answer(session, supporting_choice=None, true_false_answer=None)
        result = practice.complete_session(session)
        self.assertEqual(result['score'], .25)  # 1 correct / 4 presented items
        event = LearningEvent.objects.get(resource_type='practice_session')
        self.assertEqual((event.correct_count, event.total_count), (1, 4))
        self.assertEqual(Evidence(self.user, 7).overview()['accuracy'], .25)
        self.assertEqual(sum(v['attempted'] for v in result['section_breakdown'].values()), 2)

    def test_answer_replays_and_late_timeouts_cannot_change_a_revealed_answer(self):
        session = self.start()
        first = self.answer(session, main_answer='wrong')
        for values in ({}, {'main_answer': '', 'timed_out': True}):
            self.assertEqual(self.answer(session, **values), first)
        practice.complete_session(session)
        self.assertEqual(self.answer(session), first)
        answer = PracticeAttempt.objects.get()
        self.assertEqual(answer.main_answer, 'wrong')
        self.assertFalse(answer.timed_out)

    def test_stale_session_completion_does_not_repeat_event_rewards_or_timestamp(self):
        session = self.start()
        self.answer(session)
        first = practice.complete_session(session)
        second = practice.complete_session(session)
        self.assertEqual(first['completed_at'], second['completed_at'])
        self.assertEqual(LearningEvent.objects.filter(resource_type='practice_session').count(), 1)
        self.assertEqual(XPAward.objects.count(), 1)

    def test_report_uses_weighted_saved_answers_even_without_events_and_with_corrupt_caches(self):
        one = self.start()
        self.answer(one)
        practice.complete_session(one)
        self.station.supporting_question = {}; self.station.true_false_question = {}; self.station.save()
        two = self.start()
        self.answer(two, main_answer='wrong', supporting_choice=None, true_false_answer=None)
        practice.complete_session(two)
        LearningEvent.objects.all().delete()
        PracticeSession.objects.update(score=99, total_stations=999, main_correct=999)
        PracticeAttempt.objects.update(main_correct=False, supporting_correct=False, true_false_correct=False)
        report = full_report(self.user, 7)
        summary = report['practice'][PracticeMode.STEEPLECHASE]
        self.assertEqual(summary['average_accuracy'], .75)  # 3/4, not (1+0)/2
        self.assertEqual((summary['rounds'], summary['stations'], summary['scored_items']), (2, 2, 4))
        self.assertEqual(report['overview']['accuracy'], .75)
        self.assertEqual(report['overview']['study_minutes'], .67)
        for _ in range(2):
            LearningEvent.objects.create(user=self.user, activity=ActivityType.STEEPLECHASE_COMPLETED,
                resource_type='practice_session', resource_id=str(one.pk), total_count=100, correct_count=100)
        self.assertEqual(full_report(self.user, 7)['overview'], report['overview'])

    def test_historical_round_is_activity_but_unverifiable_score_is_not_accuracy(self):
        session = PracticeSession.objects.create(user=self.user, mode=PracticeMode.STEEPLECHASE,
            station_ids=[self.station.pk], total_stations=1, status='completed',
            completed_at=timezone.now(), score=1)
        PracticeAttempt.objects.create(session=session, station=self.station, main_correct=True, seconds_taken=30)
        report = full_report(self.user, 7)
        self.assertEqual(report['overview']['sessions'], 1)
        self.assertIsNone(report['overview']['accuracy'])
        self.assertEqual(report['evidence']['historical_image_rounds_excluded_from_accuracy'], 1)
        self.assertEqual(report['practice'][PracticeMode.STEEPLECHASE]['historical_rounds_excluded_from_accuracy'], 1)
        session.refresh_from_db()
        self.assertEqual(session.score, 1)  # No historical rewrite or invented versions.

    def test_future_open_abandoned_and_revoked_sessions_cannot_enter_report(self):
        session = self.start()
        self.answer(session)
        for state, end in (('in_progress', None), ('abandoned', timezone.now()),
                           ('completed', timezone.now()+timedelta(days=1))):
            PracticeSession.objects.filter(pk=session.pk).update(status=state, completed_at=end)
            self.assertEqual(Evidence(self.user, 7).overview()['sessions'], 0)
        PracticeSession.objects.filter(pk=session.pk).update(status='completed', completed_at=timezone.now())
        self.station.needs_review = True; self.station.save()
        self.assertEqual(Evidence(self.user, 7).overview()['sessions'], 0)
        with self.assertRaises(practice.PracticeError):
            practice.results(session)

    def test_bad_answer_shapes_are_rejected_without_recording_an_answer(self):
        session = self.start()
        for data in ({'true_false_answer': 'false'}, {'supporting_choice': True},
                     {'supporting_choice': 9}, {'seconds_taken': -1}, {'timed_out': 'false'},
                     {'main_answer': ['ulnar']}):
            req = APIRequestFactory().post('/api/test/', {'station_id': self.station.pk, **data}, format='json')
            force_authenticate(req, self.user)
            response = views.practice_answer(req, session.pk)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(PracticeAttempt.objects.exists())

    def test_histology_uses_the_same_saved_scoring_with_its_own_summary(self):
        self.station.kind = SpotStation.Kind.HISTOLOGY; self.station.save()
        session = practice.start_session(self.user, PracticeMode.HISTOLOGY, [], 1)
        self.answer(session)
        practice.complete_session(session)
        report = full_report(self.user, 7)
        self.assertEqual(report['practice'][PracticeMode.HISTOLOGY]['average_accuracy'], 1)
        self.assertEqual(report['practice'][PracticeMode.STEEPLECHASE]['rounds'], 0)
        self.assertEqual(report['by_assessment'][0]['label'], 'Histology')

    def test_unrelated_attempt_and_duplicate_station_lists_are_not_accepted_history(self):
        session = self.start()
        extra = SpotStation.objects.create(id='unrelated', is_shared=True, is_approved=True,
            prompt='Unrelated', image_url='/extra.jpg', accepted_answers=['heart'])
        PracticeAttempt.objects.create(session=session, station=extra)
        self.assertFalse(practice.visible_sessions(self.user).exists())
        with self.assertRaises(practice.PracticeError):
            practice.results(session)
        PracticeAttempt.objects.all().delete()
        session.station_ids = [self.station.pk, self.station.pk]; session.save()
        self.assertFalse(practice.visible_sessions(self.user).exists())

    def test_incomplete_saved_version_is_excluded_instead_of_crashing_report(self):
        session = self.start()
        self.answer(session)
        practice.complete_session(session)
        PracticeSession.objects.filter(pk=session.pk).update(station_snapshots=[{'id': self.station.pk}])
        report = full_report(self.user, 7)
        self.assertIsNone(report['overview']['accuracy'])
        self.assertEqual(report['evidence']['historical_image_rounds_excluded_from_accuracy'], 1)

    def test_invalid_catalogue_question_does_not_consume_a_round(self):
        self.station.supporting_question = {'enabled': True, 'correct_index': 999}
        self.station.save()
        with self.assertRaises(practice.PracticeError):
            self.start()
        self.assertFalse(PracticeSession.objects.exists())
        self.assertFalse(PracticeRoundUsage.objects.exists())


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class ImagePracticeConcurrencyTests(ImageFixture, TransactionTestCase):
    def race(self, work):
        barrier = Barrier(2)
        def run(index):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                return work(user, index)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_simultaneous_answers_preserve_first_decision(self):
        session = self.start()
        def work(user, index):
            row = PracticeSession.objects.get(pk=session.pk)
            return practice.submit_attempt(row, self.station.pk, main_answer='ulnar' if index else 'wrong')
        rows = self.race(work)
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(PracticeAttempt.objects.count(), 1)

    def test_simultaneous_completions_emit_one_result_and_reward(self):
        session = self.start()
        self.answer(session)
        rows = self.race(lambda user, _: practice.complete_session(PracticeSession.objects.get(pk=session.pk)))
        self.assertEqual(rows[0]['completed_at'], rows[1]['completed_at'])
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(XPAward.objects.count(), 1)

    def test_last_free_round_cannot_be_consumed_twice(self):
        PracticeRoundUsage.objects.create(user=self.user, mode=PracticeMode.STEEPLECHASE,
            period=practice._period(), rounds_used=4)
        def work(user, index):
            try:
                practice.start_session(user, PracticeMode.STEEPLECHASE, [], 1)
                return 'started'
            except practice.LimitReached:
                return 'limited'
        self.assertCountEqual(self.race(work), ['started', 'limited'])
        self.assertEqual(PracticeSession.objects.count(), 1)
        self.assertEqual(PracticeRoundUsage.objects.get().rounds_used, 5)
