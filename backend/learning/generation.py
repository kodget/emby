"""Build a durable bank of 15 MCQs (5 per difficulty) and 10 theory questions.

Expiring worker leases fence stale results. Retries fill verified shortfalls while
preserving saved questions and their source-page references.
"""

from __future__ import annotations

import logging
import uuid
import hashlib
import json
import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Questions per model call. Small enough to stay coherent and well within output limits.
MCQ_BATCH = 10
THEORY_BATCH = 5
MIN_TEXT_CHARS = 200


def slide_text(slide) -> str:
    """Use every page of the original, upgrading legacy unverified text caches."""
    from curriculum.services.document_extraction import ensure_slide_extraction, content_text
    return content_text(ensure_slide_extraction(slide), require_complete=True)


LEASE_DURATION = timedelta(hours=2)
RETRY_DELAY = timedelta(minutes=5)
MCQ_TARGETS = {"easy": 5, "medium": 5, "hard": 5}
THEORY_TARGETS = {"easy": 2, "medium": 4, "hard": 4}


class LostLease(Exception):
    """An expired or superseded worker may not publish results."""


def source_identity(slide):
    values = [slide.asset_id, slide.file_type, slide.file_url, str(slide.file or ''),
              slide.class_group_id, slide.subject_id, slide.block_id, slide.sub_block_id, slide.topic_id,
              MCQ_TARGETS, THEORY_TARGETS, 'bank-validation-v1']
    from curriculum.models import SlideDeck
    origin = SlideDeck.objects.filter(curriculum_slide=slide).first()
    if origin:
        from .deck_banks import deck_version
        values.append(deck_version(origin))
    return hashlib.sha256(json.dumps(values, default=str).encode()).hexdigest()


@transaction.atomic
def claim_job(slide, *, force=False):
    from curriculum.models import Slide
    from .models import QuestionGenerationJob as Job
    # All publication paths lock in this order: source, then job.
    slide = Slide.objects.select_for_update().get(pk=slide.pk)
    job, _ = Job.objects.get_or_create(slide=slide)
    job = Job.objects.select_for_update().get(pk=job.pk)
    now = timezone.now()
    expiry = job.lease_expires_at or ((job.started_at or job.updated_at) + LEASE_DURATION)
    if job.status == Job.Status.RUNNING and expiry > now:
        return None  # Even an explicit force must not steal a live lease.
    identity = source_identity(slide)
    changed = bool(job.source_key and job.source_key != identity) or bool(
        job.source_digest and job.source_digest != extracted_digest(slide.pk))
    if changed:
        # Keep old question rows for historical attempts; new selections use the new key.
        job.status = Job.Status.PENDING
        job.source_digest = ''
        job.bank_key = ''
        job.mcq_generated = job.theory_generated = job.attempts = 0
        job.next_attempt_at = None
    if not force and ((job.status == Job.Status.COMPLETED and job.bank_key) or job.attempts >= Job.MAX_ATTEMPTS
                      or (job.status != Job.Status.PENDING and job.next_attempt_at and job.next_attempt_at > now)):
        return None
    job.source_key = identity
    job.status = Job.Status.RUNNING
    job.lease_token = uuid.uuid4()
    job.lease_expires_at = now + LEASE_DURATION
    job.next_attempt_at = None
    job.attempts += 1
    job.started_at = now
    job.finished_at = None
    job.error = ''
    job.mcq_target = sum(MCQ_TARGETS.values())
    job.theory_target = sum(THEORY_TARGETS.values())
    job.save()
    Slide.objects.filter(pk=slide.pk).update(generation_status='in_progress')
    return job


def owned_job(job):
    """Must be called inside a transaction before any write from a worker."""
    from curriculum.models import Slide
    from .models import QuestionGenerationJob as Job
    current_slide = Slide.objects.select_for_update().get(pk=job.slide_id)
    current = Job.objects.select_for_update().get(pk=job.pk)
    if (current.status != Job.Status.RUNNING or current.lease_token != job.lease_token
            or not current.lease_expires_at or current.lease_expires_at <= timezone.now()
            or current.source_key != source_identity(current_slide)):
        raise LostLease()
    if current.source_digest:
        if extracted_digest(current.slide_id) != current.source_digest:
            raise LostLease()
    return current


