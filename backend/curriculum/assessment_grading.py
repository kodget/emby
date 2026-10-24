"""Persisted grading, bounded retries and worker leases for saved formal rubrics."""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AssessmentGradingJob as Job, QuizAttempt, QuizAttemptResponse
from .services import snapshot_grader as grader

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=10)
DISPATCH_RETRY = timedelta(minutes=5)


def questions(attempt):
    return [q for q in attempt.question_snapshots if q.get('question_type') == 'theory']


def save_grade(response, question, answer, grade, *, method):
    # Validate even when the evaluator is replaced by another implementation.
    grade = grader.validate_grade(grade, question)
    response.ai_score = Decimal(str(grade['score']))
    response.is_correct = response.ai_score >= Decimal(str(question['maximum_marks'])) / 2
    response.ai_feedback = {'feedback': grade['feedback']}
    response.ai_rubric_breakdown = grade['rubric_breakdown']
    response.ai_evaluation_status = 'completed'
    response.grading_evidence = {'version': grader.VERSION, 'input_sha256': grader.fingerprint(question, answer),
                                 'method': method, 'graded_at': timezone.now().isoformat(),
                                 'maximum_marks': question['maximum_marks']}
    response.save(update_fields=['ai_score', 'is_correct', 'ai_feedback', 'ai_rubric_breakdown',
                                 'ai_evaluation_status', 'grading_evidence', 'updated_at'])


def complete(attempt, job):
    """Caller holds attempt and job locks; only all valid saved grades produce a total."""
    qs = questions(attempt)
    responses = {r.snapshot_question_id: r for r in attempt.responses.all()}
    if any(q['id'] not in responses or responses[q['id']].ai_evaluation_status != 'completed'
           or responses[q['id']].grading_evidence.get('input_sha256') != grader.fingerprint(q, responses[q['id']].text_answer)
           for q in qs):
        return False
    maximum = sum((grader.number(q['maximum_marks']) for q in qs), Decimal(0))
    score = sum((responses[q['id']].ai_score for q in qs), Decimal(0))
    denominator = Decimal(attempt.mcq_total) + maximum
    attempt.theory_score = score
    attempt.theory_grading_pending = False
    attempt.theory_grading_completed = True
    attempt.overall_percentage = float((Decimal(attempt.mcq_score) + score) * 100 / denominator) if denominator else 0
    attempt.analysis_data = {**attempt.analysis_data, 'grading_status': 'complete', 'score_basis': 'all_marks',
                             'theory_maximum_marks': float(maximum), 'total_maximum_marks': float(denominator)}
    attempt.save(update_fields=['theory_score', 'theory_grading_pending', 'theory_grading_completed',
                                'overall_percentage', 'analysis_data', 'updated_at'])
    job.status = 'completed'; job.completed_at = timezone.now()
    job.lease_token = job.lease_expires_at = job.next_attempt_at = None
    job.error_code = ''; job.save()
    # Preserve the one completion event and its MCQ counts; add final evidence without re-awarding XP/points.
    from learning.models import LearningEvent
    for event in LearningEvent.objects.filter(resource_type='QuizAttempt', resource_id=attempt.pk, user=attempt.user):
        event.metadata = {**event.metadata, 'theory_grading_pending': False,
                          'theory_score': float(score), 'theory_maximum_marks': float(maximum),
                          'final_percentage': attempt.overall_percentage}
        event.save(update_fields=['metadata'])
    try:
        from learning.gamification import AchievementEngine
        AchievementEngine.recalculate_user(attempt.user)
    except Exception:
        logger.exception("Achievement recalculation failed for completed assessment %s", attempt.pk)
    return True


def prepare(attempt):
    """Called inside submission's transaction, or by the recovery sweep under its lock."""
    if not (attempt.assessment_id or attempt.snapshot_class_id) or attempt.status not in ('submitted', 'auto_submitted') or not attempt.theory_total:
        return None
    job, created = Job.objects.get_or_create(attempt=attempt)
    if not created:
        return job
    for question in questions(attempt):
        response, _ = QuizAttemptResponse.objects.get_or_create(attempt=attempt, snapshot_question_id=question['id'])
        if not response.text_answer.strip():
            save_grade(response, question, response.text_answer, grader.blank_grade(question), method='unanswered')
    if not complete(attempt, job):
        attempt.theory_grading_pending = True; attempt.theory_grading_completed = False
        attempt.save(update_fields=['theory_grading_pending', 'theory_grading_completed'])
        job.next_attempt_at = timezone.now(); job.save()
        transaction.on_commit(lambda: dispatch(job.pk))
    return job


