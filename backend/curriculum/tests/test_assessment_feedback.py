from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from curriculum import assessment_grading
from curriculum.models import QuizAttempt, QuizAttemptResponse, QuizQuestion, UserStats
from curriculum.tests.test_assessment_grading import GradingFixture, grade
from curriculum.tests.test_formal_assessments import FormalFixture
from learning.models import LearningEvent


@override_settings(ROOT_URLCONF='curriculum.tests.test_formal_assessments')
class FormalFeedbackTests(GradingFixture, TestCase):
    def test_feedback_is_withheld_until_release_and_references_saved_rubric(self):
        attempt, paper = self.submitted()
        path = f'/api/quiz-attempts/{attempt.pk}/result/'
        self.assertIsNone(self.client.get(path).data['feedback'])
        with patch('curriculum.services.snapshot_grader.evaluate', return_value=grade()):
            assessment_grading.run(attempt.pk)
        self.assertIsNone(self.client.get(path).data['feedback'])
        self.head.post(f"/api/formal-assessments/{paper['id']}/close/")
        self.head.post(f"/api/formal-assessments/{paper['id']}/release-answers/")
        result = self.client.get(path).data['feedback']
        self.assertEqual(result['mcq'], {'correct': 1, 'incorrect': 0, 'unanswered': 0})
        self.assertFalse(result['difficulty_breakdown'][0]['sufficient_evidence'])
        written = result['questions_to_review']
        self.assertEqual(len(written), 2)
        self.assertEqual(written[0]['question_id'], attempt.question_snapshots[1]['id'])
        self.assertEqual(written[0]['criteria_to_review'][0]['marks_awarded'], 1.5)
        self.assertEqual(written[1]['outcome'], 'unanswered')
        self.assertIn('does not establish its cause', result['note'])

    def test_pending_grading_does_not_claim_written_weakness(self):
        attempt, paper = self.submitted(answers=('First', 'Second'))
        self.head.post(f"/api/formal-assessments/{paper['id']}/close/")
        self.head.post(f"/api/formal-assessments/{paper['id']}/release-answers/")
        result = self.client.get(f'/api/quiz-attempts/{attempt.pk}/result/').data['feedback']
        self.assertTrue(result['grading_pending'])
        self.assertTrue(all(q['outcome'] == 'pending' and q['marks'] is None for q in result['questions_to_review']))

    def test_mcq_observations_use_snapshot_answer_and_distinguish_unanswered(self):
        self.body['mcq_count'] = 2
        self.body['questions'].append(dict(self.body['questions'][0], question_text='Another question'))
        attempt, paper = self.submitted()
        first = attempt.responses.get(snapshot_question_id=attempt.question_snapshots[0]['id'])
        first.selected_option = 'A'; first.is_correct = True; first.save()
        self.head.post(f"/api/formal-assessments/{paper['id']}/close/")
        self.head.post(f"/api/formal-assessments/{paper['id']}/release-answers/")
        result = self.client.get(f'/api/quiz-attempts/{attempt.pk}/result/').data['feedback']
        self.assertEqual(result['mcq'], {'correct': 0, 'incorrect': 1, 'unanswered': 1})
        review = result['questions_to_review'][0]
        self.assertEqual(review['selected_option'], 'A')
        self.assertEqual(review['correct_option'], 'B')
        self.assertEqual(review['explanation'], attempt.question_snapshots[0]['explanation'])


@override_settings(ROOT_URLCONF='curriculum.tests.test_formal_assessments')
class HistoricalAssessmentTests(FormalFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.q = QuizQuestion.objects.create(id='old-q', subject=self.slide.subject, question_type='mcq',
            question_text='TODAYS QUESTION', correct_option='A', explanation='TODAYS KEY')
        self.attempt = QuizAttempt.objects.create(id='historical', user=self.student, exam_type='formal',
            subject=self.slide.subject, question_ids=[self.q.pk], mcq_score=1, mcq_total=1,
            overall_percentage=100, analysis_data={'insights': 'OLD UNVERIFIED AI CLAIM'})
        QuizAttemptResponse.objects.create(attempt=self.attempt, question=self.q, selected_option='B', is_correct=True)
        self.path = f'/api/quiz-attempts/{self.attempt.pk}/'

    def test_history_keeps_saved_responses_without_current_questions_or_fake_results(self):
        result = self.client.get(self.path).data
        self.assertTrue(result['historical_read_only']); self.assertFalse(result['score_verified'])
        self.assertEqual(result['responses'][0]['selected_option'], 'B')
        self.assertIsNone(result['recorded_result'])
        self.assertNotIn('TODAYS', str(result)); self.assertNotIn('UNVERIFIED AI CLAIM', str(result))
        self.assertEqual(result['questions'], [])
        self.assertEqual(self.client.get(self.path + 'result/').status_code, 200)
        self.assertEqual(self.client.get(self.path + 'missed/').data['missed_questions'], [])

    def test_historical_writes_and_legacy_workers_cannot_change_marks_or_award_again(self):
        from curriculum.tasks import evaluate_theory_answers_task, analyze_quiz_attempt_task
        before = UserStats.objects.get_or_create(user=self.student)[0].points
        for action, body in [('answer', {'question_id': self.q.pk, 'selected_option': 'A'}),
                             ('flag', {'question_id': self.q.pk}), ('submit', {}), ('auto_submit', {}),
                             ('retry-grading', {})]:
            response = self.client.post(self.path + action + '/', body, format='json')
            self.assertEqual(response.status_code, 400, (action, response.data))
        self.assertEqual(self.client.delete(self.path).status_code, 400)
        with patch('curriculum.llm.chat') as provider:
            self.assertFalse(evaluate_theory_answers_task.run(self.attempt.pk)['success'])
            self.assertFalse(analyze_quiz_attempt_task.run(self.attempt.pk)['success'])
        provider.assert_not_called()
        self.assertFalse(LearningEvent.objects.exists())
        self.assertEqual(UserStats.objects.get(user=self.student).points, before)
        self.attempt.refresh_from_db(); self.assertEqual(self.attempt.status, 'in_progress')

    def test_submitted_historical_score_is_labelled_unverified_and_record_survives_missing_question(self):
        self.attempt.status = 'submitted'; self.attempt.submitted_at = timezone.now()-timedelta(days=1); self.attempt.save()
        self.q.delete()
        result = self.client.get(self.path + 'result/')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['recorded_result']['overall_percentage'], 100)
        self.assertFalse(result.data['score_verified'])
        self.head.force_authenticate(self.user)
        self.assertEqual(self.head.get(self.path).status_code, 404)
