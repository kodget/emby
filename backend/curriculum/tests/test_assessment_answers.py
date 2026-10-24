from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.models import QuizQuestion, QuizAttempt, QuizAttemptResponse
from curriculum.quiz_views import QuizAttemptViewSet


class AssessmentAnswerTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.question = QuizQuestion.objects.create(id='written', source_slide=self.slide,
            subject=self.slide.subject, question_type='theory', question_text='Explain the arrangement.',
            ideal_answer='Private model answer', marking_rubric=[{'criterion': 'Arrangement', 'marks': 2}], maximum_marks=2)
        self.mcq = QuizQuestion.objects.create(id='choice', source_slide=self.slide,
            subject=self.slide.subject, question_type='mcq', question_text='Choose a component.', correct_option='B')
        self.attempt = QuizAttempt.objects.create(id='mock-answers', user=self.user, exam_type='mock',
            slide=self.slide, subject=self.slide.subject, question_ids=['written', 'choice'],
            question_snapshots=[{'id': 'written', 'question_type': 'theory', 'ideal_answer': 'Private model answer'},
                                {'id': 'choice', 'question_type': 'mcq', 'correct_option': 'B'}])

    def endpoint(self, data=None, action='answer', method='post'):
        req = getattr(APIRequestFactory(), method)('/api/test/', data or {}, format='json')
        force_authenticate(req, self.user)
        return QuizAttemptViewSet.as_view({method: action})(req, pk=self.attempt.pk)

    def test_theory_is_saved_reloaded_and_can_be_cleared_without_grading(self):
        with patch('curriculum.services.ai_theory_evaluator.AITheoryEvaluator.evaluate') as grader:
            result = self.endpoint({'question_id': 'written', 'text_answer': 'My written answer', 'ai_score': 999, 'is_correct': True})
            self.assertEqual(result.status_code, 200)
            data = self.endpoint(action='retrieve', method='get').data
            self.assertEqual(data['responses'][0]['text_answer'], 'My written answer')
            self.assertNotIn('ideal_answer', data['responses'][0]['question'])
            self.assertNotIn('ai_score', data['responses'][0])
            response = QuizAttemptResponse.objects.get(attempt=self.attempt)
            self.assertIsNotNone(response.answered_at)
            self.assertIsNone(response.is_correct)
            self.assertIsNone(response.ai_score)
            self.assertEqual(self.endpoint({'question_id': 'written', 'text_answer': ''}).status_code, 200)
            response.refresh_from_db(); self.assertEqual(response.text_answer, '')
        grader.assert_not_called()

    def test_invalid_theory_input_leaves_existing_answer_untouched(self):
        self.endpoint({'question_id': 'written', 'text_answer': 'Keep this'})
        for value in (None, True, [], {}, 123, 'a' * 20001):
            self.assertEqual(self.endpoint({'question_id': 'written', 'text_answer': value}).status_code, 400)
        self.assertEqual(QuizAttemptResponse.objects.get().text_answer, 'Keep this')

    def test_types_cannot_be_swapped(self):
        for data in ({'question_id': 'written', 'selected_option': 'B', 'text_answer': 'text'},
                     {'question_id': 'choice', 'selected_option': 'B', 'text_answer': 'text'},
                     {'question_id': 'choice', 'selected_option': 'E'},
                     {'question_id': 'choice', 'selected_option': True}):
            self.assertEqual(self.endpoint(data).status_code, 400)
        self.assertFalse(QuizAttemptResponse.objects.exists())

    def test_exact_deadline_rejects_theory_and_mcq_answers(self):
        now = timezone.now()
        self.attempt.is_timed = True; self.attempt.deadline = now; self.attempt.save()
        with patch('django.utils.timezone.now', return_value=now):
            self.assertEqual(self.endpoint({'question_id': 'written', 'text_answer': 'Too late'}).status_code, 400)
            self.assertEqual(self.endpoint({'question_id': 'choice', 'selected_option': 'B'}).status_code, 400)
        self.assertFalse(QuizAttemptResponse.objects.exists())

    def test_closed_attempt_and_nonselected_question_cannot_be_changed(self):
        self.assertEqual(self.endpoint({'question_id': 'not-selected', 'text_answer': 'text'}).status_code, 400)
        self.attempt.status = 'submitted'; self.attempt.save()
        self.assertEqual(self.endpoint({'question_id': 'written', 'text_answer': 'text'}).status_code, 400)
        self.assertFalse(QuizAttemptResponse.objects.exists())

    def test_snapshot_key_is_used_when_live_question_changes(self):
        self.attempt.question_snapshots = [{'id': 'choice', 'question_type': 'mcq', 'correct_option': 'A'}]
        self.attempt.save()
        self.assertEqual(self.endpoint({'question_id': 'choice', 'selected_option': 'A'}).status_code, 200)
        self.assertTrue(QuizAttemptResponse.objects.get().is_correct)
