"""Deterministic, auditable observations from the saved paper and saved responses."""
from collections import defaultdict


def build(attempt):
    if not attempt.assessment_id or attempt.status == 'in_progress' or not attempt.assessment.answers_released_at:
        return None
    responses = {r.snapshot_question_id: r for r in attempt.responses.all()}
    counts = {'correct': 0, 'incorrect': 0, 'unanswered': 0}
    difficulties = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'unanswered': 0})
    review = []
    for index, question in enumerate(attempt.question_snapshots, 1):
        response = responses.get(question['id'])
        common = {'question_id': question['id'], 'question_number': index,
                  'question_text': question['question_text'], 'question_type': question['question_type']}
        if question['question_type'] == 'mcq':
            chosen = response.selected_option if response else ''
            outcome = 'unanswered' if not chosen else 'correct' if chosen == question['correct_option'] else 'incorrect'
            counts[outcome] += 1
            difficulties[question.get('difficulty', 'medium')][outcome] += 1
            if outcome != 'correct':
                review.append({**common, 'outcome': outcome, 'selected_option': chosen or None,
                    'correct_option': question['correct_option'], 'explanation': question['explanation'],
                    'next_step': 'Review the saved explanation, then explain why the correct option fits and the alternatives do not.'})
        else:
            answered = bool(response and response.text_answer.strip())
            complete = bool(response and response.ai_evaluation_status == 'completed')
            gaps = [r for r in response.ai_rubric_breakdown
                    if r['marks_awarded'] < r['marks_allocated']] if complete else []
            if not answered or not complete or gaps:
                review.append({**common, 'outcome': 'unanswered' if not answered else 'graded' if complete else 'pending',
                    'marks': float(response.ai_score) if complete else None,
                    'maximum_marks': question['maximum_marks'], 'criteria_to_review': gaps,
                    'next_step': ('Write an answer, then compare it with the released model answer and each rubric criterion.'
                                  if not answered else 'Use the listed rubric feedback to revise the missing parts of your answer.'
                                  if complete else 'Wait for written grading before drawing conclusions about this answer.')})
    patterns = [{'difficulty': difficulty, **values, 'total': sum(values.values()),
                 'sufficient_evidence': sum(values.values()) >= 3}
                for difficulty, values in sorted(difficulties.items())]
    return {'basis': 'saved_question_versions_and_responses', 'mcq': counts,
            'difficulty_breakdown': patterns, 'questions_to_review': review,
            'grading_pending': attempt.theory_grading_pending,
            'note': 'These observations describe this paper only. A wrong answer does not establish its cause or predict future exam performance. Difficulty groups with fewer than three questions are limited evidence.'}
