from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum import ai_views, llm
from curriculum.ai_service import SlideAwareAI, bounded_chat_source
from curriculum.flashcard_dispatch import recover_flashcard_jobs
from curriculum.models import Flashcard, FlashcardGenerationJob, QuizQuestion, SlideChatMessage
from curriculum.tasks import generate_ai_flashcards_from_slide_task
from curriculum.tests.test_bank_recovery import BankFixture, mcq
from learning import generation as gen
from learning.bank_sources import page_sources
from learning.generation_dispatch import request_generation, recover_generation_jobs
from learning.models import QuestionGenerationJob as Job
from learning.source_sampling import assessment_source


class AutomaticBankTests(BankFixture, TestCase):
    def test_partial_progress_continues_beyond_three_runs_without_another_request(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay'), self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(request_generation(self.slide, requested=True))
        for number in range(4):
            first = True
            def partial(**kwargs):
                nonlocal first
                if first:
                    first = False
                    return [mcq(number, kwargs['difficulty'])]
                return []
            with patch(
                'curriculum.services.ai_question_generator.AIQuestionGenerator.generate_mcqs_from_text', side_effect=partial), patch(
                'curriculum.services.ai_question_generator.AIQuestionGenerator.generate_theory_from_text', return_value=[]):
                result = gen.generate_for_slide(self.slide)
            self.assertEqual(result['status'], 'partial')
            job = Job.objects.get(slide=self.slide)
            self.assertEqual(job.attempts, 0)
            self.assertIsNotNone(job.next_attempt_at)
            # Neither a duplicate task nor a manual force skips the wait.
            self.assertTrue(gen.generate_for_slide(self.slide, force=True)['skipped'])
            self.assertFalse(request_generation(self.slide, force=True, requested=True))
            Job.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            with patch('curriculum.tasks.generate_question_bank_task.delay') as queue:
                self.assertEqual(recover_generation_jobs()['published'], 1)
            queue.assert_called_once_with(self.slide.pk)
        self.assertEqual(QuizQuestion.objects.count(), 4)
        saved = set(QuizQuestion.objects.values_list('pk', flat=True))
        self.serial = 100
        with patch('curriculum.services.ai_question_generator.AIQuestionGenerator.generate_mcqs_from_text', side_effect=self.rows('mcq')), patch(
            'curriculum.services.ai_question_generator.AIQuestionGenerator.generate_theory_from_text', side_effect=self.rows('theory')):
            self.assertTrue(gen.generate_for_slide(self.slide)['success'])
        self.assertEqual(QuizQuestion.objects.count(), 25)
        self.assertTrue(saved.issubset(set(QuizQuestion.objects.values_list('pk', flat=True))))

    def test_repeated_no_progress_is_bounded(self):
        with patch('curriculum.services.ai_question_generator.AIQuestionGenerator.generate_mcqs_from_text', return_value=[]), patch(
            'curriculum.services.ai_question_generator.AIQuestionGenerator.generate_theory_from_text', return_value=[]):
            for _ in range(Job.MAX_ATTEMPTS):
                gen.generate_for_slide(self.slide)
                Job.objects.filter(slide=self.slide, next_attempt_at__isnull=False).update(
                    next_attempt_at=timezone.now() - timedelta(seconds=1))
        job = Job.objects.get(slide=self.slide)
        self.assertIsNone(job.next_attempt_at)
        self.assertTrue(gen.generate_for_slide(self.slide)['skipped'])


class FlashcardContinuationTests(BankFixture, TestCase):
    def test_repeated_worker_crashes_stop_and_refund_before_more_provider_work(self):
        reservation = {'reservation_id': 'crash-request', 'reserved_amount': 3}
        job = FlashcardGenerationJob.objects.create(user=self.user, slide=self.slide,
            requested_count=5, attempts=3, reservation=reservation)
        with patch('curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text') as provider, patch(
                'credits.services.CreditManager.refund_credits') as refund:
            result = generate_ai_flashcards_from_slide_task.run(self.slide.pk, self.user.pk, 5, None, None, str(job.pk))
        self.assertFalse(result['success'])
        provider.assert_not_called()
        refund.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')

    def test_quota_wait_resumes_partial_cards_and_settles_credits_once(self):
        reservation = {'reservation_id': 'saved-request', 'reserved_amount': 3, 'action': 'GENERATE_FLASHCARDS'}
        job = FlashcardGenerationJob.objects.create(user=self.user, slide=self.slide,
            requested_count=2, reservation=reservation)
        def run():
            return generate_ai_flashcards_from_slide_task.run(self.slide.pk, self.user.pk, 2, None, None, str(job.pk))
        first = [{'front': 'First fact?', 'back': 'First answer.'}]
        second = [{'front': 'Second fact?', 'back': 'Second answer.'}]
        with patch('curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
                   side_effect=[(first, 30), llm.LLMRateLimited(retry_after=900), (second, 40)]) as provider, patch(
                   'credits.services.CreditManager.commit_usage') as commit, patch(
                   'credits.services.CreditManager.refund_credits') as refund, patch(
                   'curriculum.ai_views._dispatch_flashcard_job') as dispatch:
            run()
            job.refresh_from_db()
            self.assertEqual((job.status, job.generated_count), ('queued', 1))
            commit.assert_not_called()
            FlashcardGenerationJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(recover_flashcard_jobs()['published'], 1)
            run()
            job.refresh_from_db()
            self.assertEqual(job.status, 'queued')
            self.assertGreater(job.next_attempt_at, timezone.now() + timedelta(seconds=890))
            self.assertEqual(recover_flashcard_jobs()['published'], 0)
            run()  # Early redelivery must not call the provider.
            self.assertEqual(provider.call_count, 2)
            request = APIRequestFactory().get('/api/test/')
            force_authenticate(request, self.user)
            self.assertEqual(ai_views.flashcard_generation_status(request, job.pk).data['status'], 'queued')
            self.assertEqual(dispatch.call_count, 1)
            FlashcardGenerationJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(recover_flashcard_jobs()['published'], 1)
            run()
            run()  # Completed-task redelivery is harmless.
            job.refresh_from_db()
            self.assertEqual((job.status, job.generated_count), ('completed', 2))
            self.assertEqual(Flashcard.objects.filter(source_slide=self.slide).count(), 2)
            commit.assert_called_once_with(self.user, reservation, 70)
            refund.assert_not_called()

    def test_chat_quota_returns_retry_deadline_and_refunds_without_saving_exchange(self):
        request = APIRequestFactory().post('/api/ai/chat/', {'slide_id': self.slide.pk, 'message': 'Explain this'}, format='json')
        force_authenticate(request, self.user)
        with patch('curriculum.ai_views.CreditManager.reserve_credits', return_value={
            'reservation_id': 'chat', 'reserved_amount': 3}), patch('curriculum.ai_views.CreditManager.refund_credits') as refund, patch(
            'curriculum.ai_views.slide_ai.chat', return_value={
                'error': 'Please wait', 'error_code': 'rate_limited', 'retry_after': 12}):
            response = ai_views.chat_with_slide(request)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '12')
        refund.assert_called_once()
        self.assertFalse(SlideChatMessage.objects.exists())


