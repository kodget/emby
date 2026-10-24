"""Verifiable references and eligibility for newly generated document banks."""
import re

from django.db.models import F, Q


def page_sources(text):
    matches = list(re.finditer(r'^\[Page (\d+)\]\s*\n', text, re.MULTILINE))
    return {int(match[1]): text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip()
            for i, match in enumerate(matches)}


def evidence(row, text):
    page = row.get('source_page')
    quote = row.get('source_quote')
    if type(page) is not int or not isinstance(quote, str):
        return None
    normalized = ' '.join(quote.split())
    source = ' '.join(page_sources(text).get(page, '').split())
    if len(normalized) < 20 or len(normalized) > 2000 or normalized not in source:
        return None
    return page, normalized


def eligible_questions(queryset, *, formal=False):
    """Filter new selections only; historical attempts keep their referenced rows."""
    other_sources = ~Q(source_type='ai_generated')
    if not formal:
        other_sources |= Q(source_slide__isnull=True, bank_key='')
    bank = Q(needs_review=False, source_slide__generation_job__bank_key=F('bank_key')) & ~Q(bank_key='')
    from .generation import source_identity, extracted_digest
    from .models import QuestionGenerationJob
    candidate_sources = queryset.filter(bank).values_list('source_slide_id', flat=True).distinct()
    current_sources = [job.slide_id for job in QuestionGenerationJob.objects.filter(
        slide_id__in=candidate_sources).select_related('slide')
        if job.source_key == source_identity(job.slide) and job.source_digest == extracted_digest(job.slide_id)]
    bank &= Q(source_slide_id__in=current_sources)
    if formal:
        bank &= Q(reviewed_at__isnull=False)
    return queryset.filter(other_sources | bank)


def usable_questions(user, queryset):
    """Current, authorized, well-formed questions for new practice and coverage."""
    from curriculum.class_access import visible
    from curriculum.models import Slide, Material
    from .generation import valid_row
    candidates = eligible_questions(queryset.filter(needs_review=False).filter(
        ~Q(source_type='ai_generated') | ~Q(bank_key='')).filter(
        Q(source_slide__isnull=True) | Q(source_slide__in=visible(Slide, user))).filter(
        Q(source_material__isnull=True) | Q(source_material__in=visible(Material, user))))
    candidates = candidates.select_related('block', 'sub_block', 'source_slide__topic',
        'source_material__topic', 'source_slide__sub_block', 'source_material__sub_block')
    for question in candidates.order_by('pk'):
        if question.difficulty not in ('easy', 'medium', 'hard') or question.question_type not in ('mcq', 'theory'):
            continue
        if (question.block_id and question.block.subject_id != question.subject_id) or (
                question.sub_block_id and question.sub_block.block_id != question.block_id):
            continue
        sources = [source for source in (question.source_slide, question.source_material) if source]
        if any(any(getattr(source, field + '_id') != getattr(question, field + '_id')
                   for field in ('subject', 'block', 'sub_block')) for source in sources):
            continue
        if any(source.topic_id and (
                (source.topic.block_id and source.topic.block_id != question.block_id) or
                source.topic.sub_block_id != question.sub_block_id) for source in sources):
            continue
        if valid_row(question.__dict__, question.question_type, question.difficulty):
            yield question


