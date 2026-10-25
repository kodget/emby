"""Regression: a slow eager worker must never hold the upload HTTP response."""
from threading import Event, get_ident
from unittest.mock import Mock, patch

from celery import shared_task
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from backend import task_dispatch
from curriculum.models import SlideContent, SlideProcessingStatus, UploadReceipt
from curriculum.tests.test_upload_receipts import UploadFixture
from curriculum.views import get_slide_content


class DispatchTests(SimpleTestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_worker_mode_uses_broker_and_propagates_queue_errors(self):
        task = Mock()
        self.assertIs(task_dispatch.dispatch_task(task, 'source', token='reserved'), task.delay.return_value)
        task.delay.assert_called_once_with('source', token='reserved')
        task.apply.assert_not_called()
        task.delay.side_effect = RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):
            task_dispatch.dispatch_task(task, 'source')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_eager_execution_is_detached_and_closes_worker_database_connections(self):
        started, release, finished = Event(), Event(), Event()
        requesting_thread, worker_threads = get_ident(), []
        def work(**kwargs):
            worker_threads.append(get_ident())
            started.set()
            try:
                if not release.wait(10):
                    raise RuntimeError('test worker was not released')
            finally:
                finished.set()
        task = Mock(apply=Mock(side_effect=work))
        with patch.object(task_dispatch, 'close_old_connections') as before, patch.object(
                task_dispatch.connections, 'close_all') as after:
            try:
                receipt = task_dispatch.dispatch_task(task, 'source', token='reserved')
                self.assertTrue(receipt.id)
                self.assertTrue(started.wait(5))
                self.assertFalse(finished.is_set(), 'dispatch waited for processing to finish')
                self.assertNotEqual(requesting_thread, worker_threads[0])
                task.delay.assert_not_called()
                task.apply.assert_called_once_with(args=('source',), kwargs={'token': 'reserved'},
                                                   task_id=receipt.id, throw=True)
            finally:
                release.set()
                task_dispatch._queue.join()
        before.assert_called_once(); after.assert_called_once()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_failed_task_does_not_stop_next_job_or_expose_provider_secrets(self):
        with self.assertLogs('backend.task_dispatch', level='WARNING') as logs:
            task_dispatch.dispatch_task(Mock(apply=Mock(side_effect=RuntimeError('signed-url-secret'))))
            task_dispatch._queue.join()
        self.assertNotIn('signed-url-secret', str(logs.output))
        next_task = Mock()
        task_dispatch.dispatch_task(next_task)
        task_dispatch._queue.join()
        next_task.apply.assert_called_once()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_chained_eager_job_is_queued_without_recursive_execution(self):
        child_started, release_parent, parent_dispatched = Event(), Event(), Event()
        observations = []
        @shared_task
        def child():
            child_started.set()
            observations.append(parent_dispatched.wait(3))
        @shared_task
        def parent():
            task_dispatch.dispatch_task(child)
            parent_dispatched.set()
            # Management recovery also runs in workers. Waiting here must be a
            # no-op, otherwise this task would wait for its own completion.
            task_dispatch.wait_for_local_tasks()
            if not release_parent.wait(10):
                raise RuntimeError('test parent was not released')
        try:
            task_dispatch.dispatch_task(parent)
            self.assertTrue(child_started.wait(5))
        finally:
            release_parent.set()
            task_dispatch.wait_for_local_tasks()
        self.assertEqual(observations, [True])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class EagerUploadTests(UploadFixture, TransactionTestCase):
    def check_upload(self, kind):
        started, release, finished = Event(), Event(), Event()
        observed, errors = [], []
        def processing(source_id, **kwargs):
            try:
                receipt = UploadReceipt.objects.get(request_id=self.key)
                observed.append((receipt.completed, str(receipt.slide_id or receipt.deck_id)))
                started.set()
                if not release.wait(10):
                    raise RuntimeError('request did not return while processing was blocked')
            except Exception as exc:
                errors.append(type(exc).__name__)
                raise
            finally:
                finished.set()
        path = 'curriculum.slide_processing.process' if kind == 'slide' else 'curriculum.deck_processing.process'
        with patch('curriculum.views.upload_asset', side_effect=self.store) as storage, patch(
                path, side_effect=processing) as worker:
            try:
                response = self.upload(kind)
                self.assertEqual(response.status_code, 201, response.data)
                self.assertTrue(started.wait(5))
                self.assertFalse(finished.is_set(), 'upload response waited for document processing')
                self.assertEqual(observed, [(True, response.data['id'])])
                replay = self.upload(kind)
                self.assertEqual(replay.status_code, 201)
                self.assertEqual(response.data['id'], replay.data['id'])
                storage.assert_called_once(); worker.assert_called_once()
            finally:
                release.set()
                task_dispatch._queue.join()
        self.assertTrue(finished.is_set())
        self.assertEqual(errors, [])

    def test_course_upload_returns_before_eager_worker_finishes_and_receipt_is_replayable(self):
        self.check_upload('slide')

    def test_standalone_upload_returns_before_eager_worker_finishes_and_receipt_is_replayable(self):
        self.check_upload('deck')


class ReaderProcessingTests(UploadFixture, TestCase):
    def request_content(self):
        request = APIRequestFactory().get('/api/test/')
        force_authenticate(request, self.user)
        return get_slide_content(request, slide_id=self.slide.pk)

    def test_opening_in_progress_upload_reports_pending_without_duplicate_render(self):
        SlideContent.objects.filter(slide=self.slide).delete()
        state = SlideProcessingStatus.objects.create(slide=self.slide, status='pending')
        with patch('curriculum.slide_renderer.render_slide_pages') as render:
            for phase in ('pending', 'processing', 'downloading', 'converting_to_jpg'):
                state.status = phase; state.save()
                response = self.request_content()
                self.assertEqual(response.status_code, 202)
                self.assertTrue(response.data['processing'])
                self.assertEqual(response.data['pages'], [])
            render.assert_not_called()

    def test_failed_upload_does_not_start_an_unowned_render_from_reader(self):
        SlideContent.objects.filter(slide=self.slide).delete()
        SlideProcessingStatus.objects.create(slide=self.slide, status='failed')
        with patch('curriculum.slide_renderer.render_slide_pages') as render:
            self.assertEqual(self.request_content().status_code, 409)
            render.assert_not_called()
