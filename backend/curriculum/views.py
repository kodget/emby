import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from accounts.permissions import IsClassHeadOrReadOnly
from .content_permissions import CanWriteUploadedContent, PlatformAdminWritesOnly
from .class_access import visible, upload_class, ClassContentReferences, require_visible, visible_quizzes, visible_attempts
from .private_media import upload_asset, discard_new_asset, content_file_url, page_payloads, PrivateMediaResponseMixin
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Subject, Block, SubBlock, Topic, Slide, Material, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, PostLike, UpcomingTest, DailyStudySession,
    QuizQuestion, Quiz, QuizAnswer, SlideContent, SlideDeck, SlidePage, SteeplechaseQuestion,
    FriendChallenge, BrainBattle, BattleParticipant, Flashcard, FlashcardProgress, FlashcardReview, StudyProfile
)
from .serializers import (
    SubjectSerializer, BlockSerializer, SubBlockSerializer, TopicSerializer, SlideSerializer, MaterialSerializer,
    UserProgressSerializer, ScheduleItemSerializer, UserStatsSerializer,
    CommunityPostSerializer, PostCommentSerializer, UpcomingTestSerializer,
    QuizQuestionSerializer, QuizSerializer, QuizAnswerSerializer,
    SlideDeckSerializer, SlideDeckListSerializer, SlidePageSerializer, SteeplechaseQuestionSerializer,
    FriendChallengeSerializer, BrainBattleSerializer, BattleParticipantSerializer,
    FlashcardSerializer, FlashcardProgressSerializer, FlashcardReviewSerializer, StudyProfileSerializer
)

logger = logging.getLogger(__name__)


# -------------------------
# CURRICULUM VIEWS
# -------------------------
class StudyProfileViewSet(viewsets.ModelViewSet):
    """CRUD operations for StudyProfile"""
    serializer_class = StudyProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StudyProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubjectViewSet(viewsets.ModelViewSet):
    """List all subjects"""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsClassHeadOrReadOnly]

    def get_queryset(self):
        return visible(Subject, self.request.user)

    def perform_create(self, serializer):
        serializer.save(class_group=upload_class(self.request.user))


class BlockViewSet(viewsets.ModelViewSet):
    """List blocks, optionally filtered by subject"""
    queryset = Block.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [IsAuthenticated, IsClassHeadOrReadOnly, ClassContentReferences]
    
    def get_queryset(self):
        queryset = visible(Block, self.request.user)
        subject_id = self.request.query_params.get('subject', None)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        return queryset


class SubBlockViewSet(viewsets.ModelViewSet):
    """List sub-blocks, optionally filtered by block"""
    queryset = SubBlock.objects.all()
    serializer_class = SubBlockSerializer
    permission_classes = [IsAuthenticated, IsClassHeadOrReadOnly, ClassContentReferences]
    
    def get_queryset(self):
        queryset = visible(SubBlock, self.request.user)
        block_id = self.request.query_params.get('block', None)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        return queryset


