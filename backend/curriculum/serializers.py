from rest_framework import serializers
from .hierarchy import ContentAncestryMixin, StableHierarchyMixin, ClassScopedRelationsMixin, validate_ancestry
from .class_access import visible
from .private_media import PrivateAssetSerializerMixin
from .models import (
    Subject, Block, SubBlock, Topic, Slide, Material, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, UpcomingTest, QuizQuestion, Quiz, QuizAnswer,
    SlideDeck, SlidePage, QuizAttempt, QuizAttemptResponse,
    Flashcard, FlashcardProgress, FlashcardReview, StudyProfile,
    FriendChallenge, BrainBattle, BattleParticipant, SteeplechaseQuestion, MediaAsset
)


from django.utils.text import slugify
import uuid

def generate_unique_id(model_class, name, max_length=50):
    base_slug = slugify(name)[:max_length - 9]
    if not base_slug:
        base_slug = "item"
    if not model_class.objects.filter(id=base_slug).exists():
        return base_slug
    while True:
        suffix = str(uuid.uuid4())[:8]
        candidate = f"{base_slug}-{suffix}"
        if not model_class.objects.filter(id=candidate).exists():
            return candidate


class SubjectSerializer(StableHierarchyMixin, serializers.ModelSerializer):
    id = serializers.CharField(max_length=50, required=False, allow_blank=True)

    class Meta:
        model = Subject
        fields = ['class_group', 'id', 'name', 'description', 'order', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Subject, validated_data['name'])
        return super().create(validated_data)


class TopicSerializer(StableHierarchyMixin, serializers.ModelSerializer):
    parent_fields = ('sub_block', 'block')
    id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'order', 'sub_block', 'topic', 'block', 'created_at']

    def to_internal_value(self, data):
        if 'topic' in data and 'sub_block' in data and data['topic'] != data['sub_block']:
            raise serializers.ValidationError({'topic': 'The legacy topic alias must match sub_block.'})
        return super().to_internal_value(data)

    def validate(self, attrs):
        return super().validate(validate_ancestry(attrs, self.instance, topic_record=True))

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Topic, validated_data['name'])
        return super().create(validated_data)


