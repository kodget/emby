"""Recover saved flashcard requests without requiring an open browser."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import FlashcardGenerationJob


def recover_flashcard_jobs(limit=100):
    from .ai_views import _dispatch_flashcard_job
    now = timezone.now()
    due = (Q(status='queued', next_attempt_at__lte=now)
           | Q(status='queued', next_attempt_at__isnull=True, updated_at__lte=now - timedelta(minutes=2))
           | Q(status='running', processing_lease_until__lte=now))
    ids = list(FlashcardGenerationJob.objects.filter(due).order_by('updated_at').values_list('pk', flat=True)[:limit])
    published = 0
    for job_id in ids:
        with transaction.atomic():
            job = FlashcardGenerationJob.objects.select_for_update().filter(due, pk=job_id).first()
            if not job:
                continue
            job.status = 'queued'
            job.next_attempt_at = None
            job.processing_lease_until = job.processing_token = None
            job.save()
        try:
            _dispatch_flashcard_job(job.pk)
            published += 1
        except Exception:
            # Dispatch records the failure and refunds the reservation.
            continue
    return {'published': published}
