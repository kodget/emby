"""Generation ownership and recovery tests. Providers and the broker are isolated."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup
from curriculum import views
from curriculum.models import Subject, Slide, QuizQuestion, SlideProcessingStatus, SlideContent
from curriculum.services.ai_question_generator import AIQuestionGenerator, RateLimitExceeded
from learning.models import QuestionGenerationJob as Job
from learning import generation as gen
from learning.generation_dispatch import request_generation, recover_generation_jobs

QUOTE = 'The source describes the components, arrangement and function of a teaching specimen.'
BODY = ' '.join([QUOTE] * 20)
TEXT = '[Page 1]\n' + BODY


def mcq(number=1, difficulty='easy'):
    return dict(question_text=f'Which component is described in question {number}?',
                option_a='First component', option_b='Second component', option_c='Third component',
                option_d='Fourth component', correct_option='B', explanation='The source describes the second component.',
                difficulty=difficulty, maximum_marks=1, source_page=1, source_quote=QUOTE, needs_review=False)


def theory(number=1, difficulty='easy'):
    return dict(question_text=f'Explain the arrangement in question {number}.', ideal_answer='A source-based explanation.',
                marking_rubric=[{'criterion': 'Describes the arrangement', 'marks': 2}], maximum_marks=2, difficulty=difficulty, source_page=1, source_quote=QUOTE, needs_review=False)


class BankFixture:
    def setUp(self):
        super().setUp()
        school = School.objects.create(name='Bank test school')
        group = ClassGroup.objects.create(school=school, set_name='Year 1', code='654321')
        self.user = User.objects.create_user('bank-uploader')
        self.user.profile.class_group = group
        self.user.profile.class_role = 'material_uploader'
        self.user.profile.save()
        subject = Subject.objects.create(id='bank-subject', name='Anatomy', class_group=group)
        self.slide = Slide.objects.create(id='bank-slide', title='Source document', file_type='pdf', subject=subject,
            uploaded_by=self.user, class_group=group, file_url='https://storage.invalid/source.pdf')
        from curriculum.services.document_extraction import source_key
        SlideContent.objects.create(slide=self.slide, is_extracted=True, content_data={
            'pages': [{'page_number': 1, 'text': BODY, 'extraction_status': 'complete'}],
            'text_extraction': {'version': 1, 'status': 'complete', 'total_pages': 1,
                                'source_sha256': 'fixture-source', 'source_key': source_key(self.slide)}})
        self.serial = 0

    def rows(self, kind):
        def produce(**kwargs):
            rows = []
            for _ in range(kwargs['count']):
                self.serial += 1
                rows.append((mcq if kind == 'mcq' else theory)(self.serial, kwargs['difficulty']))
            return rows
        return produce

    def expire(self, job):
        Job.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))

    def api(self, payload=None):
        request = APIRequestFactory().post('/api/test/', payload or {}, format='json')
        force_authenticate(request, self.user)
        return views.generate_questions_from_slide_view(request, slide_id=self.slide.pk)


class BankRecoveryTests(BankFixture, TestCase):
    def test_provider_cooldown_preserves_questions_and_defers_remaining_batches(self):
        before = timezone.now()
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text',
                          side_effect=[[mcq()], RateLimitExceeded('Daily quota exhausted', retry_after=1094)]) as generate, \
             patch.object(AIQuestionGenerator, 'generate_theory_from_text') as theory_call:
            result = gen.generate_for_slide(self.slide)
        job = Job.objects.get(slide=self.slide)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(job.mcq_generated, 1)
        self.assertEqual(QuizQuestion.objects.filter(source_slide=self.slide).count(), 1)
        self.assertGreaterEqual(job.next_attempt_at, before + timedelta(seconds=1094))
        self.assertEqual(job.attempts, 0)
        self.assertEqual(generate.call_count, 2)
        theory_call.assert_not_called()
        self.assertTrue(gen.generate_for_slide(self.slide)['skipped'])

    def test_legacy_completed_bank_restarts_with_fifteen_target_without_destroying_history(self):
        Job.objects.create(slide=self.slide, status='completed', mcq_target=50, mcq_generated=50,
                           theory_generated=10, attempts=3)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(request_generation(self.slide))
        queue.assert_called_once()
        job = Job.objects.get(slide=self.slide)
        self.assertEqual((job.mcq_target, job.mcq_generated, job.attempts), (15, 0, 0))
        self.assertEqual(job.status, 'pending')

    def test_replaced_original_bytes_invalidate_current_bank_even_with_same_text_and_url(self):
        from learning.bank_sources import eligible_questions, bank_status
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['text_extraction']['source_sha256'] = 'different-original-file'
        content.save()
        self.assertFalse(eligible_questions(QuizQuestion.objects.all()).exists())
        self.assertEqual(bank_status(self.slide)['mcq_by_difficulty'], {})
        with self.assertRaises(gen.LostLease):
            gen.finish_job(job)
        self.assertEqual(QuizQuestion.objects.count(), 1)

    def test_human_review_validates_source_and_records_approval(self):
        from learning.bank_sources import approve_reviewed_question, eligible_questions
        from django.core.exceptions import ValidationError
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [dict(mcq(), needs_review=True)], TEXT, 'mcq', 'easy', 1)
        question = QuizQuestion.objects.get()
        approved = approve_reviewed_question(question.pk)
        self.assertIsNotNone(approved.reviewed_at)
        self.assertTrue(eligible_questions(QuizQuestion.objects.all(), formal=True).exists())
        QuizQuestion.objects.filter(pk=question.pk).update(source_text='An invented quote not present in the source.')
        with self.assertRaises(ValidationError):
            approve_reviewed_question(question.pk)

    def test_human_review_does_not_overfill_difficulty_pool(self):
        from learning.bank_sources import approve_reviewed_question
        from django.core.exceptions import ValidationError
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [dict(mcq(99), needs_review=True)], TEXT, 'mcq', 'easy', 1)
        held = QuizQuestion.objects.get()
        gen.save_batch(job, self.slide, [mcq(n) for n in range(5)], TEXT, 'mcq', 'easy', 5)
        with self.assertRaises(ValidationError):
            approve_reviewed_question(held.pk)
        held.refresh_from_db()
        self.assertTrue(held.needs_review)

    def test_status_reports_ready_counts_and_coverage_without_worker_token(self):
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        request = APIRequestFactory().get('/api/test/')
        force_authenticate(request, self.user)
        response = views.slide_processing_status(request, slide_id=self.slide.pk)
        self.assertEqual(response.status_code, 200)
        bank = response.data['question_bank']
        self.assertEqual(bank['mcq_target'], 15)
        self.assertEqual(bank['mcq_by_difficulty'], {'easy': 1})
        self.assertEqual(bank['represented_pages'], [1])
        self.assertNotIn(str(job.lease_token), str(response.data))
        Job.objects.filter(pk=job.pk).update(status='completed', mcq_generated=15, theory_generated=10)
        QuizQuestion.objects.update(needs_review=True)
        response = views.slide_processing_status(request, slide_id=self.slide.pk)
        self.assertEqual(response.data['question_bank']['status'], 'partial')
        self.assertEqual(response.data['question_bank']['progress_percent'], 0)

    @patch('learning.generation.slide_text', return_value=TEXT)
    def test_completed_bank_can_start_new_source_version_without_deleting_old_questions(self, extract):
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')), patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')):
            self.assertTrue(gen.generate_for_slide(self.slide)['success'])
        old_key = Job.objects.get(slide=self.slide).bank_key
        Slide.objects.filter(pk=self.slide.pk).update(file_url='https://storage.invalid/new.pdf')
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(request_generation(self.slide))
        queue.assert_called_once()
        self.slide.refresh_from_db()
        from curriculum.services.document_extraction import source_key
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['text_extraction']['source_key'] = source_key(self.slide)
        content.content_data['text_extraction']['source_sha256'] = 'replacement-source'
        content.save()
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')), patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')):
            self.assertTrue(gen.generate_for_slide(self.slide)['success'])
        self.assertNotEqual(Job.objects.get(slide=self.slide).bank_key, old_key)
        self.assertEqual(QuizQuestion.objects.filter(bank_key=old_key).count(), 25)
        self.assertEqual(gen.existing_counts_by_difficulty(self.slide, 'mcq'), {'easy': 5, 'medium': 5, 'hard': 5})

    def test_fabricated_quotes_and_wrong_page_references_are_rejected(self):
        job = gen.claim_job(self.slide)
        rows = [dict(mcq(1), source_quote='An invented assertion not present in this document.'),
                dict(mcq(2), source_page=2), dict(mcq(3), source_quote='too short'),
                dict(mcq(4), source_page=True), mcq(5)]
        self.assertEqual(gen.save_batch(job, self.slide, rows, TEXT, 'mcq', 'easy', 5), 1)
        question = QuizQuestion.objects.get()
        self.assertEqual((question.source_page, question.source_text), (1, QUOTE))
        self.assertEqual(question.bank_key, job.bank_key)

    def test_review_flags_are_preserved_bounded_and_excluded_from_new_sessions(self):
        from learning.bank_sources import eligible_questions
        from learning.selection import select_questions
        job = gen.claim_job(self.slide)
        rows = [dict(mcq(i), needs_review=True, review_reason='Conflicting claims') for i in range(30)]
        self.assertEqual(gen.save_batch(job, self.slide, rows, TEXT, 'mcq', 'easy', 5), 0)
        self.assertEqual(QuizQuestion.objects.count(), 5)
        self.assertEqual(QuizQuestion.objects.first().review_reason, 'Conflicting claims')
        self.assertFalse(eligible_questions(QuizQuestion.objects.all()).exists())
        self.assertEqual(select_questions(self.user, count=5, slide_id=self.slide.pk), [])
        self.assertEqual(gen.existing_counts_by_difficulty(self.slide, 'mcq'), {})

    def test_only_current_verified_bank_is_selected_and_formal_requires_human_review(self):
        from learning.bank_sources import eligible_questions
        from learning.selection import select_questions
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        question = QuizQuestion.objects.get()
        self.assertEqual([q.pk for q in select_questions(self.user, count=5)], [question.pk])
        self.assertFalse(eligible_questions(QuizQuestion.objects.all(), formal=True).exists())
        QuizQuestion.objects.filter(pk=question.pk).update(reviewed_at=timezone.now())
        self.assertTrue(eligible_questions(QuizQuestion.objects.all(), formal=True).exists())
        Job.objects.filter(pk=job.pk).update(bank_key='a-new-bank-version')
        self.assertFalse(eligible_questions(QuizQuestion.objects.all()).exists())
        self.assertTrue(QuizQuestion.objects.filter(pk=question.pk).exists())

    def test_changed_extracted_text_fences_worker_even_when_file_url_is_unchanged(self):
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['pages'][0]['text'] += ' A changed fact.'
        content.save()
        with self.assertRaises(gen.LostLease):
            gen.save_batch(job, self.slide, [mcq(2)], TEXT, 'mcq', 'easy', 1)
        self.assertEqual(QuizQuestion.objects.count(), 1)

    def test_force_cannot_take_an_active_worker_lease(self):
        first = gen.claim_job(self.slide)
        self.assertIsNone(gen.claim_job(self.slide, force=True))
        self.assertFalse(request_generation(self.slide, force=True))
        first.refresh_from_db()
        self.assertEqual(first.attempts, 1)

    def test_expired_worker_cannot_save_or_finish_after_replacement(self):
        first = gen.claim_job(self.slide)
        self.expire(first)
        second = gen.claim_job(self.slide)
        self.assertNotEqual(first.lease_token, second.lease_token)
        with self.assertRaises(gen.LostLease):
            gen.save_batch(first, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        with self.assertRaises(gen.LostLease):
            gen.finish_job(first)
        self.assertFalse(QuizQuestion.objects.exists())
        second.refresh_from_db()
        self.assertEqual(second.status, 'running')

    def test_expired_worker_cannot_publish_even_without_replacement(self):
        job = gen.claim_job(self.slide)
        self.expire(job)
        with self.assertRaises(gen.LostLease):
            gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)

    def test_replaced_source_rejects_publication_and_preserves_saved_questions(self):
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        Slide.objects.filter(pk=self.slide.pk).update(file_url='https://storage.invalid/replaced.pdf')
        with self.assertRaises(gen.LostLease):
            gen.save_batch(job, self.slide, [mcq(2)], TEXT, 'mcq', 'easy', 1)
        self.expire(job)
        replacement = gen.claim_job(self.slide, force=True)
        self.assertIsNotNone(replacement)
        self.assertEqual(QuizQuestion.objects.count(), 1)
        self.assertEqual(replacement.status, 'running')
        self.assertEqual(replacement.bank_key, '')
        with self.assertRaises(gen.LostLease):
            gen.finish_job(job)

    def test_batches_deduplicate_and_limit_provider_oversupply(self):
        job = gen.claim_job(self.slide)
        self.assertEqual(gen.save_batch(job, self.slide, [mcq(n) for n in range(30)], TEXT, 'mcq', 'easy', 3), 3)
        duplicate = mcq(0); duplicate['question_text'] = duplicate['question_text'].upper() + ' !!!'
        self.assertEqual(gen.save_batch(job, self.slide, [duplicate, mcq(30)], TEXT, 'mcq', 'easy', 10), 1)
        self.assertEqual(gen.save_batch(job, self.slide, [mcq(n) for n in range(31, 61)], TEXT, 'mcq', 'easy', 10), 1)
        self.assertEqual(QuizQuestion.objects.count(), 5)

    def test_invalid_answers_options_difficulty_and_rubrics_are_not_saved(self):
        job = gen.claim_job(self.slide)
        bad = [dict(mcq(), correct_option='A or B'), dict(mcq(), option_b='First component'),
               dict(mcq(), explanation=''), dict(mcq(), difficulty='hard'), dict(mcq(), maximum_marks=True)]
        self.assertEqual(gen.save_batch(job, self.slide, bad, TEXT, 'mcq', 'easy', 10), 0)
        bad_theory = [dict(theory(), maximum_marks=10), dict(theory(), ideal_answer=''),
                      dict(theory(), marking_rubric=[{'criterion': 'A', 'marks': -1}])]
        self.assertEqual(gen.save_batch(job, self.slide, bad_theory, TEXT, 'theory', 'easy', 2), 0)

    def test_finish_counts_valid_distinct_questions_not_stale_counters(self):
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        row = QuizQuestion.objects.first()
        row.pk = 'duplicate'; row.save()
        Job.objects.filter(pk=job.pk).update(mcq_generated=50, theory_generated=10)
        result = gen.finish_job(job)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['mcq_generated'], 1)
        self.assertFalse(result['success'])

    @patch('learning.generation.slide_text', return_value=TEXT)
    def test_complete_bank_has_actual_difficulty_quotas_and_repeated_task_calls_no_provider(self, extract):
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')) as mcqs, patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')) as theories:
            result = gen.generate_for_slide(self.slide)
            calls = (mcqs.call_count, theories.call_count)
            again = gen.generate_for_slide(self.slide)
            self.assertEqual((mcqs.call_count, theories.call_count), calls)
        self.assertTrue(result['success'], result)
        self.assertTrue(again['skipped'])
        self.assertEqual(gen.existing_counts_by_difficulty(self.slide, 'mcq'), gen.MCQ_TARGETS)
        self.assertEqual(gen.existing_counts_by_difficulty(self.slide, 'theory'), gen.THEORY_TARGETS)
        self.assertEqual(QuizQuestion.objects.count(), 25)

    @patch('learning.generation.slide_text', return_value=TEXT)
    def test_provider_failure_keeps_batch_and_retry_only_fills_the_shortfall(self, extract):
        produced = self.rows('mcq')
        def fail_after_first(**kwargs):
            if self.serial:
                raise RuntimeError('provider token=secret')
            return produced(**kwargs)
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=fail_after_first):
            result = gen.generate_for_slide(self.slide)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(QuizQuestion.objects.count(), 5)
        self.assertNotIn('secret', result['error'])
        saved_ids = set(QuizQuestion.objects.values_list('pk', flat=True))
        Job.objects.filter(slide=self.slide).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')) as provider, patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')):
            result = gen.generate_for_slide(self.slide)
        self.assertTrue(result['success'])
        self.assertEqual(sum(call.kwargs['count'] for call in provider.call_args_list), 10)
        self.assertTrue(saved_ids.issubset(set(QuizQuestion.objects.values_list('pk', flat=True))))

    @patch('learning.generation.slide_text', return_value=TEXT)
    def test_saved_provider_response_survives_later_failure_and_theory_still_runs(self, extract):
        theory_calls = []

        def persist_then_fail(**kwargs):
            self.serial += 1
            kwargs['on_batch']([mcq(self.serial, kwargs['difficulty'])])
            raise RuntimeError('temporary provider failure')

        def no_theory_rows(**kwargs):
            theory_calls.append(kwargs['difficulty'])
            return []

        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=persist_then_fail), patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=no_theory_rows):
            result = gen.generate_for_slide(self.slide)

        self.assertEqual(result['status'], 'partial')
        self.assertEqual(gen.existing_counts_by_difficulty(self.slide, 'mcq'), {
            'easy': 1, 'medium': 1, 'hard': 1,
        })
        self.assertEqual(theory_calls, ['easy', 'medium', 'hard'])

    def test_question_bank_task_has_no_celery_execution_time_limit(self):
        from curriculum.tasks import generate_question_bank_task

        self.assertIsNone(generate_question_bank_task.soft_time_limit)
        self.assertIsNone(generate_question_bank_task.time_limit)

    def test_broker_failure_keeps_pending_intent_then_sweep_recovers_it(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay', side_effect=RuntimeError('redis://secret')), self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(request_generation(self.slide))
        job = Job.objects.get(slide=self.slide)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.attempts, 0)
        self.assertNotIn('secret', job.error)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue:
            self.assertEqual(recover_generation_jobs()['published'], 0)
            Job.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(recover_generation_jobs()['published'], 1)
            queue.assert_called_once_with(self.slide.pk)

    def test_request_rolls_back_without_dispatching(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                request_generation(self.slide)
                raise RuntimeError('rollback')
        queue.assert_not_called()
        self.assertFalse(Job.objects.filter(slide=self.slide).exists())

    def test_duplicate_request_does_not_redispatch_before_delivery_timeout(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            request_generation(self.slide)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as second, self.captureOnCommitCallbacks(execute=True):
            self.assertFalse(request_generation(self.slide))
        queue.assert_called_once()
        second.assert_not_called()
        self.assertIsNotNone(gen.claim_job(self.slide))

    def test_recovery_requeues_expired_worker_but_not_active_one(self):
        job = gen.claim_job(self.slide)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue:
            self.assertEqual(recover_generation_jobs()['published'], 0)
            self.expire(job)
            self.assertEqual(recover_generation_jobs()['published'], 1)
        queue.assert_called_once_with(self.slide.pk)
        with self.assertRaises(gen.LostLease):
            gen.finish_job(job)

    def test_exhausted_worker_becomes_terminal_and_requires_manual_retry(self):
        job = gen.claim_job(self.slide)
        Job.objects.filter(pk=job.pk).update(attempts=Job.MAX_ATTEMPTS)
        self.expire(job)
        SlideProcessingStatus.objects.create(slide=self.slide, status='processing')
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue:
            recover_generation_jobs()
        queue.assert_not_called()
        job.refresh_from_db(); self.slide.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(self.slide.generation_status, 'failed')
        self.assertIsNone(job.next_attempt_at)
        self.assertFalse(request_generation(self.slide))
        self.assertTrue(request_generation(self.slide, force=True))

    def test_old_running_job_without_lease_can_be_recovered_after_timeout(self):
        job = Job.objects.create(slide=self.slide, status='running', attempts=1)
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now() - gen.LEASE_DURATION - timedelta(seconds=1))
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue:
            self.assertEqual(recover_generation_jobs()['published'], 1)
        queue.assert_called_once()

    def test_fix_stuck_command_never_calls_one_question_a_complete_bank(self):
        job = gen.claim_job(self.slide)
        gen.save_batch(job, self.slide, [mcq()], TEXT, 'mcq', 'easy', 1)
        gen.finish_job(job)
        with patch('curriculum.tasks.generate_question_bank_task.delay'), self.captureOnCommitCallbacks(execute=True):
            call_command('fix_stuck_slides', stdout=StringIO())
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')
        self.assertEqual(QuizQuestion.objects.count(), 1)

    def test_generation_endpoint_queues_instead_of_calling_provider(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, patch.object(
                AIQuestionGenerator, 'generate_mcqs_from_text') as provider, self.captureOnCommitCallbacks(execute=True):
            response = self.api()
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['queued'])
        queue.assert_called_once()
        provider.assert_not_called()

    def test_student_and_other_uploaders_cannot_request_generation_for_this_upload(self):
        self.user.profile.class_role = 'student'; self.user.profile.save()
        self.assertEqual(self.api().status_code, 403)
        self.user.profile.class_role = 'material_uploader'; self.user.profile.save()
        Slide.objects.filter(pk=self.slide.pk).update(uploaded_by=None)
        self.assertEqual(self.api().status_code, 403)
        self.assertFalse(Job.objects.exists())

    def test_invalid_flags_and_attempt_count_parameters_are_rejected(self):
        self.assertEqual(self.api({'force': 'yes'}).status_code, 400)
        self.assertEqual(self.api({'num_mcq': 20}).status_code, 400)
        self.assertFalse(Job.objects.exists())


@skipUnless(connection.vendor == 'postgresql', 'Row-lock race test requires disposable PostgreSQL')
class BankConcurrencyTests(BankFixture, TransactionTestCase):
    def test_two_workers_racing_to_claim_allow_only_one_owner(self):
        barrier = Barrier(2)
        def claim():
            close_old_connections()
            try:
                slide = Slide.objects.get(pk=self.slide.pk)
                barrier.wait(timeout=10)
                job = gen.claim_job(slide, force=True)
                return str(job.lease_token) if job else None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Job.objects.get(slide=self.slide).attempts, 1)

    def test_two_copies_of_same_worker_cannot_double_save_the_same_batch(self):
        job = gen.claim_job(self.slide)
        barrier = Barrier(2)
        def publish():
            close_old_connections()
            try:
                slide = Slide.objects.get(pk=self.slide.pk)
                barrier.wait(timeout=10)
                return gen.save_batch(job, slide, [mcq()], TEXT, 'mcq', 'easy', 1)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: publish(), range(2)))
        self.assertEqual(sorted(results), [0, 1])
        self.assertEqual(QuizQuestion.objects.count(), 1)


class ProviderValidationTests(SimpleTestCase):
    @patch('curriculum.services.ai_question_generator._generate')
    def test_theory_retry_includes_citation_feedback_and_existing_stems(self, provider):
        import json
        from types import SimpleNamespace
        provider.return_value = json.dumps([theory(99, 'hard')])
        AIQuestionGenerator.generate_theory_from_text(TEXT, SimpleNamespace(subject=None), None, 1, 'hard',
            exclude_questions=['Explain the existing arrangement.'],
            retry_feedback='Copy an exact quotation from its cited page.')
        prompt = provider.call_args.args[0][0]
        self.assertIn('Explain the existing arrangement.', prompt)
        self.assertIn('Copy an exact quotation from its cited page.', prompt)
        self.assertIn(TEXT, prompt)

    def test_source_windows_include_last_page_and_preserve_long_page_labels(self):
        text = '\n\n'.join(f'[Page {i}]\n' + (f'Source page {i}. ' * 2000) for i in range(1, 11))
        chunks = AIQuestionGenerator._chunk_text(text, max_chars=1000)
        self.assertTrue(all(chunk.startswith('[Page ') and len(chunk) <= 1000 for chunk in chunks))
        windows = AIQuestionGenerator._source_windows(text, 5)
        self.assertEqual(len(windows), 5)
        self.assertIn('[Page 1]', windows[0])
        self.assertIn('[Page 10]', windows[-1])

    @patch('curriculum.services.ai_question_generator._generate')
    def test_provider_oversupply_does_not_skip_later_selected_source_windows(self, provider):
        import json
        from types import SimpleNamespace
        source = '\n\n'.join(f'[Page {i}]\n' + (f'Page {i} source content. ' * 1000) for i in range(1, 11))
        provider.return_value = json.dumps([mcq(i) for i in range(50)])
        AIQuestionGenerator.generate_mcqs_from_text(source, SimpleNamespace(subject=None), None, 5, 'easy')
        self.assertEqual(provider.call_count, 5)
        self.assertIn('[Page 10]', provider.call_args.args[0][0])

    @patch('curriculum.services.ai_question_generator._generate')
    def test_successful_source_window_is_flushed_before_a_later_provider_failure(self, provider):
        import json
        from types import SimpleNamespace
        provider.side_effect = [json.dumps([mcq()]), RuntimeError('temporary provider failure')]
        persisted = []
        requested = []
        with self.assertRaises(RuntimeError):
            AIQuestionGenerator.generate_mcqs_from_text(
                TEXT * 40,
                SimpleNamespace(subject=None),
                None,
                5,
                'easy',
                on_batch=persisted.extend,
                on_request=lambda: requested.append(True),
            )
        self.assertEqual(len(persisted), 1)
        self.assertEqual(len(requested), 2)

    @patch('curriculum.services.ai_question_generator._generate')
    def test_missing_or_invalid_answer_is_never_invented_as_a(self, provider):
        import json
        from types import SimpleNamespace
        provider.return_value = json.dumps([dict(mcq(), correct_option='Z'), dict(mcq(), correct_option='A or B'), mcq()])
        rows = AIQuestionGenerator.generate_mcqs_from_text(TEXT, SimpleNamespace(subject=None), None, 3, 'easy')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['correct_option'], 'B')

    @patch('curriculum.services.ai_question_generator._generate', side_effect=RateLimitExceeded('rate limited'))
    def test_provider_failure_propagates_to_durable_retry_without_skipping_source(self, provider):
        from types import SimpleNamespace
        with self.assertRaises(RateLimitExceeded):
            AIQuestionGenerator.generate_mcqs_from_text(TEXT * 40, SimpleNamespace(subject=None), None, 10, 'easy')
        provider.assert_called_once()


class QuestionRepairTests(BankFixture, TestCase):
    def prepare_shortfall(self):
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')), patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')):
            self.assertTrue(gen.generate_for_slide(self.slide)['success'])
        QuizQuestion.objects.filter(source_slide=self.slide, question_type='theory', difficulty='hard').first().delete()
        return set(QuizQuestion.objects.values_list('pk', flat=True))

    def test_missing_theory_question_gets_one_citation_repair_and_keeps_saved_bank(self):
        saved = self.prepare_shortfall()
        invalid = dict(theory(999, 'hard'), source_quote='An assertion absent from the uploaded document.')
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text') as mcqs, patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=[[invalid], [theory(999, 'hard')]]) as provider:
            result = gen.generate_for_slide(self.slide, force=True)
        self.assertTrue(result['success'], result)
        self.assertEqual((result['mcq_generated'], result['theory_generated']), (15, 10))
        self.assertEqual(provider.call_count, 2)
        self.assertTrue(all(call.kwargs['count'] == 1 and call.kwargs['difficulty'] == 'hard'
                            for call in provider.call_args_list))
        self.assertIn('did not match', provider.call_args.kwargs['retry_feedback'])
        self.assertEqual(len(provider.call_args.kwargs['exclude_questions']), 9)
        self.assertTrue(saved <= set(QuizQuestion.objects.values_list('pk', flat=True)))
        self.assertFalse(QuizQuestion.objects.filter(source_text=invalid['source_quote']).exists())
        mcqs.assert_not_called()

    def test_repeated_bad_evidence_stops_after_one_repair_without_marking_bank_complete(self):
        saved = self.prepare_shortfall()
        with patch.object(AIQuestionGenerator, 'generate_theory_from_text', return_value=[
                dict(theory(999, 'hard'), source_page=99)]) as provider:
            result = gen.generate_for_slide(self.slide, force=True)
        self.assertFalse(result['success'])
        self.assertEqual(result['theory_generated'], 9)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(saved, set(QuizQuestion.objects.values_list('pk', flat=True)))