def bank_status(slide):
    """Student-safe progress; never expose worker tokens or provider diagnostics."""
    from curriculum.models import QuizQuestion, SlideContent
    from .generation import (MCQ_TARGETS, THEORY_TARGETS, existing_counts_by_difficulty,
                             source_identity, extracted_digest)
    from .models import QuestionGenerationJob
    job = QuestionGenerationJob.objects.filter(slide=slide).first()
    if not job or (job.status == 'completed' and not job.bank_key):
        return {'status': 'not_requested', 'mcq_target': sum(MCQ_TARGETS.values()),
                'mcq_by_difficulty': {}, 'theory_target': sum(THEORY_TARGETS.values()),
                'theory_by_difficulty': {}, 'progress_percent': 0, 'error': ''}
    if job.bank_key and (job.source_key != source_identity(slide) or job.source_digest != extracted_digest(slide.pk)):
        return {'status': 'failed', 'mcq_target': sum(MCQ_TARGETS.values()),
                'mcq_by_difficulty': {}, 'theory_target': sum(THEORY_TARGETS.values()),
                'theory_by_difficulty': {}, 'progress_percent': 0,
                'error': 'The document changed. Prepare questions for its current version.'}
    questions = QuizQuestion.objects.filter(source_slide=slide, bank_key=job.bank_key).exclude(bank_key='')
    pages = sorted(set(questions.filter(needs_review=False).exclude(source_page=None).values_list('source_page', flat=True)))
    content = SlideContent.objects.filter(slide=slide).first()
    report = (content.content_data.get('text_extraction') or {}) if content else {}
    mcqs = existing_counts_by_difficulty(slide, 'mcq')
    theory = existing_counts_by_difficulty(slide, 'theory')
    full = all(mcqs.get(d, 0) >= n for d, n in MCQ_TARGETS.items()) and all(
        theory.get(d, 0) >= n for d, n in THEORY_TARGETS.items())
    # A subsequent editor/reviewer can withdraw a question from a completed bank.
    status = 'partial' if job.status == 'completed' and not full else job.status
    progress = min(100, round(100 * (sum(mcqs.values()) + sum(theory.values())) /
                             max(1, job.mcq_target + job.theory_target)))
    return {'status': status, 'mcq_target': job.mcq_target, 'theory_target': job.theory_target,
            'mcq_by_difficulty': mcqs, 'theory_by_difficulty': theory,
            'progress_percent': progress, 'needs_review': questions.filter(needs_review=True).count(),
            'represented_pages': pages, 'source_pages': report.get('total_pages', 0),
            'attempts': job.attempts, 'next_attempt_at': job.next_attempt_at, 'error': job.error}


def approve_reviewed_question(question_id):
    """Publish only after an authorized admin explicitly confirms their human review."""
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils import timezone
    from curriculum.models import QuizQuestion, Slide, SlideContent
    from curriculum.services.document_extraction import content_text
    from .models import QuestionGenerationJob
    from .generation import (source_identity, extracted_digest, valid_row,
                             existing_counts_by_difficulty, MCQ_TARGETS, THEORY_TARGETS)
    with transaction.atomic():
        slide_id = QuizQuestion.objects.values_list('source_slide_id', flat=True).get(pk=question_id)
        slide = Slide.objects.select_for_update().filter(pk=slide_id).first()
        job = QuestionGenerationJob.objects.select_for_update().filter(slide=slide).first() if slide else None
        question = QuizQuestion.objects.select_for_update().get(pk=question_id)
        if (not job or not job.bank_key or job.bank_key != question.bank_key
                or job.source_key != source_identity(slide) or job.source_digest != extracted_digest(slide.pk)):
            raise ValidationError('Only a question from the current verified source can be approved.')
        text = content_text(SlideContent.objects.get(slide=slide).content_data, require_complete=True)
        row = {field.name: getattr(question, field.name) for field in question._meta.fields}
        row['source_quote'] = question.source_text
        if not valid_row(row, question.question_type, question.difficulty) or not evidence(row, text):
            raise ValidationError('Correct the answer, structure and source reference before approval.')
        target = (MCQ_TARGETS if question.question_type == 'mcq' else THEORY_TARGETS).get(question.difficulty, 0)
        if question.needs_review and existing_counts_by_difficulty(slide, question.question_type).get(question.difficulty, 0) >= target:
            raise ValidationError('This difficulty pool is already full; this question remains held for review.')
        question.needs_review = False
        question.reviewed_at = timezone.now()
        question.save(update_fields=['needs_review', 'reviewed_at', 'updated_at'])
        return question
