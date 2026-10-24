import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from curriculum import assessment_drafts as gen
from curriculum.models import AssessmentDraftJob as Job, FormalAssessment, QuizQuestion, SlideContent
from curriculum.tests.test_bank_recovery import mcq, theory
from curriculum.tests.test_formal_assessments import FormalFixture


class DraftFixture(FormalFixture):
    def setUp(self):
        super().setUp()
        queue_patch = patch('curriculum.tasks.generate_assessment_draft_task.delay')
        self.queue = queue_patch.start()
        self.addCleanup(queue_patch.stop)
        # A default fail-fast mock prevents accidental network calls in every test.
        provider_patch = patch('curriculum.assessment_drafts.llm.chat',
                                side_effect=AssertionError('Unconfigured test response'))
        self.provider = provider_patch.start()
        self.addCleanup(provider_patch.stop)

    def empty(self, **kwargs):
        paper = self.draft(dict(self.body, questions=[], **kwargs))
        self.path = f"/api/formal-assessments/{paper['id']}/"
        return paper

    def generate(self, paper, **kwargs):
        return self.head.post(self.path + 'generation/', {
            'operation': 'generate', 'revision': paper['revision'],
            'source_ids': [self.slide.pk], 'difficulty': 'medium', **kwargs}, format='json')

    def produce(self, job, kind, number=20):
        self.provider.side_effect = None
        self.provider.return_value = json.dumps(dict((mcq if kind == 'mcq' else theory)(number, 'medium'), question_type=kind))
        return gen.run(job.pk)

    def operation(self, paper, job, operation):
        return self.head.post(self.path + 'generation/', dict(operation=operation, revision=paper['revision'], job_id=job.pk), format='json')

    def ready(self):
        paper = self.empty()
        self.assertEqual(self.generate(paper).status_code, 200)
        job = Job.objects.get()
        self.assertTrue(self.produce(job, 'mcq'))
        self.assertTrue(self.produce(job, 'theory'))
        return paper, job