def dispatch(job_id):
    """A lost queue acknowledgement is safe: workers must acquire the lease."""
    with transaction.atomic():
        job = Job.objects.select_for_update().filter(pk=job_id).first()
        if not job or job.status != 'pending' or (job.next_attempt_at and job.next_attempt_at > timezone.now()):
            return False
        job.next_attempt_at = timezone.now() + DISPATCH_RETRY
        job.save(update_fields=['next_attempt_at', 'updated_at'])
        attempt_id = job.attempt_id
    try:
        from .tasks import grade_saved_assessment_task
        grade_saved_assessment_task.delay(attempt_id)
        return True
    except Exception as exc:
        logger.warning('Saved assessment dispatch retained (%s)', type(exc).__name__)
        Job.objects.filter(pk=job_id, status='pending').update(error_code='queue_unavailable')
        return False


@transaction.atomic
def claim(attempt_id):
    attempt = QuizAttempt.objects.select_for_update().filter(Q(assessment__isnull=False) | Q(snapshot_class__isnull=False), pk=attempt_id,
        status__in=['submitted', 'auto_submitted']).first()
    if not attempt:
        return None
    job = Job.objects.select_for_update().filter(attempt=attempt).first()
    # Recovery, not an old queued message, authorizes another lease after expiry/failure.
    if not job or job.status != 'pending' or job.attempts >= MAX_ATTEMPTS:
        return None
    job.status = 'running'; job.attempts += 1; job.total_runs += 1
    job.lease_token = uuid.uuid4(); job.lease_expires_at = timezone.now() + LEASE
    job.next_attempt_at = None; job.error_code = ''; job.save()
    attempt.analysis_data = {**attempt.analysis_data, 'grading_status': 'running'}
    attempt.save(update_fields=['analysis_data'])
    return job.lease_token


def owned_job(attempt, token):
    return Job.objects.select_for_update().filter(attempt=attempt, status='running', lease_token=token,
                                                 lease_expires_at__gt=timezone.now()).first()


@transaction.atomic
def fail(attempt_id, token, code):
    attempt = QuizAttempt.objects.select_for_update().get(pk=attempt_id)
    job = owned_job(attempt, token)
    if not job:
        return
    job.status = 'failed' if job.attempts >= MAX_ATTEMPTS else 'retry_wait'
    job.error_code = code
    job.next_attempt_at = timezone.now() + (DISPATCH_RETRY if job.status == 'failed' else timedelta(minutes=job.attempts))
    job.lease_token = job.lease_expires_at = None; job.save()
    attempt.responses.filter(ai_evaluation_status='processing').update(ai_evaluation_status='failed')
    attempt.analysis_data = {**attempt.analysis_data, 'grading_status': job.status}
    attempt.save(update_fields=['analysis_data'])


def run(attempt_id):
    token = claim(attempt_id)
    if token is None:
        return {'claimed': False}
    try:
        # A provider call never holds a database transaction open.
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        for question in questions(attempt):
            with transaction.atomic():
                attempt = QuizAttempt.objects.select_for_update().get(pk=attempt_id)
                job = owned_job(attempt, token)
                if not job:
                    return {'claimed': True, 'stale': True}
                response = attempt.responses.get(snapshot_question_id=question['id'])
                if response.ai_evaluation_status == 'completed':
                    continue
                answer = response.text_answer
                response.ai_evaluation_status = 'processing'; response.ai_evaluation_attempts += 1
                response.save(update_fields=['ai_evaluation_status', 'ai_evaluation_attempts'])
                job.lease_expires_at = timezone.now() + LEASE; job.save(update_fields=['lease_expires_at', 'updated_at'])
            grade = grader.evaluate(question, answer)
            with transaction.atomic():
                attempt = QuizAttempt.objects.select_for_update().get(pk=attempt_id)
                job = owned_job(attempt, token)
                if not job:
                    return {'claimed': True, 'stale': True}
                response = attempt.responses.get(snapshot_question_id=question['id'])
                current = next(q for q in questions(attempt) if q['id'] == question['id'])
                if grader.fingerprint(current, response.text_answer) != grader.fingerprint(question, answer):
                    raise grader.InvalidGrade('The saved input changed during grading.')
                save_grade(response, question, answer, grade, method='ai')
        with transaction.atomic():
            attempt = QuizAttempt.objects.select_for_update().get(pk=attempt_id)
            job = owned_job(attempt, token)
            if job and complete(attempt, job):
                return {'claimed': True, 'completed': True}
        raise grader.InvalidGrade('Saved grading evidence is incomplete.')
    except Exception as exc:
        # Never publish provider bodies, prompts, credentials or student text in errors.
        fail(attempt_id, token, 'invalid_grade' if isinstance(exc, grader.InvalidGrade) else 'provider_unavailable')
        logger.warning('Assessment grading retained for retry (%s)', type(exc).__name__)
        return {'claimed': True, 'completed': False}