def extracted_source(slide_id):
    from curriculum.models import SlideContent
    from curriculum.services.document_extraction import content_text, ExtractionError, source_key
    content = SlideContent.objects.select_related('slide').filter(slide_id=slide_id).first()
    if not content or (content.content_data.get('text_extraction') or {}).get('source_key') != source_key(content.slide):
        return '', ''
    try:
        text = content_text(content.content_data, require_complete=True)
    except ExtractionError:
        return '', ''
    from curriculum.models import SlideDeck
    origin = SlideDeck.objects.filter(curriculum_slide_id=slide_id).first()
    if origin:
        from .deck_banks import deck_version
        if content.content_data.get('standalone_version') != deck_version(origin):
            return '', ''
    original_hash = content.content_data['text_extraction']['source_sha256']
    return text, hashlib.sha256(json.dumps([original_hash, text]).encode()).hexdigest()


def extracted_digest(slide_id):
    return extracted_source(slide_id)[1]


@transaction.atomic
def bind_source(job, text):
    current = owned_job(job)
    canonical, digest = extracted_source(job.slide_id)
    if not digest or text != canonical:
        raise LostLease()
    current.source_digest = digest
    current.bank_key = hashlib.sha256(f'{current.source_key}:{digest}'.encode()).hexdigest()
    current.save(update_fields=['source_digest', 'bank_key', 'updated_at'])
    job.source_digest, job.bank_key = current.source_digest, current.bank_key
    return current


@transaction.atomic
def heartbeat(job):
    current = owned_job(job)
    current.lease_expires_at = timezone.now() + LEASE_DURATION
    current.save(update_fields=['lease_expires_at', 'updated_at'])


def normalized_stem(text):
    return re.sub(r'[^\w]+', ' ', str(text).casefold()).strip()


def existing_counts_by_difficulty(slide, question_type: str) -> dict[str, int]:
    """How many questions of each difficulty this slide already has."""
    from curriculum.models import QuizQuestion
    from .models import QuestionGenerationJob
    key = QuestionGenerationJob.objects.filter(slide=slide).values_list('bank_key', flat=True).first()
    if not key:
        return {}
    counts, seen = {}, set()
    for row in QuizQuestion.objects.filter(source_slide=slide, question_type=question_type, bank_key=key, needs_review=False).order_by('pk').values():
        difficulty = row['difficulty']
        stem = normalized_stem(row['question_text'])
        if stem not in seen and difficulty in MCQ_TARGETS and valid_row(row, question_type, difficulty):
            counts[difficulty] = counts.get(difficulty, 0) + 1
            seen.add(stem)
    return counts


def valid_row(row, kind, difficulty):
    if not isinstance(row, dict) or not isinstance(row.get('question_text'), str) or not row['question_text'].strip():
        return False
    if row.get('difficulty', difficulty) != difficulty:
        return False
    marks = row.get('maximum_marks', 1 if kind == 'mcq' else 20)
    if type(marks) is not int or marks <= 0:
        return False
    if kind == 'mcq':
        options = [row.get('option_' + letter) for letter in 'abcd']
        return (all(isinstance(value, str) and 0 < len(value.strip()) <= 500 for value in options)
                and len({normalized_stem(value) for value in options}) == 4
                and row.get('correct_option') in ('A', 'B', 'C', 'D')
                and isinstance(row.get('explanation'), str) and bool(row['explanation'].strip())
                and marks == 1)
    rubric = row.get('marking_rubric')
    return (isinstance(row.get('ideal_answer'), str) and bool(row['ideal_answer'].strip())
            and isinstance(rubric, list) and bool(rubric)
            and all(isinstance(part, dict) and isinstance(part.get('criterion'), str)
                    and bool(part['criterion'].strip()) and type(part.get('marks')) is int
                    and part['marks'] > 0 for part in rubric)
            and sum(part['marks'] for part in rubric) == marks)


