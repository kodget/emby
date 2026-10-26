"""Preview and recover stale standalone deck conversions without changing source files."""
from datetime import timedelta
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from curriculum.models import SlideDeck
from curriculum.slide_uploads import dispatch_standalone_deck_processing


class Command(BaseCommand):
    help = 'Preview stale standalone deck conversions, or requeue them with --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--older-than-minutes', type=int, default=10)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--retry-failed', action='store_true',
                            help='Include failed conversions in this explicit recovery run.')

    def handle(self, *args, **options):
        age = options['older_than_minutes']
        if age < 1:
            raise CommandError('--older-than-minutes must be at least 1.')

        cutoff = timezone.now() - timedelta(minutes=age)
        states = ['pending', 'processing']
        if options['retry_failed']:
            states.append('failed')
        from curriculum.deck_processing import MAX_ATTEMPTS
        eligible = SlideDeck.objects.filter(
            class_group__is_active=True, asset__class_group_id=F('class_group_id'),
        ).filter(Q(processing_status__in=states, updated_at__lte=cutoff)
                 | Q(processing_status='failed', next_attempt_at__lte=timezone.now()))
        if not options['retry_failed']:
            # Mark exhausted crashed workers terminal; never leave them spinning.
            exhausted = eligible.filter(processing_attempts__gte=MAX_ATTEMPTS).filter(
                Q(processing_lease_until__isnull=True) | Q(processing_lease_until__lte=timezone.now()))
            if options['apply']:
                exhausted.update(processing_status='failed', next_attempt_at=None, processing_lease_until=None,
                    processing_error='Processing stopped after repeated failures. An uploader can retry.')
            eligible = eligible.filter(processing_attempts__lt=MAX_ATTEMPTS)
        eligible = eligible.filter(Q(processing_lease_until__isnull=True) | Q(processing_lease_until__lte=timezone.now()))
        candidates = list(eligible.order_by('pk').values_list('pk', flat=True))

        if not options['apply']:
            for deck_id in candidates:
                self.stdout.write(f'{deck_id}: would requeue stale conversion')
            self.stdout.write(f'Found {len(candidates)} stale standalone deck(s); no data changed.')
            return

        requeued = 0
        for deck_id in candidates:
            with transaction.atomic():
                deck = eligible.select_for_update(of=('self',)).filter(pk=deck_id).first()
                if deck is None:
                    continue
                deck.processing_status = 'processing'
                deck.processing_error = ''
                deck.processing_token = uuid.uuid4()
                deck.processing_lease_until = None
                deck.next_attempt_at = None
                deck.processing_progress = {}
                if options['retry_failed']:
                    deck.processing_attempts = 0
                deck.save(update_fields=('processing_status', 'processing_error', 'processing_token',
                                         'processing_lease_until', 'next_attempt_at', 'processing_attempts',
                                         'processing_progress', 'updated_at'))
                transaction.on_commit(
                    lambda identifier=deck_id, token=deck.processing_token: dispatch_standalone_deck_processing(identifier, token),
                    robust=True,
                )
                requeued += 1

        self.stdout.write(f'Requeued {requeued} stale standalone deck(s).')
        from backend.task_dispatch import wait_for_local_tasks
        wait_for_local_tasks()