@transaction.atomic
def retry(attempt):
    attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
    job = Job.objects.select_for_update().filter(attempt=attempt).first()
    if not job or job.status != 'failed':
        raise ValidationError({'error': 'Only failed grading can be retried. Saved grades cannot be rerolled.'})
    if job.next_attempt_at and job.next_attempt_at > timezone.now():
        raise ValidationError({'error': 'Please wait a few minutes before retrying grading.'})
    job.status = 'pending'; job.attempts = 0; job.next_attempt_at = timezone.now()
    job.error_code = ''; job.save()
    attempt.analysis_data = {**attempt.analysis_data, 'grading_status': 'pending'}
    attempt.save(update_fields=['analysis_data'])
    transaction.on_commit(lambda: dispatch(job.pk))


def recovery(limit=100):
    """Adopt prior snapshot submissions, redeliver lost jobs and recover expired leases."""
    now = timezone.now()
    missing = QuizAttempt.objects.filter(Q(assessment__isnull=False) | Q(snapshot_class__isnull=False), status__in=['submitted', 'auto_submitted'],
        theory_grading_pending=True, grading_job__isnull=True).order_by('submitted_at').values_list('pk', flat=True)[:limit]
    adopted = 0
    for aid in list(missing):
        with transaction.atomic():
            attempt = QuizAttempt.objects.select_for_update().get(pk=aid)
            prepare(attempt); adopted += 1
    due = Job.objects.filter(Q(status__in=['pending', 'retry_wait'], next_attempt_at__lte=now) |
                             Q(status='pending', next_attempt_at__isnull=True) |
                             Q(status='running', lease_expires_at__lte=now)).order_by('updated_at')
    published = 0
    for jid, aid in list(due.values_list('pk', 'attempt_id')[:limit]):
        with transaction.atomic():
            attempt = QuizAttempt.objects.select_for_update().get(pk=aid)
            job = Job.objects.select_for_update().get(pk=jid)
            if job.status in ('failed', 'completed') or (job.status == 'running' and job.lease_expires_at > now):
                continue
            if job.next_attempt_at and job.next_attempt_at > now:
                continue
            if job.attempts >= MAX_ATTEMPTS:
                job.status = 'failed'; job.error_code = 'worker_interrupted'
                job.lease_token = job.lease_expires_at = None; job.next_attempt_at = now + DISPATCH_RETRY
                job.save()
                attempt.analysis_data = {**attempt.analysis_data, 'grading_status': 'failed'}
                attempt.save(update_fields=['analysis_data'])
                continue
            job.status = 'pending'; job.lease_token = job.lease_expires_at = None
            job.next_attempt_at = now; job.save()
            attempt.analysis_data = {**attempt.analysis_data, 'grading_status': 'pending'}
            attempt.save(update_fields=['analysis_data'])
            attempt.responses.filter(ai_evaluation_status='processing').update(ai_evaluation_status='pending')
        published += int(dispatch(jid))
    return {'adopted': adopted, 'published': published}


def public_status(attempt):
    if not (attempt.assessment_id or attempt.snapshot_class_id) or attempt.status == 'in_progress' or not attempt.theory_total:
        return None
    job = Job.objects.filter(attempt=attempt).first()
    if not job:
        return {'status': 'pending', 'can_retry': False, 'completed_questions': 0, 'total_questions': attempt.theory_total}
    return {'status': job.status, 'can_retry': job.status == 'failed' and (
                not job.next_attempt_at or job.next_attempt_at <= timezone.now()),
            'completed_questions': attempt.responses.filter(snapshot_question_id__in=[q['id'] for q in questions(attempt)],
                                                           ai_evaluation_status='completed').count(),
            'total_questions': attempt.theory_total, 'retry_after': job.next_attempt_at if job.status == 'failed' else None}