@override_settings(ROOT_URLCONF='curriculum.tests.test_formal_assessments')
class AssessmentDraftTests(DraftFixture, TestCase):
    def test_request_is_private_idempotent_and_does_not_fill_banks(self):
        paper = self.empty()
        with self.captureOnCommitCallbacks(execute=True):
            first = self.generate(paper)
        self.assertEqual(first.status_code, 200, first.data)
        self.queue.assert_called_once()
        self.assertEqual(self.generate(paper).data['generation']['id'], first.data['generation']['id'])
        self.assertEqual(Job.objects.count(), 1)
        self.assertFalse(QuizQuestion.objects.exists())
        self.assertEqual(FormalAssessment.objects.get().questions, [])
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(self.path + 'generation/').status_code, 403)
        self.user.profile.class_head_verified = False; self.user.profile.save()
        self.assertEqual(self.generate(paper).status_code, 403)

    def test_repeated_request_redispatches_a_due_pending_job(self):
        paper = self.empty()
        with self.captureOnCommitCallbacks(execute=False):
            first = self.generate(paper)
        self.assertEqual(first.status_code, 200, first.data)
        self.queue.assert_not_called()

        with self.captureOnCommitCallbacks(execute=True):
            retry = self.generate(paper)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(retry.data['generation']['id'], first.data['generation']['id'])
        self.queue.assert_called_once()

    def test_invalid_sources_extraction_and_counts_fail_before_dispatch(self):
        paper = self.empty()
        for ids in [[], [True], [self.slide.pk, self.slide.pk], ['other-class-slide']]:
            self.assertEqual(self.head.post(self.path + 'generation/', dict(operation='generate',
                revision=1, source_ids=ids, difficulty='easy'), format='json').status_code, 400)
        self.slide.class_group = None; self.slide.save()
        self.assertEqual(self.generate(paper).status_code, 400)
        self.slide.class_group = self.user.profile.class_group; self.slide.save()
        SlideContent.objects.filter(slide=self.slide).update(content_data={})
        self.assertEqual(self.generate(paper).status_code, 400)
        self.assertFalse(Job.objects.exists()); self.queue.assert_not_called(); self.provider.assert_not_called()

    def test_complete_generation_requires_apply_then_explicit_human_publish_review(self):
        paper, job = self.ready()
        self.assertEqual(FormalAssessment.objects.get().questions, [])
        response = self.operation(paper, job, 'apply')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['questions']), 2)
        self.assertTrue(response.data['has_ai_questions'])
        self.assertNotIn('source_quote', response.data['questions'][0])
        self.assertIn('source_quote', response.data['generation']['questions'][0])
        publish = self.path + 'publish/'
        for value in (None, False, 'true', 1):
            self.assertEqual(self.head.post(publish, dict(revision=2, review_confirmed=value), format='json').status_code, 400)
        result = self.head.post(publish, dict(revision=2, review_confirmed=True), format='json')
        self.assertEqual(result.status_code, 200, result.data)
        saved = FormalAssessment.objects.get()
        self.assertEqual(saved.ai_reviewed_by, self.user); self.assertIsNotNone(saved.ai_reviewed_at)
        student_data = self.client.get(self.path).data
        self.assertFalse({'questions', 'generation', 'has_ai_questions'} & set(student_data))
        self.assertFalse(QuizQuestion.objects.exists())
        self.assertEqual(self.operation(result.data, job, 'apply').status_code, 400)

    def test_manual_questions_preserved_and_only_missing_slots_generated(self):
        paper = self.empty()
        paper = self.head.patch(self.path, dict(self.body, revision=1,
            questions=[self.body['questions'][0]]), format='json').data
        original = paper['questions'][0]
        self.assertEqual(self.generate(paper).status_code, 200)
        job = Job.objects.get()
        self.assertEqual([p['question_type'] for p in job.plan], ['theory'])
        self.assertTrue(self.produce(job, 'theory'))
        applied = self.operation(paper, job, 'apply')
        self.assertEqual(applied.data['questions'][0], original)
        self.assertEqual(self.operation(paper, job, 'apply').status_code, 400)
        self.assertEqual(len(FormalAssessment.objects.get().questions), 2)

    def test_invalid_generated_keys_quotes_rubrics_and_duplicates_never_save(self):
        for row in [
            dict(mcq(20, 'medium'), question_type='mcq', correct_option='E'),
            dict(mcq(20, 'medium'), question_type='mcq', source_quote='This quotation does not exist in the selected document.'),
            dict(mcq(20, 'medium'), question_type='mcq', source_page=True),
            dict(mcq(20, 'easy'), question_type='mcq'),
            dict(theory(20, 'medium'), question_type='theory'),
        ]:
            with self.subTest(row=row):
                paper = self.empty()
                self.generate(paper); job = Job.objects.latest('pk')
                self.provider.side_effect = None; self.provider.return_value = json.dumps(row)
                self.assertFalse(gen.run(job.pk)); job.refresh_from_db()
                self.assertEqual(job.questions, []); self.assertEqual(job.status, 'retry_wait')
                self.assertEqual(job.error_code, 'invalid_question')
        paper = self.empty(mcq_count=2, theory_count=0)
        self.generate(paper); job = Job.objects.latest('pk')
        self.assertTrue(self.produce(job, 'mcq', 99))
        self.assertFalse(self.produce(job, 'mcq', 99))
        job.refresh_from_db(); self.assertEqual(len(job.questions), 1)

    def test_partial_progress_survives_bounded_retries_and_owner_retry(self):
        paper = self.empty()
        self.generate(paper); job = Job.objects.get()
        self.produce(job, 'mcq')
        self.provider.side_effect = RuntimeError('SECRET provider response')
        for _ in range(3):
            self.assertFalse(gen.run(job.pk))
            job.refresh_from_db()
            if job.status == 'retry_wait':
                Job.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
                gen.recovery()
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed'); self.assertEqual(len(job.questions), 1)
        self.assertNotIn('SECRET', str(self.head.get(self.path + 'generation/').data))
        self.assertEqual(self.operation(paper, job, 'retry').status_code, 400)
        Job.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.operation(paper, job, 'retry').status_code, 200)
        self.assertTrue(self.produce(job, 'theory'))
        job.refresh_from_db()
        self.assertEqual((job.status, len(job.questions), job.total_runs), ('completed', 2, 5))

    def test_edit_cancels_running_job_and_late_provider_cannot_overwrite(self):
        paper = self.empty(); self.generate(paper); job = Job.objects.get()
        def late(*args, **kwargs):
            response = self.head.patch(self.path, dict(self.body, revision=1), format='json')
            self.assertEqual(response.status_code, 200)
            return json.dumps(dict(mcq(20, 'medium'), question_type='mcq'))
        self.provider.side_effect = late
        self.assertFalse(gen.run(job.pk))
        job.refresh_from_db(); self.assertEqual(job.status, 'cancelled'); self.assertEqual(job.questions, [])
        self.assertEqual(FormalAssessment.objects.get().questions[0]['question_text'], self.body['questions'][0]['question_text'])

    def test_completed_suggestions_cannot_apply_after_source_replacement(self):
        paper, job = self.ready()
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['text_extraction']['source_sha256'] = 'replacement'
        content.save()
        self.assertEqual(self.operation(paper, job, 'apply').status_code, 400)
        self.assertEqual(FormalAssessment.objects.get().questions, [])
        self.assertEqual(self.operation(paper, job, 'discard').status_code, 200)
        self.assertEqual(self.generate(paper).status_code, 200)
        self.assertEqual(Job.objects.count(), 2)

    def test_queue_failure_and_expired_lease_recover_without_accepting_late_results(self):
        paper = self.empty()
        self.queue.side_effect = RuntimeError('broker down')
        with self.captureOnCommitCallbacks(execute=True):
            self.generate(paper)
        job = Job.objects.get(); self.assertEqual(job.error_code, 'queue_unavailable')
        Job.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        self.queue.side_effect = None
        self.assertEqual(gen.recovery(), 1)
        def expired(*args, **kwargs):
            Job.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(gen.recovery(), 1)
            return json.dumps(dict(mcq(20, 'medium'), question_type='mcq'))
        self.provider.side_effect = expired
        self.assertFalse(gen.run(job.pk))
        job.refresh_from_db(); self.assertEqual(job.status, 'pending'); self.assertEqual(job.questions, [])
        self.assertTrue(self.produce(job, 'mcq'))

    def test_repeated_worker_delivery_does_not_duplicate_question_or_rerun_completed_job(self):
        paper = self.empty(mcq_count=1, theory_count=0); self.generate(paper); job = Job.objects.get()
        def duplicate(*args, **kwargs):
            self.assertFalse(gen.run(job.pk))
            return json.dumps(dict(mcq(20, 'medium'), question_type='mcq'))
        self.provider.side_effect = duplicate
        self.assertTrue(gen.run(job.pk)); self.assertFalse(gen.run(job.pk))
        self.assertEqual(self.provider.call_count, 1)
        job.refresh_from_db(); self.assertEqual(len(job.questions), 1)

    def test_source_page_selection_spans_document_and_prompt_separates_untrusted_text(self):
        from curriculum.tests.test_bank_recovery import BODY
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['pages'] = [
            {'page_number': i, 'text': BODY, 'extraction_status': 'complete'} for i in range(1, 5)]
        content.content_data['text_extraction']['total_pages'] = 4
        content.save()
        paper = self.empty(mcq_count=2, theory_count=0); self.generate(paper); job = Job.objects.get()
        self.assertEqual([p['page'] for p in job.plan], [1, 4])
        self.assertTrue(self.produce(job, 'mcq'))
        messages = self.provider.call_args.args[0]
        self.assertEqual([m['role'] for m in messages], ['system', 'user'])
        self.assertNotIn(BODY, messages[0]['content'])

    def test_theory_rubric_must_balance_and_generation_rejects_stale_revision(self):
        paper = self.empty(mcq_count=0, theory_count=1)
        self.assertEqual(self.generate(paper, revision=0).status_code, 400)
        self.assertFalse(Job.objects.exists())
        self.generate(paper); job = Job.objects.get()
        self.provider.side_effect = None
        self.provider.return_value = json.dumps(dict(theory(20, 'medium'), question_type='theory',
            marking_rubric=[{'criterion': 'Does not add up', 'marks': 1}]))
        self.assertFalse(gen.run(job.pk)); job.refresh_from_db()
        self.assertEqual(job.questions, [])
        self.assertEqual(self.operation(paper, job, 'apply').status_code, 400)

    def test_other_class_head_cannot_inspect_or_control_generation(self):
        from accounts.models import ClassGroup
        paper = self.empty(); self.generate(paper)
        other = ClassGroup.objects.create(school=self.user.profile.class_group.school, set_name='Other year', code='000123')
        self.student.profile.class_group = other
        self.student.profile.class_role = 'class_head'
        self.student.profile.class_head_verified = True
        self.student.profile.save()
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(self.path + 'generation/').status_code, 404)
        self.assertEqual(Job.objects.count(), 1)


