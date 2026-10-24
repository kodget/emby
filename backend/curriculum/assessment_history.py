"""Historical attempts without original question versions are evidence, not resumable exams."""
from rest_framework.exceptions import ValidationError


def is_historical(attempt):
    return not attempt.question_snapshots and not attempt.assessment_id and not attempt.snapshot_class_id


def require_current(attempt):
    if is_historical(attempt):
        raise ValidationError({'error': 'This historical attempt has no saved question versions. It is read-only; start a new practice, mock or published class paper.',
                               'code': 'historical_attempt_read_only'})


def representation(attempt):
    # Never join today's questions or expose old generated narratives as verified feedback.
    return {
        'id': attempt.pk, 'exam_type': attempt.exam_type, 'status': attempt.status,
        'started_at': attempt.started_at, 'submitted_at': attempt.submitted_at,
        'historical_read_only': True, 'score_verified': False, 'answers_released': False,
        'history_notice': 'The original question versions were not saved. This record cannot be resumed or regraded. Stored scores are historical and are excluded from verified assessment analytics.',
        'recorded_result': {'mcq_score': attempt.mcq_score, 'mcq_total': attempt.mcq_total,
                            'theory_score': attempt.theory_score, 'theory_total': attempt.theory_total,
                            'overall_percentage': attempt.overall_percentage} if attempt.submitted_at else None,
        'questions': [], 'question_ids': [], 'flagged_questions': [],
        'responses': [{'id': r.pk, 'question_id': r.question_id or r.snapshot_question_id,
                       'selected_option': r.selected_option, 'text_answer': r.text_answer,
                       'answered_at': r.answered_at} for r in attempt.responses.all()],
        'theory_grading_pending': False, 'grading': None, 'analysis_data': {}, 'feedback': None,
        'time_remaining_seconds': None, 'is_timed': False,
    }
