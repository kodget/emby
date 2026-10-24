"""Persist selected-attempt answers without calling a grader or trusting client scores."""
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import QuizQuestion, QuizAttemptResponse


def save_answer(attempt, data):
    from .assessment_history import require_current
    require_current(attempt)
    # The view holds the same attempt row lock used by submission.
    if attempt.status != 'in_progress' or attempt.is_expired:
        raise ValidationError({'error': 'This attempt is closed or its deadline has passed. Submit to see your result.'})
    qid = data.get('question_id')
    if not isinstance(qid, str) or qid not in attempt.question_ids:
        raise ValidationError({'error': 'Question not in this attempt.'})
    if attempt.question_snapshots:
        question = next((q for q in attempt.question_snapshots if q['id'] == qid), None)
    else:
        question = QuizQuestion.objects.filter(pk=qid).values('question_type', 'correct_option').first()
    if question is None:
        raise ValidationError({'error': 'The selected question is unavailable.'})
    if question['question_type'] == 'mcq':
        option = data.get('selected_option')
        if not isinstance(option, str) or option not in ('A', 'B', 'C', 'D'):
            raise ValidationError({'error': 'Choose A, B, C or D.'})
        if data.get('text_answer') not in (None, ''):
            raise ValidationError({'error': 'MCQ answers must use an option.'})
        defaults = {'selected_option': option, 'text_answer': '', 'is_correct': option == question['correct_option']}
    elif question['question_type'] == 'theory':
        answer = data.get('text_answer')
        if not isinstance(answer, str) or len(answer) > 20000:
            raise ValidationError({'error': 'A written answer must be text of at most 20,000 characters.'})
        if data.get('selected_option') not in (None, ''):
            raise ValidationError({'error': 'Theory questions require a written answer.'})
        defaults = {'text_answer': answer, 'selected_option': '', 'is_correct': None,
                    'ai_score': None, 'ai_feedback': {}, 'ai_rubric_breakdown': [],
                    'ai_evaluation_status': 'pending'}
    else:
        raise ValidationError({'error': 'Unsupported question type.'})
    defaults['answered_at'] = timezone.now()
    reference = {'snapshot_question_id': qid} if attempt.assessment_id or attempt.snapshot_class_id else {'question_id': qid}
    QuizAttemptResponse.objects.update_or_create(attempt=attempt, **reference, defaults=defaults)
