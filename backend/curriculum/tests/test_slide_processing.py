from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from io import StringIO
from pathlib import Path
import tempfile
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from PIL import Image
from django.core.management import call_command
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from curriculum import slide_processing as worker
from curriculum.models import MediaAsset, SlideContent, SlideProcessingStatus
from curriculum.tests.test_bank_recovery import BankFixture, BODY


class ProcessingFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.group = self.user.profile.class_group
        self.state = SlideProcessingStatus.objects.create(slide=self.slide, status='pending')

    def store(self, *args, **kwargs):
        return MediaAsset.objects.create(class_group=self.group, resource_type='image', public_id=f'page/{uuid.uuid4()}')

    def mocks(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='emby-course-test-')))
        paths = []
        for n in (1, 2):
            path = directory / f'{n}.png'
            Image.new('RGB', (20, 30), 'white').save(path); paths.append(str(path))
        self.result = {'success': True, 'image_paths': paths, 'page_count': 2,
            'pages': [{'page_number': n, 'text': BODY, 'extraction_status': 'complete'} for n in (1, 2)],
            'text_content': BODY, 'text_extraction': {'version': 1, 'status': 'complete', 'total_pages': 2,
                'source_sha256': 'fixture-source'}}
        self.convert = stack.enter_context(patch('curriculum.services.slide_conversion_pipeline.SlideConversionPipeline.process_slide', return_value=self.result))
        self.upload = stack.enter_context(patch('curriculum.private_media.upload_asset', side_effect=self.store))
        self.destroy = stack.enter_context(patch('cloudinary.uploader.destroy', return_value={'result': 'ok'}))
        self.generate = stack.enter_context(patch('learning.generation_dispatch.request_generation'))


