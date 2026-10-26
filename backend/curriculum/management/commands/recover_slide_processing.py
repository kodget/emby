"""Requeue stale slide-processing records without deleting their stored originals."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from curriculum.models import SlideProcessingStatus
from curriculum.slide_uploads import dispatch_slide_processing


class Command(BaseCommand):
    help = 'Preview stale slide jobs, or explicitly requeue them with --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--older-than-minutes', type=int, default=10)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        age = options['older_than_minutes']
        if age < 1:
            raise CommandError('--older-than-minutes must be at least 1.')

        now = timezone.now()
        cutoff = now - timedelta(minutes=age)
        from curriculum.slide_processing import ACTIVE_STATES
        stale = SlideProcessingStatus.objects.filter(slide__class_group__is_active=True).filter(
            Q(status__in=ACTIVE_STATES, started_at__lte=cutoff)
            | Q(status__in=ACTIVE_STATES, started_at__isnull=True, slide__created_at__lte=cutoff)
            | Q(next_attempt_at__lte=now)
        ).filter(Q(processing_lease_until__isnull=True) | Q(processing_lease_until__lte=now)).order_by('slide_id')
        candidates = list(stale.values_list('slide_id', flat=True))
        if not options['apply']:
            for slide_id in candidates:
                self.stdout.write(f'{slide_id}: would requeue stale processing')
            self.stdout.write(f'Found {len(candidates)} stale slide job(s); no data changed.')
            return

        requeued = 0
        for slide_id in candidates:
            from curriculum.slide_processing import reserve
            with transaction.atomic():
                token = reserve(slide_id, cutoff=cutoff)
                if token is None:
                    continue
                transaction.on_commit(lambda sid=slide_id, key=token: dispatch_slide_processing(sid, key), robust=True)
                requeued += 1

        self.stdout.write(f'Requeued {requeued} stale slide job(s).')
        from backend.task_dispatch import wait_for_local_tasks
        wait_for_local_tasks()
