from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from curriculum.models import SlideProcessingStatus
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.tasks import recover_slide_processing_task


class SlideProcessingRecoveryTests(BankFixture, TestCase):
    def status(self, state='pending', *, started_at=None, created_at=None):
        if created_at is not None:
            type(self.slide).objects.filter(pk=self.slide.pk).update(created_at=created_at)
            self.slide.refresh_from_db()
        return SlideProcessingStatus.objects.create(
            slide=self.slide, status=state, started_at=started_at,
        )

    def test_default_run_is_a_read_only_preview(self):
        old = timezone.now() - timedelta(hours=2)
        status = self.status(created_at=old)
        output = StringIO()

        with patch('curriculum.tasks.process_slide_task.delay') as dispatch:
            call_command('recover_slide_processing', stdout=output)

        status.refresh_from_db()
        self.assertIn('would requeue stale processing', output.getvalue())
        self.assertEqual(status.status, 'pending')
        self.assertIsNone(status.started_at)
        dispatch.assert_not_called()

    def test_apply_claims_and_dispatches_stale_pending_job_once(self):
        old = timezone.now() - timedelta(hours=2)
        status = self.status(created_at=old)

        with patch('curriculum.tasks.process_slide_task.delay') as dispatch, self.captureOnCommitCallbacks(
            execute=True
        ):
            call_command('recover_slide_processing', apply=True, stdout=StringIO())
            call_command('recover_slide_processing', apply=True, stdout=StringIO())

        status.refresh_from_db()
        self.assertEqual(status.status, 'processing')
        self.assertGreater(status.started_at, old)
        dispatch.assert_called_once_with(self.slide.pk, token=str(status.processing_token))

    def test_old_processing_job_is_requeued_but_recent_job_is_left_alone(self):
        old_status = self.status(
            state='processing', started_at=timezone.now() - timedelta(hours=2),
        )
        with patch('curriculum.tasks.process_slide_task.delay') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                call_command('recover_slide_processing', apply=True, stdout=StringIO())
        old_status.refresh_from_db()
        self.assertEqual(old_status.status, 'processing')
        dispatch.assert_called_once_with(self.slide.pk, token=str(old_status.processing_token))

        old_status.started_at = timezone.now()
        old_status.save(update_fields=('started_at',))
        with patch('curriculum.tasks.process_slide_task.delay') as dispatch:
            call_command('recover_slide_processing', apply=True, stdout=StringIO())
        dispatch.assert_not_called()

    def test_dispatch_failure_leaves_job_explicitly_failed_and_retryable(self):
        old = timezone.now() - timedelta(hours=2)
        status = self.status(created_at=old)
        with patch('curriculum.tasks.process_slide_task.delay', side_effect=RuntimeError('broker detail')), self.captureOnCommitCallbacks(
            execute=True
        ):
            call_command('recover_slide_processing', apply=True, stdout=StringIO())
        status.refresh_from_db()
        self.assertEqual(status.status, 'failed')
        self.assertIn('retry', status.error_message.lower())
        self.assertNotIn('broker detail', status.error_message)

    def test_invalid_age_is_rejected_without_dispatch(self):
        with patch('curriculum.tasks.process_slide_task.delay') as dispatch:
            with self.assertRaisesMessage(CommandError, '--older-than-minutes must be at least 1.'):
                call_command('recover_slide_processing', apply=True, older_than_minutes=0, stdout=StringIO())
        dispatch.assert_not_called()

    def test_scheduled_recovery_task_runs_apply_mode(self):
        with patch('django.core.management.call_command') as command:
            recover_slide_processing_task.run()
        command.assert_called_once_with('recover_slide_processing', '--apply')

    def test_celery_beat_schedules_stale_slide_recovery(self):
        from backend.celery import app
        schedule = app.conf.beat_schedule['recover-slide-processing']
        self.assertEqual(schedule['task'], 'curriculum.tasks.recover_slide_processing_task')
