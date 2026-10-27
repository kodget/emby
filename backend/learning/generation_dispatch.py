"""Database-backed generation requests; broker outages do not erase queued work."""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import QuestionGenerationJob as Job

logger = logging.getLogger(__name__)


def request_generation(slide, *, force=False, requested=False):
    from curriculum.ai_policy import on_demand, DEFERRED_MESSAGE
    if on_demand(slide) and not requested:
        return False
    from curriculum.models import Slide
    from .generation import LEASE_DURATION, source_identity, extracted_digest, MCQ_TARGETS, THEORY_TARGETS
    with transaction.atomic():
        slide = Slide.objects.select_for_update().get(pk=slide.pk)
        job, created = Job.objects.get_or_create(slide=slide)
        job = Job.objects.select_for_update().get(pk=job.pk)
        if requested and job.error == DEFERRED_MESSAGE:
            job.attempts = 0
        expiry = job.lease_expires_at or ((job.started_at or job.updated_at) + LEASE_DURATION)
        if job.status == Job.Status.RUNNING and expiry > timezone.now():
            return False
        current_version = (job.source_key == source_identity(slide) and job.bank_key
                           and job.source_digest == extracted_digest(slide.pk))
        changed_version = bool(job.source_key and job.source_key != source_identity(slide)) or bool(
            job.source_digest and job.source_digest != extracted_digest(slide.pk))
        if job.status == Job.Status.COMPLETED and current_version and not force:
            return False
        if not created and job.status == Job.Status.PENDING and job.next_attempt_at and job.next_attempt_at > timezone.now():
            return False
        if changed_version or (job.status == Job.Status.COMPLETED and not job.bank_key):
            job.source_key = job.source_digest = job.bank_key = ''
            job.mcq_generated = job.theory_generated = job.attempts = 0
        if job.attempts >= Job.MAX_ATTEMPTS and not changed_version:
            if not force:
                return False
            # A manual request explicitly grants another bounded retry cycle.
            job.attempts = 0
        job.status = Job.Status.PENDING
        job.mcq_target = sum(MCQ_TARGETS.values())
        job.theory_target = sum(THEORY_TARGETS.values())
        job.error = ''
        job.finished_at = None
        job.lease_token = None
        job.lease_expires_at = None
        job.next_attempt_at = timezone.now()
        job.save()
        Slide.objects.filter(pk=slide.pk).update(generation_status='in_progress')
        transaction.on_commit(lambda: publish_pending(job.pk), robust=True)
    return True


def publish_pending(job_id):
    from curriculum.tasks import generate_question_bank_task
    with transaction.atomic():
        job = Job.objects.select_for_update().filter(pk=job_id).first()
        if not job or job.status != Job.Status.PENDING or (job.next_attempt_at and job.next_attempt_at > timezone.now()):
            return False
        # A lost broker acknowledgement may deliver twice. The worker lease handles that.
        job.next_attempt_at = timezone.now() + timedelta(minutes=5)
        job.save(update_fields=['next_attempt_at', 'updated_at'])
        slide_id = job.slide_id
    try:
        from backend.task_dispatch import dispatch_task
        dispatch_task(generate_question_bank_task, slide_id)
        return True
    except Exception as exc:
        logger.warning('Generation dispatch retained for %s (%s)', slide_id, type(exc).__name__)
        Job.objects.filter(pk=job_id, status=Job.Status.PENDING).update(
            error='The worker queue is unavailable. The saved request will be retried.')
        return False


def recover_generation_jobs(limit=100):
    """Bounded periodic sweep for undelivered requests and expired workers."""
    from .generation import LEASE_DURATION
    from curriculum.models import Slide, SlideProcessingStatus
    now = timezone.now()
    candidates = Job.objects.filter(
        Q(status=Job.Status.PENDING, next_attempt_at__lte=now)
        | Q(status=Job.Status.PENDING, next_attempt_at__isnull=True)
        | Q(status__in=[Job.Status.FAILED, Job.Status.PARTIAL], next_attempt_at__lte=now)
        | Q(status=Job.Status.RUNNING, lease_expires_at__lte=now)
        | Q(status=Job.Status.RUNNING, lease_expires_at__isnull=True, updated_at__lte=now - LEASE_DURATION)
    ).order_by('updated_at').values_list('pk', 'slide_id')[:limit]
    published = 0
    for job_id, slide_id in list(candidates):
        with transaction.atomic():
            if not Slide.objects.select_for_update().filter(pk=slide_id).exists():
                continue
            job = Job.objects.select_for_update().filter(pk=job_id).first()
            if job is None:
                continue
            if job.status == Job.Status.COMPLETED:
                continue
            expiry = job.lease_expires_at or ((job.started_at or job.updated_at) + LEASE_DURATION)
            if job.status == Job.Status.RUNNING and expiry > now:
                continue
            if job.next_attempt_at and job.next_attempt_at > now:
                continue
            if job.attempts >= Job.MAX_ATTEMPTS:
                if job.status in {Job.Status.RUNNING, Job.Status.PENDING}:
                    job.status = Job.Status.FAILED
                    job.error = 'Generation stopped after repeated worker interruptions. Retry manually.'
                    job.finished_at = now
                    job.lease_token = None
                    job.lease_expires_at = None
                    job.next_attempt_at = None
                    job.save()
                    Slide.objects.filter(pk=slide_id).update(generation_status='failed')
                    from curriculum.slide_processing import ACTIVE_STATES
                    SlideProcessingStatus.objects.filter(slide_id=slide_id).exclude(
                        processing_token__isnull=False, status__in=ACTIVE_STATES).update(
                        status='failed', error_message=job.error, completed_at=now)
                continue
            job.status = Job.Status.PENDING
            job.lease_token = None
            job.lease_expires_at = None
            job.next_attempt_at = now
            job.save()
            Slide.objects.filter(pk=slide_id).update(generation_status='in_progress')
        published += int(publish_pending(job_id))
    return {'published': published}
