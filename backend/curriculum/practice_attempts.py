"""Single-deck practice assembled from saved, current banks; no provider calls."""
import random
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from learning.bank_sources import usable_questions
from .class_access import require_visible, visible
from .models import Slide, QuizQuestion, QuizAttempt, QuizAttemptResponse, UserStats


def pool(user, slide, difficulty, source='hierarchy'):
    qs = visible(QuizQuestion, user).filter(
        source_slide=slide, source_type='ai_generated', needs_review=False,
        question_type='mcq', difficulty=difficulty).exclude(bank_key='')
    if source == 'missed_questions':
        qs = qs.filter(pk__in=QuizAttemptResponse.objects.filter(
            attempt__user=user, attempt__status__in=['submitted', 'auto_submitted'],
            is_correct=False).values_list('question_id', flat=True))
    # Defend against duplicate stems in imported/edited banks as well as duplicate IDs.
    seen, questions = set(), []
    for question in usable_questions(user, qs):
        key = ' '.join(question.question_text.casefold().split())
        if key not in seen:
            seen.add(key)
            questions.append(question)
    return questions


def options(user, slide_id, source='hierarchy'):
    if source not in ('hierarchy', 'missed_questions'):
        raise ValidationError({'error': 'Choose saved questions or missed questions from one deck.'})
    slide = require_visible(Slide, user, slide_id)
    return {'slide': slide.pk, 'title': slide.title, 'maximum': 20,
            'available': {d: len(pool(user, slide, d, source)) for d in ('easy', 'medium', 'hard')}}


@transaction.atomic
def create(user, data):
    config = data.get('configuration', {})
    if not isinstance(config, dict):
        raise ValidationError({'error': 'Configuration must be an object.'})
    count, theory = config.get('mcq_count', 5), config.get('theory_count', 0)
    difficulty, source = config.get('difficulty', 'medium'), config.get('question_source', 'hierarchy')
    if type(count) is not int or not 1 <= count <= 20 or type(theory) is not int or theory != 0:
        raise ValidationError({'error': 'Practice requires 1–20 MCQs and no theory questions.'})
    if difficulty not in ('easy', 'medium', 'hard') or source not in ('hierarchy', 'missed_questions'):
        raise ValidationError({'error': 'Choose a valid difficulty and saved or missed questions.'})
    if not data.get('slide'):
        raise ValidationError({'error': 'Select one deck for practice.'})
    slide = require_visible(Slide, user, data['slide'])
    # Same lock order as bank preparation/review: Slide first, then questions.
    slide = Slide.objects.select_for_update().get(pk=slide.pk)
    for field in ('subject', 'block', 'sub_block', 'topic'):
        if data.get(field) and str(data[field]) != str(getattr(slide, field + '_id')):
            raise ValidationError({'error': 'The selected course/module must match the deck.'})
    timed, duration = data.get('is_timed', False), data.get('duration_minutes')
    if type(timed) is not bool or (timed and (type(duration) is not int or not 1 <= duration <= 180)):
        raise ValidationError({'error': 'Timed practice needs a whole-number duration of 1–180 minutes.'})
    if not timed and duration is not None:
        raise ValidationError({'error': 'Untimed practice must not include a duration.'})
    questions = pool(user, slide, difficulty, source)
    if len(questions) < count:
        raise ValidationError({'error': f'Only {len(questions)} {difficulty} questions are available in this deck.',
                               'available': len(questions), 'requested': count, 'code': 'insufficient_questions'})
    questions = random.sample(questions, count)
    from .serializers import QuizQuestionSerializer
    snapshots = [dict(QuizQuestionSerializer(q).data, bank_key=q.bank_key) for q in questions]
    return QuizAttempt.objects.create(
        id=f'practice-{uuid.uuid4().hex}', user=user, exam_type='practice',
        slide=slide, subject=slide.subject, block=slide.block, sub_block=slide.sub_block, topic=slide.topic,
        configuration={'mcq_count': count, 'theory_count': 0, 'difficulty': difficulty, 'question_source': source},
        is_timed=timed, duration_minutes=duration, deadline=timezone.now() + timedelta(minutes=duration) if timed else None,
        question_ids=[q.pk for q in questions], question_snapshots=snapshots, mcq_total=count)


def public_questions(attempt):
    hidden = {'correct_option', 'explanation', 'ideal_answer', 'model_answer', 'marking_rubric', 'source_text', 'bank_key'}
    if attempt.status != 'in_progress' and (not attempt.assessment_id or attempt.assessment.answers_released_at):
        hidden = {'bank_key'}
    return [{k: v for k, v in q.items() if k not in hidden} for q in attempt.question_snapshots]


def answer(attempt, data):
    from .attempt_answers import save_answer
    return save_answer(attempt, data)


def submit(attempt):
    """Persist score and side effects once under the attempt lock; retries return it."""
    if attempt.status == 'in_progress':
        responses = {r.question_id: r for r in attempt.responses.all()}
        correct = 0
        for q in attempt.question_snapshots:
            response = responses.get(q['id'])
            if response:
                response.is_correct = response.selected_option == q['correct_option']
                response.save(update_fields=['is_correct'])
                correct += int(response.is_correct)
        attempt.status = 'auto_submitted' if attempt.is_expired else 'submitted'
        attempt.submitted_at = timezone.now()
        attempt.mcq_score = correct
        attempt.mcq_total = len(attempt.question_snapshots)
        attempt.overall_percentage = correct / attempt.mcq_total * 100
        attempt.analysis_data = {'points_earned': correct}
        attempt.save()
        stats, _ = UserStats.objects.get_or_create(user=attempt.user)
        UserStats.objects.filter(pk=stats.pk).update(points=F('points') + correct, quizzes_taken=F('quizzes_taken') + 1)
        from learning.selection import mark_served, mark_answered
        mark_served(attempt.user, attempt.question_ids)
        for response in responses.values():
            if response.question_id in attempt.question_ids:
                mark_answered(attempt.user, response.question_id, response.is_correct)
        from learning import events
        from learning.models import ActivityType
        # Serialize per-user event/stat updates across simultaneous practice attempts.
        UserStats.objects.select_for_update().get(pk=stats.pk)
        events.record(user=attempt.user, activity=ActivityType.QUIZ_COMPLETED,
            subject=attempt.subject, block=attempt.block, sub_block=attempt.sub_block, topic=attempt.topic,
            correct_count=correct, total_count=attempt.mcq_total,
            duration_seconds=int(((attempt.deadline if attempt.deadline and attempt.deadline < attempt.submitted_at
                                   else attempt.submitted_at) - attempt.started_at).total_seconds()),
            resource_type='QuizAttempt', resource_id=attempt.pk, metadata={'exam_type': 'practice'})
    return {'id': attempt.pk, 'status': attempt.status, 'mcq_score': attempt.mcq_score,
            'overall_percentage': attempt.overall_percentage,
            'points_earned': attempt.analysis_data.get('points_earned', 0)}