class TopicViewSet(viewsets.ModelViewSet):
    """List topics, optionally filtered by block"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated, IsClassHeadOrReadOnly, ClassContentReferences]
    
    def get_queryset(self):
        queryset = visible(Topic, self.request.user)
        block_id = self.request.query_params.get('block', None)
        sub_block_id = self.request.query_params.get('sub_block', None)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if sub_block_id:
            queryset = queryset.filter(sub_block_id=sub_block_id)
        return queryset


class SlideViewSet(PrivateMediaResponseMixin, viewsets.ModelViewSet):
    """CRUD operations for slides (PDF/PPT/DOCX only)"""
    queryset = Slide.objects.all()
    serializer_class = SlideSerializer
    permission_classes = [CanWriteUploadedContent, ClassContentReferences]
    
    def get_queryset(self):
        queryset = visible(Slide, self.request.user)
        subject_id = self.request.query_params.get('subject', None)
        block_id = self.request.query_params.get('block', None)
        topic_id = self.request.query_params.get('topic', None)
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        sub_block_id = self.request.query_params.get('sub_block')
        if sub_block_id:
            queryset = queryset.filter(sub_block_id=sub_block_id)
        return queryset
    
    @action(detail=False, methods=['post'])
    def upload_and_process(self, request):
        import uuid
        import cloudinary.uploader
        from cloudinary import CloudinaryResource
        from django.db import transaction
        from rest_framework.exceptions import ValidationError
        from .models import SlideProcessingStatus
        from .slide_uploads import validate_slide_file, dispatch_slide_processing, topic_for_upload

        file_obj = request.FILES.get('file')
        if file_obj is None:
            raise ValidationError({'file': 'Select a file to upload.'})
        file_type = validate_slide_file(file_obj)
        metadata = {'title': request.data.get('title', file_obj.name), 'file_type': file_type}
        for name in ('subject', 'block', 'sub_block', 'topic'):
            value = request.data.get(name)
            if value not in (None, '', 'null', 'undefined', 'None'):
                metadata[name] = value
        serializer = self.get_serializer(data=metadata)
        serializer.is_valid(raise_exception=True)
        owning_class = upload_class(request.user)

        from rest_framework.exceptions import APIException
        from .upload_receipts import execute_upload, StorageUnavailable

        def create(staged):
            try:
                asset = upload_asset(file_obj, class_group=owning_class, uploaded_by=request.user,
                    folder='emby/slides_original', resource_type='auto', timeout=60)
            except Exception as exc:
                logger.warning('Slide storage failed (%s)', type(exc).__name__)
                raise StorageUnavailable()
            staged.append(asset)
            topic = topic_for_upload(serializer.validated_data)
            slide = serializer.save(id=f'slide_{uuid.uuid4().hex}', uploaded_by=request.user,
                class_group=owning_class, asset=asset, file_url='', file=None, topic=topic)
            SlideProcessingStatus.objects.create(slide=slide, status='pending')
            transaction.on_commit(lambda: dispatch_slide_processing(slide.pk), robust=True)
            return slide

        try:
            slide, _ = execute_upload(user=request.user, request_id=request.data.get('request_id'),
                kind='slide', metadata={**metadata, 'class_group': str(owning_class.pk)}, upload=file_obj,
                create=create, queryset=self.get_queryset())
        except APIException:
            raise
        except Exception as exc:
            logger.warning('Slide record save failed (%s)', type(exc).__name__)
            return Response({'error': 'Could not save this upload. Please try again.'}, status=503)
        return Response(self.get_serializer(slide).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user, class_group=upload_class(self.request.user))


class MaterialViewSet(PrivateMediaResponseMixin, viewsets.ModelViewSet):
    """CRUD operations for materials (videos, images, PDFs, past questions, etc.)"""
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [CanWriteUploadedContent, ClassContentReferences]
    
    def get_queryset(self):
        queryset = visible(Material, self.request.user)
        subject_id = self.request.query_params.get('subject', None)
        block_id = self.request.query_params.get('block', None)
        topic_id = self.request.query_params.get('topic', None)
        sub_block_id = self.request.query_params.get('sub_block', None)
        material_type = self.request.query_params.get('type', None)
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        if sub_block_id:
            queryset = queryset.filter(sub_block_id=sub_block_id)
        if material_type:
            queryset = queryset.filter(material_type=material_type)
        
        return queryset
    
    def perform_create(self, serializer):
        # Upload rights live in accounts.permissions, which understands verified class
        # heads, material uploaders and the SLIDE_UPLOADER capability. This used to read
        # `profile.role`, which does not exist, so it raised instead of authorising.
        from accounts.permissions import can_upload_slides

        profile = getattr(self.request.user, 'profile', None)
        if profile is None or not can_upload_slides(profile):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only class heads and material uploaders can upload materials")
        
        serializer.save(uploaded_by=self.request.user, class_group=upload_class(self.request.user))


# -------------------------
# PROGRESS VIEWS
# -------------------------
class UserProgressViewSet(viewsets.ModelViewSet):
    """Track user progress on slides"""
    serializer_class = UserProgressSerializer
    permission_classes = [IsAuthenticated, ClassContentReferences]
    
    def get_queryset(self):
        rows = visible(UserProgress, self.request.user).filter(user=self.request.user)
        slide = self.request.query_params.get('slide')
        return rows.filter(slide_id=slide) if slide else rows
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recently accessed slides"""
        recent_progress = self.get_queryset().order_by('-last_accessed')[:5]
        serializer = self.get_serializer(recent_progress, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def update_progress(self, request):
        from .course_reading import save
        progress = save(request.user, request.data)
        return Response(self.get_serializer(progress).data)

    @action(detail=False, methods=['get'])
    def subject_progress(self, request):
        """Return per-subject completion percentage based on slides accessed."""
        progress_qs = self.get_queryset().select_related('slide__subject')
        
        subject_data: dict[str, dict] = {}
        for p in progress_qs:
            if not p.slide or not p.slide.subject:
                continue
            sid = str(p.slide.subject.id)
            sname = p.slide.subject.name
            if sid not in subject_data:
                subject_data[sid] = {
                    'subject_id': sid,
                    'subject_name': sname,
                    'total_pages': 0,
                    'completed_pages': 0,
                }
            subject_data[sid]['total_pages'] += p.total_pages or 0
            subject_data[sid]['completed_pages'] += p.current_page or 0

        result = []
        for item in subject_data.values():
            pct = (
                round((item['completed_pages'] / item['total_pages']) * 100)
                if item['total_pages'] > 0
                else 0
            )
            result.append({
                'subject_id': item['subject_id'],
                'subject_name': item['subject_name'],
                'completion_percentage': min(pct, 100),
            })

        return Response(result)


# -------------------------
# SCHEDULE VIEWS
# -------------------------
class ScheduleItemViewSet(viewsets.ModelViewSet):
    """CRUD operations for schedule items"""
    serializer_class = ScheduleItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return visible(ScheduleItem, self.request.user).filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's schedule"""
        today = timezone.localdate()
        items = self.get_queryset().filter(scheduled_date=today)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming schedule (next 7 days)"""
        today = timezone.localdate()
        next_week = today + timedelta(days=7)
        items = self.get_queryset().filter(
            scheduled_date__gte=today,
            scheduled_date__lte=next_week
        )
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """Persist a checklist completion and its activity together, once."""
        from learning import events
        from learning.models import ActivityType

        item = self.get_queryset().select_for_update(of=('self',)).get(pk=self.get_object().pk)
        if not item.completed:
            item.completed = True
            item.completed_at = timezone.now()
            item.save(update_fields=['completed', 'completed_at', 'updated_at'])
            # An estimate is a planning aid, not elapsed study time. Reading,
            # practice, and explicit study logs record the time actually reported.
            events.record(
                request.user, ActivityType.PLANNER_TASK_COMPLETED,
                subject=item.slide.subject if item.slide_id else None,
                block=item.block, sub_block=item.sub_block,
                duration_seconds=0, resource_type='schedule_item', resource_id=str(item.id),
                occurred_at=item.completed_at,
                metadata={'activity_type': item.activity_type, 'title': item.title,
                          'estimated_minutes': item.estimated_minutes},
            )
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def uncomplete(self, request, pk=None):
        """Undo the checklist tick without deleting history or replaying rewards."""
        item = self.get_queryset().select_for_update(of=('self',)).get(pk=self.get_object().pk)
        if item.completed:
            item.completed = False
            item.completed_at = None
            item.save(update_fields=['completed', 'completed_at', 'updated_at'])
        return Response(self.get_serializer(item).data)


# -------------------------
# GAMIFICATION VIEWS
# -------------------------
class UserStatsViewSet(viewsets.ModelViewSet):
    """User statistics and gamification"""
    serializer_class = UserStatsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserStats.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """Get current user's stats"""
        stats, created = UserStats.objects.get_or_create(user=request.user)
        if request.method == 'PATCH':
            from rest_framework import serializers
            values = {key: serializers.BooleanField().run_validation(value)
                      for key, value in request.data.items() if key in ('public_profile', 'public_rank')}
            for key, value in values.items():
                setattr(stats, key, value)
            if values:
                stats.save(update_fields=list(values))
        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'public/(?P<user_id>[0-9]+)')
    def public_profile(self, request, user_id=None):
        from .class_access import member_class
        group = member_class(request.user)
        stats = UserStats.objects.select_related('user__profile__class_group__school').filter(
            user_id=user_id, user__is_active=True, user__profile__class_group=group,
        ).first() if group else None
        if stats is None or (not stats.public_profile and stats.user_id != request.user.pk):
            return Response({'detail': 'Profile not available.'}, status=404)
        profile = stats.user.profile
        return Response({
            'id': stats.user_id, 'full_name': stats.user.get_full_name() or stats.user.username,
            'photo_url': profile.photo_url, 'school_name': group.school.name, 'set_name': group.set_name,
            'points': stats.points if stats.public_rank else None,
            'current_streak': stats.current_streak,
        })
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get leaderboard (top users by points)"""
        from .class_access import member_class
        try:
            limit = min(100, max(1, int(request.query_params.get('limit', 10))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid limit.'}, status=400)
        group = member_class(request.user)
        top_users = UserStats.objects.filter(
            public_rank=True, public_profile=True, user__profile__class_group=group
        ).order_by('-points')[:limit] if group else UserStats.objects.none()
        
        serializer = self.get_serializer(top_users, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def award_points(self, request):
        """Points are awarded by verified server-side activity, never client totals."""
        return Response({'error': 'Points are awarded automatically for completed activities.'}, status=403)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def update_streak(self, request):
        """Refresh derived streaks; opening the app is not learning activity."""
        from learning import events
        events.lock_stats(request.user)
        events._touch_streak(request.user)
        stats = request.user.stats
        if hasattr(request.user, 'profile'):
            type(request.user.profile).objects.filter(pk=request.user.profile.pk).update(streak=stats.active_streak)
        return Response(self.get_serializer(stats).data)


# -------------------------
# COMMUNITY VIEWS
# -------------------------
class CommunityPostViewSet(viewsets.ModelViewSet):
    """Community posts and feed"""
    serializer_class = CommunityPostSerializer
    permission_classes = [IsAuthenticated, ClassContentReferences]
    
    def get_queryset(self):
        from .class_access import content_admin, member_class

        queryset = CommunityPost.objects.all()
        if content_admin(self.request.user):
            return queryset
        group = member_class(self.request.user)
        if group is None:
            return queryset.none()
        # Preserve the post's class even if its author subsequently moves classes.
        # Old unassigned posts and inconsistent links are not a shared feed.
        queryset = queryset.filter(class_group=group)
        for field, model in (('slide', Slide), ('sub_block', SubBlock), ('topic', Topic)):
            queryset = queryset.filter(
                Q(**{field + '__isnull': True}) |
                Q(**{field + '__in': visible(model, self.request.user)})
            )
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, class_group=upload_class(self.request.user))
    
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
            
            # Schedule notification for post author
            if post.user != request.user:
                from learning.notifications import schedule
                from learning.models import NotificationType
                schedule(
                    user=post.user,
                    type_=NotificationType.POST_LIKED,
                    title=f"{request.user.first_name or request.user.username} liked your post",
                    body=post.content[:100] + ("..." if len(post.content) > 100 else ""),
                    action_url=f"/community/post/{post.id}",
                    dedupe_key=f"like:post:{post.id}:user:{request.user.id}",
                )
        
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
        
        # Schedule notification for post author
        if post.user != request.user:
            from learning.notifications import schedule
            from learning.models import NotificationType
            schedule(
                user=post.user,
                type_=NotificationType.POST_COMMENTED,
                title=f"{request.user.first_name or request.user.username} commented on your post",
                body=content[:100] + ("..." if len(content) > 100 else ""),
                action_url=f"/community/post/{post.id}",
                dedupe_key=f"comment:post:{post.id}:comment:{comment.id}",
            )
        
        serializer = PostCommentSerializer(comment)
        return Response(serializer.data)


# -------------------------
# TESTS VIEWS
# -------------------------
class UpcomingTestViewSet(viewsets.ModelViewSet):
    """Upcoming tests and exams"""
    serializer_class = UpcomingTestSerializer
    permission_classes = [IsAuthenticated, IsClassHeadOrReadOnly, ClassContentReferences]
    
    def get_queryset(self):
        return visible(UpcomingTest, self.request.user).filter(test_date__gte=date.today())
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def get_slide_content(request, slide_id):
    """Get rendered slide pages as images."""
    try:
        slide = visible(Slide, request.user).get(id=slide_id)
    except Slide.DoesNotExist:
        return Response({'error': 'Slide not found'}, status=status.HTTP_404_NOT_FOUND)

    slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
    from .content_permissions import can_reprocess_upload
    from .document_index import status_for
    extraction_info = {
        'ai_index': status_for(slide),
        'text_extraction': (slide_content.content_data or {}).get('text_extraction', {'status': 'unverified'}),
        'can_reprocess': can_reprocess_upload(request.user, slide),
    }
    
    # Return cached if available — check both 'pages' exists and has content
    cached_pages = slide_content.content_data.get('pages', []) if slide_content.content_data else []
    if slide_content.is_extracted and cached_pages:
        total = slide_content.content_data.get('total_pages') or slide_content.content_data.get('page_count') or len(cached_pages)
        return Response({
            'slide_id': slide.id,
            'title': slide.title,
            'total_pages': total,
            'pages': page_payloads(cached_pages, slide.class_group_id),
            **extraction_info,
        }, headers={'Cache-Control': 'private, no-store'})

    # A newly uploaded document already has an owned background conversion.
    # Opening the reader must not start a second render inside a GET request.
    from .models import SlideProcessingStatus
    from .slide_processing import ACTIVE_STATES
    processing = SlideProcessingStatus.objects.filter(slide=slide).first()
    if processing and processing.status in (*ACTIVE_STATES, 'failed'):
        failed = processing.status == 'failed' and not processing.next_attempt_at
        return Response({
            'slide_id': slide.id, 'title': slide.title, 'pages': [], 'total_pages': 0,
            'processing': not failed, 'processing_status': processing.status,
            'progress': processing.processing_progress, 'next_attempt_at': processing.next_attempt_at,
            **extraction_info,
            **({'error': 'Document preparation failed. Please retry processing.'} if failed else {}),
        }, status=409 if failed else 202, headers={'Cache-Control': 'private, no-store', 'Retry-After': '2'})

    # Legacy documents without a processing job can still render on demand.
    file_url = slide.get_file_url
    if not file_url:
        return Response({'error': 'Slide has no file URL'}, status=status.HTTP_400_BAD_REQUEST)

    from .slide_renderer import render_slide_pages
    try:
        content = render_slide_pages(file_url, slide.file_type, slide.id)
        from django.db import transaction
        from .services.document_extraction import is_complete, ERRORS
        with transaction.atomic():
            slide_content = SlideContent.objects.select_for_update().get(slide=slide)
            previous = slide_content.content_data or {}
            # OCR may have completed while images were rendering. Preserve its text.
            if (is_complete(previous) and previous['text_extraction'].get('source_sha256') ==
                    content.get('text_extraction', {}).get('source_sha256')):
                text_pages = {p['page_number']: p for p in previous['pages']}
                for page in content['pages']:
                    extracted = text_pages[page['page_number']]
                    for key in ('text', 'extraction_status', 'extraction_method', 'error_code'):
                        page[key] = extracted[key]
                content['text_extraction'] = previous['text_extraction']
                content['text'] = previous.get('text', '')
            content = {**previous, **content}
            from .services.document_extraction import source_key
            content['text_extraction']['source_key'] = source_key(slide)
            slide_content.content_data = content
            slide_content.is_extracted = content['total_pages'] > 0
            slide_content.extraction_error = ''
            slide_content.extracted_at = timezone.now()
            slide_content.save()
        
        if content['total_pages'] > 0:
            Slide.objects.filter(id=slide.id).update(page_count=content['total_pages'])
            from .document_index import request_index
            request_index(slide)
            extraction_info['ai_index'] = status_for(slide)
        
        return Response({
            'slide_id': slide.id,
            'title': slide.title,
            'total_pages': content['total_pages'],
            'pages': page_payloads(content['pages'], slide.class_group_id),
            **extraction_info,
            'text_extraction': content.get('text_extraction', {'status': 'unverified'}),
        }, headers={'Cache-Control': 'private, no-store'})
    except Exception as e:
        logger.warning('Slide rendering failed (%s)', type(e).__name__)
        return Response({'error': 'Rendering failed. Please retry.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -------------------------
# QUIZ SYSTEM
# -------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def generate_quiz(request):
    """Retired unscoped creator; existing legacy history remains readable."""
    return Response({'error': 'Open Practice and select one deck to start a saved-bank quiz.',
                     'code': 'use_deck_practice', 'url': '/quiz'}, status=410)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def submit_quiz_answer(request):
    """Submit an answer to a quiz question"""
    quiz_id = request.data.get('quiz_id')
    question_id = request.data.get('question_id')
    selected_option = request.data.get('selected_option', '')  # For MCQ
    text_answer = request.data.get('text_answer', '')  # For Theory
    time_taken = int(request.data.get('time_taken_seconds', 0))
    
    try:
        quiz = visible_quizzes(request.user).get(id=quiz_id)
        question = visible(QuizQuestion, request.user).get(id=question_id)
        if not quiz.questions.filter(pk=question.pk).exists():
            return Response({'error': 'Question does not belong to this quiz.'}, status=400)
        
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def complete_quiz(request, quiz_id):
    """Mark quiz as complete and calculate score"""
    try:
        quiz = visible_quizzes(request.user).get(id=quiz_id)
        
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def get_quiz_history(request):
    """Get user's quiz history"""
    quizzes = visible_quizzes(request.user).filter(completed=True).order_by('-completed_at')[:20]
    serializer = QuizSerializer(quizzes, many=True)
    return Response(serializer.data)


