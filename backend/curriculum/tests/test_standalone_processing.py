from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from io import StringIO
from pathlib import Path
import tempfile
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch, Mock
import uuid

from PIL import Image
from django.core.management import call_command
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from curriculum import deck_processing as worker
from curriculum.models import MediaAsset, SlideDeck, SlidePage
from curriculum.tests.test_bank_recovery import BankFixture


class ProcessingFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.group = self.user.profile.class_group
        self.source = MediaAsset.objects.create(class_group=self.group, uploaded_by=self.user,
            public_id='source.pdf', resource_type='raw')
        self.deck = SlideDeck.objects.create(id='processing', title='Deck', asset=self.source,
            file_type='pdf', class_group=self.group, uploaded_by=self.user)

    def mocks(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='emby-page-test-')))
        images = []
        for number in (1, 2):
            image = directory / f'{number}.png'
            Image.new('RGB', (20, 30), 'white').save(image); images.append(str(image))
        self.result = {'slide_images': images, 'page_count': 2, 'pages': [{'text': 'One'}, {'text': 'Two'}],
                       'text_extraction': {'status': 'complete'}}
        stack.enter_context(patch('requests.get', return_value=Mock(status_code=200, iter_content=Mock(return_value=[b'%PDF-source']))))
        self.convert = stack.enter_context(patch('curriculum.services.converter.SlideConverter.convert_document',
                                                return_value=(True, self.result)))
        self.destroy = stack.enter_context(patch('cloudinary.uploader.destroy', return_value={'result': 'ok'}))
        self.upload = stack.enter_context(patch('curriculum.deck_processing.upload_asset', side_effect=self.store))

    def store(self, *args, **kwargs):
        return MediaAsset.objects.create(class_group=self.group, public_id=f'page/{uuid.uuid4()}', resource_type='image')

    def old_page(self):
        return SlidePage.objects.create(deck=self.deck, slide_number=1, extracted_text='Old partial render',
            asset=self.store(), width=10, height=10)

    def recover(self):
        SlideDeck.objects.filter(pk=self.deck.pk).update(updated_at=timezone.now()-timedelta(hours=3))
        with patch('curriculum.tasks.process_standalone_deck_task.delay'), self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, retry_failed=True, stdout=StringIO())
        self.deck.refresh_from_db()
        return str(self.deck.processing_token)


class StandaloneProcessingTests(ProcessingFixture, TestCase):
    def test_retry_replaces_partial_pages_atomically_and_completed_redelivery_does_nothing(self):
        self.mocks(); previous = self.old_page()
        self.assertTrue(worker.process(self.deck.pk))
        self.assertEqual(list(self.deck.pages.values_list('slide_number', 'extracted_text')), [(1, 'One'), (2, 'Two')])
        self.assertTrue(MediaAsset.objects.filter(pk=previous.asset_id).exists())
        self.assertFalse(worker.process(self.deck.pk))
        self.assertEqual(self.upload.call_count, 2)
        self.assertEqual(self.convert.call_count, 1)
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_status, 'completed')

    def test_later_page_failure_preserves_old_pages_and_retry_finishes_without_duplicates(self):
        self.mocks(); old = self.old_page()
        def upload(*args, **kwargs):
            if self.upload.call_count == 2:
                raise RuntimeError('storage failure')
            return self.store()
        self.upload.side_effect = upload
        self.assertFalse(worker.process(self.deck.pk))
        self.assertEqual(self.deck.pages.get().pk, old.pk)
        self.assertEqual(MediaAsset.objects.count(), 2)  # Original and old published page.
        self.destroy.assert_called_once()
        token = self.recover(); self.upload.side_effect = self.store
        self.assertTrue(worker.process(self.deck.pk, token))
        self.assertEqual(self.deck.pages.count(), 2)
        self.assertFalse(worker.process(self.deck.pk, token))

    def test_failed_publication_rolls_back_deletion_and_cleans_unpublished_files(self):
        self.mocks(); old = self.old_page()
        with patch('curriculum.deck_processing.SlidePage.objects.bulk_create', side_effect=RuntimeError('DB failed')):
            self.assertFalse(worker.process(self.deck.pk))
        self.assertEqual(self.deck.pages.get().pk, old.pk)
        self.assertEqual(MediaAsset.objects.count(), 2)
        self.assertEqual(self.destroy.call_count, 2)
        self.deck.refresh_from_db(); self.assertEqual(self.deck.processing_status, 'failed')

    def test_superseded_worker_cannot_publish_or_fail_the_new_generation(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                SlideDeck.objects.filter(pk=self.deck.pk).update(processing_status='pending', processing_token=None,
                                                                processing_lease_until=None)
                self.mocks()
                replacement = uuid.uuid4()
                def upload(*args, **kwargs):
                    SlideDeck.objects.filter(pk=self.deck.pk).update(processing_token=replacement,
                        processing_status='completed', page_count=7)
                    if failure: raise RuntimeError('old worker failed')
                    return self.store()
                self.upload.side_effect = upload
                self.assertFalse(worker.process(self.deck.pk))
                self.deck.refresh_from_db()
                self.assertEqual((self.deck.processing_status, self.deck.page_count), ('completed', 7))
                self.assertEqual(self.deck.processing_token, replacement)
                self.assertEqual(MediaAsset.objects.count(), 1)

    def test_duplicate_delivery_cannot_enter_an_active_render(self):
        self.mocks()
        def convert(*args, **kwargs):
            self.assertFalse(worker.process(self.deck.pk))
            return True, self.result
        self.convert.side_effect = convert
        self.assertTrue(worker.process(self.deck.pk))
        self.assertEqual(self.convert.call_count, 1)

    def test_expired_generation_is_replaced_and_old_queued_message_is_rejected(self):
        initial = worker.claim(self.deck.pk)
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_lease_until=timezone.now()-timedelta(hours=1))
        token = self.recover()
        self.assertNotEqual(token, str(initial.processing_token))
        self.assertIsNone(worker.claim(self.deck.pk, initial.processing_token))
        self.assertIsNotNone(worker.claim(self.deck.pk, token))
        self.assertIsNone(worker.claim(self.deck.pk, token))

    def test_cleanup_failure_preserves_registry_for_later_reconciliation(self):
        self.mocks()
        self.destroy.side_effect = RuntimeError('storage offline')
        with patch('curriculum.deck_processing.SlidePage.objects.bulk_create', side_effect=RuntimeError('DB failed')):
            self.assertFalse(worker.process(self.deck.pk))
        self.assertEqual(MediaAsset.objects.count(), 3)
        self.assertFalse(self.deck.pages.exists())


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class StandaloneProcessingConcurrencyTests(ProcessingFixture, TransactionTestCase):
    def test_parallel_workers_have_one_claim(self):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                result = worker.claim(self.deck.pk)
                return str(result.processing_token) if result else None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)

    def test_parallel_recovery_commands_reserve_and_dispatch_once(self):
        SlideDeck.objects.filter(pk=self.deck.pk).update(updated_at=timezone.now()-timedelta(hours=3))
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                call_command('recover_standalone_decks', apply=True, stdout=StringIO())
            finally:
                close_old_connections()
        with patch('curriculum.management.commands.recover_standalone_decks.dispatch_standalone_deck_processing') as dispatch:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(run, range(2)))
        dispatch.assert_called_once()
