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
        theory_count = config.get('theory_count', 0)
        difficulty = config.get('difficulty', 'medium')
        exam_type = request.data.get('exam_type', 'practice')
        
        # Enforce formal assessment rules
        if exam_type == 'formal_assessment':
            if request.data.get('slide') or request.data.get('topic'):
                return Response({'error': 'Formal assessments can only be taken at the Block or Subject level.'}, status=status.HTTP_400_BAD_REQUEST)
            mcq_count = 100
            theory_count = 10
            request.data['is_timed'] = True
            request.data['duration_minutes'] = 180
            config['mcq_count'] = 100
            config['theory_count'] = 10
        
        user = request.user
        
        # 1. Fetch questions based on source
        mcq_qs = QuizQuestion.objects.filter(question_type='mcq')
        theory_qs = QuizQuestion.objects.filter(question_type='theory')
        
        if source == 'missed_questions':
            missed_q_ids = QuizAttemptResponse.objects.filter(
                attempt__user=user, 
                is_correct=False
            ).values_list('question_id', flat=True).distinct()
            mcq_qs = mcq_qs.filter(id__in=missed_q_ids)
            theory_qs = theory_qs.filter(id__in=missed_q_ids)
            
        elif source == 'hierarchy':
            # Filter by hierarchy
            if request.data.get('subject'):
                mcq_qs = mcq_qs.filter(subject_id=request.data['subject'])
                theory_qs = theory_qs.filter(subject_id=request.data['subject'])
            if request.data.get('block'):
                mcq_qs = mcq_qs.filter(block_id=request.data['block'])
                theory_qs = theory_qs.filter(block_id=request.data['block'])
            if request.data.get('topic'):
                mcq_qs = mcq_qs.filter(sub_block_id=request.data['topic'])
                theory_qs = theory_qs.filter(sub_block_id=request.data['topic'])
            if request.data.get('slide'):
                mcq_qs = mcq_qs.filter(source_slide_id=request.data['slide'])
                theory_qs = theory_qs.filter(source_slide_id=request.data['slide'])
                
        # 2. Limit and shuffle with fallback
        def get_with_fallback(qs, diff, count):
            primary = list(qs.filter(difficulty=diff).order_by('?')[:count])
            if len(primary) < count:
                shortfall = count - len(primary)
                secondary = list(qs.exclude(difficulty=diff).order_by('?')[:shortfall])
                primary.extend(secondary)
            return primary

        mcq_questions = get_with_fallback(mcq_qs, difficulty, mcq_count)
        theory_questions = get_with_fallback(theory_qs, difficulty, theory_count)
        questions = mcq_questions + theory_questions
        
        if not questions:
            if source == 'missed_questions':
                return Response({'error': "You don't have any missed questions to review yet! Keep practicing."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'error': "No questions found matching your selected criteria. Try selecting a broader topic or difficulty."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 3. Create the attempt
        attempt = QuizAttempt.objects.create(
            id=f"attempt-{uuid.uuid4().hex[:8]}",
            user=user,
            exam_type=request.data.get('exam_type', 'practice'),
            is_timed=request.data.get('is_timed', False),
            duration_minutes=request.data.get('duration_minutes'),
            configuration=config,
            status='in_progress',
            question_ids=[q.id for q in questions],
            mcq_total=len(mcq_questions),
            theory_total=len(theory_questions)
        )
        
        # Optional fields
        if request.data.get('subject'):
            attempt.subject_id = request.data['subject']
        if request.data.get('block'):
            attempt.block_id = request.data['block']
        if request.data.get('topic'):
            attempt.sub_block_id = request.data['topic']
        if request.data.get('slide'):
            attempt.slide_id = request.data['slide']
            
        attempt.save()

        # Use the standard QuizAttemptSerializer to return all fields including id
        serializer = QuizAttemptSerializer(attempt)
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
        attempt.submitted_at = timezone.now()
        attempt.save()
        
        # Calculate score
        from .models import QuizQuestion
        if not attempt.mcq_total and not attempt.theory_total and attempt.question_ids:
            mcq_qs = QuizQuestion.objects.filter(id__in=attempt.question_ids, question_type='mcq')
            theory_qs = QuizQuestion.objects.filter(id__in=attempt.question_ids, question_type='theory')
            total_mcq = mcq_qs.count()
            total_theory = theory_qs.count()
        else:
            total_mcq = attempt.mcq_total
            total_theory = attempt.theory_total

        responses = attempt.responses.filter(question__question_type='mcq')
        correct_mcq_count = responses.filter(is_correct=True).count()
        incorrect_mcq_count = responses.filter(is_correct=False).count()
        
        try:
            from learning.selection import mark_answered, mark_served
            if attempt.question_ids:
                mark_served(request.user, attempt.question_ids)
            for response in responses:
                mark_answered(request.user, str(response.question_id), response.is_correct)
        except Exception as e:
            print("Failed to record question exposure:", e)
        
        percentage = (correct_mcq_count / total_mcq * 100) if total_mcq > 0 else 0
        attempt.mcq_score = correct_mcq_count
        attempt.mcq_total = total_mcq
        attempt.theory_total = total_theory
        attempt.overall_percentage = percentage
        attempt.save()
        
        # Calculate points
        points_earned = 0
        try:
            stats = request.user.stats
            
            # Points calculation base
            base_points = correct_mcq_count
            
            if attempt.exam_type == 'formal':
                base_points -= (incorrect_mcq_count * 0.25)
                multiplier = 2.0
            elif attempt.exam_type == 'mock':
                multiplier = 1.5
            else:
                multiplier = 1.0
                
            points_earned = max(0, int(base_points * multiplier))
            stats.points += points_earned
            stats.quizzes_taken += 1
            stats.save(update_fields=['points', 'quizzes_taken'])
        except Exception as e:
            print("Could not update user stats", e)
            
        if attempt.exam_type in ['formal', 'mock']:
            from curriculum.tasks import analyze_quiz_attempt_task
            analyze_quiz_attempt_task.delay(attempt.id)
            
        try:
            from learning import events
            from learning.models import ActivityType
            
            duration = 0
            if getattr(attempt, 'started_at', None) and getattr(attempt, 'submitted_at', None):
                duration = int((attempt.submitted_at - attempt.started_at).total_seconds())
                
            events.record(
                user=request.user,
                activity=ActivityType.QUIZ_COMPLETED,
                subject=getattr(attempt, 'subject', None),
                correct_count=correct_mcq_count,
                total_count=total_mcq,
                duration_seconds=duration,
                resource_type='QuizAttempt',
                resource_id=str(attempt.id),
                metadata={'exam_type': attempt.exam_type}
            )
        except Exception as e:
            print("Failed to record learning event:", e)
        
        return Response({
            'status': 'submitted',
            'mcq_score': correct_mcq_count,
            'overall_percentage': percentage,
            'points_earned': points_earned
        })

    @action(detail=True, methods=['get'])
    def result(self, request, pk=None):
        attempt = self.get_object()
        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def missed(self, request, pk=None):
        attempt = self.get_object()
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
                    'question_text': q.get('text', ''),
                    'question_type': q.get('question_type', 'mcq'),
                    'selected_option': r.get('selected_option'),
                    'student_answer': r.get('text_answer'),
                    'correct_option': q.get('correct_option'),
                    'correct_answer': q.get('correct_answer'),
                    'explanation': q.get('explanation'),
                    'topic': q.get('topic')
                })
        return Response(data)
