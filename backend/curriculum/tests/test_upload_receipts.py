from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import Block, MediaAsset, Slide, SlideDeck, UploadReceipt
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.views import SlideViewSet, SlideDeckViewSet


class UploadFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.key = str(uuid.uuid4())
        self.block = Block.objects.create(id='upload-module', name='Module', subject=self.slide.subject)

    def store(self, *args, **kwargs):
        return MediaAsset.objects.create(class_group=self.user.profile.class_group, uploaded_by=self.user,
            public_id=f'emby/original/{uuid.uuid4()}', resource_type='raw', format='pdf')

    def upload(self, kind='slide', **changes):
        data = {'request_id': self.key, 'title': 'Receipt document',
            'file': SimpleUploadedFile('lecture.pdf', b'%PDF-1.7\noriginal')}
        if kind == 'slide':
            data['subject'] = self.slide.subject_id
            data['block'] = self.block.pk
        data.update(changes)
        request = APIRequestFactory().post('/api/test/', data, format='multipart')
        force_authenticate(request, self.user)
        view, action = (SlideViewSet, 'upload_and_process') if kind == 'slide' else (SlideDeckViewSet, 'create')
        return view.as_view({'post': action})(request)


class UploadReceiptTests(UploadFixture, TestCase):
    def test_saved_upload_processes_then_response_retry_returns_the_same_readable_document(self):
        from pathlib import Path
        import tempfile
        from PIL import Image
        from curriculum.slide_processing import process
        from curriculum.models import SlideContent
        from curriculum.tests.test_bank_recovery import BODY
        with tempfile.TemporaryDirectory(prefix='emby-upload-journey-') as directory:
            path = Path(directory) / 'page.png'
            Image.new('RGB', (20, 30), 'white').save(path)
            converted = {'success': True, 'image_paths': [str(path)], 'page_count': 1,
                'pages': [{'page_number': 1, 'text': BODY, 'extraction_status': 'complete'}],
                'text_extraction': {'version': 1, 'status': 'complete', 'total_pages': 1, 'source_sha256': 'saved-source'}}
            with patch('curriculum.views.upload_asset', side_effect=self.store) as original, patch(
                'curriculum.private_media.upload_asset', side_effect=self.store) as page_upload, patch(
                'curriculum.services.slide_conversion_pipeline.SlideConversionPipeline.process_slide', return_value=converted), patch(
                'learning.generation_dispatch.request_generation') as generation, patch(
                'curriculum.slide_uploads.dispatch_slide_processing', side_effect=process):
                with self.captureOnCommitCallbacks(execute=True):
                    first = self.upload()
                second = self.upload()
            self.assertEqual((first.status_code, second.status_code), (201, 201))
            self.assertEqual(first.data['id'], second.data['id'])
            saved = Slide.objects.get(pk=first.data['id'])
            self.assertEqual(saved.page_count, 1)
            page = SlideContent.objects.get(slide=saved).content_data['pages'][0]
            self.assertEqual(page['text'], BODY)
            self.assertTrue(MediaAsset.objects.filter(pk=page['asset_id'], class_group=saved.class_group).exists())
            original.assert_called_once(); page_upload.assert_called_once(); generation.assert_called_once()

    def test_repeated_course_upload_returns_saved_document_and_dispatches_once(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
            'curriculum.slide_uploads.dispatch_slide_processing') as dispatch, self.captureOnCommitCallbacks(execute=True):
            first, second = self.upload(), self.upload()
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Slide.objects.count(), 2)  # Existing fixture + one upload.
        storage.assert_called_once(); dispatch.assert_called_once()

    def test_repeated_standalone_upload_returns_saved_deck_without_rerender(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
            'curriculum.slide_uploads.dispatch_standalone_deck_processing') as render, self.captureOnCommitCallbacks(execute=True):
            first, second = self.upload('deck'), self.upload('deck')
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(SlideDeck.objects.count(), 1)
        storage.assert_called_once(); render.assert_called_once()

    def test_reused_request_with_different_bytes_or_metadata_is_rejected(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage:
            self.assertEqual(self.upload().status_code, 201)
            for changes in ({'title': 'Changed'}, {'file': SimpleUploadedFile('lecture.pdf', b'%PDF-1.7\nchanged')}):
                self.assertEqual(self.upload(**changes).status_code, 409)
            self.assertEqual(self.upload('deck').status_code, 409)
        storage.assert_called_once()

    def test_invalid_id_is_rejected_before_storage(self):
        with patch('curriculum.views.upload_asset') as storage:
            self.assertEqual(self.upload(request_id='not-a-uuid').status_code, 400)
        storage.assert_not_called()

    def test_standalone_title_is_validated_before_uploading_bytes(self):
        with patch('curriculum.views.upload_asset') as storage:
            for title in (' ', 'a' * 201):
                self.assertEqual(self.upload('deck', title=title).status_code, 400)
        storage.assert_not_called()

    def test_deleted_upload_is_not_silently_recreated_by_retry(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage:
            response = self.upload()
            Slide.objects.get(pk=response.data['id']).delete()
            self.assertEqual(self.upload().status_code, 410)
        storage.assert_called_once()
        self.assertTrue(UploadReceipt.objects.get().completed)

    def test_failed_save_rolls_back_receipt_result_and_cleans_asset_then_retry_succeeds(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
            'cloudinary.uploader.destroy', return_value={'result': 'ok'}) as destroy:
            with patch('curriculum.models.SlideProcessingStatus.objects.create', side_effect=RuntimeError('db failed')):
                self.assertEqual(self.upload().status_code, 503)
            self.assertFalse(UploadReceipt.objects.get().completed)
            self.assertFalse(MediaAsset.objects.exists())
            self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(storage.call_count, 2); destroy.assert_called_once()

    def test_record_is_replayable_when_background_dispatch_fails(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
            'curriculum.tasks.process_standalone_deck_task.delay', side_effect=RuntimeError('queue offline')) as render:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.upload('deck')
            second = self.upload('deck')
            self.assertEqual((first.status_code, second.status_code), (201, 201))
            self.assertEqual(first.data['id'], second.data['id'])
        storage.assert_called_once(); render.assert_called_once()
        self.assertEqual(SlideDeck.objects.get().processing_status, 'failed')

    def test_retry_still_requires_current_upload_permission(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage:
            self.assertEqual(self.upload().status_code, 201)
            self.user.profile.class_role = 'student'; self.user.profile.save()
            self.assertEqual(self.upload().status_code, 403)
        storage.assert_called_once()

    def test_foreign_document_is_not_revealed_by_saved_receipt(self):
        from accounts.models import ClassGroup
        foreign = ClassGroup.objects.create(school=self.user.profile.class_group.school, set_name='Other', code='998877')
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage:
            response = self.upload()
            Slide.objects.filter(pk=response.data['id']).update(class_group=foreign)
            self.assertEqual(self.upload().status_code, 410)
        storage.assert_called_once()


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class UploadReceiptConcurrencyTests(UploadFixture, TransactionTestCase):
    def parallel_uploads(self, kind):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                response = self.upload(kind)
                return response.status_code, response.data.get('id')
            finally:
                close_old_connections()
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
            'curriculum.slide_uploads.dispatch_slide_processing'), patch('curriculum.slide_uploads.dispatch_standalone_deck_processing'):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, range(2)))
        self.assertEqual([r[0] for r in results], [201, 201])
        self.assertEqual(results[0][1], results[1][1])
        storage.assert_called_once()

    def test_simultaneous_course_retries_store_one_original(self):
        self.parallel_uploads('slide')

    def test_simultaneous_standalone_retries_store_one_original(self):
        self.parallel_uploads('deck')