class PromptBudgetTests(SimpleTestCase):
    def test_assessment_sampling_spreads_pages_then_prefers_unrepresented_pages(self):
        text = '\n\n'.join(f'[Page {n}]\n' + (f'Function and mechanism on teaching page {n}. ' * 100) for n in range(1, 31))
        first = assessment_source(text, count=5, seed='batch-one')
        used = list(page_sources(first))
        self.assertEqual(len(used), 5)
        self.assertLessEqual(min(used), 6)
        self.assertGreaterEqual(max(used), 25)
        second = assessment_source(text, count=5, used_pages=used, seed='batch-two')
        self.assertFalse(set(page_sources(second)) & set(used))
        for sample in (first, second):
            self.assertLessEqual(len(sample), 5500)
            for page, quote in page_sources(sample).items():
                self.assertIn(quote, page_sources(text)[page])

    def test_chat_keeps_relevant_late_page_with_bounded_history(self):
        text = '\n\n'.join(f'[Page {n}]\n' + ('general anatomy ' * 500) for n in range(1, 20))
        text += '\n\n[Page 20]\nSpecific cerebellar peduncle pathway.'
        self.assertIn('[Page 20]', bounded_chat_source(text, 'cerebellar peduncle'))
        with patch('curriculum.ai_service._generate', return_value='An answer') as generate:
            result = SlideAwareAI().chat('Explain cerebellar peduncle', {'text': text},
                conversation_history=[{'role': 'assistant', 'content': 'x' * 30000}] * 50)
        self.assertNotIn('error', result)
        prompt = generate.call_args.args[0][-1]
        self.assertLess(len(prompt), 12000)
        self.assertIn('[Page 20]', prompt)

    def test_oversized_chat_retries_once_with_smaller_context_and_keeps_image(self):
        text = '[Page 7]\n' + 'Relevant mechanism and diagram detail. ' * 1000
        with patch('curriculum.ai_service._generate', side_effect=[llm.RequestTooLarge('too large'), ('Answer', 30)]) as generate:
            result = SlideAwareAI().chat('Explain page 7', {'text': text, 'image_page': 7},
                slide_image_base64='test-image', return_usage=True)
        self.assertEqual(result['total_tokens'], 30)
        first, second = generate.call_args_list
        self.assertLess(len(second.args[0][-1]), len(first.args[0][-1]))
        self.assertTrue(second.kwargs['require_image'])
        self.assertEqual(second.args[0][0]['data'], 'test-image')

    def test_oversized_chat_stops_after_one_compact_retry(self):
        with patch('curriculum.ai_service._generate', side_effect=llm.RequestTooLarge('too large')) as generate:
            result = SlideAwareAI().chat('Explain', {'text': 'source'})
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(result['error_code'], 'request_too_large')