# -------------------------
# STUDY TIME TRACKING
# -------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def get_weekly_study_data(request):
    """Use the same accepted evidence and local seven-day window as analytics."""
    from learning.analytics_evidence import Evidence
    evidence = Evidence(request.user, 7)
    data = [dict(row, day=date.fromisoformat(row['date']).strftime('%a')) for row in evidence.daily()]
    total = evidence.overview()['study_minutes']
    return Response({'week_data': data, 'total_minutes': total,
                     'total_hours': int(total // 60), 'remaining_minutes': round(total % 60, 2)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
@transaction.atomic
def log_study_time(request):
    """Persist a validated manual log; retries with the same request ID count once."""
    from datetime import datetime, time
    from rest_framework import serializers
    from learning import events
    from learning.models import ActivityType, LearningEvent
    from learning.analytics_evidence import Evidence, minutes as as_minutes

    class Input(serializers.Serializer):
        minutes = serializers.IntegerField(min_value=1, max_value=1440)
        date = serializers.DateField(required=False)
        request_id = serializers.UUIDField(required=False)

    data = Input(data=request.data)
    data.is_valid(raise_exception=True)
    now = timezone.now()
    request_id = data.validated_data.get('request_id')
    key = f'manual:{request_id}' if request_id else ''
    events.lock_stats(request.user)
    previous = LearningEvent.objects.filter(user=request.user, idempotency_key=key).first() if key else None
    default_date = date.fromisoformat(previous.metadata['date']) if previous else timezone.localdate(now)
    study_date = data.validated_data.get('date', default_date)
    if study_date > timezone.localdate(now):
        raise serializers.ValidationError({'date': 'Study time cannot be logged in the future.'})
    at = now if study_date == timezone.localdate(now) else timezone.make_aware(datetime.combine(study_date, time.min))
    events.record(request.user, ActivityType.STUDY_SESSION_COMPLETED,
        duration_seconds=data.validated_data['minutes'] * 60, occurred_at=at,
        resource_type='manual_study', metadata={'date': study_date.isoformat(), 'manual': True},
        idempotency_key=key, award_xp=False)
    evidence = Evidence(request.user, 7, now=now)
    day_seconds = sum(row['seconds'] for row in evidence.rows if timezone.localdate(row['at']) == study_date)
    return Response({'message': 'Study time logged successfully',
                     'total_today': as_minutes(day_seconds),
                     'total_overall': as_minutes(sum(row['seconds'] for row in evidence.rows))})


# -------------------------
# AI LEARNING SUPPORT
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
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
            slide = visible(Slide, request.user).get(id=slide_id)
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def suggest_videos(request, slide_id):
    """AI suggests 3 best related videos for a slide."""
    try:
        slide = visible(Slide, request.user).get(id=slide_id)
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

    try:
        videos = suggest_related_videos(slide_info)
        return Response({'videos': videos})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error suggesting videos: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -------------------------
# SLIDE DECK VIEWS
# -------------------------
class SlideDeckViewSet(PrivateMediaResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing slide decks (uploaded documents).
    
    Supports:
    - List all decks
    - Retrieve a specific deck with all its pages
    - Create a new deck (upload document)
    - Delete a deck
    """
    serializer_class = SlideDeckSerializer
    permission_classes = [CanWriteUploadedContent, ClassContentReferences]
    lookup_field = 'id'

    @action(detail=True, methods=['get', 'post'], url_path='reading-progress', permission_classes=[IsAuthenticated])
    def reading_progress(self, request, id=None):
        from . import deck_reading
        deck = self.get_object()  # Current class authorization applies to every read and write.
        return Response(deck_reading.payload(request.user, deck) if request.method == 'GET'
                        else deck_reading.save(request.user, deck, request.data))
    
    def get_queryset(self):
        """Get decks uploaded by current user"""
        return visible(SlideDeck, self.request.user).order_by('-created_at')
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return SlideDeckListSerializer
        return SlideDeckSerializer

    @action(detail=True, methods=['get', 'post'], url_path='question-bank')
    def question_bank(self, request, id=None):
        from learning.deck_banks import deck_bank_status, prepare_deck_bank
        deck = self.get_object()
        if request.method == 'GET':
            return Response(deck_bank_status(deck, request.user))
        queued, result = prepare_deck_bank(deck.pk, request.user, request.data)
        return Response({**result, 'queued': queued}, status=202 if queued else 200)
    
    def create(self, request, *args, **kwargs):
        """
        Upload a new document for conversion.
        
        Expected request:
        - MultipartForm with 'file' and 'title' fields
        
        Only 'class_head' and 'material_uploader' roles can upload decks.
        """
        # ========== ROLE-BASED ACCESS CONTROL ==========
        from accounts.permissions import can_upload_slides
        try:
            profile = request.user.profile
            if not can_upload_slides(profile):
                return Response(
                    {'error': 'Only class heads and material uploaders can upload documents.'},
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
        
        from .slide_uploads import validate_slide_file
        file_type = validate_slide_file(file_obj)
        
        import uuid
        from rest_framework.exceptions import APIException, ValidationError
        from .upload_receipts import execute_upload, StorageUnavailable
        owning_class = upload_class(request.user)
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValidationError({'title': 'Enter a title of 1 to 200 characters.'})

        def create(staged):
            try:
                asset = upload_asset(file_obj, class_group=owning_class, uploaded_by=request.user,
                    resource_type='auto', folder='emby/decks', timeout=300)
            except Exception:
                raise StorageUnavailable()
            staged.append(asset)
            deck = SlideDeck.objects.create(id=f'deck_{uuid.uuid4().hex}', title=title,
                file_type=file_type, file_size=file_obj.size, original_file='', asset=asset,
                uploaded_by=request.user, class_group=owning_class, processing_status='pending')
            from .slide_uploads import dispatch_standalone_deck_processing
            transaction.on_commit(lambda: dispatch_standalone_deck_processing(deck.pk), robust=True)
            return deck

        try:
            deck, _ = execute_upload(user=request.user, request_id=request.data.get('request_id'),
                kind='deck', metadata={'title': title, 'file_type': file_type, 'class_group': str(owning_class.pk)},
                upload=file_obj, create=create, queryset=self.get_queryset())
            # The saved receipt can be replayed while the worker prepares pages.
            return Response(self.get_serializer(deck).data, status=status.HTTP_201_CREATED)
        except APIException:
            raise
        except Exception as exc:
            logger.warning('Deck upload failed (%s)', type(exc).__name__)
            return Response({'error': 'Could not store this document. Please try again.'}, status=502)

    def _process_deck_async(self, deck, token=None):
        from .deck_processing import process
        process(deck.pk, token=token)
        deck.refresh_from_db()

    @action(detail=True, methods=['post'], url_path='retry-processing')
    def retry_processing(self, request, id=None):
        from .deck_processing import LEASE
        from .slide_uploads import dispatch_standalone_deck_processing
        from .content_permissions import can_reprocess_upload
        import uuid
        deck = self.get_object()
        if not can_reprocess_upload(request.user, deck):
            return Response({'error': 'You cannot reprocess this upload.'}, status=403)
        with transaction.atomic():
            deck = SlideDeck.objects.select_for_update().get(pk=deck.pk)
            now = timezone.now()
            if (deck.processing_status == 'completed'
                    or (deck.processing_lease_until and deck.processing_lease_until > now)
                    or (deck.processing_status in ('pending', 'processing') and deck.updated_at > now-LEASE)):
                return Response({'queued': False, 'processing_status': deck.processing_status}, status=202)
            deck.processing_status = 'processing'
            deck.processing_attempts = 0
            deck.next_attempt_at = deck.processing_lease_until = None
            deck.processing_token = uuid.uuid4()
            deck.processing_error = ''
            deck.processing_progress = {}
            deck.save(update_fields=['processing_status', 'processing_attempts', 'next_attempt_at',
                'processing_lease_until', 'processing_token', 'processing_error', 'processing_progress', 'updated_at'])
            transaction.on_commit(lambda: dispatch_standalone_deck_processing(deck.pk, deck.processing_token), robust=True)
        return Response({'queued': True, 'processing_status': 'processing'}, status=202)

    @action(detail=True, methods=['get'])
    def pages(self, request, id=None):
        """Get all pages of a slide deck"""
        deck = self.get_object()
        pages = deck.pages.all().order_by('slide_number')
        serializer = SlidePageSerializer(pages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='prepare-ai')
    def prepare_ai(self, request, id=None):
        from .document_index import request_index, status_for
        deck = self.get_object()
        if deck.processing_status != 'completed':
            return Response({'error': 'Wait for the document pages to finish rendering.'}, status=409)
        queued = request_index(deck, force=True)
        return Response({'queued': queued, 'ai_index': status_for(deck)}, status=202)
    
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
        from accounts.permissions import can_upload_slides
        try:
            profile = request.user.profile
            can_delete = is_uploader or can_upload_slides(profile)
        except AttributeError:
            can_delete = False
        
        if not can_delete:
            return Response(
                {'error': 'You do not have permission to delete this deck'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Private assets are retained for the registry's separate orphan reconciliation.
        # A deck ID is not authority to delete arbitrary provider prefixes.
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def generate_questions_from_slide_view(request, slide_id):
    """Persist a bank-generation request; provider work always runs in a worker."""
    from .content_permissions import can_reprocess_upload
    from learning.generation_dispatch import request_generation
    from learning.models import QuestionGenerationJob
    slide = visible(Slide, request.user).filter(pk=slide_id).first()
    if slide is None:
        return Response({'error': 'Slide not found'}, status=404)
    if not can_reprocess_upload(request.user, slide):
        return Response({'error': 'You cannot generate questions for this upload.'}, status=403)
    force = request.data.get('force', False)
    if type(force) is not bool:
        return Response({'error': 'force must be a boolean.'}, status=400)
    if 'num_mcq' in request.data or 'num_theory' in request.data:
        return Response({'error': 'Bank generation uses the configured bank targets, not quiz attempt counts.'}, status=400)
    queued = request_generation(slide, force=force)
    job = QuestionGenerationJob.objects.get(slide=slide)
    return Response({'slide_id': slide.pk, 'queued': queued, 'status': job.status,
                     'mcq_target': job.mcq_target, 'theory_target': job.theory_target,
                     'mcq_generated': job.mcq_generated, 'theory_generated': job.theory_generated,
                     'error': job.error}, status=202 if queued else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def ai_study_recommendations(request):
    """Return study session context for the 5-step dynamic session."""
    from curriculum.models import SlidePage, Topic, ScheduleItem, FlashcardProgress, QuizAttempt, UserProgress
    from learning.analytics_evidence import Evidence
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    today = timezone.localdate()

    # 1. Flashcards due
    flashcards_due = FlashcardProgress.objects.filter(
        user=request.user, flashcard__in=visible(Flashcard, request.user),
        due_date__lte=now
    ).count()

    # 2. Practice Topic (Weakest area)
    evidence = Evidence(request.user, 30)
    weak_area = next(iter(evidence.topics()['weakest']), None)
    practice_topic = weak_area['label'] if weak_area else 'General Review'
    
    # 3. Slide to read (next unread slide)
    completed_slides = list(UserProgress.objects.filter(
        user=request.user, completed=True
    ).values_list('slide_id', flat=True))
    next_slide = visible(Slide, request.user).exclude(id__in=completed_slides).first()
    slide_to_read = {"id": next_slide.id, "title": next_slide.title} if next_slide else None

    # 4. Stale slides (read > 1 week ago)
    one_week_ago = now - timedelta(days=7)
    stale_progress = visible(UserProgress, request.user).filter(
        user=request.user, completed=True, last_accessed__lte=one_week_ago
    ).select_related('slide').order_by('last_accessed')[:3]
    
    stale_slides = [
        {"id": sp.slide.id, "title": sp.slide.title} for sp in stale_progress if sp.slide
    ]

    # 5. Study Plan Items (Tasks for today)
    schedule_qs = visible(ScheduleItem, request.user).filter(
        user=request.user,
        scheduled_date=today,
        completed=False
    ).values('id', 'title', 'activity_type', 'completed')
    
    plan_items = []
    for item in schedule_qs:
        plan_items.append({
            'id': item['id'],
            'title': item['title'],
            'item_type': item['activity_type'],
            'status': 'completed' if item['completed'] else 'pending'
        })

    # Use saved objective results, including unanswered MCQs. Historical analysis
    # narratives are not evidence for current recommendations.
    completed = [row for row in evidence.rows if row['kind'] in ('practice', 'mock', 'formal')]
    latest = max(completed, key=lambda row: row['at'], default=None)
    missed_count = latest['attempted'] - latest['correct'] if latest else 0
    insights = None

    return Response({
        "slide_to_read": slide_to_read,
        "flashcards_due": flashcards_due,
        "practice_topic": practice_topic,
        "stale_slides": stale_slides,
        "study_plan_items": list(plan_items),
        
        # Legacy fields to avoid breaking TodaySessionCard until we update it
        "focus_areas": [practice_topic] if practice_topic else [],
        "recommendations": [{"action": "Read", "topic": slide_to_read}],
        "missed_count": missed_count,
        "insights": insights
    })

# -------------------------
# AI ENHANCEMENT ENDPOINTS
# -------------------------

def has_premium_access(user):
    """Whether this user may use premium features.

    Delegates to accounts.permissions so entitlement is decided in exactly one place.
    The previous implementation read `profile.role`, a field that does not exist — the
    model has `platform_role` and `class_role`. In views.py that raised AttributeError
    whenever is_premium was False; in ai_views.py it was swallowed by an except clause,
    which silently denied premium AI to verified class heads. The clause was also
    redundant: Profile.is_premium already covers admins and verified class heads.
    """
    from accounts.permissions import can_access_premium_features

    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    return can_access_premium_features(profile)

@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def get_textbook_suggestions(request):
    """Get AI-generated textbook suggestions for a slide"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text, ExtractionError
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
            slide = visible(Slide, request.user).get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = content_file_url(slide)
        
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
        
    except ExtractionError as exc:
        return Response({'error': str(exc), 'text_extraction': exc.report}, status=409)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def get_video_suggestions(request):
    """Get AI-generated video suggestions for a slide"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text, ExtractionError
    
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
            slide = visible(Slide, request.user).get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = content_file_url(slide)
        
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
        
    except ExtractionError as exc:
        return Response({'error': str(exc), 'text_extraction': exc.report}, status=409)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def generate_slide_mcqs(request):
    """Generate AI-powered MCQs from slide content"""
    from .ai_service import ai_service
    from .content_extractor import get_slide_full_text, ExtractionError
    
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
            slide = visible(Slide, request.user).get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': 'Slide not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract slide content from PDF/PPTX/DOCX
        file_url = content_file_url(slide)
        
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
        
    except ExtractionError as exc:
        return Response({'error': str(exc), 'text_extraction': exc.report}, status=409)
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
@permission_classes([CanWriteUploadedContent, ClassContentReferences])
def reprocess_slide(request, slide_id):
    """
    Reprocess a specific slide (useful for failed slides)
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from .tasks import process_slide_task
        
        # Get the slide
        try:
            slide = visible(Slide, request.user).get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': f'Slide {slide_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        if not CanWriteUploadedContent().has_object_permission(request, None, slide):
            return Response({'error': 'You cannot reprocess this upload.'}, status=403)

        if request.data.get('index_only') is True:
            from .document_index import request_index, status_for
            queued = request_index(slide, force=True)
            return Response({'queued': queued, 'ai_index': status_for(slide)}, status=202)

        from .slide_processing import reserve
        from .slide_uploads import dispatch_slide_processing
        token = reserve(slide_id, manual=True)
        if token is None:
            return Response({'error': 'This document is already being processed.'}, status=409)
        task = dispatch_slide_processing(slide_id, token)
        if task is None:
            return Response({'error': 'Processing could not be queued. Please retry.'}, status=500)

        return Response({
            'message': f'Slide {slide_id} queued for reprocessing',
            'task_id': task.id,
            'slide_title': slide.title
        })
        
    except Exception as e:
        return Response({
            'error': 'Processing could not be queued. Please retry.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([CanWriteUploadedContent, ClassContentReferences])
def reprocess_failed_slides(request):
    """
    Reprocess all slides that previously failed
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from .tasks import process_slide_task
        
        # Get all failed slides
        failed_statuses = visible(SlideProcessingStatus, request.user).filter(status='failed')
        failed_slide_ids = [entry.slide_id for entry in failed_statuses.select_related('slide')
                           if CanWriteUploadedContent().has_object_permission(request, None, entry.slide)]
        
        if not failed_slide_ids:
            return Response({
                'message': 'No failed slides found',
                'queued_count': 0
            })
        
        # Reset their status and queue for reprocessing
        queued_tasks = []
        for slide_id in failed_slide_ids:
            try:
                from .slide_processing import reserve
                from .slide_uploads import dispatch_slide_processing
                token = reserve(slide_id, manual=True)
                if token is None:
                    continue
                task = dispatch_slide_processing(slide_id, token)
                if task is None:
                    continue
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def slide_processing_status(request, slide_id):
    """
    Get processing status for a specific slide
    """
    try:
        from .models import Slide, SlideProcessingStatus
        
        try:
            slide = visible(Slide, request.user).get(id=slide_id)
        except Slide.DoesNotExist:
            return Response({
                'error': f'Slide {slide_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        from learning.bank_sources import bank_status
        generation = bank_status(slide)
        from .document_index import status_for
        from .models import SlideContent
        content = SlideContent.objects.filter(slide=slide, is_extracted=True).first()
        availability = {'reading_ready': bool(content and (content.content_data or {}).get('pages')),
                        'ai_index': status_for(slide)}
        # Get processing status
        try:
            status_obj = SlideProcessingStatus.objects.get(slide=slide)
            return Response({
                'slide_id': slide_id,
                'slide_title': slide.title,
                'question_bank': generation,
                **availability,
                'status': status_obj.status,
                'content_extracted': status_obj.content_extracted,
                'rag_processed': status_obj.rag_processed,
                'is_chunked': status_obj.is_chunked,
                'is_embedded': status_obj.is_embedded,
                'chunk_count': status_obj.chunk_count,
                'started_at': status_obj.started_at,
                'completed_at': status_obj.completed_at,
                'progress': status_obj.processing_progress,
                'attempts': status_obj.processing_attempts,
                'next_attempt_at': status_obj.next_attempt_at,
                'error_message': status_obj.error_message
            })
        except SlideProcessingStatus.DoesNotExist:
            return Response({
                'slide_id': slide_id,
                'slide_title': slide.title,
                'question_bank': generation,
                **availability,
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def processing_overview(request):
    """
    Get overview of all slide processing statuses
    """
    try:
        from .models import Slide, SlideProcessingStatus
        from django.db.models import Count
        
        # Get counts by status
        status_counts = visible(SlideProcessingStatus, request.user).values('status').annotate(count=Count('status'))
        
        # Get total slides
        total_slides = visible(Slide, request.user).count()
        processed_slides = visible(SlideProcessingStatus, request.user).count()
        unprocessed_slides = total_slides - processed_slides
        
        # Format status counts
        status_summary = {item['status']: item['count'] for item in status_counts}
        if unprocessed_slides > 0:
            status_summary['unprocessed'] = unprocessed_slides
        
        # Get recent failures
        recent_failures = visible(SlideProcessingStatus, request.user).filter(
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
class SteeplechaseQuestionViewSet(viewsets.ModelViewSet):
    queryset = SteeplechaseQuestion.objects.all()
    serializer_class = SteeplechaseQuestionSerializer
    permission_classes = [IsAuthenticated, PlatformAdminWritesOnly]
    
    def get_queryset(self):
        from .class_access import content_admin
        from learning.practice import playable_stations
        if content_admin(self.request.user):
            return self.queryset.all()
        return playable_stations(self.request.user)

class FriendChallengeViewSet(viewsets.ModelViewSet):
    queryset = FriendChallenge.objects.all()
    serializer_class = FriendChallengeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(Q(challenger=user) | Q(challenged=user))

    def perform_create(self, serializer):
        serializer.save(challenger=self.request.user)

    @action(detail=True, methods=['patch'])
    def respond(self, request, pk=None):
        challenge = self.get_object()
        status_update = request.data.get('status')
        if status_update in ['accepted', 'declined']:
            challenge.status = status_update
            challenge.save()
            return Response({'status': 'challenge updated'})
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

class BrainBattleViewSet(viewsets.ModelViewSet):
    queryset = BrainBattle.objects.all()
    serializer_class = BrainBattleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from learning.views import _visible_battles
        return _visible_battles(self.request.user)

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from .ai_service import generate_battle_questions
        from .serializers import BattleQuestionSerializer
        
        class_group = upload_class(self.request.user)
        source = serializer.validated_data.pop('question_source', 'ai')
        num_questions = serializer.validated_data.pop('num_questions', 10)
        manual_questions = serializer.validated_data.pop('manual_questions', [])
            
        if source == 'manual':
            serializer.save(host=self.request.user, class_group=class_group, questions=manual_questions)
            return
        battle = serializer.save(host=self.request.user, class_group=class_group)
        
        # Determine topic string from hierarchy
        hierarchy_parts = []
        if battle.linked_subject: hierarchy_parts.append(battle.linked_subject.name)
        if battle.linked_block: hierarchy_parts.append(battle.linked_block.name)
        if battle.linked_sub_block: hierarchy_parts.append(battle.linked_sub_block.name)
        if battle.linked_topic: hierarchy_parts.append(battle.linked_topic.name)
        
        topic_str = " > ".join(hierarchy_parts) or battle.topic or battle.title
        from .library_tutor import library_context
        filters = {name + '_id': getattr(battle, 'linked_' + name + '_id')
                   for name in ('subject', 'block', 'sub_block', 'topic')
                   if getattr(battle, 'linked_' + name + '_id')}
        source_text, _, _ = library_context(self.request.user, topic_str, slide_filters=filters)
        if not source_text:
            battle.delete()
            raise ValidationError('No readable slides are available for this battle yet. Wait for AI preparation or add questions manually.')
        
        # Generating a battle costs AI credits like any other AI action, and the host is
        # the one who pays. A failure here must leave the battle in an honest state
        # rather than a playable-looking one with no questions.
        from credits.services import CreditManager, InsufficientCreditsError

        reservation = None
        try:
            reservation = CreditManager.reserve_credits(
                self.request.user, 'BRAIN_BATTLE', reference_id=f'battle:{battle.pk}',
            )
            questions, tokens = generate_battle_questions(
                topic_str, num_questions=num_questions, difficulty=battle.difficulty,
                return_usage=True,
                source_text=source_text,
            )
            if not isinstance(questions, list) or len(questions) != num_questions:
                raise ValueError('The generator did not return the requested questions.')
            question_serializer = BattleQuestionSerializer(data=questions, many=True)
            question_serializer.is_valid(raise_exception=True)
            from django.db import transaction
            with transaction.atomic():
                battle.questions = question_serializer.validated_data
                battle.save(update_fields=['questions'])
                CreditManager.commit_usage(self.request.user, reservation, tokens)
        except InsufficientCreditsError as exc:
            from rest_framework.exceptions import APIException
            battle.delete()
            error = APIException(str(exc), code='insufficient_credits')
            error.status_code = status.HTTP_402_PAYMENT_REQUIRED
            raise error from None
        except Exception as exc:
            if reservation is not None:
                CreditManager.refund_credits(
                    self.request.user, reservation['reserved_amount'],
                    action='REFUND_BATTLE_ERROR', reservation_id=reservation['reservation_id'],
                )
            battle.delete()
            logger.exception('Battle question generation failed')
            raise ValidationError(
                'Could not generate questions for this battle. Please try again.'
            ) from exc

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied, ValidationError
        battle = self.get_object()
        if battle.host_id != self.request.user.pk:
            raise PermissionDenied('Only the host can edit this battle.')
        if battle.status != 'scheduled':
            raise ValidationError('Started battles cannot be edited.')
        for key in ('question_source', 'num_questions', 'manual_questions'):
            if key in self.request.data:
                raise ValidationError('Create a new battle to change its question bank.')
            serializer.validated_data.pop(key, None)
        serializer.save()

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        battle = self.get_object()
        from learning import battles as battle_service
        try:
            _, participant, created = battle_service.join(request.user, battle.code)
        except battle_service.BattleError as exc:
            return Response({'detail': str(exc), 'code': exc.code}, status=exc.status)
        return Response(
            {'status': 'joined battle', 'newly_joined': created, 'score': participant.score},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        battle = self.get_object()
        from learning import battles as battle_service
        try:
            question = battle_service.advance_question(request.user, battle.pk)
        except battle_service.BattleError as exc:
            return Response({'detail': str(exc), 'code': exc.code}, status=exc.status)
        return Response({'status': 'battle started', 'question': question})

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        battle = self.get_object()
        from learning import battles as battle_service
        try:
            battle_service.end_battle(request.user, battle.pk)
        except battle_service.BattleError as exc:
            return Response({'detail': str(exc), 'code': exc.code}, status=exc.status)
        return Response({'status': 'battle ended'})
        
    def destroy(self, request, *args, **kwargs):
        battle = self.get_object()
        if request.user != battle.host:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        if battle.status != 'scheduled':
            return Response(
                {'detail': 'Started battles cannot be deleted; their results must remain available.'},
                status=status.HTTP_409_CONFLICT,
            )
        battle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -------------------------
# FLASHCARD VIEWS
# -------------------------
class FlashcardViewSet(viewsets.ModelViewSet):
    """
    CRUD endpoints for Flashcards.
    """
    serializer_class = FlashcardSerializer
    permission_classes = [IsAuthenticated, ClassContentReferences]

    def get_queryset(self):
        qs = visible(Flashcard, self.request.user).filter(user=self.request.user)
        for param in ['subject', 'block', 'sub_block', 'topic']:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{f"{param}_id": val})
        
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)

        slide_id = self.request.query_params.get('slide_id')
        if slide_id:
            from .models import Slide
            slide = visible(Slide, self.request.user).filter(pk=slide_id).first()
            if slide is None:
                return qs.none()
            if source == 'ai':
                qs = qs.filter(source_slide=slide)
            elif slide.topic_id:
                qs = qs.filter(topic_id=slide.topic_id)
            else:
                qs = qs.filter(source_slide=slide)
            
        return qs

    @action(detail=False, methods=['get'])
    def due(self, request):
        """Get flashcards that are due for review."""
        now = timezone.now()
        # Find flashcards with no progress (never reviewed) OR due_date <= now
        queryset = self.get_queryset().filter(
            Q(progress_records__isnull=True) | Q(progress_records__due_date__lte=now)
        ).distinct()
        
        # Apply filters like subject, block, sub_block, topic if they exist in query_params
        for param in ['subject', 'block', 'sub_block', 'topic']:
            val = request.query_params.get(param)
            if val:
                queryset = queryset.filter(**{f"{param}_id": val})
                
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Returns flashcard statistics."""
        now = timezone.now()
        user = request.user
        qs = visible(Flashcard, user).filter(user=user)
        due_count = qs.filter(
            Q(progress_records__isnull=True) | Q(progress_records__due_date__lte=now)
        ).distinct().count()
        total_cards = qs.count()
        total_reviews = FlashcardReview.objects.filter(progress__user=user, progress__flashcard__in=qs).count()
        
        # Calculate retention rate
        reviews = FlashcardReview.objects.filter(progress__user=user, progress__flashcard__in=qs)
        successful_reviews = reviews.filter(rating__in=['good', 'easy']).count()
        retention_rate = int((successful_reviews / total_reviews) * 100) if total_reviews > 0 else 0
        
        # Group by topic for decks
        decks_dict = {}
        cards = qs.select_related(
            'topic', 
            'topic__sub_block', 
            'topic__sub_block__block', 
            'topic__sub_block__block__subject',
            'topic__block',
            'topic__block__subject',
            'sub_block',
            'sub_block__block',
            'sub_block__block__subject',
            'block',
            'block__subject',
            'subject'
        ).prefetch_related('progress_records')
        
        for fc in cards:
            if fc.topic:
                topic = fc.topic
                if topic.sub_block:
                    subject_name = topic.sub_block.block.subject.name if topic.sub_block.block and topic.sub_block.block.subject else "Unknown Subject"
                    block_name = topic.sub_block.block.name if topic.sub_block.block else "Unknown Block"
                    sub_block_name = topic.sub_block.name
                    deck_name = f"{subject_name} > {block_name} > {sub_block_name} > {topic.name}"
                elif topic.block:
                    subject_name = topic.block.subject.name if topic.block.subject else "Unknown Subject"
                    block_name = topic.block.name
                    deck_name = f"{subject_name} > {block_name} > {topic.name}"
                else:
                    deck_name = topic.name
                deck_id = f"topic_{topic.id}"
            elif fc.sub_block:
                sub_block = fc.sub_block
                subject_name = sub_block.block.subject.name if sub_block.block and sub_block.block.subject else "Unknown Subject"
                block_name = sub_block.block.name if sub_block.block else "Unknown Block"
                deck_name = f"{subject_name} > {block_name} > {sub_block.name}"
                deck_id = f"sub_block_{sub_block.id}"
            elif fc.block:
                block = fc.block
                subject_name = block.subject.name if block.subject else "Unknown Subject"
                deck_name = f"{subject_name} > {block.name}"
                deck_id = f"block_{block.id}"
            elif fc.subject:
                deck_name = fc.subject.name
                deck_id = f"subject_{fc.subject.id}"
            else:
                deck_name = "General Knowledge"
                deck_id = "general"
                
            if deck_id not in decks_dict:
                decks_dict[deck_id] = {
                    "subject_id": deck_id,
                    "subject_name": deck_name,
                    "total_cards": 0,
                    "due_today": 0
                }
                
            decks_dict[deck_id]["total_cards"] += 1
            
            progress_list = fc.progress_records.all()
            progress = progress_list[0] if progress_list else None
            
            is_due = False
            if not progress or progress.due_date <= now:
                is_due = True
                
            if is_due:
                decks_dict[deck_id]["due_today"] += 1
                
        decks = list(decks_dict.values())
        decks.sort(key=lambda x: x['total_cards'], reverse=True)
        
        return Response({
            "due_today": due_count,
            "total_cards": total_cards,
            "retention_rate": retention_rate,
            "total_reviews": total_reviews,
            "decks": decks,
        })

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Submit a review rating for a flashcard."""
        flashcard = self.get_object()
        rating = request.data.get('rating')
        if rating not in ['again', 'hard', 'good', 'easy']:
            return Response({"error": "Invalid rating"}, status=400)

        progress, created = FlashcardProgress.objects.get_or_create(
            user=request.user, flashcard=flashcard
        )

        previous_interval = progress.interval

        # Simple SM-2 implementation
        if rating == 'again':
            progress.repetitions = 0
            progress.interval = 1
        elif rating == 'hard':
            progress.interval = max(1, int(progress.interval * 1.2))
            progress.repetitions = max(1, progress.repetitions)
        elif rating == 'good':
            progress.interval = max(1, int(progress.interval * progress.ease_factor))
            progress.repetitions += 1
        elif rating == 'easy':
            progress.ease_factor += 0.15
            progress.interval = max(1, int(progress.interval * progress.ease_factor * 1.3))
            progress.repetitions += 1

        if rating == 'again':
            progress.ease_factor = max(1.3, progress.ease_factor - 0.2)

        progress.due_date = timezone.now() + timedelta(days=progress.interval)
        progress.last_reviewed = timezone.now()
        progress.save()

        FlashcardReview.objects.create(
            progress=progress,
            rating=rating,
            previous_interval=previous_interval,
            next_interval=progress.interval
        )

        return Response({
            "rating": rating,
            "previous_interval": previous_interval,
            "next_interval": progress.interval,
            "due_date": progress.due_date
        })
