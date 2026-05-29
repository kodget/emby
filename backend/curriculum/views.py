from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Subject, Block, Topic, Section, Slide, Material, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, PostLike, UpcomingTest, DailyStudySession,
    QuizQuestion, Quiz, QuizAnswer, SlideContent, SlideDeck, SlidePage
)
from .serializers import (
    SubjectSerializer, BlockSerializer, TopicSerializer, SectionSerializer, SlideSerializer, MaterialSerializer,
    UserProgressSerializer, ScheduleItemSerializer, UserStatsSerializer,
    CommunityPostSerializer, PostCommentSerializer, UpcomingTestSerializer,
    QuizQuestionSerializer, QuizSerializer, QuizAnswerSerializer,
    SlideDeckSerializer, SlideDeckListSerializer, SlidePageSerializer
)


# -------------------------
# CURRICULUM VIEWS
# -------------------------
class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """List all subjects"""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [AllowAny]


class BlockViewSet(viewsets.ReadOnlyModelViewSet):
    """List blocks, optionally filtered by subject"""
    queryset = Block.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Block.objects.all()
        subject_id = self.request.query_params.get('subject', None)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        return queryset


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    """List topics, optionally filtered by block"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Topic.objects.all()
        block_id = self.request.query_params.get('block', None)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        return queryset


class SectionViewSet(viewsets.ReadOnlyModelViewSet):
    """List sections, optionally filtered by topic or block"""
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Section.objects.all()
        topic_id = self.request.query_params.get('topic', None)
        block_id = self.request.query_params.get('block', None)
        
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        elif block_id:
            queryset = queryset.filter(block_id=block_id)
        
        return queryset


class SlideViewSet(viewsets.ModelViewSet):
    """CRUD operations for slides (PDF/PPT/DOCX only)"""
    queryset = Slide.objects.all()
    serializer_class = SlideSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Slide.objects.all()
        subject_id = self.request.query_params.get('subject', None)
        block_id = self.request.query_params.get('block', None)
        topic_id = self.request.query_params.get('topic', None)
        section_id = self.request.query_params.get('section', None)
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        
        return queryset
    
    def perform_create(self, serializer):
        # Check if user can upload (class_head or material_uploader)
        profile = self.request.user.profile
        if profile.role not in ['class_head', 'material_uploader']:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only class heads and material uploaders can upload slides")
        
        slide = serializer.save(uploaded_by=self.request.user)
        
        # The slide will be automatically processed by the Celery signal
        print(f"Slide {slide.id} created successfully. Processing will start automatically via Celery.")


class MaterialViewSet(viewsets.ModelViewSet):
    """CRUD operations for materials (videos, images, PDFs, past questions, etc.)"""
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Material.objects.all()
        subject_id = self.request.query_params.get('subject', None)
        block_id = self.request.query_params.get('block', None)
        topic_id = self.request.query_params.get('topic', None)
        section_id = self.request.query_params.get('section', None)
        material_type = self.request.query_params.get('type', None)
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        if material_type:
            queryset = queryset.filter(material_type=material_type)
        
        return queryset
    
    def perform_create(self, serializer):
        # Check if user can upload (class_head or material_uploader)
        profile = self.request.user.profile
        if profile.role not in ['class_head', 'material_uploader']:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only class heads and material uploaders can upload materials")
        
        serializer.save(uploaded_by=self.request.user)


# -------------------------
# PROGRESS VIEWS
# -------------------------
class UserProgressViewSet(viewsets.ModelViewSet):
    """Track user progress on slides"""
    serializer_class = UserProgressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserProgress.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recently accessed slides"""
        recent_progress = self.get_queryset().order_by('-last_accessed')[:5]
        serializer = self.get_serializer(recent_progress, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_progress(self, request):
        """Update progress for a slide"""
        slide_id = request.data.get('slide_id')
        current_page = request.data.get('current_page', 1)
        total_pages = request.data.get('total_pages', 0)
        time_spent = request.data.get('time_spent_minutes', 0)
        
        progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            slide_id=slide_id,
            defaults={'total_pages': total_pages}
        )
        
        progress.current_page = current_page
        progress.total_pages = total_pages
        progress.time_spent_minutes += time_spent
        progress.completed = current_page >= total_pages
        progress.save()
        
        # Update daily study session
        if time_spent > 0:
            today = date.today()
            session, _ = DailyStudySession.objects.get_or_create(
                user=request.user,
                date=today
            )
            session.minutes_studied += time_spent
            session.sessions_count += 1
            session.save()
            
            # Update user stats
            stats, _ = UserStats.objects.get_or_create(user=request.user)
            stats.total_study_minutes += time_spent
            stats.save()
        
        serializer = self.get_serializer(progress)
        return Response(serializer.data)


