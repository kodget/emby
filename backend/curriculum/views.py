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
    QuizQuestion, Quiz, QuizAnswer, SlideContent
)
from .serializers import (
    SubjectSerializer, BlockSerializer, TopicSerializer, SectionSerializer, SlideSerializer, MaterialSerializer,
    UserProgressSerializer, ScheduleItemSerializer, UserStatsSerializer,
    CommunityPostSerializer, PostCommentSerializer, UpcomingTestSerializer,
    QuizQuestionSerializer, QuizSerializer, QuizAnswerSerializer
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
        
        # Render slide pages in background (non-blocking)
        try:
            from .slide_renderer import render_slide_pages
            if slide.file_url:
                print(f"Starting slide rendering for {slide.id}...")
                content = render_slide_pages(slide.file_url, slide.file_type, slide.id)
                slide.page_count = content['total_pages']
                slide.save(update_fields=['page_count'])
                print(f"Slide rendering complete: {slide.page_count} pages")
        except Exception as e:
            print(f"Slide rendering failed for {slide.id}: {e}")
            import traceback
            traceback.print_exc()
            # Set default page_count so slide still appears
            slide.page_count = 1
            slide.save(update_fields=['page_count'])


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
    """Get rendered slide pages with text coordinates"""
    try:
        print(f"Getting content for slide: {slide_id}")
        slide = Slide.objects.get(id=slide_id)
        print(f"Slide found: {slide.title}, file_url: {slide.file_url}")
        
        from .slide_renderer import render_slide_pages
        
        print(f"Rendering pages from {slide.file_url}...")
        content = render_slide_pages(slide.file_url, slide.file_type, slide.id)
        print(f"Pages rendered: {content['total_pages']} pages")
        
        return Response({
            'slide_id': slide.id,
            'title': slide.title,
            'total_pages': content['total_pages'],
            'pages': content['pages']
        })
                
    except Slide.DoesNotExist:
        print(f"Slide not found: {slide_id}")
        return Response(
            {'error': 'Slide not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Slide rendering error: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Slide rendering failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
        
        # TODO: For theory questions, use AI to score and provide feedback
        # For now, just save the answer
        
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
        
        # Award points
        points = quiz.score * 2  # 2 points per correct answer
        statsApi.awardPoints(points, f'Completed {quiz.quiz_type.upper()} quiz')
        
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