class SlideProcessingTests(ProcessingFixture, TestCase):
    def test_rerender_with_finished_bank_does_not_stay_generating_forever(self):
        from learning import generation
        from learning.generation_dispatch import request_generation
        from learning.models import QuestionGenerationJob as Job
        self.mocks()
        self.generate.side_effect = request_generation
        self.assertTrue(worker.process(self.slide.pk)['success'])
        job = generation.claim_job(self.slide)
        generation.bind_source(job, generation.extracted_source(self.slide.pk)[0])
        for terminal in (Job.Status.COMPLETED, Job.Status.FAILED):
            with self.subTest(terminal=terminal):
                Job.objects.filter(pk=job.pk).update(status=terminal, attempts=Job.MAX_ATTEMPTS,
                    lease_token=None, lease_expires_at=None)
                token = worker.reserve(self.slide.pk, manual=True)
                self.assertTrue(worker.process(self.slide.pk, token=token)['success'])
                self.state.refresh_from_db(); self.slide.refresh_from_db()
                self.assertEqual(self.state.status, terminal)
                self.assertEqual(self.slide.generation_status, terminal)

    def test_complete_pages_publish_together_and_redelivery_skips(self):
        self.mocks()
        self.assertTrue(worker.process(self.slide.pk)['success'])
        self.state.refresh_from_db()
        token = self.state.processing_token
        self.assertTrue(worker.process(self.slide.pk, token=token)['skipped'])
        self.assertTrue(worker.process(self.slide.pk)['skipped'])
        self.assertEqual(self.upload.call_count, 2)
        self.assertEqual(len(SlideContent.objects.get(slide=self.slide).content_data['pages']), 2)
        self.generate.assert_called_once()

    def test_later_page_failure_keeps_old_pages_and_cleans_only_staged_assets(self):
        self.mocks()
        original = SlideContent.objects.get(slide=self.slide).content_data
        def upload(*args, **kwargs):
            if self.upload.call_count == 2:
                raise RuntimeError('provider failed')
            return self.store()
        self.upload.side_effect = upload
        self.assertFalse(worker.process(self.slide.pk)['success'])
        self.assertEqual(SlideContent.objects.get(slide=self.slide).content_data, original)
        self.assertEqual(MediaAsset.objects.count(), 0)
        self.destroy.assert_called_once()
        self.generate.assert_not_called()
        self.state.refresh_from_db()
        self.assertIsNotNone(self.state.next_attempt_at)
        self.assertTrue(worker.process(self.slide.pk, token=self.state.processing_token)['skipped'])
        token = worker.reserve(self.slide.pk, manual=True)
        self.upload.side_effect = self.store
        self.assertTrue(worker.process(self.slide.pk, token=token)['success'])

    def test_publication_failure_rolls_back_content_and_preserves_old_page(self):
        self.mocks()
        original = SlideContent.objects.get(slide=self.slide).content_data
        self.generate.side_effect = RuntimeError('database failure')
        self.assertFalse(worker.process(self.slide.pk)['success'])
        self.assertEqual(SlideContent.objects.get(slide=self.slide).content_data, original)
        self.assertEqual(MediaAsset.objects.count(), 0)
        self.assertEqual(self.destroy.call_count, 2)

    def test_superseded_worker_cannot_publish_or_fail_replacement(self):
        self.mocks()
        replacement = uuid.uuid4()
        original = SlideContent.objects.get(slide=self.slide).content_data
        def upload(*args, **kwargs):
            SlideProcessingStatus.objects.filter(pk=self.state.pk).update(processing_token=replacement, status='completed')
            return self.store()
        self.upload.side_effect = upload
        self.assertTrue(worker.process(self.slide.pk)['skipped'])
        self.state.refresh_from_db()
        self.assertEqual((self.state.status, self.state.processing_token), ('completed', replacement))
        self.assertEqual(SlideContent.objects.get(slide=self.slide).content_data, original)
        self.assertFalse(MediaAsset.objects.exists())

    def test_live_lease_blocks_recovery_and_manual_retry(self):
        worker.claim(self.slide.pk)
        SlideProcessingStatus.objects.filter(pk=self.state.pk).update(started_at=timezone.now()-timedelta(hours=2))
        with patch('curriculum.management.commands.recover_slide_processing.dispatch_slide_processing') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_slide_processing', apply=True, stdout=StringIO())
            self.assertIsNone(worker.reserve(self.slide.pk, manual=True))
        dispatch.assert_not_called()

    def test_expired_worker_is_replaced_and_old_message_rejected(self):
        _, state, _ = worker.claim(self.slide.pk)
        SlideProcessingStatus.objects.filter(pk=state.pk).update(processing_lease_until=timezone.now()-timedelta(seconds=1),
            started_at=timezone.now()-timedelta(hours=2))
        token = worker.reserve(self.slide.pk)
        self.assertIsNotNone(token)
        self.assertIsNone(worker.claim(self.slide.pk, state.processing_token))
        self.assertIsNotNone(worker.claim(self.slide.pk, token))
        self.assertIsNone(worker.claim(self.slide.pk, token))

    def test_failures_have_bounded_retries_and_manual_retry_starts_new_cycle(self):
        self.mocks(); self.convert.return_value = {'success': False}
        token = None
        for attempt in range(1, worker.MAX_ATTEMPTS+1):
            self.assertFalse(worker.process(self.slide.pk, token=token)['success'])
            self.state.refresh_from_db()
            self.assertEqual(self.state.processing_attempts, attempt)
            if attempt < worker.MAX_ATTEMPTS:
                SlideProcessingStatus.objects.filter(pk=self.state.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
                token = worker.reserve(self.slide.pk)
        self.assertIsNone(self.state.next_attempt_at)
        self.assertIsNone(worker.reserve(self.slide.pk))
        self.assertIsNotNone(worker.reserve(self.slide.pk, manual=True))
        self.state.refresh_from_db(); self.assertEqual(self.state.processing_attempts, 0)

    def test_lost_dispatch_acknowledgement_does_not_fail_started_worker(self):
        from curriculum.slide_uploads import dispatch_slide_processing
        token = worker.reserve(self.slide.pk, manual=True)
        def dispatch(*args, **kwargs):
            self.assertIsNotNone(worker.claim(self.slide.pk, token))
            raise RuntimeError('ack lost')
        with patch('curriculum.tasks.process_slide_task.delay', side_effect=dispatch):
            dispatch_slide_processing(self.slide.pk, token)
        self.state.refresh_from_db()
        self.assertEqual(self.state.status, 'processing')
        self.assertIsNotNone(self.state.processing_lease_until)

    def test_cached_page_cannot_be_discarded_as_unpublished(self):
        from curriculum.private_media import discard_new_asset
        self.mocks(); asset = self.store()
        SlideContent.objects.filter(slide=self.slide).update(content_data={'pages': [{'asset_id': str(asset.pk)}]})
        with self.assertRaises(ValueError):
            discard_new_asset(asset)
        self.destroy.assert_not_called()
        self.assertTrue(MediaAsset.objects.filter(pk=asset.pk).exists())

    def test_old_question_job_does_not_overwrite_active_conversion_status(self):
        from learning import generation
        job = generation.claim_job(self.slide)
        worker.claim(self.slide.pk)
        generation.finish_job(job, error='provider failed')
        self.state.refresh_from_db()
        self.assertEqual(self.state.status, 'processing')


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class SlideProcessingConcurrencyTests(ProcessingFixture, TransactionTestCase):
    def parallel(self, action):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return bool(action())
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_concurrent_workers_claim_once(self):
        self.assertEqual(sum(self.parallel(lambda: worker.claim(self.slide.pk))), 1)

    def test_concurrent_manual_retries_reserve_once(self):
        self.assertEqual(sum(self.parallel(lambda: worker.reserve(self.slide.pk, manual=True))), 1)
