from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.tests.test_bank_recovery import BankFixture, mcq, TEXT
from curriculum.models import QuizAttempt, QuizQuestion, QuizAttemptResponse
from curriculum.quiz_views import QuizAttemptViewSet
from learning import generation as gen
from learning.models import LearningEvent


class PracticeFixture(BankFixture):
    def setUp(self):
        super().setUp()
        job = gen.claim_job(self.slide)
        for difficulty in ('easy', 'medium', 'hard'):
            gen.save_batch(job, self.slide, [mcq(f'{difficulty}-{i}', difficulty) for i in range(5)], TEXT, 'mcq', difficulty, 5)
        self.payload = {'slide': self.slide.pk, 'exam_type': 'practice', 'is_timed': False,
                        'configuration': {'mcq_count': 5, 'theory_count': 0, 'difficulty': 'medium'}}

    def api(self, action='create', data=None, pk=None, method='post', user=None):
        req = getattr(APIRequestFactory(), method)('/api/test/', data or {}, format='json')
        force_authenticate(req, user or self.user)
        return QuizAttemptViewSet.as_view({method: action})(req, **({'pk': pk} if pk else {}))

    def create(self, **overrides):
        response = self.api(data={**self.payload, **overrides})
        self.assertEqual(response.status_code, 201, response.data)
        return response.data


