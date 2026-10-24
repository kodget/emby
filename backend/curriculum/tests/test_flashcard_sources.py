import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum import ai_views
from curriculum import views
from curriculum.models import Flashcard, FlashcardGenerationJob, FlashcardProgress, Slide, SlideContent
from curriculum.tasks import generate_ai_flashcards_from_slide_task
from curriculum.tests.test_bank_recovery import BankFixture


class FlashcardSourceTests(BankFixture, TestCase):
    @patch('curriculum.services.ai_flashcard_generator._generate')
    def test_flashcard_generation_samples_bounded_windows_across_all_source_pages(self, generate):
        from curriculum.services.ai_flashcard_generator import AIFlashcardGenerator

        text = '\n\n'.join(
            f'[Page {page}]\n{"Anatomy source material " * 250}END OF PAGE {page}'
            for page in range(1, 4)
        )
        calls = []

        def completion(parts, return_usage=False):
            prompt = parts[0]
            calls.append(prompt)
            response = [{
                'front': f'Question from source window {len(calls)}',
                'back': f'Answer from source window {len(calls)}',
                'explanation': '',
            }]
            return (json.dumps(response), 10 * len(calls)) if return_usage else json.dumps(response)

        generate.side_effect = completion

        cards, tokens = AIFlashcardGenerator.generate_flashcards_from_text(
            text=text,
            slide=self.slide,
            topic=None,
            count=3,
            return_usage=True,
        )

        self.assertEqual(len(calls), 3)
        self.assertTrue(all(len(prompt) < 10_000 for prompt in calls))
        self.assertIn('END OF PAGE 1', calls[0])
        self.assertIn('END OF PAGE 2', calls[1])
        self.assertIn('END OF PAGE 3', calls[2])
        self.assertEqual(len(cards), 3)
        self.assertEqual(tokens, 60)

    def test_generated_cards_are_bound_to_the_source_and_task_retry_is_idempotent(self):
        cards = [{
            'front': 'What does the source describe?',
            'back': 'The documented anatomy.',
            'explanation': 'From the source material.',
        }]
        reservation = {
            'reservation_id': 'flashcard-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=1,
        )
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
            return_value=(cards, 40),
        ) as generate, patch('credits.services.CreditManager.commit_usage') as commit, patch(
            'credits.services.CreditManager.refund_credits',
        ) as refund:
            first = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation, None, str(job.pk),
            )
            redelivery = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation, None, str(job.pk),
            )

        self.assertTrue(first['success'])
        self.assertEqual(first['generated_count'], 1)
        self.assertTrue(redelivery['success'])
        self.assertEqual(redelivery['generated_count'], 1)
        generate.assert_called_once()
        commit.assert_called_once_with(self.user, reservation, 40)
        refund.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')

        flashcard = Flashcard.objects.get(user=self.user, source='ai')
        self.assertEqual(flashcard.source_slide, self.slide)
        self.assertEqual(
            FlashcardProgress.objects.filter(user=self.user, flashcard=flashcard).count(),
            1,
        )

    def test_ai_flashcard_list_is_scoped_to_exact_source_slide(self):
        other_slide = Slide.objects.create(
            id='other-source-slide',
            title='Other source',
            file_type='pdf',
            subject=self.slide.subject,
            uploaded_by=self.user,
            class_group=self.slide.class_group,
        )
        selected = Flashcard.objects.create(
            user=self.user,
            source='ai',
            source_slide=self.slide,
            front='Selected source card',
            back='Selected answer',
            subject=self.slide.subject,
        )
        Flashcard.objects.create(
            user=self.user,
            source='ai',
            source_slide=other_slide,
            front='Selected source card',
            back='Other source answer',
            subject=self.slide.subject,
        )
        request = APIRequestFactory().get('/api/flashcards/', {
            'slide_id': self.slide.pk,
            'source': 'ai',
        })
        force_authenticate(request, self.user)

        response = views.FlashcardViewSet.as_view({'get': 'list'})(request)

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual([row['id'] for row in results], [selected.pk])

    def test_empty_generation_refunds_and_does_not_commit_usage(self):
        reservation = {
            'reservation_id': 'empty-flashcard-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
            return_value=([], 0),
        ), patch('credits.services.CreditManager.commit_usage') as commit, patch(
            'credits.services.CreditManager.refund_credits',
        ) as refund:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation,
            )

        self.assertFalse(result['success'])
        self.assertEqual(Flashcard.objects.filter(user=self.user, source='ai').count(), 0)
        commit.assert_not_called()
        refund.assert_called_once_with(
            self.user,
            3,
            action='REFUND_FLASHCARD_ERROR',
            reservation_id='empty-flashcard-reservation',
        )

    def test_existing_cards_refund_the_new_reservation_without_provider_work(self):
        Flashcard.objects.create(
            user=self.user,
            source='ai',
            source_slide=self.slide,
            front='Existing question',
            back='Existing answer',
        )
        reservation = {
            'reservation_id': 'already-generated-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
        ) as generate, patch('credits.services.CreditManager.refund_credits') as refund:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation,
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['generated_count'], 0)
        generate.assert_not_called()
        refund.assert_called_once_with(
            self.user,
            3,
            action='REFUND_FLASHCARD_ERROR',
            reservation_id='already-generated-reservation',
        )

    def test_unverified_source_is_rejected_before_provider_call_and_refunded(self):
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['text_extraction']['status'] = 'partial'
        content.save(update_fields=['content_data'])
        reservation = {
            'reservation_id': 'incomplete-flashcard-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
        ) as generate, patch('credits.services.CreditManager.refund_credits') as refund:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation,
            )

        self.assertFalse(result['success'])
        generate.assert_not_called()
        refund.assert_called_once_with(
            self.user,
            3,
            action='REFUND_FLASHCARD_ERROR',
            reservation_id='incomplete-flashcard-reservation',
        )

    def test_flashcard_count_validation_happens_before_credit_reservation(self):
        for count in (0, 21, True, 'not-a-number'):
            with self.subTest(count=count), patch(
                'curriculum.ai_views.CreditManager.reserve_credits',
            ) as reserve:
                request = APIRequestFactory().post('/api/ai/generate-flashcards/', {
                    'slide_id': self.slide.pk,
                    'count': count,
                }, format='json')
                force_authenticate(request, self.user)

                response = ai_views.generate_flashcards(request)

                self.assertEqual(response.status_code, 400)
                reserve.assert_not_called()

    def test_generation_job_records_successful_worker_completion(self):
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=1,
        )
        cards = [{
            'front': 'What does the source describe?',
            'back': 'The documented anatomy.',
            'explanation': '',
        }]
        reservation = {
            'reservation_id': 'job-completion-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
            return_value=(cards, 20),
        ), patch('credits.services.CreditManager.commit_usage'), patch(
            'credits.services.CreditManager.refund_credits',
        ) as refund:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation, None, str(job.pk),
            )

        job.refresh_from_db()
        self.assertTrue(result['success'])
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.generated_count, 1)
        self.assertIsNotNone(job.completed_at)
        refund.assert_not_called()

    def test_generation_job_status_is_visible_only_to_its_owner(self):
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=5,
        )

        request = APIRequestFactory().get(f'/api/ai/flashcards/{job.pk}/')
        force_authenticate(request, self.user)
        response = ai_views.flashcard_generation_status(request, job_id=str(job.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'queued')
        self.assertEqual(response.data['requested_count'], 5)

        from django.contrib.auth.models import User
        other_user = User.objects.create_user('flashcard-status-peer')
        request = APIRequestFactory().get(f'/api/ai/flashcards/{job.pk}/')
        force_authenticate(request, other_user)
        response = ai_views.flashcard_generation_status(request, job_id=str(job.pk))

        self.assertEqual(response.status_code, 404)

    def test_stale_queued_job_is_requeued_when_status_is_checked(self):
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=5,
            reservation={'reservation_id': 'stale-queue', 'reserved_amount': 3, 'action': 'GENERATE_FLASHCARDS'},
        )
        FlashcardGenerationJob.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - timedelta(minutes=3),
        )
        request = APIRequestFactory().get(f'/api/ai/flashcards/{job.pk}/')
        force_authenticate(request, self.user)

        with patch('curriculum.ai_views._dispatch_flashcard_job') as dispatch:
            response = ai_views.flashcard_generation_status(request, job_id=str(job.pk))

        job.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.status, 'queued')
        self.assertIsNone(job.processing_token)
        dispatch.assert_called_once_with(job.pk)

    def test_expired_running_job_invalidates_old_worker_and_requeues(self):
        old_token = uuid4()
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=1,
            status='running',
            processing_token=old_token,
            processing_lease_until=timezone.now() - timedelta(seconds=1),
            reservation={'reservation_id': 'expired-worker', 'reserved_amount': 3, 'action': 'GENERATE_FLASHCARDS'},
        )
        request = APIRequestFactory().get(f'/api/ai/flashcards/{job.pk}/')
        force_authenticate(request, self.user)

        with patch('curriculum.ai_views._dispatch_flashcard_job') as dispatch:
            response = ai_views.flashcard_generation_status(request, job_id=str(job.pk))

        job.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.status, 'queued')
        self.assertIsNone(job.processing_token)
        dispatch.assert_called_once_with(job.pk)

    def test_duplicate_worker_does_not_run_while_generation_lease_is_active(self):
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=1,
            status='running',
            processing_token=uuid4(),
            processing_lease_until=timezone.now() + timedelta(minutes=5),
        )
        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
        ) as generate:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, {}, None, str(job.pk),
            )

        self.assertTrue(result['in_progress'])
        generate.assert_not_called()

    def test_worker_superseded_after_expired_lease_cannot_persist_or_refund(self):
        reservation = {
            'reservation_id': 'superseded-worker-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=1,
            reservation=reservation,
        )
        cards = [{
            'front': 'What does the source describe?',
            'back': 'The documented anatomy.',
            'explanation': '',
        }]

        def provider_response(*args, **kwargs):
            FlashcardGenerationJob.objects.filter(pk=job.pk).update(
                processing_token=uuid4(),
                processing_lease_until=timezone.now() + timedelta(minutes=5),
            )
            return cards, 20

        with patch(
            'curriculum.services.ai_flashcard_generator.AIFlashcardGenerator.generate_flashcards_from_text',
            side_effect=provider_response,
        ), patch('credits.services.CreditManager.commit_usage') as commit, patch(
            'credits.services.CreditManager.refund_credits',
        ) as refund:
            result = generate_ai_flashcards_from_slide_task.run(
                self.slide.pk, self.user.pk, 1, reservation, None, str(job.pk),
            )

        self.assertFalse(result['success'])
        self.assertEqual(Flashcard.objects.filter(user=self.user, source='ai').count(), 0)
        commit.assert_not_called()
        refund.assert_not_called()

    def test_queue_failure_refunds_and_persists_failed_job(self):
        reservation = {
            'reservation_id': 'queue-failure-reservation',
            'reserved_amount': 3,
            'action': 'GENERATE_FLASHCARDS',
        }
        with override_settings(CELERY_TASK_ALWAYS_EAGER=False), patch(
            'curriculum.ai_views.CreditManager.reserve_credits',
            return_value=reservation,
        ), patch(
            'curriculum.ai_views.CreditManager.refund_credits',
        ) as refund, patch(
            'curriculum.tasks.generate_ai_flashcards_from_slide_task.delay',
            side_effect=RuntimeError('queue unavailable'),
        ), patch('curriculum.ai_views.CreditManager.get_user_balance', return_value=0):
            request = APIRequestFactory().post('/api/ai/generate-flashcards/', {
                'slide_id': self.slide.pk,
                'count': 5,
            }, format='json')
            force_authenticate(request, self.user)
            response = ai_views.generate_flashcards(request)

        self.assertEqual(response.status_code, 202)
        job = FlashcardGenerationJob.objects.get(user=self.user, slide=self.slide)
        self.assertEqual(response.data['job_id'], str(job.pk))
        self.assertEqual(job.status, 'failed')
        self.assertIsNotNone(job.completed_at)
        refund.assert_called_once_with(
            self.user,
            3,
            action='REFUND_FLASHCARD_ERROR',
            reservation_id='queue-failure-reservation',
        )

    def test_active_generation_request_is_reused_without_reserving_more_credits(self):
        job = FlashcardGenerationJob.objects.create(
            user=self.user,
            slide=self.slide,
            requested_count=5,
        )
        with patch('curriculum.ai_views.CreditManager.reserve_credits') as reserve, patch(
            'curriculum.ai_views.CreditManager.get_user_balance',
            return_value=12,
        ):
            request = APIRequestFactory().post('/api/ai/generate-flashcards/', {
                'slide_id': self.slide.pk,
                'count': 5,
            }, format='json')
            force_authenticate(request, self.user)
            response = ai_views.generate_flashcards(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['job_id'], str(job.pk))
        self.assertEqual(response.data['balance'], 12)
        reserve.assert_not_called()

    def test_video_suggestions_return_verified_results_when_configured(self):
        verified_video = {
            'title': 'Anatomy dissection',
            'channel': 'Teaching channel',
            'video_id': 'verified-id',
            'url': 'https://www.youtube.com/watch?v=verified-id',
            'thumbnail': 'https://i.ytimg.com/vi/verified-id/mqdefault.jpg',
            'duration': '8:24',
        }
        request = APIRequestFactory().post('/api/ai/video-suggestions/', {
            'slide_id': self.slide.pk,
        }, format='json')
        force_authenticate(request, self.user)
        with patch('curriculum.ai_views.has_premium_access', return_value=True), patch(
            'curriculum.ai_views._get_or_generate_resources',
            return_value={'youtube': [{'title': 'Anatomy dissection', 'query': 'anatomy dissection'}]},
        ), patch('curriculum.youtube_service.is_configured', return_value=True), patch(
            'curriculum.youtube_service.search_videos',
            return_value=[verified_video],
        ):
            response = ai_views.video_suggestions(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'youtube_api')
        self.assertEqual(response.data['videos'], [verified_video])

    def test_video_suggestions_fallback_is_explicitly_ai_search_suggestions(self):
        suggestion = {
            'title': 'Anatomy dissection',
            'query': 'anatomy dissection',
            'reason': 'Review the anatomy.',
        }
        request = APIRequestFactory().post('/api/ai/video-suggestions/', {
            'slide_id': self.slide.pk,
        }, format='json')
        force_authenticate(request, self.user)
        with patch('curriculum.ai_views.has_premium_access', return_value=True), patch(
            'curriculum.ai_views._get_or_generate_resources',
            return_value={'youtube': [suggestion]},
        ), patch('curriculum.youtube_service.is_configured', return_value=False):
            response = ai_views.video_suggestions(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'ai_suggestions')
        self.assertEqual(response.data['videos'], [suggestion])
