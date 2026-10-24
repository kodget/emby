from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from . import practice_attempts
from .models import QuizAttempt, QuizQuestion, QuizAttemptResponse
from .serializers import QuizAttemptSerializer, QuizAttemptCreateSerializer
from .class_access import visible, visible_attempts, ClassContentReferences

class QuizAttemptViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing quiz attempts.
    """
    serializer_class = QuizAttemptSerializer
    permission_classes = [IsAuthenticated, ClassContentReferences]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return visible_attempts(self.request.user).order_by('-started_at', '-pk')

    def get_serializer_class(self):
        if self.action == 'create':
            return QuizAttemptCreateSerializer
        return QuizAttemptSerializer

    def create(self, request, *args, **kwargs):
        if request.data.get('exam_type') in ('formal', 'formal_assessment'):
            return Response({'error': 'Choose a published assessment from your class head.',
                             'code': 'published_assessment_required'}, status=400)
        if request.data.get('exam_type', 'practice') == 'practice':
            attempt = practice_attempts.create(request.user, request.data)
            return Response(QuizAttemptSerializer(attempt, context={'request': request}).data, status=201)
        if request.data.get('exam_type') == 'mock':
            from .mock_attempts import create
            attempt = create(request.user, request.data)
            return Response(QuizAttemptSerializer(attempt, context={'request': request}).data, status=201)
        return Response({'error': 'Choose practice, mock or a published class assessment.'}, status=400)

    @action(detail=False, methods=['get'], url_path='mock-options')
    def mock_options(self, request):
        from .mock_attempts import availability
        return Response(availability(request.user, request.query_params))

    @action(detail=False, methods=['get'], url_path='practice-options')
    def practice_options(self, request):
        return Response(practice_attempts.options(request.user, request.query_params.get('slide'),
                        request.query_params.get('question_source', 'hierarchy')))

    @action(detail=True, methods=['post'], url_path='answer')
    @transaction.atomic
    def answer(self, request, pk=None):
        attempt = self.get_object()
        attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        from .attempt_answers import save_answer
        save_answer(attempt, request.data)
        return Response({'status': 'Answer recorded'})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def flag(self, request, pk=None):
        attempt = self.get_object()
        attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        from .assessment_history import require_current
        require_current(attempt)
        question_id = request.data.get('question_id')
        if attempt.status != 'in_progress' or attempt.is_expired or question_id not in attempt.question_ids:
            return Response({'error': 'Choose a question in an active attempt.'}, status=400)
        if not question_id:
            return Response({'error': 'Missing question_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        flagged = request.data.get('is_flagged', True)
        if type(flagged) is not bool:
            return Response({'error': 'is_flagged must be true or false.'}, status=400)
        if flagged and question_id not in attempt.flagged_questions:
            attempt.flagged_questions.append(question_id)
        elif not flagged and question_id in attempt.flagged_questions:
            attempt.flagged_questions.remove(question_id)
        attempt.save(update_fields=['flagged_questions'])
            
        return Response({'status': 'Question flagged'})

    @action(detail=True, methods=['post'])
    def auto_submit(self, request, pk=None):
        return self.submit(request, pk)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        attempt = self.get_object()
        attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.assessment_id or attempt.snapshot_class_id:
            from .formal_assessments import submit
            return Response(submit(attempt))
        if attempt.question_snapshots:
            return Response(practice_attempts.submit(attempt))
        from .assessment_history import require_current
        require_current(attempt)

    @action(detail=True, methods=['get'])
    def result(self, request, pk=None):
        attempt = self.get_object()
        if attempt.question_snapshots and attempt.status == 'in_progress':
            return Response({'error': 'Submit the attempt before viewing its result.'}, status=400)
        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='retry-grading')
    def retry_grading(self, request, pk=None):
        from .assessment_grading import retry, public_status
        attempt = self.get_object()
        from .assessment_history import require_current
        require_current(attempt)
        retry(attempt)
        return Response({'grading': public_status(attempt)}, status=202)

    @action(detail=True, methods=['get'])
    def missed(self, request, pk=None):
        attempt = self.get_object()
        from .assessment_history import is_historical
        if is_historical(attempt):
            return Response({'missed_questions': [], 'total_missed': None,
                             'historical_read_only': True, 'answers_released': False})
        if attempt.assessment_id and not attempt.assessment.answers_released_at:
            return Response({'missed_questions': [], 'total_missed': None,
                             'answers_released': False})
        if attempt.status == 'in_progress':
            return Response({'error': 'Submit the attempt before reviewing answers.'}, status=400)
        if attempt.question_snapshots:
            responses = {r.snapshot_question_id or r.question_id: r for r in attempt.responses.all()}
            data = [dict(q, selected_option=responses[q['id']].selected_option if q['id'] in responses else None)
                    for q in practice_attempts.public_questions(attempt)
                    if q['question_type'] == 'mcq'
                    and (q['id'] not in responses or not responses[q['id']].is_correct)]
            return Response({'missed_questions': data, 'total_missed': len(data)})
        # Return all responses where MCQ is incorrect or theory was graded < max
        # For simplicity in this endpoint, mostly returning incorrect MCQs for now.
        from curriculum.serializers import QuizAttemptResponseSerializer
        missed_responses = attempt.responses.filter(is_correct=False)
        serializer = QuizAttemptResponseSerializer(missed_responses, many=True)
        # Format it exactly as the frontend expects
        data = []
        for r in serializer.data:
            q = r.get('question')
            if q:
                data.append({
                    'id': r['id'],
                    'question_text': q.get('question_text', ''),
                    'question_type': q.get('question_type', 'mcq'),
                    'selected_option': r.get('selected_option'),
                    'student_answer': r.get('text_answer'),
                    'correct_option': q.get('correct_option'),
                    'correct_answer': q.get('model_answer'),
                    'explanation': q.get('explanation'),
                    'topic': q.get('topic_name')
                })
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        from .assessment_history import require_current
        attempt = self.get_object()
        require_current(attempt)
        if attempt.assessment_id:
            return Response({'error': 'Formal attempts are permanent and cannot be deleted or retaken.'}, status=400)
        return super().destroy(request, *args, **kwargs)