class DeckPracticeTests(PracticeFixture, TestCase):
    def test_another_same_class_deck_never_fills_the_shortage(self):
        from curriculum.models import Slide
        other = Slide.objects.create(id='sibling-deck', title='Sibling', file_type='pdf', subject=self.slide.subject,
                                     class_group=self.slide.class_group, uploaded_by=self.user)
        question = QuizQuestion.objects.filter(difficulty='medium').first()
        question.pk = 'sibling-question'; question.source_slide = other
        question.question_text = 'Question from a different deck'; question.save(force_insert=True)
        self.assertEqual(self.api('practice_options', {'slide': self.slide.pk}, method='get').data['available']['medium'], 5)
        self.assertNotIn(question.pk, self.create()['question_ids'])

    def test_another_student_cannot_read_answer_or_submit_an_attempt(self):
        from django.contrib.auth.models import User
        peer = User.objects.create_user('practice-peer')
        peer.profile.class_group = self.slide.class_group; peer.profile.save()
        data = self.create()
        for action, method in [('retrieve', 'get'), ('answer', 'post'), ('submit', 'post'), ('result', 'get')]:
            self.assertEqual(self.api(action, pk=data['id'], method=method, user=peer).status_code, 404)

    def test_failed_completion_rolls_back_score_and_awards_before_retry(self):
        data = self.create(); pk = data['id']
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'B'}, pk)
        from curriculum.models import UserStats
        UserStats.objects.get_or_create(user=self.user)
        self.user.stats.refresh_from_db()
        initial = self.user.stats.points, self.user.stats.quizzes_taken
        with patch('learning.events.record', side_effect=RuntimeError('unavailable')), self.assertRaises(RuntimeError):
            self.api('submit', pk=pk)
        attempt = QuizAttempt.objects.get(pk=pk)
        self.assertEqual(attempt.status, 'in_progress')
        self.assertIsNone(attempt.submitted_at)
        self.user.stats.refresh_from_db()
        self.assertEqual((self.user.stats.points, self.user.stats.quizzes_taken), initial)
        self.assertEqual(self.api('submit', pk=pk).data['mcq_score'], 1)
        self.assertEqual(LearningEvent.objects.filter(resource_id=pk).count(), 1)

    def test_exact_saved_scope_and_difficulty_with_no_generation_or_debit(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, patch('curriculum.services.ai_question_generator.AIQuestionGenerator.generate_mcqs_from_text') as provider:
            data = self.create()
        queue.assert_not_called(); provider.assert_not_called()
        self.assertEqual(len(set(data['question_ids'])), 5)
        self.assertTrue(all(q['difficulty'] == 'medium' for q in data['questions']))
        self.assertNotIn('correct_option', data['questions'][0])
        self.assertNotIn('source_text', data['questions'][0])
        self.assertNotIn('question_snapshots', data)

    def test_missing_scope_wrong_scope_and_foreign_class_are_rejected(self):
        self.assertEqual(self.api(data={**self.payload, 'slide': None}).status_code, 400)
        from curriculum.models import Subject
        other = Subject.objects.create(id='another', name='Another', class_group=self.slide.class_group)
        self.assertEqual(self.api(data={**self.payload, 'subject': other.pk}).status_code, 400)
        from django.contrib.auth.models import User
        outsider = User.objects.create_user('outsider')
        self.assertEqual(self.api(data=self.payload, user=outsider).status_code, 404)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_strict_input_validation_creates_no_attempt(self):
        for count in (0, -1, 21, True, '5', 1.2, None):
            with self.subTest(count=count):
                self.assertEqual(self.api(data={**self.payload, 'configuration': {**self.payload['configuration'], 'mcq_count': count}}).status_code, 400)
        for config in ([], 'bad', {'mcq_count': 5, 'theory_count': 1}, {'difficulty': 'all'}, {'question_source': 'weak_areas'}):
            self.assertEqual(self.api(data={**self.payload, 'configuration': config}).status_code, 400)
        for extras in ({'is_timed': 'false'}, {'is_timed': True}, {'is_timed': True, 'duration_minutes': True}, {'duration_minutes': 10}):
            self.assertEqual(self.api(data={**self.payload, **extras}).status_code, 400)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_shortage_returns_exact_available_count_never_other_difficulty(self):
        response = self.api(data={**self.payload, 'configuration': {**self.payload['configuration'], 'mcq_count': 6}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(int(response.data['available']), 5)
        self.assertFalse(QuizAttempt.objects.exists())
        self.assertEqual(self.api('practice_options', {'slide': self.slide.pk}, method='get').data['available'], {'easy': 5, 'medium': 5, 'hard': 5})

    def test_review_hold_stale_bank_and_duplicate_stems_are_excluded(self):
        qs = QuizQuestion.objects.filter(difficulty='medium')
        questions = list(qs)
        QuizQuestion.objects.filter(pk=questions[0].pk).update(needs_review=True)
        QuizQuestion.objects.filter(pk=questions[1].pk).update(question_text=questions[2].question_text)
        self.assertEqual(self.api('practice_options', {'slide': self.slide.pk}, method='get').data['available']['medium'], 3)
        self.slide.file_url = 'https://storage.invalid/new.pdf'; self.slide.save()
        self.assertEqual(self.api('practice_options', {'slide': self.slide.pk}, method='get').data['available']['medium'], 0)

    def test_answers_survive_reload_hide_keys_and_score_from_original_version(self):
        data = self.create(); pk, qid = data['id'], data['question_ids'][0]
        self.assertEqual(self.api('answer', {'question_id': qid, 'selected_option': 'B'}, pk).status_code, 200)
        QuizQuestion.objects.filter(pk=qid).update(correct_option='A', question_text='Edited after start')
        reloaded = self.api('retrieve', pk=pk, method='get').data
        self.assertEqual(reloaded['questions'], data['questions'])
        self.assertEqual(reloaded['responses'][0]['selected_option'], 'B')
        self.assertNotIn('is_correct', reloaded['responses'][0])
        self.assertNotIn('correct_option', reloaded['responses'][0]['question'])
        self.assertEqual(self.api('missed', pk=pk, method='get').status_code, 400)
        self.assertEqual(self.api('result', pk=pk, method='get').status_code, 400)
        # Do not trust even a corrupted cached correctness flag when submitting.
        QuizAttemptResponse.objects.filter(attempt_id=pk).update(is_correct=False)
        result = self.api('submit', pk=pk)
        self.assertEqual(result.data['mcq_score'], 1)
        self.assertEqual(result.data['overall_percentage'], 20)
        self.assertEqual(self.api('submit', pk=pk).data, result.data)
        self.assertEqual(LearningEvent.objects.filter(resource_id=pk).count(), 1)
        final = self.api('result', pk=pk, method='get').data
        self.assertEqual(final['questions'][0]['correct_option'], 'B')
        self.assertTrue(final['responses'][0]['is_correct'])
        self.assertEqual(self.api('missed', pk=pk, method='get').data['total_missed'], 4)
        self.assertEqual(self.api('answer', {'question_id': qid, 'selected_option': 'A'}, pk).status_code, 400)

    def test_invalid_options_and_unselected_questions_cannot_be_answered_or_flagged(self):
        data = self.create(); pk = data['id']
        for option in ('E', 'b', ['A'], True):
            self.assertEqual(self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': option}, pk).status_code, 400)
        other = QuizQuestion.objects.filter(difficulty='hard').first()
        self.assertEqual(self.api('answer', {'question_id': other.pk, 'selected_option': 'B'}, pk).status_code, 400)
        self.assertEqual(self.api('flag', {'question_id': other.pk}, pk).status_code, 400)
        self.assertFalse(QuizAttemptResponse.objects.exists())

    def test_flags_can_be_saved_and_cleared_idempotently(self):
        data = self.create(); pk, qid = data['id'], data['question_ids'][0]
        for flagged in (True, True, False, False):
            self.assertEqual(self.api('flag', {'question_id': qid, 'is_flagged': flagged}, pk).status_code, 200)
            self.assertEqual(self.api('retrieve', pk=pk, method='get').data['flagged_questions'], [qid] if flagged else [])

    def test_deadline_blocks_late_answers_and_scores_previously_saved_answers(self):
        data = self.create(is_timed=True, duration_minutes=1); pk = data['id']
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'B'}, pk)
        QuizAttempt.objects.filter(pk=pk).update(deadline=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.api('answer', {'question_id': data['question_ids'][1], 'selected_option': 'B'}, pk).status_code, 400)
        response = self.api('auto_submit', pk=pk)
        self.assertEqual(response.data['status'], 'auto_submitted')
        self.assertEqual(response.data['mcq_score'], 1)

    def test_source_deletion_preserves_attempt_and_snapshot_result(self):
        data = self.create(); self.slide.delete()
        self.assertTrue(QuizAttempt.objects.filter(pk=data['id']).exists())
        self.assertEqual(self.api('submit', pk=data['id']).status_code, 200)
        self.assertEqual(len(self.api('result', pk=data['id'], method='get').data['questions']), 5)

    def test_missed_pool_remains_deck_and_difficulty_scoped(self):
        data = self.create()
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'A'}, data['id'])
        self.api('submit', pk=data['id'])
        result = self.api('practice_options', {'slide': self.slide.pk, 'question_source': 'missed_questions'}, method='get')
        self.assertEqual(result.data['available'], {'easy': 0, 'medium': 1, 'hard': 0})

    def test_twenty_question_ceiling_accepts_twenty_when_available(self):
        original = QuizQuestion.objects.filter(difficulty='medium').first()
        for i in range(15):
            original.pk = f'extra-medium-{i}'; original.question_text = f'Additional validated question {i}'
            original.save(force_insert=True)
        data = self.create(configuration={**self.payload['configuration'], 'mcq_count': 20})
        self.assertEqual(len(set(data['question_ids'])), 20)


@skipUnless(connection.vendor == 'postgresql', 'Row-lock checks require isolated local PostgreSQL')
class PracticeConcurrencyTests(PracticeFixture, TransactionTestCase):
    def test_concurrent_submit_records_one_result_and_one_event(self):
        data = self.create(); pk = data['id']
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'B'}, pk)
        gate = Barrier(2)
        def run():
            close_old_connections()
            try:
                gate.wait(timeout=10)
                response = self.api('submit', pk=pk)
                return response.status_code, response.data
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        self.assertEqual([r[0] for r in results], [200, 200])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(LearningEvent.objects.filter(resource_id=pk).count(), 1)
        self.user.stats.refresh_from_db()
        self.assertEqual(self.user.stats.quizzes_taken, 1)