@transaction.atomic
def save_batch(job, slide, rows, text, kind, difficulty, limit):
    from curriculum.models import QuizQuestion
    from .bank_sources import evidence
    current = bind_source(job, text)
    if not isinstance(rows, list):
        rows = []
    pool = QuizQuestion.objects.filter(source_slide=slide, question_type=kind, bank_key=current.bank_key)
    seen = {normalized_stem(value) for value in pool.values_list('question_text', flat=True)}
    target = (MCQ_TARGETS if kind == 'mcq' else THEORY_TARGETS)[difficulty]
    limit = min(limit, max(0, target - existing_counts_by_difficulty(slide, kind).get(difficulty, 0)))
    saved = 0
    stored = 0
    for row in rows:
        if stored >= limit:
            break
        if not valid_row(row, kind, difficulty):
            continue
        reference = evidence(row, text)
        if not reference:
            continue
        stem = normalized_stem(row['question_text'])
        if not stem or stem in seen:
            continue
        values = dict(id=f'q_{uuid.uuid4().hex[:12]}', question_type=kind, difficulty=difficulty,
                      subject=slide.subject, block=slide.block, sub_block=slide.sub_block,
                      question_text=row['question_text'].strip(), source_type='ai_generated',
                      source_slide=slide, source_text=reference[1], source_page=reference[0], bank_key=current.bank_key,
                      needs_review=row.get('needs_review') is not False,
                      review_reason=str(row.get('review_reason') or 'Requires review')[:500] if row.get('needs_review') is not False else '',
                      maximum_marks=row.get('maximum_marks', 1 if kind == 'mcq' else 20))
        if kind == 'mcq':
            values.update({key: row[key].strip() for key in ('option_a', 'option_b', 'option_c', 'option_d', 'explanation')})
            values['correct_option'] = row['correct_option']
        else:
            values.update(ideal_answer=row['ideal_answer'], model_answer=row['ideal_answer'], marking_rubric=row['marking_rubric'])
        QuizQuestion.objects.create(**values)
        stored += 1
        seen.add(stem)
        saved += int(not values['needs_review'])
    current.mcq_generated = sum(existing_counts_by_difficulty(slide, 'mcq').values())
    current.theory_generated = sum(existing_counts_by_difficulty(slide, 'theory').values())
    current.lease_expires_at = timezone.now() + LEASE_DURATION
    current.save(update_fields=['mcq_generated', 'theory_generated', 'lease_expires_at', 'updated_at'])
    return saved


@transaction.atomic
def finish_job(job, *, error=''):
    from .models import QuestionGenerationJob as Job
    from curriculum.models import Slide, SlideProcessingStatus
    current = owned_job(job)
    mcqs = existing_counts_by_difficulty(current.slide, 'mcq')
    theory = existing_counts_by_difficulty(current.slide, 'theory')
    current.mcq_generated = sum(mcqs.values())
    current.theory_generated = sum(theory.values())
    complete = not error and all(mcqs.get(d, 0) >= n for d, n in MCQ_TARGETS.items()) and all(
        theory.get(d, 0) >= n for d, n in THEORY_TARGETS.items())
    current.status = Job.Status.COMPLETED if complete else Job.Status.PARTIAL if (current.mcq_generated or current.theory_generated) else Job.Status.FAILED
    current.error = '' if complete else error or 'The provider did not return enough valid, distinct questions. Retry generation.'
    current.finished_at = timezone.now()
    current.lease_expires_at = None
    current.lease_token = None
    current.next_attempt_at = timezone.now() + RETRY_DELAY if not complete and current.attempts < Job.MAX_ATTEMPTS else None
    current.save()
    Slide.objects.filter(pk=current.slide_id).update(generation_status='completed' if complete else 'failed')
    from curriculum.slide_processing import ACTIVE_STATES
    SlideProcessingStatus.objects.filter(slide_id=current.slide_id).exclude(
        processing_token__isnull=False, status__in=ACTIVE_STATES).update(
        status='completed' if complete else 'failed', error_message=current.error, completed_at=current.finished_at)
    return {'slide_id': current.slide_id, 'success': complete, 'status': current.status,
            'mcq_generated': current.mcq_generated, 'theory_generated': current.theory_generated,
            'progress_percent': current.progress_percent, 'error': current.error}


