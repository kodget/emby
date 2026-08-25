from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import QuizAttempt, QuizQuestion, QuizAttemptResponse, UserProgress, Subject, Topic
from .serializers import QuizAttemptSerializer, QuizAttemptCreateSerializer
from django.db.models import Q
import uuid

class QuizAttemptViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing quiz attempts.
    """
    serializer_class = QuizAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return QuizAttemptCreateSerializer
        return QuizAttemptSerializer

    def create(self, request, *args, **kwargs):
        # Determine question source
        config = request.data.get('configuration', {})
        source = config.get('question_source', 'hierarchy')
        mcq_count = config.get('mcq_count', 5)
        difficulty = config.get('difficulty', 'medium')
        
        user = request.user
        
        # 1. Fetch questions based on source
        questions_qs = QuizQuestion.objects.filter(question_type='mcq', difficulty=difficulty)
        
        if source == 'missed_questions':
            # Get missed questions
            # This requires checking where the user previously got questions wrong
            # Actually, simpler: find questions where they answered incorrectly
            missed_q_ids = QuizAttemptResponse.objects.filter(
                attempt__user=user, 
                is_correct=False
            ).values_list('question_id', flat=True).distinct()
            questions_qs = QuizQuestion.objects.filter(id__in=missed_q_ids, question_type='mcq')
            
        elif source == 'hierarchy':
            # Filter by hierarchy
            if request.data.get('subject'):
                questions_qs = questions_qs.filter(subject_id=request.data['subject'])
            if request.data.get('block'):
                questions_qs = questions_qs.filter(topic__sub_block__block_id=request.data['block'])
            if request.data.get('topic'):
                questions_qs = questions_qs.filter(topic_id=request.data['topic'])
                
        # 2. Limit and shuffle
        questions = list(questions_qs.order_by('?')[:mcq_count])
        
        if not questions and source == 'missed_questions':
            return Response({'error': "You don't have any missed questions to review yet! Keep practicing."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 3. Create the attempt
        attempt = QuizAttempt.objects.create(
            id=f"attempt-{uuid.uuid4().hex[:8]}",
            user=user,
            exam_type=request.data.get('exam_type', 'practice'),
            is_timed=request.data.get('is_timed', False),
            duration_minutes=request.data.get('duration_minutes'),
            configuration=config,
            status='in_progress',
            question_ids=[q.id for q in questions]
        )
        
        # Optional fields
        if request.data.get('subject'):
            attempt.subject_id = request.data['subject']
            
        attempt.save()

        serializer = self.get_serializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        attempt = self.get_object()
        if attempt.status != 'in_progress':
            return Response({'error': 'Attempt is not in progress'}, status=status.HTTP_400_BAD_REQUEST)
            
        question_id = request.data.get('question_id')
        selected_option = request.data.get('selected_option')
        
        if not question_id or not selected_option:
            return Response({'error': 'Missing data'}, status=status.HTTP_400_BAD_REQUEST)
            
        question = QuizQuestion.objects.get(id=question_id)
        
        # Determine correct
        is_correct = (selected_option == question.correct_option)
        
        response, created = QuizAttemptResponse.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_option': selected_option,
                'is_correct': is_correct
            }
        )
        
        return Response({'status': 'Answer recorded'})

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        if attempt.status != 'in_progress':
            return Response({'error': 'Attempt is not in progress'}, status=status.HTTP_400_BAD_REQUEST)
            
        attempt.status = 'submitted'
        attempt.end_time = timezone.now()
        attempt.save()
        
        # Calculate score
        responses = attempt.responses.filter(question__question_type='mcq')
        mcq_score = responses.filter(is_correct=True).count()
        total_mcq = attempt.configuration.get('mcq_count', 0)
        
        percentage = (mcq_score / total_mcq * 100) if total_mcq > 0 else 0
        attempt.mcq_score = mcq_score
        attempt.overall_percentage = percentage
        attempt.save()
        
        return Response({
            'status': 'submitted',
            'mcq_score': mcq_score,
            'overall_percentage': percentage
        })

    @action(detail=True, methods=['get'])
    def result(self, request, pk=None):
        attempt = self.get_object()
        serializer = self.get_serializer(attempt)
        return Response(serializer.data)
