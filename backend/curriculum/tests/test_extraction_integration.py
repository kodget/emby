import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup
from curriculum import views
from curriculum.models import Slide, SlideContent, SlideChunk, SlideProcessingStatus, MediaAsset, SlideDeck
from curriculum.services.document_extraction import (
    ExtractionError, content_text, ensure_slide_extraction, extract_document, source_key,
)
from curriculum.rag_service import RAGService
from curriculum.tasks import process_slide_task, generate_question_bank_task, _extract_text_from_content
from curriculum.tests.test_document_extraction import pdf_bytes
from learning.generation import slide_text, generate_for_slide
from learning.models import QuestionGenerationJob


class ExtractionIntegrationTests(TestCase):
    def setUp(self):
        queued = patch('curriculum.tasks.generate_question_bank_task.delay')
        self.queue = queued.start()
        self.addCleanup(queued.stop)
        school = School.objects.create(name='Extraction school')
        self.group = ClassGroup.objects.create(school=school, set_name='Year 1', code='234567')
        self.user = User.objects.create_user('extractor')
        self.user.profile.class_group = self.group
        self.user.profile.class_role = 'material_uploader'
        self.user.profile.save()
        self.slide = Slide.objects.create(id='extract', title='Extraction lecture', file_type='pdf',
            class_group=self.group, uploaded_by=self.user, file_url='https://storage.invalid/lecture.pdf')
        self.queue.reset_mock()
        self.raw = pdf_bytes()
        download = patch('curriculum.services.slide_conversion_pipeline._download_from_cloudinary', return_value=self.raw)
        self.download = download.start()
        self.addCleanup(download.stop)
        self.factory = APIRequestFactory()

    def request(self, handler, *, post=False):
        req = self.factory.post('/api/test/', {}, format='json') if post else self.factory.get('/api/test/')
        force_authenticate(req, self.user)
        return handler(req, slide_id=self.slide.pk)

    def asset(self, *args, **kwargs):
        return MediaAsset.objects.create(class_group=self.group, uploaded_by=self.user,
            public_id=f'extraction/{MediaAsset.objects.count()}.jpg', resource_type='image',
            delivery_type='authenticated', format='jpg')

    def cache(self, data, **kwargs):
        return SlideContent.objects.create(slide=self.slide, content_data=data, **kwargs)

    def test_legacy_prefix_cache_is_replaced_using_every_original_page(self):
        asset = self.asset()
        self.cache({'text': 'first three pages ' * 50, 'resources': {'saved': True},
                    'pages': [{'page_number': 1, 'asset_id': str(asset.pk), 'width': 600}]}, is_extracted=True)
        text = slide_text(self.slide)
        self.assertIn('[Page 5]', text)
        self.assertIn('Final marker number 5', text)
        content = SlideContent.objects.get(slide=self.slide)
        self.assertEqual(content.content_data['pages'][0]['asset_id'], str(asset.pk))
        self.assertEqual(content.content_data['resources'], {'saved': True})
        self.assertTrue(content.is_extracted)
        self.assertEqual(slide_text(self.slide), text)
        self.download.assert_called_once()

    def test_complete_cache_from_another_source_is_not_reused(self):
        data = extract_document(self.raw, 'pdf')
        data['text_extraction']['source_key'] = 'old-source'
        self.cache(data)
        result = ensure_slide_extraction(self.slide)
        self.assertEqual(result['text_extraction']['source_key'], source_key(self.slide))
        self.download.assert_called_once()

    def test_failed_source_download_retains_previous_pages_and_safe_error(self):
        original = {'text': 'old text', 'pages': [{'page_number': 1, 'image_url': 'previous-image'}]}
        self.cache(original, is_extracted=True)
        self.download.side_effect = RuntimeError('https://storage.invalid/?signature=secret')
        with self.assertRaises(ExtractionError):
            ensure_slide_extraction(self.slide)
        content = SlideContent.objects.get(slide=self.slide)
        self.assertEqual(content.content_data, original)
        self.assertNotIn('secret', content.extraction_error)
        self.assertTrue(content.is_extracted)

    def test_ocr_failure_blocks_question_provider_and_persists_a_failed_job(self):
        self.download.return_value = pdf_bytes(scanned=(4, 5))
        with patch.dict(os.environ, {'TESSDATA_PREFIX': '/missing-data'}), patch(
                'curriculum.services.ai_question_generator.AIQuestionGenerator.generate_mcqs_from_text') as provider:
            result = generate_for_slide(self.slide)
        self.assertFalse(result['success'])
        self.assertEqual(result['text_extraction']['missing_pages'], [4, 5])
        provider.assert_not_called()
        self.assertEqual(QuestionGenerationJob.objects.get(slide=self.slide).status, 'failed')
        self.assertEqual(SlideContent.objects.get(slide=self.slide).content_data['text_extraction']['status'], 'partial')

    def test_question_task_does_not_mark_extraction_failure_as_completed(self):
        self.download.return_value = pdf_bytes(scanned=(5,))
        SlideProcessingStatus.objects.create(slide=self.slide)
        with patch.dict(os.environ, {'TESSDATA_PREFIX': '/missing-data'}):
            result = generate_question_bank_task.run(self.slide.pk)
        self.assertFalse(result['success'])
        self.slide.refresh_from_db()
        self.assertEqual(self.slide.generation_status, 'failed')
        self.assertEqual(SlideProcessingStatus.objects.get(slide=self.slide).status, 'failed')

    def test_skipped_generation_does_not_claim_completion(self):
        self.slide.generation_status = 'in_progress'; self.slide.save()
        with patch('learning.generation.generate_for_slide', return_value={'skipped': True}):
            generate_question_bank_task.run(self.slide.pk)
        self.slide.refresh_from_db()
        self.assertEqual(self.slide.generation_status, 'in_progress')

    def test_worker_stores_every_pages_text_and_queues_only_complete_extraction(self):
        with self.captureOnCommitCallbacks(execute=True), patch('curriculum.private_media.upload_asset', side_effect=self.asset):
            result = process_slide_task.run(self.slide.pk)
        self.assertTrue(result['success'], result)
        content = SlideContent.objects.get(slide=self.slide)
        self.assertEqual(len(content.content_data['pages']), 5)
        self.assertIn('Final marker number 5', _extract_text_from_content(content.content_data))
        self.assertEqual(content.content_data['text_extraction']['status'], 'complete')
        self.assertTrue(SlideProcessingStatus.objects.get(slide=self.slide).content_extracted)
        self.assertTrue(content.is_extracted)
        self.queue.assert_called_once_with(self.slide.pk)

    def test_partial_worker_keeps_readable_images_and_does_not_queue_questions(self):
        self.download.return_value = pdf_bytes(scanned=(2,), count=2)
        with patch.dict(os.environ, {'TESSDATA_PREFIX': '/missing-data'}), patch(
                'curriculum.private_media.upload_asset', side_effect=self.asset):
            result = process_slide_task.run(self.slide.pk)
        self.assertFalse(result['success'])
        self.assertTrue(result['reading_ready'])
        content = SlideContent.objects.get(slide=self.slide)
        self.assertTrue(content.is_extracted)
        self.assertEqual(len(content.content_data['pages']), 2)
        self.assertEqual(content.content_data['text_extraction']['missing_pages'], [2])
        self.assertEqual(result['page_errors'], {'ocr_unavailable': 1})
        self.queue.assert_not_called()

    def test_rag_indexes_all_pages_in_global_order_and_reuses_verified_index(self):
        service = RAGService()
        with patch.object(service, 'generate_embedding', return_value=[1.0, 0.0]) as embed:
            self.assertTrue(service.process_slide(self.slide))
            self.assertTrue(service.process_slide(self.slide))
        self.assertEqual(embed.call_count, 5)
        rows = list(SlideChunk.objects.filter(slide=self.slide))
        self.assertEqual([row.chunk_index for row in rows], [0, 1, 2, 3, 4])
        self.assertEqual([row.page_number for row in rows], [1, 2, 3, 4, 5])
        self.assertIn('Final marker number 5', rows[-1].text)

    def test_rag_failure_keeps_old_chunks_without_claiming_a_complete_index(self):
        old = SlideChunk.objects.create(slide=self.slide, chunk_index=0, text='previous verified chunk', embedding=[1.0, 0.0])
        service = RAGService()
        with patch.object(service, 'generate_embedding', side_effect=[[1.0, 0.0], None]):
            self.assertFalse(service.process_slide(self.slide))
        self.assertEqual(list(SlideChunk.objects.values_list('pk', flat=True)), [old.pk])
        self.assertFalse(SlideProcessingStatus.objects.get(slide=self.slide).is_embedded)

    def test_rag_insert_failure_rolls_back_deletion(self):
        old = SlideChunk.objects.create(slide=self.slide, chunk_index=0, text='previous verified chunk')
        service = RAGService()
        with patch.object(service, 'generate_embedding', return_value=[1.0, 0.0]), patch(
                'curriculum.rag_service.SlideChunk.objects.bulk_create', side_effect=RuntimeError('write failed')):
            self.assertFalse(service.process_slide(self.slide))
        self.assertTrue(SlideChunk.objects.filter(pk=old.pk).exists())

    def test_legacy_rag_index_is_rebuilt_instead_of_trusted(self):
        SlideProcessingStatus.objects.create(slide=self.slide, is_embedded=True, chunk_count=1)
        SlideChunk.objects.create(slide=self.slide, chunk_index=0, text='first page only')
        service = RAGService()
        with patch.object(service, 'generate_embedding', return_value=[1.0, 0.0]):
            self.assertTrue(service.process_slide(self.slide))
        self.assertEqual(SlideChunk.objects.count(), 5)

    def test_reader_exposes_missing_pages_and_retry_permission_without_hiding_images(self):
        data = extract_document(pdf_bytes(scanned=(2,), count=2), 'pdf', ocr=False)
        for page in data['pages']:
            page['asset_id'] = str(self.asset().pk)
        self.cache(data, is_extracted=True)
        response = self.request(views.get_slide_content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['text_extraction']['missing_pages'], [2])
        self.assertTrue(response.data['can_reprocess'])
        self.assertEqual(len(response.data['pages']), 2)
        self.user.profile.class_role = 'student'; self.user.profile.save()
        self.assertFalse(self.request(views.get_slide_content).data['can_reprocess'])

    def test_retry_requires_uploader_and_broker_errors_are_safe(self):
        with patch('curriculum.tasks.process_slide_task.delay', side_effect=RuntimeError('redis://secret')):
            response = self.request(views.reprocess_slide, post=True)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secret', str(response.data))
        self.user.profile.class_role = 'student'; self.user.profile.save()
        with patch('curriculum.tasks.process_slide_task.delay') as queue:
            self.assertEqual(self.request(views.reprocess_slide, post=True).status_code, 403)
            queue.assert_not_called()

    def test_page_text_takes_precedence_over_old_top_level_prefix(self):
        data = extract_document(self.raw, 'pdf')
        data['text'] = 'outdated prefix'
        self.assertIn('Final marker number 5', _extract_text_from_content(data))
        self.assertNotIn('outdated prefix', content_text(data))

    def test_opening_reader_preserves_previously_completed_ocr_and_saved_resources(self):
        data = extract_document(self.raw, 'pdf')
        data['text_extraction']['source_key'] = source_key(self.slide)
        data['pages'][0]['text'] = 'Previously recovered OCR text'
        data['resources'] = {'saved': True}
        self.cache(data)
        with patch('curriculum.private_media.upload_asset', side_effect=self.asset):
            response = self.request(views.get_slide_content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['pages'][0]['text'], 'Previously recovered OCR text')
        content = SlideContent.objects.get(slide=self.slide)
        self.assertEqual(content.content_data['resources'], {'saved': True})
        self.assertEqual(content.content_data['text_extraction']['status'], 'complete')

    def test_standalone_deck_saves_page_text_and_distinguishes_partial_ocr_from_rendering(self):
        for scanned in ((), (2,)):
            with self.subTest(scanned=scanned):
                deck = SlideDeck.objects.create(id=f'deck-{len(scanned)}', title='Standalone',
                    uploaded_by=self.user, class_group=self.group, file_type='pdf', asset=self.asset())
                with patch('curriculum.deck_processing.upload_asset', side_effect=self.asset), patch('requests.get') as get, patch.dict(
                        os.environ, {'TESSDATA_PREFIX': '/missing-data'}):
                    get.return_value.status_code = 200
                    get.return_value.content = pdf_bytes(scanned=scanned, count=2)
                    views.SlideDeckViewSet()._process_deck_async(deck)
                deck.refresh_from_db()
                self.assertEqual(deck.processing_status, 'completed', deck.processing_error)
                self.assertEqual(deck.pages.count(), 2)
                self.assertIn('Final marker number 1', deck.pages.get(slide_number=1).extracted_text)
                self.assertEqual(deck.text_extraction['status'], 'partial' if scanned else 'complete')
                self.assertEqual(deck.text_extraction['missing_pages'], list(scanned))
                from curriculum.serializers import SlideDeckSerializer
                self.assertEqual(SlideDeckSerializer(deck).data['text_extraction'], deck.text_extraction)

    def test_blank_page_does_not_reuse_old_text_blocks_or_document_prefix(self):
        self.assertEqual(content_text({'text': 'stale prefix', 'text_extraction': {'status': 'complete'},
            'pages': [{'page_number': 1, 'text': '', 'extraction_status': 'blank', 'text_blocks': ['stale page']}]}), '')

    def test_legacy_ai_endpoints_report_incomplete_extraction_before_calling_provider(self):
        self.download.return_value = pdf_bytes(scanned=(2,), count=2)
        with patch.dict(os.environ, {'TESSDATA_PREFIX': '/missing-data'}), patch(
                'curriculum.views.has_premium_access', return_value=True):
            for handler in (views.get_textbook_suggestions, views.get_video_suggestions, views.generate_slide_mcqs):
                request = self.factory.post('/api/test/', {'slide_id': self.slide.pk}, format='json')
                force_authenticate(request, self.user)
                response = handler(request)
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data['text_extraction']['missing_pages'], [2])