def generate_for_slide(slide, *, force=False):
    """Resume saved batches under an expiring lease; never publish from an old worker."""
    from curriculum.services.ai_question_generator import AIQuestionGenerator
    from curriculum.services.document_extraction import ExtractionError
    job = claim_job(slide, force=force)
    if job is None:
        return {'slide_id': slide.id, 'skipped': True, 'reason': 'not runnable'}
    slide = job.slide
    try:
        text = slide_text(slide)
        heartbeat(job)
        bind_source(job, text)
        if len(text) < MIN_TEXT_CHARS:
            return finish_job(job, error='The source has too little readable text to generate this bank.')
        if not slide.subject_id or not slide.class_group_id:
            return finish_job(job, error='Assign this document to a class and subject before generating questions.')
        errors = []
        for kind, targets, batch_size, generator in (
                ('mcq', MCQ_TARGETS, MCQ_BATCH, AIQuestionGenerator.generate_mcqs_from_text),
                ('theory', THEORY_TARGETS, THEORY_BATCH, AIQuestionGenerator.generate_theory_from_text)):
            for difficulty, target in targets.items():
                have = existing_counts_by_difficulty(slide, kind).get(difficulty, 0)
                while have < target:
                    heartbeat(job)
                    want = min(batch_size, target - have)
                    def persist(rows):
                        save_batch(job, slide, rows, text, kind, difficulty, want)

                    try:
                        rows = generator(
                            text=text,
                            slide=slide,
                            topic=getattr(slide, 'topic', None),
                            count=want,
                            difficulty=difficulty,
                            on_batch=persist,
                            on_request=lambda: heartbeat(job),
                        )
                    except LostLease:
                        raise
                    except Exception as exc:
                        from django.db import DatabaseError
                        if isinstance(exc, DatabaseError):
                            raise
                        logger.warning(
                            "Question generation failed for %s/%s (%s)",
                            kind, difficulty, type(exc).__name__,
                        )
                        errors.append(exc)
                        break

                    # Keep compatibility with generators that don't implement incremental
                    # persistence (including integrations and older test doubles).
                    if rows:
                        persist(rows)
                    updated = existing_counts_by_difficulty(slide, kind).get(difficulty, 0)
                    if updated <= have:
                        break
                    have = updated
        incomplete = any(
            existing_counts_by_difficulty(slide, kind).get(difficulty, 0) < target
            for kind, targets in (('mcq', MCQ_TARGETS), ('theory', THEORY_TARGETS))
            for difficulty, target in targets.items()
        )
        error = (
            'Some question requests failed. Saved questions were preserved; retry generation to fill the remaining targets.'
            if errors and incomplete else ''
        )
        return finish_job(job, error=error)
    except LostLease:
        return {'slide_id': slide.id, 'skipped': True, 'reason': 'worker ownership expired or source changed'}
    except Exception as exc:
        logger.warning('Question generation failed for %s (%s)', slide.id, type(exc).__name__)
        try:
            result = finish_job(job, error=str(exc) if isinstance(exc, ExtractionError) else
                                'Question generation failed. Saved questions are preserved; retry generation.')
            if isinstance(exc, ExtractionError):
                result['text_extraction'] = exc.report
            return result
        except LostLease:
            return {'slide_id': slide.id, 'skipped': True, 'reason': 'worker ownership expired or source changed'}
