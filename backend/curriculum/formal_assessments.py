"""Class-owned private papers and a single durable attempt per published paper."""
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .class_access import member_class
from .models import FormalAssessment, QuizAttempt, UserStats


def can_author(user):
    return bool(member_class(user) and user.profile.is_class_head)


def require_author(user):
    if not can_author(user):
        raise PermissionDenied('An approved head of this class must manage its assessments.')


def integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError({'error': f'{label} must be a whole number from {minimum} to {maximum}.'})
    return value


def text(value, label, limit=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError({'error': f'{label} is required and must be at most {limit} characters.'})
    return value.strip()


def validate_paper(data):
    if not isinstance(data, dict):
        raise ValidationError({'error': 'The assessment must be a JSON object.'})
    allowed = {'title', 'duration_minutes', 'mcq_count', 'theory_count', 'questions', 'revision'}
    if set(data) - allowed:
        raise ValidationError({'error': 'Only the paper settings and questions may be edited.'})
    title = text(data.get('title'), 'Title', 200)
    duration = integer(data.get('duration_minutes'), 1, 150, 'Duration')
    mcqs = integer(data.get('mcq_count'), 0, 50, 'MCQ count')
    theories = integer(data.get('theory_count'), 0, 5, 'Theory count')
    if not mcqs + theories:
        raise ValidationError({'error': 'Choose at least one question.'})
    questions = data.get('questions', [])
    if not isinstance(questions, list) or len(questions) > 55:
        raise ValidationError({'error': 'Questions must be a list with at most 55 entries.'})
    clean = []
    for q in questions:
        if not isinstance(q, dict) or q.get('question_type') not in ('mcq', 'theory'):
            raise ValidationError({'error': 'Each question must be an MCQ or theory question.'})
        row = {'id': f'formal-q-{uuid.uuid4().hex}', 'question_type': q['question_type'],
               'question_text': text(q.get('question_text'), 'Question'),
               'difficulty': q.get('difficulty', 'medium')}
        if row['difficulty'] not in ('easy', 'medium', 'hard'):
            raise ValidationError({'error': 'Choose easy, medium or hard difficulty.'})
        if row['question_type'] == 'mcq':
            for option in ('a', 'b', 'c', 'd'):
                row['option_' + option] = text(q.get('option_' + option), 'Option', 2000)
            if len({row['option_' + option].casefold() for option in ('a', 'b', 'c', 'd')}) != 4:
                raise ValidationError({'error': 'The four MCQ options must be different.'})
            if q.get('correct_option') not in ('A', 'B', 'C', 'D'):
                raise ValidationError({'error': 'Choose the correct option A, B, C or D.'})
            row.update(correct_option=q['correct_option'], maximum_marks=1,
                       explanation=text(q.get('explanation'), 'Explanation'))
        else:
            marks = integer(q.get('maximum_marks'), 1, 100, 'Theory marks')
            rubric = q.get('marking_rubric')
            if not isinstance(rubric, list) or not 1 <= len(rubric) <= 100:
                raise ValidationError({'error': 'Provide a marking rubric for each theory question.'})
            rubric = [{'criterion': text(r.get('criterion'), 'Rubric criterion', 2000),
                       'marks': integer(r.get('marks'), 1, marks, 'Criterion marks')}
                      for r in rubric if isinstance(r, dict)]
            if len(rubric) != len(q['marking_rubric']) or sum(r['marks'] for r in rubric) != marks:
                raise ValidationError({'error': 'Rubric marks must add up to the question maximum.'})
            row.update(maximum_marks=marks, marking_rubric=rubric,
                       ideal_answer=text(q.get('ideal_answer'), 'Model answer'))
        clean.append(row)
    if sum(q['question_type'] == 'mcq' for q in clean) > mcqs or sum(q['question_type'] == 'theory' for q in clean) > theories:
        raise ValidationError({'error': 'The draft contains more questions than its chosen counts.'})
    return dict(title=title, duration_minutes=duration, mcq_count=mcqs, theory_count=theories, questions=clean)


def representation(paper, user, detail=False):
    attempt = paper.attempts.filter(user=user).first()
    data = {name: getattr(paper, name) for name in (
        'title', 'duration_minutes', 'mcq_count', 'theory_count', 'revision', 'published_at',
        'closed_at', 'answers_released_at')}
    data.update(id=str(paper.pk), can_manage=can_author(user),
                attempt={'id': attempt.pk, 'status': attempt.status} if attempt else None)
    if detail and can_author(user):
        data['questions'] = paper.questions
        data['has_ai_questions'] = paper.has_ai_questions
        from .assessment_drafts import public
        data['generation'] = public(paper.draft_jobs.order_by('-pk').first())
    return data


class FormalAssessmentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def papers(self):
        group = member_class(self.request.user)
        qs = FormalAssessment.objects.filter(class_group=group) if group else FormalAssessment.objects.none()
        return qs if can_author(self.request.user) else qs.filter(published_at__isnull=False)

    def paper(self, pk, lock=False):
        try:
            uuid.UUID(str(pk))
        except (ValueError, TypeError, AttributeError):
            raise NotFound('Assessment not found.')
        qs = self.papers().select_for_update() if lock else self.papers()
        paper = qs.filter(pk=pk).first()
        if not paper:
            raise NotFound('Assessment not found.')
        return paper

    def list(self, request):
        return Response({'can_manage': can_author(request.user),
                         'assessments': [representation(p, request.user) for p in self.papers()]})

    def retrieve(self, request, pk=None):
        return Response(representation(self.paper(pk), request.user, detail=True))

    def create(self, request):
        require_author(request.user)
        paper = FormalAssessment.objects.create(class_group=member_class(request.user),
            created_by=request.user, **validate_paper(request.data))
        return Response(representation(paper, request.user, detail=True), status=201)

    def check_revision(self, paper, data):
        if not isinstance(data, dict) or type(data.get('revision')) is not int or data['revision'] != paper.revision:
            raise ValidationError({'error': 'This draft changed. Reload it before saving or publishing.'})

    @transaction.atomic
    def partial_update(self, request, pk=None):
        require_author(request.user)
        paper = self.paper(pk, lock=True)
        if paper.published_at:
            raise ValidationError({'error': 'Published questions and settings cannot be changed.'})
        self.check_revision(paper, request.data)
        for name, value in validate_paper(request.data).items():
            setattr(paper, name, value)
        paper.ai_reviewed_at = paper.ai_reviewed_by = None
        paper.revision += 1
        paper.save()
        paper.draft_jobs.filter(status__in=['pending', 'running', 'retry_wait', 'failed', 'completed']).update(
            status='cancelled', error_code='draft_changed', lease_token=None, lease_expires_at=None,
            next_attempt_at=None)
        return Response(representation(paper, request.user, detail=True))

    @action(detail=True, methods=['get', 'post'])
    @transaction.atomic
    def generation(self, request, pk=None):
        require_author(request.user)
        paper = self.paper(pk, lock=True)
        from . import assessment_drafts as drafts
        if request.method == 'GET':
            return Response(drafts.public(paper.draft_jobs.order_by('-pk').first()))
        if paper.published_at:
            raise ValidationError({'error': 'Published papers cannot receive generated questions.'})
        self.check_revision(paper, request.data)
        if request.data.get('operation') == 'generate':
            drafts.request(paper, request.user, request.data)
        else:
            drafts.action(paper, request.user, request.data)
        return Response(representation(paper, request.user, detail=True))

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def publish(self, request, pk=None):
        require_author(request.user)
        paper = self.paper(pk, lock=True)
        if not paper.published_at:
            self.check_revision(paper, request.data)
            if paper.has_ai_questions and request.data.get('review_confirmed') is not True:
                raise ValidationError({'error': 'Confirm you reviewed every generated question, answer and marking rubric before publishing.'})
            checked = validate_paper({name: getattr(paper, name) for name in (
                'title', 'duration_minutes', 'mcq_count', 'theory_count', 'questions')})
            if len(checked['questions']) != paper.mcq_count + paper.theory_count:
                raise ValidationError({'error': 'Add all the chosen questions before publishing.'})
            paper.questions = checked['questions']
            paper.published_at = timezone.now()
            if paper.has_ai_questions:
                paper.ai_reviewed_at = timezone.now()
                paper.ai_reviewed_by = request.user
            paper.revision += 1
            paper.save()
        return Response(representation(paper, request.user, detail=True))

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def start(self, request, pk=None):
        if request.data:
            raise ValidationError({'error': 'The class head sets the questions and timing. Start with an empty request.'})
        paper = self.paper(pk, lock=True)
        if not paper.published_at:
            raise ValidationError({'error': 'Publish this paper before starting an attempt.'})
        attempt = paper.attempts.filter(user=request.user).first()
        if attempt is None:
            if paper.closed_at:
                raise ValidationError({'error': 'This assessment is closed to new attempts.'})
            attempt = QuizAttempt.objects.create(id=f'formal-{uuid.uuid4().hex}', user=request.user,
                assessment=paper, exam_type='formal', is_timed=True, duration_minutes=paper.duration_minutes,
                deadline=timezone.now() + timedelta(minutes=paper.duration_minutes),
                configuration={'mcq_count': paper.mcq_count, 'theory_count': paper.theory_count,
                               'assessment_title': paper.title},
                question_ids=[q['id'] for q in paper.questions], question_snapshots=paper.questions,
                mcq_total=paper.mcq_count, theory_total=paper.theory_count)
        from .serializers import QuizAttemptSerializer
        return Response(QuizAttemptSerializer(attempt, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def close(self, request, pk=None):
        require_author(request.user)
        paper = self.paper(pk, lock=True)
        if not paper.published_at:
            raise ValidationError({'error': 'This paper has not been published.'})
        if not paper.closed_at:
            paper.closed_at = timezone.now()
            paper.save(update_fields=['closed_at'])
        return Response(representation(paper, request.user))

    @action(detail=True, methods=['post'], url_path='release-answers')
    @transaction.atomic
    def release_answers(self, request, pk=None):
        require_author(request.user)
        paper = self.paper(pk, lock=True)
        if not paper.closed_at or paper.attempts.filter(status='in_progress', deadline__gt=timezone.now()).exists():
            raise ValidationError({'error': 'Close new entries and wait for active students to finish before releasing answers.'})
        if not paper.answers_released_at:
            paper.answers_released_at = timezone.now()
            paper.save(update_fields=['answers_released_at'])
        return Response(representation(paper, request.user))


def submit(attempt):
    """Caller holds the attempt lock. Never dispatch the legacy live-question grader."""
    if attempt.status == 'in_progress':
        responses = {r.snapshot_question_id: r for r in attempt.responses.all()}
        correct = incorrect = 0
        for q in attempt.question_snapshots:
            response = responses.get(q['id'])
            if q['question_type'] == 'mcq' and response:
                response.is_correct = response.selected_option == q['correct_option']
                response.save(update_fields=['is_correct'])
                correct += int(response.is_correct)
                incorrect += int(not response.is_correct)
        attempt.status = 'auto_submitted' if attempt.is_expired else 'submitted'
        attempt.submitted_at = timezone.now()
        attempt.mcq_score = correct
        attempt.theory_grading_pending = attempt.theory_total > 0
        attempt.theory_grading_completed = attempt.theory_total == 0
        attempt.overall_percentage = correct / attempt.mcq_total * 100 if attempt.mcq_total else 0
        points = max(0, int((correct - incorrect * .25) * 2)) if attempt.assessment_id else int(correct * 1.5)
        attempt.analysis_data = {'points_earned': points, 'grading_status': 'pending' if attempt.theory_total else 'complete',
                                'score_basis': 'mcq_only', 'theory_maximum_marks': sum(
                                    q['maximum_marks'] for q in attempt.question_snapshots if q['question_type'] == 'theory')}
        if attempt.snapshot_class_id:
            from .mock_attempts import review
            attempt.analysis_data['topic_breakdown'] = review(attempt)
        if not attempt.theory_total:
            attempt.analysis_data.update(score_basis='all_marks', total_maximum_marks=attempt.mcq_total)
        attempt.save()
        if attempt.theory_total:
            from .assessment_grading import prepare
            prepare(attempt)
        stats, _ = UserStats.objects.get_or_create(user=attempt.user)
        UserStats.objects.filter(pk=stats.pk).update(points=F('points') + points, quizzes_taken=F('quizzes_taken') + 1)
        from learning import events
        from learning.models import ActivityType
        events.record(user=attempt.user, activity=ActivityType.QUIZ_COMPLETED,
            subject=attempt.subject, block=attempt.block, sub_block=attempt.sub_block, topic=attempt.topic,
            correct_count=correct, total_count=attempt.mcq_total,
            duration_seconds=int(((min(attempt.submitted_at, attempt.deadline) if attempt.deadline else attempt.submitted_at) - attempt.started_at).total_seconds()),
            resource_type='QuizAttempt', resource_id=attempt.pk,
            metadata={'exam_type': attempt.exam_type, 'assessment_id': str(attempt.assessment_id) if attempt.assessment_id else None,
                      'theory_grading_pending': attempt.theory_grading_pending,
                      **({'theory_score': float(attempt.theory_score),
                          'theory_maximum_marks': attempt.analysis_data['theory_maximum_marks'],
                          'final_percentage': attempt.overall_percentage} if attempt.theory_grading_completed else {})})
    return {'id': attempt.pk, 'status': attempt.status, 'mcq_score': attempt.mcq_score,
            'overall_percentage': attempt.overall_percentage, 'theory_grading_pending': attempt.theory_grading_pending,
            'points_earned': attempt.analysis_data.get('points_earned', 0)}
