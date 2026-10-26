"""Real multi-megabyte documents, bounded rasters and isolated failure handling."""
from io import BytesIO, StringIO
from pathlib import Path
import random
import os
import subprocess
import sys
import tempfile
from unittest import skipUnless
from unittest.mock import Mock, PropertyMock, patch

import fitz
from PIL import Image
from django.test import SimpleTestCase, TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta

from curriculum.services.document_rendering import DocumentRenderingError, render_document
from curriculum.services.isolated_rendering import render_document_isolated
from curriculum.services.slide_conversion_pipeline import download_source
from curriculum.tests.test_document_rendering import make_document
from curriculum.tests.test_standalone_processing import ProcessingFixture
from curriculum import deck_processing
from curriculum.models import SlideDeck


class LargeRenderingTests(SimpleTestCase):
    def test_multi_megabyte_pdf_keeps_every_page_and_text_in_isolated_renderer(self):
        with tempfile.TemporaryDirectory(prefix='emby-large-fixture-') as directory:
            image = Image.frombytes('RGB', (1200, 900), random.Random(4).randbytes(1200*900*3))
            buffer = BytesIO(); image.save(buffer, format='PNG')
            source = Path(directory) / 'large.pdf'
            with fitz.open() as document:
                for number in range(1, 17):
                    page = document.new_page(width=1200, height=950)
                    page.insert_text((20, 25), f'Large lecture page {number}')
                    page.insert_image(fitz.Rect(0, 40, 1200, 940), stream=buffer.getvalue())
                document.save(source)
            self.assertGreater(source.stat().st_size, 3 * 1024 * 1024)
            original = source.read_bytes()
            reports = []
            result = render_document_isolated(source, 'pdf', Path(directory)/'render',
                progress=lambda phase, completed, total: reports.append((phase, completed, total)))
            self.assertEqual(result['page_count'], 16)
            self.assertEqual(reports[-1], ('rendering', 16, 16))
            for number, (path, text) in enumerate(zip(result['image_paths'], result['page_texts']), 1):
                self.assertIn(f'Large lecture page {number}', text)
                with Image.open(path) as rendered:
                    self.assertLessEqual(max(rendered.size), 1921)
                    self.assertLessEqual(rendered.width*rendered.height, 2_004_000)
            self.assertEqual(source.read_bytes(), original)

    def test_enormous_pdf_page_does_not_allocate_an_enormous_bitmap(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'poster.pdf'
            with fitz.open() as document:
                page = document.new_page(width=100000, height=50000)
                page.insert_text((30, 50), 'Unusual page dimensions')
                document.save(source)
            result = render_document(source, 'pdf', Path(directory)/'render')
            with Image.open(result['image_paths'][0]) as image:
                self.assertLessEqual(max(image.size), 1921)
            self.assertIn('Unusual page dimensions', result['page_texts'][0])

    def test_insufficient_container_memory_does_not_launch_a_converter(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                'curriculum.services.isolated_rendering.available_container_memory', return_value=40*1024**2), patch(
                'curriculum.services.isolated_rendering.subprocess.Popen') as launch:
            with self.assertRaises(DocumentRenderingError) as error:
                render_document_isolated('unused.pdf', 'pdf', directory)
            self.assertEqual(error.exception.code, 'render_memory')
            launch.assert_not_called()

    def test_timeout_stops_child_and_leaves_original_available(self):
        with tempfile.TemporaryDirectory() as directory:
            source = make_document(directory, 'pdf')
            with self.assertRaises(DocumentRenderingError) as error:
                render_document_isolated(source, 'pdf', Path(directory)/'render', timeout=0)
            self.assertEqual(error.exception.code, 'render_timeout')
            self.assertTrue(source.is_file())

    def test_parent_stops_renderer_when_memory_budget_is_exceeded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'EMBY_RENDER_MEMORY_MB': '192'}), patch(
                'curriculum.services.isolated_rendering.group_memory', return_value=200*1024**2), patch(
                'curriculum.services.isolated_rendering.available_container_memory', return_value=None):
            source = make_document(directory, 'pdf')
            with self.assertRaises(DocumentRenderingError) as error:
                render_document_isolated(source, 'pdf', Path(directory)/'render')
            self.assertEqual(error.exception.code, 'render_memory')
            self.assertTrue(source.is_file())

    @skipUnless(sys.platform.startswith('linux'), 'Render process-group lifecycle runs on Linux')
    def test_renderer_exits_when_its_parent_pipe_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = make_document(directory, 'pdf')
            process = subprocess.Popen([sys.executable, '-m', 'curriculum.services.render_worker',
                str(source), 'pdf', directory, '192'], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                process.stdin.close()
                self.assertEqual(process.wait(timeout=15), -9)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_download_streams_without_accessing_response_content(self):
        response = Mock(status_code=200, iter_content=Mock(return_value=[b'a'*262144]*12))
        type(response).content = PropertyMock(side_effect=AssertionError('Full-buffer download is forbidden'))
        with tempfile.TemporaryDirectory() as directory, patch('requests.get', return_value=response) as get:
            destination = Path(directory)/'source.pdf'
            download_source('https://api.cloudinary.com/v1_1/test/raw/download?signature=private', destination)
            self.assertEqual(destination.stat().st_size, 3*1024*1024)
            self.assertTrue(get.call_args.kwargs['stream'])
            response.close.assert_called_once()


class RecoveryTests(ProcessingFixture, TestCase):
    def retry_request(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from curriculum.views import SlideDeckViewSet
        request = APIRequestFactory().post('/api/decks/processing/retry-processing/', {})
        force_authenticate(request, self.user)
        return SlideDeckViewSet.as_view({'post': 'retry_processing'})(request, id=self.deck.pk)

    def test_authorized_retry_resets_exhausted_attempts_and_dispatches_once(self):
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_status='failed', processing_attempts=4)
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            first = self.retry_request()
            second = self.retry_request()
        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.data['queued'])
        self.assertFalse(second.data['queued'])
        dispatch.assert_called_once()
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_attempts, 0)

    def test_student_cannot_retry_processing(self):
        self.user.profile.class_role = 'student'
        self.user.profile.save()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch:
            self.assertEqual(self.retry_request().status_code, 403)
        dispatch.assert_not_called()

    def test_render_heartbeat_keeps_active_attempt_owned_and_reports_page_counts(self):
        deck = deck_processing.claim(self.deck.pk)
        deck_processing.heartbeat(deck, 'rendering', 4, 20)
        deck.refresh_from_db()
        self.assertEqual(deck.processing_progress, {'phase': 'rendering', 'completed': 4, 'total': 20})
        self.assertLess(deck.processing_lease_until, timezone.now()+timedelta(minutes=11))
        self.assertGreater(deck.processing_lease_until, timezone.now()+timedelta(minutes=9))

    def test_failed_standalone_retries_automatically_and_stops_at_four_attempts(self):
        for attempt in range(1, 5):
            self.deck.refresh_from_db()
            deck = deck_processing.claim(self.deck.pk, self.deck.processing_token)
            self.assertIsNotNone(deck)
            deck_processing.fail(deck)
            SlideDeck.objects.filter(pk=deck.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
            with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
                call_command('recover_standalone_decks', apply=True, stdout=StringIO())
            self.assertEqual(dispatch.call_count, 1 if attempt < 4 else 0)
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_status, 'failed')
        self.assertIsNone(self.deck.next_attempt_at)
        self.assertEqual(self.deck.processing_attempts, 4)
        self.assertTrue(self.deck.asset_id)

    def test_interrupted_attempt_is_recovered_after_ten_minutes_not_two_hours(self):
        deck = deck_processing.claim(self.deck.pk)
        SlideDeck.objects.filter(pk=deck.pk).update(updated_at=timezone.now()-timedelta(minutes=11),
            processing_lease_until=timezone.now()-timedelta(seconds=1))
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_called_once()
        self.assertIsNone(deck_processing.claim(deck.pk, deck.processing_token))