# -------------------------
# SCHEDULE VIEWS
# -------------------------
class ScheduleItemViewSet(viewsets.ModelViewSet):
    """CRUD operations for schedule items"""
    serializer_class = ScheduleItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ScheduleItem.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's schedule"""
        today = date.today()
        items = self.get_queryset().filter(scheduled_date=today)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming schedule (next 7 days)"""
        today = date.today()
        next_week = today + timedelta(days=7)
        items = self.get_queryset().filter(
            scheduled_date__gte=today,
            scheduled_date__lte=next_week
        )
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark schedule item as complete"""
        item = self.get_object()
        item.completed = True
        item.completed_at = timezone.now()
        item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def uncomplete(self, request, pk=None):
        """Mark schedule item as incomplete"""
        item = self.get_object()
        item.completed = False
        item.completed_at = None
        item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)


# -------------------------
# GAMIFICATION VIEWS
# -------------------------
class UserStatsViewSet(viewsets.ModelViewSet):
    """User statistics and gamification"""
    serializer_class = UserStatsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserStats.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's stats"""
        stats, created = UserStats.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get leaderboard (top users by points)"""
        limit = int(request.query_params.get('limit', 10))
        top_users = UserStats.objects.filter(
            public_rank=True
        ).order_by('-points')[:limit]
        
        serializer = self.get_serializer(top_users, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def award_points(self, request):
        """Award points to user"""
        points = request.data.get('points', 0)
        reason = request.data.get('reason', '')
        
        stats, created = UserStats.objects.get_or_create(user=request.user)
        stats.points += points
        stats.save()
        
        # Update rank based on points
        all_stats = UserStats.objects.order_by('-points')
        for idx, stat in enumerate(all_stats, 1):
            stat.rank = idx
            stat.save(update_fields=['rank'])
        
        serializer = self.get_serializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_streak(self, request):
        """Update user's streak"""
        stats, created = UserStats.objects.get_or_create(user=request.user)
        today = date.today()
        
        if stats.last_activity_date:
            days_diff = (today - stats.last_activity_date).days
            
            if days_diff == 0:
                # Same day, no change
                pass
            elif days_diff == 1:
                # Consecutive day, increment streak
                stats.current_streak += 1
                if stats.current_streak > stats.longest_streak:
                    stats.longest_streak = stats.current_streak
            else:
                # Streak broken
                stats.current_streak = 1
        else:
            # First activity
            stats.current_streak = 1
            stats.longest_streak = 1
        
        stats.last_activity_date = today
        stats.save()
        
        # Update profile streak
        if hasattr(request.user, 'profile'):
            request.user.profile.streak = stats.current_streak
            request.user.profile.save()
        
        serializer = self.get_serializer(stats)
        return Response(serializer.data)


