"""Reader availability and grounded AI access do not depend on synchronous OCR."""
from datetime import timedelta
from unittest.mock import patch, Mock

from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone

from curriculum import document_index as index, llm, slide_processing
from curriculum.models import DocumentIndexJob, SlideContent, SlideDeck, SlidePage
from curriculum.services.document_extraction import ensure_slide_extraction, is_complete
from curriculum.tests.test_slide_processing import ProcessingFixture


def visual_read(source, page):
    return {**page, 'text': f"Detailed image content for page {page['page_number']}. " * 15,
            'extraction_status': 'complete', 'extraction_method': 'vision', 'error_code': ''}


class VisualIndexTests(ProcessingFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.mocks()
        for page in self.result['pages']:
            page.update(text='', extraction_status='needs_ocr', extraction_method='ocr', error_code='incomplete')
        self.result['text_content'] = ''
        self.result['text_extraction'].update(status='failed', missing_pages=[1, 2], processed_pages=0)
        self.vision = patch('curriculum.document_index.llm.supports_vision', return_value=True).start()
        self.local = patch.object(index, 'read_page_locally', side_effect=lambda source, page:
            {**page, 'local_ocr_version': index.LOCAL_OCR_VERSION}).start()
        self.addCleanup(patch.stopall)

    def render(self):
        result = slide_processing.process(self.slide.pk)
        self.assertTrue(result['success'])
        self.assertTrue(result['reading_ready'])
        self.assertFalse(result['ai_ready'])
        return DocumentIndexJob.objects.get(slide=self.slide)

    def test_render_succeeds_and_visual_index_unlocks_shared_content(self):
        job = self.render()
        self.state.refresh_from_db()
        self.assertEqual(self.state.status, 'indexing')
        self.generate.assert_not_called()
        with patch.object(index, 'read_page', side_effect=visual_read) as reader:
            self.assertTrue(index.run(job.pk))
            self.assertFalse(index.run(job.pk))
        self.assertEqual(reader.call_count, 2)
        with patch('curriculum.services.document_extraction.extract_document') as old_extractor:
            data = ensure_slide_extraction(self.slide)
        old_extractor.assert_not_called()
        self.assertTrue(is_complete(data))
        self.assertEqual(data['text_extraction']['vision_pages'], [1, 2])
        self.generate.assert_called_once()
        self.assertTrue(all(p.get('asset_id') for p in data['pages']))

    def test_retry_reuses_successful_pages_without_rerendering(self):
        job = self.render()
        def read(source, page):
            if page['page_number'] == 2:
                raise index.IndexUnavailable('visual_read_failed')
            return visual_read(source, page)
        with patch.object(index, 'read_page', side_effect=read):
            self.assertFalse(index.run(job.pk))
        content = SlideContent.objects.get(slide=self.slide)
        self.assertEqual(content.content_data['pages'][0]['extraction_method'], 'vision')
        self.assertTrue(content.is_extracted)
        self.assertTrue(index.request_index(self.slide, force=True))
        with patch.object(index, 'read_page', side_effect=visual_read) as reader:
            self.assertTrue(index.run(job.pk))
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(reader.call_args.args[1]['page_number'], 2)
        self.assertEqual(self.upload.call_count, 2)

    def test_provider_cooldown_keeps_pages_and_defers_recovery_without_spending_failure_budget(self):
        job = self.render()
        before = timezone.now()
        def read(source, page):
            if page['page_number'] == 2:
                raise llm.LLMRateLimited(retry_after=1094)
            return visual_read(source, page)
        with patch.object(index, 'read_page', side_effect=read):
            self.assertFalse(index.run(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.error_code, 'provider_rate_limited')
        self.assertEqual(job.attempts, 0)
        self.assertGreaterEqual(job.next_attempt_at, before + timedelta(seconds=1094))
        self.assertEqual(index.status_for(self.slide)['status'], 'pending')
        self.assertFalse(index.request_index(self.slide, force=True))
        self.assertEqual(index.recover(), 0)
        self.assertTrue(SlideContent.objects.get(slide=self.slide).is_extracted)
        DocumentIndexJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        self.assertTrue(index.request_index(self.slide))
        with patch.object(index, 'read_page', side_effect=visual_read) as reader:
            self.assertTrue(index.run(job.pk))
        reader.assert_called_once()
        self.assertEqual(reader.call_args.args[1]['page_number'], 2)
        self.assertEqual(self.upload.call_count, 2)

    def test_source_replacement_fences_an_old_image_read(self):
        job = self.render()
        def replace(source, page):
            token = slide_processing.reserve(self.slide.pk, manual=True)
            self.assertTrue(slide_processing.process(self.slide.pk, token=token)['success'])
            return visual_read(source, page)
        with patch.object(index, 'read_page', side_effect=replace):
            self.assertFalse(index.run(job.pk))
        data = SlideContent.objects.get(slide=self.slide).content_data
        self.assertTrue(all(p['extraction_status'] == 'needs_ocr' for p in data['pages']))
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')

    def test_local_text_recognition_finishes_without_any_provider_call(self):
        job = self.render()
        self.local.side_effect = lambda source, page: {**visual_read(source, page),
            'extraction_method': 'ocr', 'local_ocr_version': index.LOCAL_OCR_VERSION}
        with patch.object(index, 'read_page') as vision:
            self.assertTrue(index.run(job.pk))
        vision.assert_not_called()
        self.assertTrue(is_complete(index.source_data(self.slide)))
        self.assertEqual(index.source_data(self.slide)['text_extraction']['ocr_pages'], [1, 2])

    def test_old_provider_wait_does_not_block_first_local_scan(self):
        job = self.render()
        DocumentIndexJob.objects.filter(pk=job.pk).update(status='failed',
            error_code='provider_rate_limited', next_attempt_at=timezone.now()+timedelta(hours=1))
        self.assertTrue(index.request_index(self.slide, requested=True))
        self.local.side_effect = lambda source, page: {**visual_read(source, page),
            'extraction_method': 'ocr', 'local_ocr_version': index.LOCAL_OCR_VERSION}
        with patch.object(index, 'read_page') as vision:
            self.assertTrue(index.run(job.pk))
        vision.assert_not_called()

    def test_later_page_ocr_is_saved_before_earlier_page_vision_hits_quota(self):
        job = self.render()
        self.local.side_effect = lambda source, page: {**(visual_read(source, page) if page['page_number'] == 2 else page),
            'extraction_method': 'ocr', 'local_ocr_version': index.LOCAL_OCR_VERSION}
        with patch.object(index, 'read_page', side_effect=llm.LLMRateLimited(retry_after=100)):
            self.assertFalse(index.run(job.pk))
        data = index.source_data(self.slide)
        self.assertEqual(data['text_extraction']['missing_pages'], [1])
        self.assertEqual(data['pages'][1]['extraction_status'], 'complete')

    def test_local_scan_is_bounded_and_resumes_before_vision(self):
        job = self.render()
        with patch.object(index, 'BATCH_SIZE', 1), patch.object(index, 'read_page') as vision:
            self.assertFalse(index.run(job.pk))
        self.local.assert_called_once()
        vision.assert_not_called()
        self.local.reset_mock()
        with patch.object(index, 'read_page', side_effect=visual_read):
            self.assertTrue(index.run(job.pk))
        self.local.assert_called_once()
        self.assertEqual(self.local.call_args.args[1]['page_number'], 2)

    def test_broker_failure_keeps_pages_and_recoverable_request(self):
        job = self.render()
        with patch('curriculum.tasks.index_document_task.delay', side_effect=RuntimeError('offline')):
            self.assertFalse(index.publish(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')
        self.assertIsNotNone(job.next_attempt_at)
        self.assertTrue(SlideContent.objects.get(slide=self.slide).is_extracted)
        DocumentIndexJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        with patch('curriculum.tasks.index_document_task.delay') as send:
            self.assertEqual(index.recover(), 1)
        send.assert_called_once_with(job.pk)

    def test_expired_lease_recovers_and_repeated_failures_stop(self):
        job = self.render()
        DocumentIndexJob.objects.filter(pk=job.pk).update(status='running', lease_token=None,
            lease_expires_at=timezone.now()-timedelta(seconds=1), attempts=index.MAX_FAILURES)
        self.assertEqual(index.recover(), 0)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIsNone(job.next_attempt_at)
        self.assertTrue(SlideContent.objects.get(slide=self.slide).is_extracted)

    def test_standalone_pages_get_the_same_searchable_visual_content(self):
        self.render()
        data = SlideContent.objects.get(slide=self.slide).content_data
        deck = SlideDeck.objects.create(id='visual-deck', title='Visual lecture', file_type='pdf',
            original_file='', uploaded_by=self.user, class_group=self.group, page_count=2,
            processing_status='completed', text_extraction={**data['text_extraction'],
            'pages': [{k:v for k,v in p.items() if k != 'text'} for p in data['pages']]})
        for p in data['pages']:
            SlidePage.objects.create(deck=deck, slide_number=p['page_number'], asset_id=p['asset_id'])
        index.request_index(deck)
        with patch.object(index, 'read_page', side_effect=visual_read):
            self.assertTrue(index.run(DocumentIndexJob.objects.get(deck=deck).pk))
        deck.refresh_from_db()
        self.assertEqual(deck.processing_status, 'completed')
        self.assertTrue(is_complete(index.source_data(deck)))
        self.assertIn('Detailed image content', deck.pages.first().extracted_text)
        from curriculum.library_tutor import library_context
        text, sources, count = library_context(self.user, 'Detailed image content')
        self.assertIn('Detailed image content', text)
        self.assertTrue(any(p['kind'] == 'deck' for p in sources))

    def test_current_image_chat_works_before_indexing_and_missing_page_is_not_charged(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from curriculum.ai_views import chat_with_slide
        self.render()
        with patch.object(index, 'page_image', return_value='server-owned-image') as image, \
                patch('curriculum.ai_views.slide_ai.chat', return_value={'response': 'From Page 2', 'total_tokens': 20}) as chat, \
                patch('curriculum.ai_views.CreditManager') as credits:
            credits.reserve_credits.return_value = {'reservation_id': 'test', 'reserved_amount': 3}
            credits.get_user_balance.return_value = 10
            request = APIRequestFactory().post('/api/ai/chat/',
                {'slide_id': self.slide.pk, 'page_number': 2, 'message': 'Explain the diagram'}, format='json')
            force_authenticate(request, self.user)
            response = chat_with_slide(request)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(chat.call_args.kwargs['slide_image_base64'], 'server-owned-image')
            self.assertEqual(chat.call_args.kwargs['slide_context']['image_page'], 2)
            self.assertEqual(image.call_args.args[1]['page_number'], 2)
            credits.reserve_credits.reset_mock()
            request = APIRequestFactory().post('/api/ai/chat/',
                {'slide_id': self.slide.pk, 'page_number': 99, 'message': 'Explain'}, format='json')
            force_authenticate(request, self.user)
            self.assertEqual(chat_with_slide(request).status_code, 409)
            credits.reserve_credits.assert_not_called()

    def test_page_image_rejects_an_asset_from_another_class_before_download(self):
        from accounts.models import ClassGroup
        self.render()
        data = SlideContent.objects.get(slide=self.slide).content_data
        other = ClassGroup.objects.create(school=self.group.school, set_name='Other', code='999999')
        from curriculum.models import MediaAsset
        MediaAsset.objects.filter(pk=data['pages'][0]['asset_id']).update(class_group=other)
        with patch('requests.get') as download, self.assertRaises(index.IndexUnavailable):
            index.page_image(self.slide, data['pages'][0])
        download.assert_not_called()

    def test_indexed_page_chat_reuses_text_but_diagram_questions_keep_the_image(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from curriculum.ai_views import chat_with_slide
        job = self.render()
        self.local.side_effect = lambda source, page: {**visual_read(source, page),
            'extraction_method': 'ocr', 'local_ocr_version': index.LOCAL_OCR_VERSION}
        self.assertTrue(index.run(job.pk))
        with patch.object(index, 'page_image', return_value='owned-image') as image, \
                patch('curriculum.ai_views.slide_ai.chat', return_value={'response': 'From Page 1', 'total_tokens': 20}) as chat, \
                patch('curriculum.ai_views.CreditManager') as credits:
            credits.reserve_credits.return_value = {'reservation_id': 'test', 'reserved_amount': 3}
            credits.get_user_balance.return_value = 10
            for question, expect_image in [('Explain the main idea', False), ('Explain the diagram', True)]:
                request = APIRequestFactory().post('/api/ai/chat/',
                    {'slide_id': self.slide.pk, 'page_number': 1, 'message': question}, format='json')
                force_authenticate(request, self.user)
                response = chat_with_slide(request)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(bool(chat.call_args.kwargs['slide_image_base64']), expect_image)
            image.assert_called_once()


class VisionProviderTests(SimpleTestCase):
    def test_local_reader_recognizes_real_image_and_keeps_native_text(self):
        import base64
        import fitz
        from curriculum.tests.test_document_extraction import pdf_bytes
        with fitz.open(stream=pdf_bytes(count=1), filetype='pdf') as document:
            image = document[0].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes('png')
        with patch.object(index, 'page_image', return_value=base64.b64encode(image).decode()), \
                patch.object(llm, 'chat_with_image') as provider:
            page = index.read_page_locally(None, {'page_number': 7, 'text': 'Native heading',
                'extraction_status': 'needs_ocr', 'asset_id': 'unchanged'})
        self.assertEqual(page['page_number'], 7)
        self.assertEqual(page['asset_id'], 'unchanged')
        self.assertEqual(page['extraction_status'], 'complete', page)
        self.assertIn('Native heading', page['text'])
        self.assertIn('The heart pumps blood', page['text'])
        provider.assert_not_called()

    def test_chat_cannot_silently_drop_an_unreadable_image(self):
        from curriculum.ai_service import _generate
        with patch.object(llm, 'supports_vision', return_value=True), \
                patch.object(llm, 'chat_with_image', side_effect=llm.LLMError('unavailable')), \
                patch.object(llm, 'chat') as text_chat, self.assertRaises(llm.LLMError):
            _generate(['Explain this image', {'data': 'image'}], require_image=True)
        text_chat.assert_not_called()

    def test_image_routes_only_to_provider_specific_vision_models(self):
        chain = [llm.Provider('text', 'https://text.invalid', 'key', 'text-model', ''),
                 llm.Provider('vision', 'https://vision.invalid', 'key', 'text-model', '', 'image-model')]
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'read image'}, 'finish_reason': 'stop'}]}
        with patch.object(llm, 'providers', return_value=chain), patch.object(llm.requests, 'post', return_value=response) as post:
            self.assertEqual(llm.chat_with_image('read', 'image', require_complete=True), 'read image')
        self.assertEqual(post.call_args.args[0], 'https://vision.invalid/chat/completions')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'image-model')

    def test_truncated_image_reading_cannot_be_marked_complete(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': '{"text":"prefix"}'}, 'finish_reason': 'length'}]}
        with patch.object(llm.requests, 'post', return_value=response):
            content, error, _, _ = llm._try_model('url', {}, {}, '', require_complete=True)
        self.assertIsNone(content)
        self.assertEqual(error, 'incomplete image reading')

    @override_settings(LLM_VISION_MODEL='')
    def test_explicit_empty_setting_disables_primary_vision(self):
        self.assertEqual(llm.vision_model(), '')

    def test_unreadable_image_does_not_become_complete(self):
        with patch.object(index, 'page_image', return_value='image'), patch.object(llm, 'chat_with_image',
                return_value='{"status":"unreadable","text":"I cannot see the labels"}'):
            with self.assertRaises(index.IndexUnavailable):
                index.read_page(None, {'page_number': 1, 'text': ''})
