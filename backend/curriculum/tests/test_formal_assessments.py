from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIClient

from accounts.models import ClassGroup
from curriculum.formal_assessments import FormalAssessmentViewSet
from curriculum.models import FormalAssessment, QuizAttempt, QuizAttemptResponse, QuizQuestion, UserStats
from curriculum.quiz_views import QuizAttemptViewSet
from curriculum.tests.test_bank_recovery import BankFixture, mcq, theory

router = DefaultRouter()
router.register('api/formal-assessments', FormalAssessmentViewSet, basename='formal')
router.register('api/quiz-attempts', QuizAttemptViewSet, basename='attempt')
urlpatterns = router.urls


class FormalFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.user.profile.class_role = 'class_head'
        self.user.profile.class_head_verified = True
        self.user.profile.save()
        self.student = User.objects.create_user('exam-student')
        self.student.profile.class_group = self.user.profile.class_group
        self.student.profile.save()
        self.head = APIClient(); self.head.force_authenticate(self.user)
        self.client = APIClient(); self.client.force_authenticate(self.student)
        self.body = dict(title='Anatomy formal paper', duration_minutes=15, mcq_count=1, theory_count=1,
                         questions=[dict(mcq(), question_type='mcq'), dict(theory(), question_type='theory')])

    def draft(self, body=None):
        response = self.head.post('/api/formal-assessments/', body or self.body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def published(self):
        draft = self.draft()
        response = self.head.post(f"/api/formal-assessments/{draft['id']}/publish/", {'revision': draft['revision']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def start(self, paper):
        response = self.client.post(f"/api/formal-assessments/{paper['id']}/start/", {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


@override_settings(ROOT_URLCONF=__name__)
class FormalAssessmentTests(FormalFixture, TestCase):
    def test_only_approved_current_class_heads_can_author(self):
        self.assertEqual(self.client.post('/api/formal-assessments/', self.body, format='json').status_code, 403)
        for role, verified in [('class_head', False), ('material_uploader', True), ('student', True)]:
            self.user.profile.class_role = role; self.user.profile.class_head_verified = verified; self.user.profile.save()
            self.assertEqual(self.head.post('/api/formal-assessments/', self.body, format='json').status_code, 403)
        self.assertFalse(FormalAssessment.objects.exists())

    def test_drafts_never_enter_banks_or_student_responses(self):
        paper = self.draft()
        self.assertFalse(QuizQuestion.objects.exists())
        self.assertEqual(self.client.get('/api/formal-assessments/').data['assessments'], [])
        for suffix in ['', 'start/', 'publish/']:
            method = self.client.get if not suffix else self.client.post
            self.assertIn(method(f"/api/formal-assessments/{paper['id']}/{suffix}").status_code, (403, 404))

    def test_settings_limits_reject_wrong_types_and_unknown_ownership(self):
        for field, value in [('mcq_count', 51), ('theory_count', 6), ('duration_minutes', 151),
                             ('duration_minutes', 0), ('mcq_count', True), ('theory_count', -1),
                             ('duration_minutes', '15'), ('class_group', self.user.profile.class_group_id)]:
            with self.subTest(field=field, value=value):
                body = deepcopy(self.body); body[field] = value
                self.assertEqual(self.head.post('/api/formal-assessments/', body, format='json').status_code, 400)
        body = dict(self.body, mcq_count=50, theory_count=5, duration_minutes=150)
        self.assertEqual(self.head.post('/api/formal-assessments/', body, format='json').status_code, 201)

    def test_question_validation_does_not_accept_bad_keys_rubrics_or_duplicates(self):
        variants = [('correct_option', 'E'), ('option_b', self.body['questions'][0]['option_a']), ('question_text', '')]
        for field, value in variants:
            body = deepcopy(self.body); body['questions'][0][field] = value
            self.assertEqual(self.head.post('/api/formal-assessments/', body, format='json').status_code, 400)
        for rubric in [[], [None], [{'criterion': 'Something', 'marks': 1}], [{'criterion': 'Something', 'marks': True}]]:
            body = deepcopy(self.body); body['questions'][1]['marking_rubric'] = rubric
            self.assertEqual(self.head.post('/api/formal-assessments/', body, format='json').status_code, 400)

    def test_incomplete_draft_cannot_publish_and_stale_editor_cannot_overwrite(self):
        paper = self.draft(dict(self.body, questions=[]))
        path = f"/api/formal-assessments/{paper['id']}/"
        self.assertEqual(self.head.post(path + 'publish/', {'revision': 1}, format='json').status_code, 400)
        self.assertEqual(self.head.patch(path, dict(self.body, revision=1), format='json').status_code, 200)
        self.assertEqual(self.head.patch(path, dict(self.body, revision=1), format='json').status_code, 400)
        self.assertEqual(self.head.post(path + 'publish/', {'revision': 1}, format='json').status_code, 400)
        self.assertEqual(self.head.post(path + 'publish/', {'revision': 2}, format='json').status_code, 200)
        self.assertEqual(self.head.patch(path, dict(self.body, revision=3), format='json').status_code, 400)
        self.assertEqual(self.head.delete(path).status_code, 405)

    def test_student_cannot_choose_formal_settings_or_see_paper_answers(self):
        paper = self.published()
        path = f"/api/formal-assessments/{paper['id']}/"
        self.assertNotIn('questions', self.client.get(path).data)
        self.assertNotIn('questions', self.client.get('/api/formal-assessments/').data['assessments'][0])
        self.assertEqual(self.client.post(path + 'start/', {'duration_minutes': 150}).status_code, 400)
        for kind in ['formal', 'formal_assessment']:
            self.assertEqual(self.client.post('/api/quiz-attempts/', {'exam_type': kind}).status_code, 400)
        attempt = self.start(paper)
        self.assertEqual((attempt['mcq_total'], attempt['theory_total'], attempt['duration_minutes']), (1, 1, 15))
        for q in attempt['questions']:
            self.assertFalse({'correct_option', 'explanation', 'marking_rubric', 'ideal_answer'} & set(q))

    def test_one_attempt_survives_repeat_start_submission_and_delete_request(self):
        paper = self.published(); first = self.start(paper); second = self.start(paper)
        self.assertEqual((first['id'], first['deadline']), (second['id'], second['deadline']))
        path = f"/api/quiz-attempts/{first['id']}/"
        self.assertEqual(self.client.delete(path).status_code, 400)
        self.assertEqual(self.client.post(path + 'submit/').status_code, 200)
        resumed = self.start(paper)
        self.assertEqual(resumed['id'], first['id']); self.assertEqual(resumed['status'], 'submitted')
        self.assertEqual(QuizAttempt.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuizAttempt.objects.create(id='duplicate-attempt', user=self.student, assessment_id=paper['id'], exam_type='formal')

    def test_cross_class_and_unapproved_head_access_fail_closed(self):
        paper = self.published(); attempt = self.start(paper)
        group = ClassGroup.objects.create(school=self.user.profile.class_group.school, set_name='Other', code='888888')
        self.student.profile.class_group = group; self.student.profile.save()
        self.assertEqual(self.client.get(f"/api/formal-assessments/{paper['id']}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/quiz-attempts/{attempt['id']}/").status_code, 404)
        self.user.profile.class_group = group; self.user.profile.save()
        self.assertEqual(self.head.post(f"/api/formal-assessments/{paper['id']}/close/").status_code, 404)

    def test_private_snapshot_answers_reload_clear_and_refuse_expired_writes(self):
        paper = self.published(); attempt = self.start(paper); path = f"/api/quiz-attempts/{attempt['id']}/"
        qid = attempt['questions'][1]['id']
        for answer in ['My written answer', '']:
            self.assertEqual(self.client.post(path + 'answer/', {'question_id': qid, 'text_answer': answer}).status_code, 200)
            saved = self.client.get(path).data['responses'][0]
            self.assertEqual(saved['text_answer'], answer); self.assertEqual(saved['question']['id'], qid)
        self.assertIsNone(QuizAttemptResponse.objects.get().question_id)
        QuizAttempt.objects.filter(pk=attempt['id']).update(deadline=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(path + 'answer/', {'question_id': qid, 'text_answer': 'Late'}).status_code, 400)
        self.assertEqual(self.client.post(path + 'submit/').data['status'], 'auto_submitted')

    def test_submission_is_idempotent_and_written_grading_stays_pending(self):
        paper = self.published(); attempt = self.start(paper); path = f"/api/quiz-attempts/{attempt['id']}/"
        qid = attempt['questions'][0]['id']
        self.assertEqual(self.client.post(path + 'answer/', {'question_id': qid, 'selected_option': 'B'}).status_code, 200)
        self.client.post(path + 'answer/', {'question_id': attempt['questions'][1]['id'], 'text_answer': 'Saved written answer'})
        first = self.client.post(path + 'submit/'); second = self.client.post(path + 'submit/')
        self.assertEqual(first.data, second.data)
        self.assertEqual(first.data['mcq_score'], 1)
        result = self.client.get(path + 'result/').data
        self.assertTrue(result['theory_grading_pending']); self.assertFalse(result['theory_grading_completed'])
        self.assertEqual(result['analysis_data']['theory_maximum_marks'], 2)
        self.assertFalse(result['answers_released'])
        self.assertNotIn('correct_option', result['questions'][0])
        self.assertNotIn('correct_option', result['responses'][0]['question'])
        self.assertEqual(UserStats.objects.get(user=self.student).quizzes_taken, 1)
        from learning.models import LearningEvent
        self.assertEqual(LearningEvent.objects.filter(resource_type='QuizAttempt', resource_id=attempt['id']).count(), 1)

    def test_close_and_release_block_new_entries_and_do_not_leak_to_active_attempts(self):
        paper = self.published(); attempt = self.start(paper)
        path = f"/api/formal-assessments/{paper['id']}/"
        self.assertEqual(self.head.post(path + 'release-answers/').status_code, 400)
        self.assertEqual(self.head.post(path + 'close/').status_code, 200)
        self.assertEqual(self.head.post(path + 'release-answers/').status_code, 400)
        self.assertEqual(self.head.post(path + 'start/').status_code, 400)
        self.assertEqual(self.start(paper)['id'], attempt['id'])
        attempt_path = f"/api/quiz-attempts/{attempt['id']}/"
        self.client.post(attempt_path + 'submit/')
        self.assertEqual(self.head.post(path + 'release-answers/').status_code, 200)
        result = self.client.get(attempt_path + 'result/').data
        self.assertTrue(result['answers_released']); self.assertEqual(result['questions'][0]['correct_option'], 'B')
        self.assertEqual(self.client.post(path + 'release-answers/').status_code, 403)

    def test_source_removal_cannot_reset_formal_attempt(self):
        paper = self.published(); attempt = self.start(paper)
        self.slide.subject.delete()
        self.assertEqual(self.start(paper)['id'], attempt['id'])
        self.assertEqual(self.client.get(f"/api/quiz-attempts/{attempt['id']}/").status_code, 200)

    def test_malformed_payload_and_disabled_class_do_not_write(self):
        self.assertEqual(self.head.post('/api/formal-assessments/', [self.body], format='json').status_code, 400)
        paper = self.draft(); path = f"/api/formal-assessments/{paper['id']}/"
        self.assertEqual(self.head.patch(path, [], format='json').status_code, 400)
        self.assertEqual(self.head.post(path + 'publish/', [], format='json').status_code, 400)
        group = self.user.profile.class_group; group.is_active = False; group.save()
        self.assertEqual(self.head.post(path + 'publish/', {'revision': 1}, format='json').status_code, 403)

    def test_completion_failure_rolls_back_and_can_be_retried(self):
        paper = self.published(); attempt = self.start(paper)
        stats, _ = UserStats.objects.get_or_create(user=self.student)
        before = (stats.points, stats.quizzes_taken)
        path = f"/api/quiz-attempts/{attempt['id']}/submit/"
        with patch('learning.events.record', side_effect=RuntimeError('Storage unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(path)
        stats.refresh_from_db()
        self.assertEqual((stats.points, stats.quizzes_taken), before)
        self.assertEqual(QuizAttempt.objects.get(pk=attempt['id']).status, 'in_progress')
        self.assertEqual(self.client.post(path).status_code, 200)
        stats.refresh_from_db(); self.assertEqual(stats.quizzes_taken, before[1] + 1)

    def test_legacy_grader_and_analysis_cannot_finalize_snapshot_results(self):
        from curriculum.tasks import evaluate_theory_answers_task, analyze_quiz_attempt_task
        from curriculum.services.flashcard_generator import generate_flashcards_for_attempt
        paper = self.published(); attempt = self.start(paper)
        self.client.post(f"/api/quiz-attempts/{attempt['id']}/answer/", {'question_id': attempt['questions'][1]['id'], 'text_answer': 'Saved written answer'})
        self.client.post(f"/api/quiz-attempts/{attempt['id']}/submit/")
        self.assertFalse(evaluate_theory_answers_task.run(attempt['id'])['success'])
        self.assertFalse(analyze_quiz_attempt_task.run(attempt['id'])['success'])
        self.assertEqual(generate_flashcards_for_attempt(attempt['id'])['created_count'], 0)
        saved = QuizAttempt.objects.get(pk=attempt['id'])
        self.assertTrue(saved.theory_grading_pending)
        self.assertFalse(saved.theory_grading_completed)


@override_settings(ROOT_URLCONF=__name__)
@skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL row locks')
class FormalAssessmentRaceTests(FormalFixture, TransactionTestCase):
    def race(self, operation):
        barrier = Barrier(2)
        def worker(_):
            close_old_connections()
            try:
                client = APIClient(); client.force_authenticate(User.objects.get(pk=self.student.pk))
                barrier.wait(timeout=15)
                return operation(client)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, range(2)))

    def test_concurrent_start_and_submission_keep_one_attempt_and_one_stats_update(self):
        paper = self.published()
        responses = self.race(lambda client: client.post(f"/api/formal-assessments/{paper['id']}/start/"))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].data['id'], responses[1].data['id'])
        self.assertEqual(responses[0].data['deadline'], responses[1].data['deadline'])
        aid = responses[0].data['id']
        responses = self.race(lambda client: client.post(f'/api/quiz-attempts/{aid}/submit/'))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(QuizAttempt.objects.count(), 1)
        self.assertEqual(UserStats.objects.get(user=self.student).quizzes_taken, 1)