# -------------------------
# COMMUNITY VIEWS
# -------------------------
class CommunityPostViewSet(viewsets.ModelViewSet):
    """Community posts and feed"""
    serializer_class = CommunityPostSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CommunityPost.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def update(self, request, *args, **kwargs):
        """Update post - only owner can edit"""
        post = self.get_object()
        
        if post.user != request.user:
            return Response(
                {'error': 'You can only edit your own posts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete post - only owner can delete"""
        post = self.get_object()
        
        if post.user != request.user:
            return Response(
                {'error': 'You can only delete your own posts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like a post"""
        post = self.get_object()
        like, created = PostLike.objects.get_or_create(
            user=request.user,
            post=post
        )
        
        if created:
            post.likes_count += 1
            post.save()
        
        return Response({'liked': True, 'likes_count': post.likes_count})
    
    @action(detail=True, methods=['post'])
    def unlike(self, request, pk=None):
        """Unlike a post"""
        post = self.get_object()
        deleted = PostLike.objects.filter(
            user=request.user,
            post=post
        ).delete()
        
        if deleted[0] > 0:
            post.likes_count = max(0, post.likes_count - 1)
            post.save()
        
        return Response({'liked': False, 'likes_count': post.likes_count})
    
    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post"""
        post = self.get_object()
        content = request.data.get('content', '')
        
        if not content:
            return Response(
                {'error': 'Content required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = PostComment.objects.create(
            user=request.user,
            post=post,
            content=content
        )
        
        post.comments_count += 1
        post.save()
        
        serializer = PostCommentSerializer(comment)
        return Response(serializer.data)


# -------------------------
# TESTS VIEWS
# -------------------------
class UpcomingTestViewSet(viewsets.ModelViewSet):
    """Upcoming tests and exams"""
    serializer_class = UpcomingTestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UpcomingTest.objects.filter(test_date__gte=date.today())
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_slide_content(request, slide_id):
    """Get rendered slide pages as images."""
    try:
        slide = Slide.objects.get(id=slide_id)
    except Slide.DoesNotExist:
        return Response({'error': 'Slide not found'}, status=status.HTTP_404_NOT_FOUND)

    slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
    
    # Return cached if available
    if slide_content.is_extracted and slide_content.content_data.get('pages'):
        return Response({
            'slide_id': slide.id,
            'title': slide.title,
            'total_pages': slide_content.content_data.get('total_pages', 0),
            'pages': slide_content.content_data.get('pages', []),
        })

    # Render on-demand if not cached
    file_url = slide.get_file_url
    if not file_url:
        return Response({'error': 'Slide has no file URL'}, status=status.HTTP_400_BAD_REQUEST)

    from .slide_renderer import render_slide_pages
    try:
        content = render_slide_pages(file_url, slide.file_type, slide.id)
        
        slide_content.content_data = content
        slide_content.is_extracted = content['total_pages'] > 0
        slide_content.extraction_error = ''
        slide_content.extracted_at = timezone.now()
        slide_content.save()
        
        if content['total_pages'] > 0:
            Slide.objects.filter(id=slide.id).update(page_count=content['total_pages'])
        
        return Response({
            'slide_id': slide.id,
            'title': slide.title,
            'total_pages': content['total_pages'],
            'pages': content['pages'],
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Rendering failed: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -------------------------
# QUIZ SYSTEM
# -------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_quiz(request):
    """Generate a quiz based on subject/block/topic"""
    user = request.user
    profile = user.profile
    
    quiz_type = request.data.get('quiz_type', 'mcq')  # mcq or theory
    subject_id = request.data.get('subject')
    block_id = request.data.get('block')
    topic_id = request.data.get('topic')
    num_questions = int(request.data.get('num_questions', 10))
    
    # Check premium limits
    if quiz_type == 'theory' and not profile.is_premium:
        return Response(
            {'error': 'Theory questions are only available for Premium users. Upgrade to access up to 10 theory questions.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if quiz_type == 'mcq':
        if not profile.is_premium and num_questions > 10:
            return Response(
                {'error': 'Free users can access up to 10 MCQ questions. Upgrade to Premium for up to 100 questions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        if profile.is_premium and num_questions > 100:
            num_questions = 100
    else:  # theory
        if num_questions > 10:
            num_questions = 10
    
    # Build query filter
    filters = Q(question_type=quiz_type)
    if subject_id:
        filters &= Q(subject_id=subject_id)
    if block_id:
        filters &= Q(block_id=block_id)
    if topic_id:
        filters &= Q(topic_id=topic_id)
    
    # Get questions
    questions = list(QuizQuestion.objects.filter(filters).order_by('?')[:num_questions])
    
    if not questions:
        return Response(
            {'error': 'No questions available for this selection. Try a different topic or wait for more questions to be added.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create quiz
    import uuid
    quiz = Quiz.objects.create(
        id=str(uuid.uuid4())[:8],
        user=user,
        quiz_type=quiz_type,
        subject_id=subject_id,
        block_id=block_id,
        topic_id=topic_id,
        total_questions=len(questions)
    )
    quiz.questions.set(questions)
    
    serializer = QuizSerializer(quiz)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz_answer(request):
    """Submit an answer to a quiz question"""
    quiz_id = request.data.get('quiz_id')
    question_id = request.data.get('question_id')
    selected_option = request.data.get('selected_option', '')  # For MCQ
    text_answer = request.data.get('text_answer', '')  # For Theory
    time_taken = int(request.data.get('time_taken_seconds', 0))
    
    try:
        quiz = Quiz.objects.get(id=quiz_id, user=request.user)
        question = QuizQuestion.objects.get(id=question_id)
        
        # Check if already answered
        answer, created = QuizAnswer.objects.get_or_create(
            quiz=quiz,
            question=question,
            defaults={
                'selected_option': selected_option,
                'text_answer': text_answer,
                'time_taken_seconds': time_taken
            }
        )
        
        if not created:
            # Update existing answer
            answer.selected_option = selected_option
            answer.text_answer = text_answer
            answer.time_taken_seconds = time_taken
        
        # Check correctness for MCQ
        if quiz.quiz_type == 'mcq':
            answer.is_correct = (selected_option.upper() == question.correct_option.upper())

        # AI grading for theory answers
        if quiz.quiz_type == 'theory' and text_answer.strip():
            try:
                from .ai_service import grade_theory_answer
                grading = grade_theory_answer(
                    question_text=question.question_text,
                    model_answer=question.model_answer,
                    student_answer=text_answer,
                )
                answer.ai_score = grading.get('score', 0)
                answer.ai_feedback = grading.get('feedback', '')
            except Exception as e:
                print(f"Theory grading failed: {e}")

        answer.save()
        
        serializer = QuizAnswerSerializer(answer)
        return Response(serializer.data)
        
    except Quiz.DoesNotExist:
        return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)
    except QuizQuestion.DoesNotExist:
        return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_quiz(request, quiz_id):
    """Mark quiz as complete and calculate score"""
    try:
        quiz = Quiz.objects.get(id=quiz_id, user=request.user)
        
        if quiz.completed:
            return Response({'error': 'Quiz already completed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate score for MCQ
        if quiz.quiz_type == 'mcq':
            correct_answers = quiz.answers.filter(is_correct=True).count()
            quiz.score = correct_answers
        else:
            # For theory, score is average of AI scores
            scores = quiz.answers.filter(ai_score__isnull=False).values_list('ai_score', flat=True)
            if scores:
                quiz.score = sum(scores) // len(scores)
        
        quiz.completed = True
        quiz.completed_at = timezone.now()
        quiz.save()
        
        # Update user stats
        stats, _ = UserStats.objects.get_or_create(user=request.user)
        stats.quizzes_taken += 1
        stats.save()
        
        # Award points (2 per correct answer)
        points = quiz.score * 2
        stats.points += points
        stats.save()
        
        serializer = QuizSerializer(quiz)
        return Response(serializer.data)
        
    except Quiz.DoesNotExist:
        return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_quiz_history(request):
    """Get user's quiz history"""
    quizzes = Quiz.objects.filter(user=request.user, completed=True).order_by('-completed_at')[:20]
    serializer = QuizSerializer(quizzes, many=True)
    return Response(serializer.data)


# -------------------------
# STUDY TIME TRACKING
# -------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_weekly_study_data(request):
    """Get study time data for the past 7 days"""
    today = date.today()
    week_ago = today - timedelta(days=6)
    
    # Get all sessions for the past 7 days
    sessions = DailyStudySession.objects.filter(
        user=request.user,
        date__gte=week_ago,
        date__lte=today
    ).order_by('date')
    
    # Create a dict with all 7 days
    week_data = {}
    for i in range(7):
        day = week_ago + timedelta(days=i)
        week_data[day] = {
            'day': day.strftime('%a'),
            'date': day.isoformat(),
            'minutes': 0,
            'sessions': 0
        }
    
    # Fill in actual data
    for session in sessions:
        week_data[session.date]['minutes'] = session.minutes_studied
        week_data[session.date]['sessions'] = session.sessions_count
    
    # Convert to list and calculate total
    data_list = list(week_data.values())
    total_minutes = sum(d['minutes'] for d in data_list)
    
    return Response({
        'week_data': data_list,
        'total_minutes': total_minutes,
        'total_hours': total_minutes // 60,
        'remaining_minutes': total_minutes % 60
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_study_time(request):
    """Manually log study time"""
    minutes = request.data.get('minutes', 0)
    study_date = request.data.get('date', date.today().isoformat())
    
    if minutes <= 0:
        return Response(
            {'error': 'Minutes must be greater than 0'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        study_date = date.fromisoformat(study_date)
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update daily session
    session, _ = DailyStudySession.objects.get_or_create(
        user=request.user,
        date=study_date
    )
    session.minutes_studied += minutes
    session.sessions_count += 1
    session.save()
    
    # Update user stats
    stats, _ = UserStats.objects.get_or_create(user=request.user)
    stats.total_study_minutes += minutes
    stats.save()
    
    return Response({
        'message': 'Study time logged successfully',
        'total_today': session.minutes_studied,
        'total_overall': stats.total_study_minutes
    })


# -------------------------
# AI LEARNING SUPPORT
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_tutor(request):
    """
    AI tutor chat endpoint.
    Body: {message, slide_id (optional), history (optional list of {role, content})}
    """
    from .ai_service import ai_tutor_chat

    message = request.data.get('message', '').strip()
    if not message:
        return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

    slide_context = ''
    slide_id = request.data.get('slide_id')
    if slide_id:
        try:
            slide = Slide.objects.get(id=slide_id)
            sc = SlideContent.objects.filter(slide=slide, is_extracted=True).first()
            if sc and sc.content_data.get('pages'):
                # Extract text from text_blocks for context
                texts = []
                for p in sc.content_data['pages']:
                    page_text = []
                    for block in p.get('text_blocks', []):
                        page_text.append(block.get('text', ''))
                    texts.append(' '.join(page_text))
                slide_context = '\n\n'.join(texts)[:8000]
        except Slide.DoesNotExist:
            pass

    history = request.data.get('history', [])
    result = ai_tutor_chat(message, slide_text_context=slide_context, conversation_history=history)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggest_videos(request, slide_id):
    """AI suggests 3 best related videos for a slide."""
    try:
        slide = Slide.objects.get(id=slide_id)
    except Slide.DoesNotExist:
        return Response({'error': 'Slide not found'}, status=status.HTTP_404_NOT_FOUND)
    
    from .ai_service import suggest_related_videos
    
    # Get slide context
    slide_info = {
        'title': slide.title,
        'subject': slide.subject_name,
        'block': slide.block_name,
        'topic': slide.topic_name,
    }


# -------------------------
# SLIDE DECK VIEWS
# -------------------------
class SlideDeckViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing slide decks (uploaded documents).
    
    Supports:
    - List all decks
    - Retrieve a specific deck with all its pages
    - Create a new deck (upload document)
    - Delete a deck
    """
    serializer_class = SlideDeckSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Get decks uploaded by current user"""
        return SlideDeck.objects.filter(
            uploaded_by=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return SlideDeckListSerializer
        return SlideDeckSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Upload a new document for conversion.
        
        Expected request:
        - MultipartForm with 'file' and 'title' fields
        
        Only 'class_head' and 'material_uploader' roles can upload decks.
        """
        # ========== ROLE-BASED ACCESS CONTROL ==========
        try:
            profile = request.user.profile
            if profile.role not in ['class_head', 'material_uploader']:
                return Response(
                    {'error': f'Only class heads and material uploaders can upload documents. Your role: {profile.role}'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except AttributeError:
            return Response(
                {'error': 'User profile not found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        file_obj = request.FILES.get('file')
        title = request.data.get('title', 'Untitled')
        
        if not file_obj:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Detect file type
        from .services.converter import FileTypeDetector
        file_type = FileTypeDetector.detect_file_type(file_obj.name)
        
        if not file_type:
            return Response(
                {'error': f'Unsupported file type. Supported: pdf, pptx, ppt, docx'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create SlideDeck record
        import uuid
        deck_id = f"deck_{str(uuid.uuid4())[:8]}"
        
        # Upload to Cloudinary via model
        try:
            from cloudinary.uploader import upload_large
            
            # Read file content
            file_obj.seek(0)
            file_content = file_obj.read()
            
            # Upload to Cloudinary
            result = upload_large(
                file_content,
                resource_type='auto',
                public_id=f"{deck_id}_{file_obj.name}",
                folder='slide_uploads'
            )
            
            deck = SlideDeck.objects.create(
                id=deck_id,
                title=title,
                file_type=file_type,
                file_size=file_obj.size,
                original_file=result['public_id'],
                uploaded_by=request.user,
                processing_status='pending'
            )
            
            # Trigger async processing (will implement with Celery later)
            # For now, will be synchronous
            self._process_deck_async(deck)
            
            serializer = self.get_serializer(deck)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _process_deck_async(self, deck):
        """Process deck (convert and render)"""
        try:
            from .services.converter import SlideConverter, FileTypeDetector
            import os
            
            # Update status to processing
            deck.processing_status = 'processing'
            deck.save()
            
            # Get file from Cloudinary
            from cloudinary.utils import cloudinary_url
            file_url, _ = cloudinary_url(deck.original_file, resource_type='auto')
            
            # Download file temporarily
            import requests
            import tempfile
            
            response = requests.get(file_url)
            if response.status_code != 200:
                raise Exception("Failed to download file from Cloudinary")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{deck.file_type}") as tmp_file:
                tmp_file.write(response.content)
                tmp_file_path = tmp_file.name
            
            try:
                # Convert document
                success, result = SlideConverter.convert_document(
                    tmp_file_path,
                    deck.file_type,
                    deck.id
                )
                
                if not success:
                    raise Exception(result.get('error', 'Unknown error'))
                
                # Save rendered pages to database
                for page_number, image_path in enumerate(result['slide_images'], 1):
                    try:
                        # Upload image to Cloudinary
                        from cloudinary.uploader import upload
                        
                        img_result = upload(
                            image_path,
                            resource_type='image',
                            public_id=f"{deck.id}_slide_{page_number:04d}",
                            folder=f'slide_renders/{deck.id}'
                        )
                        
                        # Get image dimensions
                        from PIL import Image
                        img = Image.open(image_path)
                        width, height = img.size
                        
                        # Create SlidePage record
                        SlidePage.objects.create(
                            deck=deck,
                            slide_number=page_number,
                            image=img_result['public_id'],
                            width=width,
                            height=height
                        )
                    
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to save page {page_number}: {e}")
                
                # Update deck with completion status
                deck.page_count = result['page_count']
                deck.processing_status = 'completed'
                deck.save()
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Deck processing error: {e}")
            
            deck.processing_status = 'failed'
            deck.processing_error = str(e)
            deck.save()
    
    @action(detail=True, methods=['get'])
    def pages(self, request, id=None):
        """Get all pages of a slide deck"""
        deck = self.get_object()
        pages = deck.pages.all().order_by('slide_number')
        serializer = SlidePageSerializer(pages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def page(self, request, id=None):
        """Get a specific page of a slide deck"""
        deck = self.get_object()
        page_number = request.query_params.get('page', 1)
        
        try:
            page_number = int(page_number)
        except ValueError:
            return Response(
                {'error': 'page must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            page = deck.pages.get(slide_number=page_number)
            serializer = SlidePageSerializer(page)
            return Response(serializer.data)
        except SlidePage.DoesNotExist:
            return Response(
                {'error': f'Page {page_number} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['delete'])
    def delete_deck(self, request, id=None):
        """Delete a slide deck and all its pages"""
        deck = self.get_object()
        deck_id = deck.id
        
        # ========== PERMISSION CHECK ==========
        # User must be the uploader OR have class_head/material_uploader role
        is_uploader = deck.uploaded_by == request.user
        try:
            profile = request.user.profile
            can_delete = is_uploader or profile.role in ['class_head', 'material_uploader']
        except AttributeError:
            can_delete = False
        
        if not can_delete:
            return Response(
                {'error': 'You do not have permission to delete this deck'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete from Cloudinary
        try:
            from cloudinary.api import delete_resources_by_prefix
            delete_resources_by_prefix(f'slide_renders/{deck_id}')
            delete_resources_by_prefix(f'slide_uploads/{deck_id}')
        except:
            pass
        
        # Delete from database (pages auto-deleted via CASCADE)
        deck.delete()
        
        return Response(
            {'message': f'Deck {deck_id} deleted'},
            status=status.HTTP_204_NO_CONTENT
        )


# ===== Rest of the suggest_videos function (incomplete in original file) =====
    # videos = suggest_related_videos(slide_info)
    # return Response({'videos': videos})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_questions_from_slide_view(request, slide_id):
    """
    Auto-generate MCQ and theory questions from a slide.
    Body: {num_mcq (default 5), num_theory (default 3)}
    Only class heads and material uploaders can trigger this.
    """
    profile = request.user.profile
    if profile.role not in ['class_head', 'material_uploader']:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    try:
        slide = Slide.objects.get(id=slide_id)
    except Slide.DoesNotExist:
        return Response({'error': 'Slide not found'}, status=status.HTTP_404_NOT_FOUND)

    from .question_generator import generate_questions_from_slide
    num_mcq = int(request.data.get('num_mcq', 5))
    num_theory = int(request.data.get('num_theory', 3))

    result = generate_questions_from_slide(slide, num_mcq=num_mcq, num_theory=num_theory)
    return Response(result, status=status.HTTP_201_CREATED if not result.get('error') else status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_study_recommendations(request):
    """Return personalised study recommendations for the current user."""
    from .ai_service import get_study_recommendations

    recent_quizzes = Quiz.objects.filter(
        user=request.user, completed=True
    ).select_related('topic', 'subject').order_by('-completed_at')[:10]

    history = []
    for q in recent_quizzes:
        history.append({
            'topic': q.topic.name if q.topic else (q.subject.name if q.subject else 'General'),
            'score': q.score,
            'quiz_type': q.quiz_type,
        })

    # Topics with low average score (below 60%)
    weak_topics = list({
        (q.topic.name if q.topic else '') for q in recent_quizzes
        if q.score < 60 and q.topic
    })

    # Topics from slides not yet completed
    completed_slides = UserProgress.objects.filter(
        user=request.user, completed=True
    ).values_list('slide__topic__name', flat=True)
    upcoming = list(Topic.objects.exclude(name__in=completed_slides).values_list('name', flat=True)[:5])

    result = get_study_recommendations(history, weak_topics, upcoming)
    return Response(result)

# -------------------------
# AI ENHANCEMENT ENDPOINTS
# -------------------------

def has_premium_access(user):
    """Check if user has premium access (premium subscription OR class head)"""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_premium or user.profile.role == 'Class Head'

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_textbook_suggestions(request):
    """Get AI-generated textbook suggestions for a slide"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text
    import json
    
    if not has_premium_access(request.user):
        return Response({
            'error': 'Premium access required',
            'message': 'Textbook suggestions are available with premium subscription'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        slide_id = request.data.get('slide_id')
        
        if not slide_id:
            return Response({
                'error': 'Missing slide_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = None
        if slide.file:
            file_url = slide.file.url
        elif slide.file_url:
            file_url = slide.file_url
        
        slide_content = ""
        if file_url:
            slide_content = get_slide_full_text(file_url, slide.file_type or 'pdf')
        
        # Get subject name
        subject = slide.subject_name or 'Medical'
        
        # Generate suggestions
        suggestions = ai_service.get_textbook_suggestions(
            slide.title, 
            slide_content, 
            subject,
            slide.id  # Pass slide ID for proper caching
        )
        
        return Response({
            'suggestions': suggestions,
            'slide_title': slide.title,
            'subject': subject
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_video_suggestions(request):
    """Get AI-generated video suggestions for a slide"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text
    
    if not has_premium_access(request.user):
        return Response({
            'error': 'Premium access required',
            'message': 'Video suggestions are available with premium subscription'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        slide_id = request.data.get('slide_id')
        
        if not slide_id:
            return Response({
                'error': 'Missing slide_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = None
        if slide.file:
            file_url = slide.file.url
        elif slide.file_url:
            file_url = slide.file_url
        
        slide_content = ""
        if file_url:
            slide_content = get_slide_full_text(file_url, slide.file_type or 'pdf')
        
        # Get subject name
        subject = slide.subject_name or 'Medical'
        
        # Generate suggestions
        suggestions = ai_service.get_video_suggestions(
            slide.title, 
            slide_content, 
            subject,
            slide.id  # Pass slide ID for proper caching
        )
        
        return Response({
            'suggestions': suggestions,
            'slide_title': slide.title,
            'subject': subject
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_slide_mcqs(request):
    """Generate AI-powered MCQs from slide content"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text
    
    if not has_premium_access(request.user):
        return Response({
            'error': 'Premium access required',
            'message': 'MCQ generation is available with premium subscription'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        slide_id = request.data.get('slide_id')
        
        if not slide_id:
            return Response({
                'error': 'Missing slide_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = None
        if slide.file:
            file_url = slide.file.url
        elif slide.file_url:
            file_url = slide.file_url
        
        slide_content = ""
        if file_url:
            slide_content = get_slide_full_text(file_url, slide.file_type or 'pdf')
        
        # Get subject name
        subject = slide.subject_name or 'Medical'
        
        # Generate MCQs
        mcqs = ai_service.generate_mcqs(
            slide.title, 
            slide_content, 
            subject,
            slide.id  # Pass slide ID for proper caching
        )
        
        return Response({
            'mcqs': mcqs,
            'total_questions': len(mcqs),
            'slide_title': slide.title,
            'subject': subject
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -------------------------
# SLIDE PROCESSING VIEWS
# -------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reprocess_slide(request, slide_id):
    """
    Reprocess a specific slide (useful for failed slides)
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from .tasks import process_slide_task
        
        # Get the slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': f'Slide {slide_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Reset processing status
        status_obj, created = SlideProcessingStatus.objects.get_or_create(slide=slide)
        status_obj.status = 'pending'
        status_obj.error_message = ''
        status_obj.content_extracted = False
        status_obj.rag_processed = False
        status_obj.is_chunked = False
        status_obj.is_embedded = False
        status_obj.save()
        
        # Queue for reprocessing
        task = process_slide_task.delay(slide_id)
        
        return Response({
            'message': f'Slide {slide_id} queued for reprocessing',
            'task_id': task.id,
            'slide_title': slide.title
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reprocess_failed_slides(request):
    """
    Reprocess all slides that previously failed
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from .tasks import process_slide_task
        
        # Get all failed slides
        failed_statuses = SlideProcessingStatus.objects.filter(status='failed')
        failed_slide_ids = [status.slide_id for status in failed_statuses]
        
        if not failed_slide_ids:
            return Response({
                'message': 'No failed slides found',
                'queued_count': 0
            })
        
        # Reset their status and queue for reprocessing
        queued_tasks = []
        for slide_id in failed_slide_ids:
            try:
                # Reset status
                status_obj = SlideProcessingStatus.objects.get(slide_id=slide_id)
                status_obj.status = 'pending'
                status_obj.error_message = ''
                status_obj.save()
                
                # Queue task
                task = process_slide_task.delay(slide_id)
                queued_tasks.append({
                    'slide_id': slide_id,
                    'task_id': task.id
                })
                
            except Exception as e:
                continue
        
        return Response({
            'message': f'Queued {len(queued_tasks)} failed slides for reprocessing',
            'queued_count': len(queued_tasks),
            'tasks': queued_tasks
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def slide_processing_status(request, slide_id):
    """
    Get processing status for a specific slide
    """
    try:
        from .models import Slide, SlideProcessingStatus
        
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': f'Slide {slide_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get processing status
        try:
            status_obj = SlideProcessingStatus.objects.get(slide=slide)
            return Response({
                'slide_id': slide_id,
                'slide_title': slide.title,
                'status': status_obj.status,
                'content_extracted': status_obj.content_extracted,
                'rag_processed': status_obj.rag_processed,
                'is_chunked': status_obj.is_chunked,
                'is_embedded': status_obj.is_embedded,
                'chunk_count': status_obj.chunk_count,
                'started_at': status_obj.started_at,
                'completed_at': status_obj.completed_at,
                'error_message': status_obj.error_message
            })
        except SlideProcessingStatus.DoesNotExist:
            return Response({
                'slide_id': slide_id,
                'slide_title': slide.title,
                'status': 'not_processed',
                'content_extracted': False,
                'rag_processed': False,
                'is_chunked': False,
                'is_embedded': False,
                'chunk_count': 0,
                'started_at': None,
                'completed_at': None,
                'error_message': ''
            })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_overview(request):
    """
    Get overview of all slide processing statuses
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from django.db.models import Count
        
        # Get counts by status
        status_counts = SlideProcessingStatus.objects.values('status').annotate(count=Count('status'))
        
        # Get total slides
        total_slides = Slide.objects.count()
        processed_slides = SlideProcessingStatus.objects.count()
        unprocessed_slides = total_slides - processed_slides
        
        # Format status counts
        status_summary = {item['status']: item['count'] for item in status_counts}
        if unprocessed_slides > 0:
            status_summary['unprocessed'] = unprocessed_slides
        
        # Get recent failures
        recent_failures = SlideProcessingStatus.objects.filter(
            status='failed'
        ).select_related('slide').order_by('-started_at')[:10]
        
        failure_details = []
        for failure in recent_failures:
            failure_details.append({
                'slide_id': failure.slide.id,
                'slide_title': failure.slide.title,
                'error_message': failure.error_message,
                'started_at': failure.started_at
            })
        
        return Response({
            'total_slides': total_slides,
            'status_summary': status_summary,
            'recent_failures': failure_details
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)