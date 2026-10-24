from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from curriculum.models import MediaAsset, SlideDeck
from curriculum.tasks import process_standalone_deck_task, recover_standalone_decks_task
from curriculum.tests.test_bank_recovery import BankFixture


class StandaloneDeckRecoveryTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.asset = MediaAsset.objects.create(
            class_group=self.user.profile.class_group,
            uploaded_by=self.user,
            public_id='private/standalone-source',
            resource_type='raw',
        )
        self.deck = SlideDeck.objects.create(
            id='standalone-recovery',
            title='Standalone source',
            original_file='private/standalone-source.pdf',
            asset=self.asset,
            file_type='pdf',
            uploaded_by=self.user,
            class_group=self.user.profile.class_group,
            processing_status='processing',
        )

    def make_stale(self, deck=None):
        deck = deck or self.deck
        old = timezone.now() - timedelta(hours=3)
        SlideDeck.objects.filter(pk=deck.pk).update(updated_at=old)
        return old

    def test_default_run_previews_without_mutation_or_dispatch(self):
        old = self.make_stale()
        output = StringIO()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch:
            call_command('recover_standalone_decks', stdout=output)
        self.deck.refresh_from_db()
        self.assertIn('would requeue stale conversion', output.getvalue())
        self.assertEqual(self.deck.processing_status, 'processing')
        self.assertEqual(self.deck.updated_at, old)
        dispatch.assert_not_called()

    def test_apply_requeues_stale_deck_once_and_refreshes_lease_timestamp(self):
        old = self.make_stale()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(
            execute=True
        ):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_status, 'processing')
        self.assertEqual(self.deck.processing_error, '')
        self.assertGreater(self.deck.updated_at, old)
        dispatch.assert_called_once_with(self.deck.pk, str(self.deck.processing_token))

    def test_failed_decks_require_explicit_retry_flag(self):
        self.make_stale()
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_status='failed')
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(
            execute=True
        ):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_not_called()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(
            execute=True
        ):
            call_command('recover_standalone_decks', apply=True, retry_failed=True, stdout=StringIO())
        self.deck.refresh_from_db()
        dispatch.assert_called_once_with(self.deck.pk, str(self.deck.processing_token))

    def test_invalid_age_is_rejected(self):
        with self.assertRaisesMessage(CommandError, '--older-than-minutes must be at least 1.'):
            call_command('recover_standalone_decks', older_than_minutes=0, stdout=StringIO())

    def test_processing_task_runs_existing_deck_conversion(self):
        with patch('curriculum.views.SlideDeckViewSet._process_deck_async') as process:
            process_standalone_deck_task.run(self.deck.pk)
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0].pk, self.deck.pk)

    def test_scheduled_recovery_task_runs_apply_mode(self):
        with patch('django.core.management.call_command') as command:
            recover_standalone_decks_task.run()
        command.assert_called_once_with('recover_standalone_decks', '--apply')

    def test_celery_beat_schedules_standalone_deck_recovery(self):
        from backend.celery import app
        schedule = app.conf.beat_schedule['recover-standalone-decks']
        self.assertEqual(schedule['task'], 'curriculum.tasks.recover_standalone_decks_task')

    def test_pending_request_crashes_are_recovered_but_live_leases_are_not(self):
        self.make_stale()
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_status='pending')
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_called_once()
        self.make_stale()
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_lease_until=timezone.now()+timedelta(minutes=10))
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_not_called()

    def test_broker_failure_cannot_overwrite_a_worker_that_already_started(self):
        from curriculum.slide_uploads import dispatch_standalone_deck_processing
        from curriculum.deck_processing import claim
        import uuid
        token = uuid.uuid4()
        SlideDeck.objects.filter(pk=self.deck.pk).update(processing_token=token)
        def started(*args):
            self.assertIsNotNone(claim(self.deck.pk, token))
            raise RuntimeError('Acknowledgement lost')
        with patch('curriculum.tasks.process_standalone_deck_task.delay', side_effect=started):
            dispatch_standalone_deck_processing(self.deck.pk, token)
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_status, 'processing')
        self.assertIsNotNone(self.deck.processing_lease_until)

    def test_broker_failure_without_a_worker_is_retryable(self):
        self.make_stale()
        with patch('curriculum.tasks.process_standalone_deck_task.delay', side_effect=RuntimeError('offline')), \
                self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.processing_status, 'failed')
        self.assertIsNone(self.deck.processing_lease_until)

    def test_inactive_class_is_never_requeued(self):
        self.make_stale()
        group = self.deck.class_group
        group.is_active = False; group.save()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_not_called()

    def test_wrong_asset_owner_is_never_requeued(self):
        from accounts.models import ClassGroup
        self.make_stale()
        foreign = ClassGroup.objects.create(school=self.deck.class_group.school, set_name='Foreign', code='987654')
        self.asset.class_group = foreign; self.asset.save()
        with patch('curriculum.tasks.process_standalone_deck_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            call_command('recover_standalone_decks', apply=True, stdout=StringIO())
        dispatch.assert_not_called()