class SubBlockSerializer(StableHierarchyMixin, serializers.ModelSerializer):
    parent_fields = ('block',)
    topics = serializers.SerializerMethodField()
    id = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def get_topics(self, obj):
        request = self.context.get('request')
        qs = visible(Topic, request.user).filter(sub_block=obj) if request else obj.topics.all()
        return TopicSerializer(qs, many=True, context=self.context).data
    
    class Meta:
        model = SubBlock
        fields = ['id', 'block', 'name', 'description', 'order', 'topics', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(SubBlock, validated_data['name'])
        return super().create(validated_data)


class BlockSerializer(StableHierarchyMixin, serializers.ModelSerializer):
    parent_fields = ('subject',)
    sub_blocks = SubBlockSerializer(many=True, read_only=True)
    topics = serializers.SerializerMethodField()
    id = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def get_topics(self, obj):
        return TopicSerializer(obj.topics.filter(sub_block__isnull=True), many=True, context=self.context).data
    
    class Meta:
        model = Block
        fields = ['id', 'subject', 'name', 'description', 'order', 'sub_blocks', 'topics', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Block, validated_data['name'])
        return super().create(validated_data)


class SlideSerializer(PrivateAssetSerializerMixin, ContentAncestryMixin, serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(source='asset', queryset=MediaAsset.objects.none(), required=False)
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Slide
        fields = ['class_group',
            'id', 'title', 'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name',
            'asset_id', 'file_url', 'file_type', 'page_count', 'generation_status',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uploaded_by', 'page_count', 'generation_status', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = str(uuid.uuid4())[:8]
        
        return super().create(validated_data)

    def get_file_url(self, obj):
        return obj.get_file_url


class MaterialSerializer(PrivateAssetSerializerMixin, ContentAncestryMixin, serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(source='asset', queryset=MediaAsset.objects.none(), required=False)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    block_name = serializers.CharField(source='block.name', read_only=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Material
        fields = ['class_group',
            'id', 'title', 'description', 'material_type',
            'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name',
            'asset_id', 'file_url', 'file_size',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uploaded_by', 'file_size', 'created_at', 'updated_at']
    
    def get_file_url(self, obj):
        return obj.get_file_url
    
    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = str(uuid.uuid4())[:8]
        return super().create(validated_data)


class UserProgressSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    slide_title = serializers.CharField(source='slide.title', read_only=True)
    progress_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = UserProgress
        fields = [
            'id', 'slide', 'slide_title', 'current_page', 'total_pages',
            'completed', 'last_accessed', 'time_spent_minutes', 'progress_percentage'
        ]


class StudyProfileSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    target_subjects = serializers.PrimaryKeyRelatedField(many=True, queryset=Subject.objects.all(), required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request:
            data['target_subjects'] = list(visible(Subject, request.user).filter(
                targeted_by_profiles=instance).values_list('pk', flat=True))
        return data
    
    class Meta:
        model = StudyProfile
        fields = [
            'id', 'exam_date', 'daily_study_minutes', 'target_subjects', 'focus_areas'
        ]


class ScheduleItemSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    """Serializer for planner items.

    This previously declared a `topic` field, but ScheduleItem has no such relation — it
    links to `sub_block`. DRF only resolves fields when it serializes an instance, so an
    empty planner returned 200 and the endpoint blew up with ImproperlyConfigured the
    moment a user actually had an item. The frontend never called it, so it went unnoticed.
    """

    slide_title = serializers.CharField(source='slide.title', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)

    class Meta:
        model = ScheduleItem
        fields = [
            'id', 'activity_type', 'title', 'slide', 'slide_title',
            'sub_block', 'sub_block_name', 'block', 'block_name',
            'scheduled_date', 'scheduled_time', 'estimated_minutes',
            'completed', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['completed', 'completed_at', 'created_at', 'updated_at']


class UserStatsSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    name = serializers.CharField(source='user.first_name', read_only=True)
    usage = serializers.SerializerMethodField()
    current_streak = serializers.SerializerMethodField()
    longest_streak = serializers.SerializerMethodField()
    total_study_minutes = serializers.SerializerMethodField()
    quizzes_taken = serializers.SerializerMethodField()
    slides_completed = serializers.SerializerMethodField()

    def progress(self, obj, field):
        from learning.progress_evidence import summary
        return summary(obj.user, self.context)[field]

    def get_current_streak(self, obj):
        return self.progress(obj, 'current_streak')

    def get_longest_streak(self, obj):
        return self.progress(obj, 'longest_streak')

    def get_total_study_minutes(self, obj):
        return self.progress(obj, 'total_study_minutes')

    def get_quizzes_taken(self, obj):
        return self.progress(obj, 'quizzes_taken')

    def get_slides_completed(self, obj):
        return self.progress(obj, 'slides_completed')
    
    class Meta:
        model = UserStats
        fields = [
            'id', 'username', 'name', 'points', 'rank', 'current_streak',
            'longest_streak', 'school', 'set_name', 'public_profile',
            'public_rank', 'total_study_minutes', 'slides_completed', 'quizzes_taken',
            'usage'
        ]
        read_only_fields = ['points', 'rank']

    def get_usage(self, obj):
        from .models import QuizAttempt, Flashcard
        
        # Calculate usage based on available models
        # For non-existent models, return 0 (stub for future features)
        try:
            flashcards_count = Flashcard.objects.filter(user=obj.user).count()
        except Exception:
            flashcards_count = 0
            
        try:
            quizzes_count = QuizAttempt.objects.filter(user=obj.user).count()
        except Exception:
            quizzes_count = obj.quizzes_taken
            
        return {
            'aiQuestionsUsed': 0,
            'flashcardsCreated': flashcards_count,
            'pastQuestionsUsed': 0,
            'quizzesTaken': quizzes_count,
            'steeplechaseAttempts': 0,
            'lastReset': obj.updated_at.isoformat()
        }


class PostCommentSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    
    class Meta:
        model = PostComment
        fields = ['id', 'user', 'user_name', 'content', 'created_at']


class CommunityPostSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    user_photo = serializers.SerializerMethodField()
    comments = PostCommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = CommunityPost
        fields = [
            'id', 'user', 'user_name', 'user_photo', 'post_type', 'content',
            'slide', 'topic', 'likes_count', 'comments_count', 'comments',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'likes_count', 'comments_count', 'created_at', 'updated_at']
    
    def get_user_photo(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile.photo_url:
            return obj.user.profile.photo_url
        return None


class UpcomingTestSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topics = serializers.PrimaryKeyRelatedField(source='sub_blocks', queryset=SubBlock.objects.all(), many=True, required=False)
    topics_list = SubBlockSerializer(source='sub_blocks', many=True, read_only=True)
    
    class Meta:
        model = UpcomingTest
        fields = [
            'id', 'title', 'description', 'subject', 'subject_name',
            'topics', 'topics_list', 'test_date', 'test_time',
            'duration_minutes', 'created_at'
        ]


class SteeplechaseQuestionSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    class Meta:
        model = SteeplechaseQuestion
        fields = ['id', 'image_url', 'prompt', 'source_file']
        
class QuizQuestionSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)
    topic_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    
    class Meta:
        model = QuizQuestion
        fields = [
            'id', 'question_type', 'difficulty', 'subject', 'subject_name',
            'block', 'block_name', 'sub_block', 'sub_block_name',
            'topic', 'topic_name',
            'question_text', 'explanation',
            'option_a', 'option_b', 'option_c', 'option_d', 'correct_option',
            'model_answer', 'source_type', 'created_at',
            'ideal_answer', 'marking_rubric', 'maximum_marks', 'source_text', 'source_page', 'needs_review', 'reviewed_at', 'question_options_order'
        ]
    
        read_only_fields = ['source_page', 'needs_review', 'reviewed_at']

    def to_representation(self, instance):
        """Hide answers and explanations during active attempts"""
        data = super().to_representation(instance)
        
        # Check if answers should be hidden
        hide_answers = self.context.get('hide_answers', False)
        
        if hide_answers:
            data.pop('source_text', None)
            # Hide correct answers and explanations for MCQ questions
            if instance.question_type == 'mcq':
                data.pop('correct_option', None)
                data.pop('explanation', None)
            
            # Hide ideal answers, marking rubric and explanations for theory questions
            if instance.question_type == 'theory':
                data.pop('ideal_answer', None)
                data.pop('marking_rubric', None)
                data.pop('model_answer', None)
                data.pop('explanation', None)
        
        return data


# -------------------------
# SLIDE DECK & PAGE SERIALIZERS
# -------------------------
class SlidePageSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    """Serializer for individual pages in a slide deck"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SlidePage
        fields = [
            'id', 'slide_number', 'image_url', 'width', 'height',
            'extracted_text', 'created_at'
        ]
    
    def get_image_url(self, obj):
        return obj.get_image_url


class SlideDeckSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    """Serializer for slide decks with nested pages"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    pages = SlidePageSerializer(many=True, read_only=True)
    id = serializers.CharField(max_length=50, required=False)
    ai_index = serializers.SerializerMethodField()
    can_prepare_ai = serializers.SerializerMethodField()

    def get_can_prepare_ai(self, obj):
        from .content_permissions import can_reprocess_upload
        request = self.context.get('request')
        return bool(request and can_reprocess_upload(request.user, obj))

    def get_ai_index(self, obj):
        from .document_index import status_for
        return status_for(obj)
    
    class Meta:
        model = SlideDeck
        fields = ['class_group',
            'id', 'title', 'file_type', 'file_size',
            'processing_status', 'processing_error',
            'text_extraction', 'ai_index', 'can_prepare_ai',
            'page_count', 'uploaded_by', 'uploaded_by_name',
            'pages', 'created_at', 'updated_at'
        ]
    
    def get_fields(self):
        fields = super().get_fields()
        for name, field in fields.items():
            if name != 'title':
                field.read_only = True
        return fields

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = f"deck_{str(uuid.uuid4())[:8]}"
        return super().create(validated_data)


class SlideDeckListSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    """Lightweight serializer for listing slide decks"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = SlideDeck
        fields = [
            'id', 'title', 'file_type', 'file_size',
            'processing_status', 'page_count',
            'uploaded_by', 'uploaded_by_name', 'created_at'
        ]


class QuizAnswerSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    question = QuizQuestionSerializer(read_only=True)
    question_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = QuizAnswer
        fields = [
            'id', 'quiz', 'question', 'question_id',
            'selected_option', 'text_answer', 'is_correct',
            'ai_score', 'ai_feedback', 'time_taken_seconds', 'created_at'
        ]


class QuizSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)
    topic_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    answers = QuizAnswerSerializer(many=True, read_only=True)
    questions_list = QuizQuestionSerializer(source='questions', many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'user', 'quiz_type', 'subject', 'subject_name',
            'block', 'block_name', 'sub_block', 'sub_block_name',
            'topic', 'topic_name',
            'questions_list', 'total_questions', 'score',
            'completed', 'completed_at', 'created_at', 'answers'
        ]

# -------------------------
# QUIZ EXAMINATION SYSTEM SERIALIZERS  
# -------------------------
class QuizAttemptResponseSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    question = QuizQuestionSerializer(read_only=True)
    question_id = serializers.CharField(write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from .practice_attempts import public_questions
        if instance.attempt.question_snapshots:
            key = instance.snapshot_question_id or instance.question_id
            data['question'] = next((q for q in public_questions(instance.attempt) if q['id'] == key), None)
        if instance.attempt.status == 'in_progress':
            for key in ('is_correct', 'ai_score', 'ai_feedback', 'ai_rubric_breakdown'):
                data.pop(key, None)
            if data.get('question'):
                for key in ('correct_option', 'explanation', 'ideal_answer', 'model_answer', 'marking_rubric', 'source_text'):
                    data['question'].pop(key, None)
        if instance.attempt.assessment_id and not instance.attempt.assessment.answers_released_at:
            # Written feedback can contain the answer key and rubric text.
            data.pop('ai_feedback', None)
            data.pop('ai_rubric_breakdown', None)
        return data
    
    class Meta:
        model = QuizAttemptResponse
        fields = [
            'id', 'question', 'question_id', 'selected_option', 'text_answer',
            'is_correct', 'ai_evaluation_status', 'ai_score', 'ai_feedback', 'ai_rubric_breakdown',
            'answered_at', 'time_taken_seconds', 'is_flagged', 'created_at', 'updated_at'
        ]
        read_only_fields = ['is_correct', 'ai_evaluation_status', 'ai_score', 'ai_feedback', 'ai_rubric_breakdown']


class QuizAttemptSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    feedback = serializers.SerializerMethodField()

    def to_representation(self, instance):
        from .assessment_history import is_historical, representation
        if is_historical(instance):
            return representation(instance)
        return super().to_representation(instance)

    def get_feedback(self, obj):
        from .assessment_feedback import build
        return build(obj)

    topic_breakdown = serializers.SerializerMethodField()
    grading = serializers.SerializerMethodField()
    answers_released = serializers.SerializerMethodField()

    def get_topic_breakdown(self, obj):
        return obj.analysis_data.get('topic_breakdown', []) if obj.status != 'in_progress' else []

    def get_grading(self, obj):
        from .assessment_grading import public_status
        return public_status(obj)

    def get_answers_released(self, obj):
        return obj.status != 'in_progress' and (not obj.assessment_id or bool(obj.assessment.answers_released_at))

    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)  
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic = serializers.PrimaryKeyRelatedField(queryset=Topic.objects.all(), required=False, allow_null=True)
    topic_name = serializers.SerializerMethodField()
    slide_name = serializers.CharField(source='slide.title', read_only=True, allow_null=True)
    responses = QuizAttemptResponseSerializer(many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    time_taken_minutes = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()

    def get_topic_name(self, obj):
        if obj.topic:
            return obj.topic.name
        if obj.sub_block:
            return obj.sub_block.name
        return None
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'user', 'assessment', 'answers_released', 'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name', 'slide', 'slide_name', 'exam_type', 'is_timed', 'duration_minutes',
            'configuration', 'question_ids', 'flagged_questions', 'status',
            'started_at', 'submitted_at', 'deadline', 'mcq_score', 'mcq_total',
            'theory_score', 'theory_total', 'overall_percentage',
            'theory_grading_pending', 'theory_grading_completed', 'grading', 'topic_breakdown', 'feedback',
            'questions', 'responses', 'time_taken_minutes', 'time_remaining_seconds', 'analysis_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'question_ids', 'status', 'started_at', 'submitted_at',
            'mcq_score', 'mcq_total', 'theory_score', 'theory_total',
            'overall_percentage', 'theory_grading_pending', 'theory_grading_completed'
        ]
    
    def get_questions(self, obj):
        from .models import QuizQuestion
        if obj.question_snapshots:
            from .practice_attempts import public_questions
            return public_questions(obj)
        
        if not obj.question_ids:
            return []
        
        request = self.context.get('request')
        questions = visible(QuizQuestion, request.user if request else obj.user).filter(id__in=obj.question_ids)
        question_dict = {q.id: q for q in questions}
        ordered_questions = [question_dict[qid] for qid in obj.question_ids if qid in question_dict]
        
        if obj.status in ['submitted', 'auto_submitted', 'expired']:
            serializer = QuizQuestionSerializer(ordered_questions, many=True)
        else:
            serializer = QuizQuestionSerializer(
                ordered_questions, 
                many=True,
                context={'hide_answers': True}
            )
        
        return serializer.data
    
    def get_time_taken_minutes(self, obj):
        if obj.started_at and obj.submitted_at:
            delta = obj.submitted_at - obj.started_at
            return delta.total_seconds() / 60.0
        return None
        
    def get_time_remaining_seconds(self, obj):
        if not obj.is_timed or not obj.deadline:
            return None
            
        if obj.status != 'in_progress':
            return 0
            
        from django.utils import timezone
        now = timezone.now()
        if now > obj.deadline:
            return 0
            
        return int((obj.deadline - now).total_seconds())
    
    def validate_configuration(self, value):
        required_fields = ['mcq_count', 'theory_count', 'difficulty']
        
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f'Configuration must include {field}')
        
        mcq_count = value.get('mcq_count', 0)
        theory_count = value.get('theory_count', 0)
        
        if not isinstance(mcq_count, int) or mcq_count < 0:
            raise serializers.ValidationError('mcq_count must be a non-negative integer')
        
        if not isinstance(theory_count, int) or theory_count < 0:
            raise serializers.ValidationError('theory_count must be a non-negative integer')
        
        if mcq_count == 0 and theory_count == 0:
            raise serializers.ValidationError('At least one question type must be selected')
        
        valid_difficulties = ['easy', 'medium', 'hard']
        if value.get('difficulty') not in valid_difficulties:
            raise serializers.ValidationError(f'Difficulty must be one of: {valid_difficulties}')
        
        return value
    
    def validate(self, attrs):
        is_timed = attrs.get('is_timed', False)
        duration_minutes = attrs.get('duration_minutes')
        
        if is_timed and not duration_minutes:
            raise serializers.ValidationError('Timed exams must specify duration_minutes')
        
        if is_timed and (not isinstance(duration_minutes, int) or duration_minutes <= 0):
            raise serializers.ValidationError('duration_minutes must be a positive integer')
        
        if not is_timed and duration_minutes:
            raise serializers.ValidationError('Untimed exams should not specify duration_minutes')
        
        return attrs


class QuizAttemptCreateSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    topic = serializers.PrimaryKeyRelatedField(queryset=Topic.objects.all(), required=False, allow_null=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'subject', 'block', 'sub_block', 'topic', 'slide', 'exam_type', 'is_timed', 
            'duration_minutes', 'configuration'
        ]
    
    def validate_configuration(self, value):
        return QuizAttemptSerializer().validate_configuration(value)
    
    def validate(self, attrs):
        attrs = super().validate(attrs)
        
        topic = attrs.get('topic')
        if topic:
            if not attrs.get('sub_block') and topic.sub_block:
                attrs['sub_block'] = topic.sub_block
            if not attrs.get('block') and topic.block:
                attrs['block'] = topic.block
        
        try:
            from curriculum.ai_views import has_premium_access
            user = self.context['request'].user
            configuration = attrs['configuration']
            
            # Check basic subscription limits
            mcq_count = configuration['mcq_count']
            theory_count = configuration['theory_count']
            
            if not has_premium_access(user):
                if mcq_count > 5:
                    raise serializers.ValidationError({
                        'configuration': 'Free tier allows up to 5 MCQ questions. Upgrade to Premium.',
                        'upgrade_required': True
                    })
                if theory_count > 1:
                    raise serializers.ValidationError({
                        'configuration': 'Free tier allows up to 1 theory question. Upgrade to Premium.',
                        'upgrade_required': True
                    })
                if mcq_count + theory_count > 6:
                    raise serializers.ValidationError({
                        'configuration': 'Free tier allows up to 6 total questions. Upgrade to Premium.',
                        'upgrade_required': True
                    })
        except ImportError:
            pass  # Fallback if service not available
        
        return attrs


class QuizAttemptListSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    time_taken_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'subject_name', 'block_name', 'sub_block_name', 'topic_name', 'exam_type',
            'is_timed', 'status', 'overall_percentage', 'theory_grading_complete',
            'started_at', 'submitted_at', 'time_taken_minutes', 'analysis_data', 'created_at'
        ]

    def get_time_taken_minutes(self, obj):
        if obj.started_at and obj.submitted_at:
            delta = obj.submitted_at - obj.started_at
            return delta.total_seconds() / 60.0
        return None

# -------------------------
# FLASHCARD SERIALIZERS
# -------------------------
class FlashcardProgressSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    is_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = FlashcardProgress
        fields = [
            'id', 'due_date', 'interval', 'repetitions', 'ease_factor',
            'last_reviewed', 'is_due', 'created_at', 'updated_at'
        ]


class FlashcardSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    # Nested read-only progress for the requesting user
    progress = serializers.SerializerMethodField()

    # Readable labels (read-only)
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    source_question_text = serializers.CharField(
        source='source_question.question_text', read_only=True, allow_null=True
    )

    class Meta:
        model = Flashcard
        fields = [
            'id', 'user',
            'subject', 'subject_name',
            'block', 'block_name',
            'sub_block', 'sub_block_name',
            'topic', 'topic_name',
            'source_question', 'source_question_text',
            'source_slide',
            'front', 'back', 'explanation',
            'source',
            'progress',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['user', 'source_question_text', 'source_slide', 'progress']

    def get_progress(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            prog = obj.progress_records.get(user=request.user)
            return FlashcardProgressSerializer(prog).data
        except FlashcardProgress.DoesNotExist:
            return None

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        flashcard = super().create(validated_data)
        # Create initial progress record so card is immediately due for review
        from django.utils import timezone
        FlashcardProgress.objects.get_or_create(
            user=flashcard.user,
            flashcard=flashcard,
            defaults={'due_date': timezone.now()}
        )
        return flashcard


class FlashcardReviewSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    class Meta:
        model = FlashcardReview
        fields = ['id', 'rating', 'reviewed_at', 'previous_interval', 'next_interval']


# -------------------------
# SOCIAL & COMPETITION
# -------------------------

class FriendChallengeSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    challenger_name = serializers.CharField(source='challenger.first_name', read_only=True)
    challenged_name = serializers.CharField(source='challenged.first_name', read_only=True)

    class Meta:
        model = FriendChallenge
        fields = '__all__'
        read_only_fields = ['challenger', 'status', 'challenger_score', 'challenged_score', 'created_at', 'completed_at']


class BattleParticipantSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    name = serializers.CharField(source='user.first_name', read_only=True)

    class Meta:
        model = BattleParticipant
        fields = '__all__'


class BattleQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=3000)
    options = serializers.ListField(
        child=serializers.CharField(max_length=1000), min_length=2, max_length=4,
    )
    correct_index = serializers.IntegerField(min_value=0, max_value=3)
    explanation = serializers.CharField(required=False, allow_blank=True, max_length=5000)

    def validate(self, attrs):
        if attrs['correct_index'] >= len(attrs['options']):
            raise serializers.ValidationError('The correct answer must be one of the options.')
        if len({option.casefold() for option in attrs['options']}) != len(attrs['options']):
            raise serializers.ValidationError('Answer options must be different.')
        return attrs


class BrainBattleSerializer(ClassScopedRelationsMixin, serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.first_name', read_only=True)
    participants_count = serializers.SerializerMethodField()
    question_count = serializers.IntegerField(read_only=True)
    time_per_question = serializers.IntegerField(min_value=5, max_value=300, default=20)
    question_source = serializers.ChoiceField(choices=['ai', 'manual'], default='ai', write_only=True)
    num_questions = serializers.IntegerField(min_value=1, max_value=40, default=10, write_only=True)
    manual_questions = serializers.ListField(
        child=BattleQuestionSerializer(), min_length=1, max_length=40,
        required=False, write_only=True,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('question_source') == 'manual' and not attrs.get('manual_questions'):
            raise serializers.ValidationError({'manual_questions': 'Add at least one question.'})
        if attrs.get('question_source', 'ai') == 'ai' and attrs.get('manual_questions'):
            raise serializers.ValidationError({'question_source': 'Choose manual to use your questions.'})
        return attrs

    class Meta:
        model = BrainBattle
        fields = '__all__'
        # `code` is generated server-side and shared by the host; a client must never
        # be able to choose or overwrite it.
        read_only_fields = [
            'host', 'class_group', 'status', 'start_time', 'created_at', 'code',
            'questions', 'current_question_index', 'current_question_started_at',
            'current_question_revealed_at',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if getattr(getattr(request, 'user', None), 'pk', None) != instance.host_id:
            data['questions'] = []
        return data

    def validate_time_per_question(self, value):
        if not 1 <= value <= 300:
            raise serializers.ValidationError("Time per question must be between 1 and 300 seconds.")
        if self.instance and self.instance.status != "scheduled":
            if value != self.instance.time_per_question:
                raise serializers.ValidationError("Battle timing cannot change after it starts.")
        return value

    def get_participants_count(self, obj):
        return obj.participants.count()