@skipUnless(connection.vendor == 'postgresql', 'Real row locks require PostgreSQL.')
@override_settings(ROOT_URLCONF='curriculum.tests.test_formal_assessments')
class AssessmentDraftConcurrencyTests(DraftFixture, TransactionTestCase):
    def test_simultaneous_requests_create_only_one_job_and_simultaneous_apply_adds_once(self):
        paper = self.empty(mcq_count=1, theory_count=0)
        barrier = Barrier(2)
        def post(body):
            close_old_connections()
            try:
                client = APIClient(); client.force_authenticate(self.user)
                barrier.wait(timeout=10)
                return client.post(self.path + 'generation/', body, format='json').status_code
            finally:
                close_old_connections()
        body = dict(operation='generate', revision=1, source_ids=[self.slide.pk], difficulty='medium')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(post, [body, body]))
        self.assertEqual(results, [200, 200]); self.assertEqual(Job.objects.count(), 1)
        job = Job.objects.get(); self.assertTrue(self.produce(job, 'mcq'))
        barrier = Barrier(2)
        body = dict(operation='apply', revision=1, job_id=job.pk)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(post, [body, body]))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(len(FormalAssessment.objects.get().questions), 1)

    def test_two_workers_claim_only_one_provider_call(self):
        paper = self.empty(mcq_count=1, theory_count=0); self.generate(paper); job = Job.objects.get()
        self.provider.side_effect = None
        self.provider.return_value = json.dumps(dict(mcq(20, 'medium'), question_type='mcq'))
        barrier = Barrier(2)
        def worker(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return gen.run(job.pk)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.provider.assert_called_once()
        job.refresh_from_db(); self.assertEqual(len(job.questions), 1)
