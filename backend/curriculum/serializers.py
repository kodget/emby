from rest_framework import serializers
from .models import (
    Subject, Block, SubBlock, Topic, Slide, Material, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, UpcomingTest, QuizQuestion, Quiz, QuizAnswer,
    SlideDeck, SlidePage, QuizAttempt, QuizAttemptResponse,
    Flashcard, FlashcardProgress, FlashcardReview, StudyProfile,
    FriendChallenge, BrainBattle, BattleParticipant, SteeplechaseQuestion
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


class SubjectSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'order', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Subject, validated_data['name'])
        return super().create(validated_data)


class TopicSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, allow_blank=True)
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'order', 'sub_block', 'topic', 'block', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Topic, validated_data['name'])
        return super().create(validated_data)


class SubBlockSerializer(serializers.ModelSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    id = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = SubBlock
        fields = ['id', 'block', 'name', 'description', 'order', 'topics', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(SubBlock, validated_data['name'])
        return super().create(validated_data)


class BlockSerializer(serializers.ModelSerializer):
    sub_blocks = SubBlockSerializer(many=True, read_only=True)
    topics = TopicSerializer(many=True, read_only=True)
    id = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Block
        fields = ['id', 'subject', 'name', 'description', 'order', 'sub_blocks', 'topics', 'created_at']

    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            validated_data['id'] = generate_unique_id(Block, validated_data['name'])
        return super().create(validated_data)


class SlideSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Slide
        fields = [
            'id', 'title', 'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name',
            'file_url', 'file_type', 'page_count',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = str(uuid.uuid4())[:8]
        
        # If file_url is provided, try to extract Cloudinary public_id and populate file field
        file_url = validated_data.get('file_url')
        if file_url and 'cloudinary.com' in file_url:
            try:
                # Extract public_id from Cloudinary URL
                # URL format: https://res.cloudinary.com/cloud_name/resource_type/upload/public_id.ext
                import re
                from cloudinary import CloudinaryResource
                
                # Extract public_id from URL
                match = re.search(r'/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$', file_url)
                if match:
                    public_id = match.group(1)
                    
                    # Create CloudinaryResource and assign to file field
                    validated_data['file'] = CloudinaryResource(
                        public_id=public_id,
                        resource_type='raw'  # For PDFs, PPTX, etc.
                    )
                    
                    print(f"Extracted Cloudinary public_id: {public_id}")
                else:
                    print(f"Could not extract public_id from URL: {file_url}")
            except Exception as e:
                print(f"Error processing Cloudinary URL: {e}")
                # Keep file_url as fallback
        
        return super().create(validated_data)


class MaterialSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    block_name = serializers.CharField(source='block.name', read_only=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'material_type',
            'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name',
            'file_url', 'file_size',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at'
        ]
    
    def get_file_url(self, obj):
        return obj.get_file_url
    
    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = str(uuid.uuid4())[:8]
        return super().create(validated_data)


class UserProgressSerializer(serializers.ModelSerializer):
    slide_title = serializers.CharField(source='slide.title', read_only=True)
    progress_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = UserProgress
        fields = [
            'id', 'slide', 'slide_title', 'current_page', 'total_pages',
            'completed', 'last_accessed', 'time_spent_minutes', 'progress_percentage'
        ]


class StudyProfileSerializer(serializers.ModelSerializer):
    target_subjects = serializers.PrimaryKeyRelatedField(many=True, queryset=Subject.objects.all(), required=False)
    
    class Meta:
        model = StudyProfile
        fields = [
            'id', 'exam_date', 'daily_study_minutes', 'target_subjects', 'focus_areas'
        ]


class ScheduleItemSerializer(serializers.ModelSerializer):
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
        read_only_fields = ['completed_at', 'created_at', 'updated_at']


class UserStatsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    name = serializers.CharField(source='user.first_name', read_only=True)
    usage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserStats
        fields = [
            'id', 'username', 'name', 'points', 'rank', 'current_streak',
            'longest_streak', 'school', 'set_name', 'public_profile',
            'public_rank', 'total_study_minutes', 'slides_completed', 'quizzes_taken',
            'usage'
        ]

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


class PostCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    
    class Meta:
        model = PostComment
        fields = ['id', 'user', 'user_name', 'content', 'created_at']


class CommunityPostSerializer(serializers.ModelSerializer):
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


class UpcomingTestSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topics_list = TopicSerializer(source='topics', many=True, read_only=True)
    
    class Meta:
        model = UpcomingTest
        fields = [
            'id', 'title', 'description', 'subject', 'subject_name',
            'topics', 'topics_list', 'test_date', 'test_time',
            'duration_minutes', 'created_at'
        ]


class SteeplechaseQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SteeplechaseQuestion
        fields = ['id', 'image_url', 'prompt', 'source_file']
        
class QuizQuestionSerializer(serializers.ModelSerializer):
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
            'ideal_answer', 'marking_rubric', 'maximum_marks', 'source_text', 'question_options_order'
        ]
    
    def to_representation(self, instance):
        """Hide answers and explanations during active attempts"""
        data = super().to_representation(instance)
        
        # Check if answers should be hidden
        hide_answers = self.context.get('hide_answers', False)
        
        if hide_answers:
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
class SlidePageSerializer(serializers.ModelSerializer):
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


class SlideDeckSerializer(serializers.ModelSerializer):
    """Serializer for slide decks with nested pages"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    pages = SlidePageSerializer(many=True, read_only=True)
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = SlideDeck
        fields = [
            'id', 'title', 'file_type', 'file_size',
            'processing_status', 'processing_error',
            'page_count', 'uploaded_by', 'uploaded_by_name',
            'pages', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        if 'id' not in validated_data or not validated_data['id']:
            import uuid
            validated_data['id'] = f"deck_{str(uuid.uuid4())[:8]}"
        return super().create(validated_data)


class SlideDeckListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing slide decks"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = SlideDeck
        fields = [
            'id', 'title', 'file_type', 'file_size',
            'processing_status', 'page_count',
            'uploaded_by', 'uploaded_by_name', 'created_at'
        ]


class QuizAnswerSerializer(serializers.ModelSerializer):
    question = QuizQuestionSerializer(read_only=True)
    question_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = QuizAnswer
        fields = [
            'id', 'quiz', 'question', 'question_id',
            'selected_option', 'text_answer', 'is_correct',
            'ai_score', 'ai_feedback', 'time_taken_seconds', 'created_at'
        ]


class QuizSerializer(serializers.ModelSerializer):
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
class QuizAttemptResponseSerializer(serializers.ModelSerializer):
    question = QuizQuestionSerializer(read_only=True)
    question_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = QuizAttemptResponse
        fields = [
            'id', 'question', 'question_id', 'selected_option', 'text_answer',
            'is_correct', 'ai_evaluation_status', 'ai_score', 'ai_feedback', 'ai_rubric_breakdown',
            'answered_at', 'time_taken_seconds', 'is_flagged', 'created_at', 'updated_at'
        ]
        read_only_fields = ['is_correct', 'ai_evaluation_status', 'ai_score', 'ai_feedback', 'ai_rubric_breakdown']


class QuizAttemptSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)  
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)
    topic_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    slide_name = serializers.CharField(source='slide.title', read_only=True, allow_null=True)
    responses = QuizAttemptResponseSerializer(many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'user', 'subject', 'subject_name', 'block', 'block_name',
            'sub_block', 'sub_block_name', 'topic', 'topic_name', 'slide', 'slide_name', 'exam_type', 'is_timed', 'duration_minutes',
            'configuration', 'question_ids', 'flagged_questions', 'status',
            'started_at', 'submitted_at', 'deadline', 'mcq_score', 'mcq_total',
            'theory_score', 'theory_total', 'overall_percentage',
            'theory_grading_pending', 'theory_grading_completed',
            'questions', 'responses', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'question_ids', 'status', 'started_at', 'submitted_at',
            'mcq_score', 'mcq_total', 'theory_score', 'theory_total',
            'overall_percentage', 'theory_grading_pending', 'theory_grading_completed'
        ]
    
    def get_questions(self, obj):
        from .models import QuizQuestion
        
        if not obj.question_ids:
            return []
        
        questions = QuizQuestion.objects.filter(id__in=obj.question_ids)
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


class QuizAttemptCreateSerializer(serializers.ModelSerializer):
    topic = serializers.PrimaryKeyRelatedField(source='sub_block', queryset=SubBlock.objects.all(), required=False, allow_null=True)
    
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


class QuizAttemptListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    sub_block_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='sub_block.name', read_only=True, allow_null=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'subject_name', 'block_name', 'sub_block_name', 'topic_name', 'exam_type',
            'is_timed', 'status', 'overall_percentage', 'theory_grading_complete',
            'started_at', 'submitted_at', 'created_at'
        ]


# -------------------------
# FLASHCARD SERIALIZERS
# -------------------------
class FlashcardProgressSerializer(serializers.ModelSerializer):
    is_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = FlashcardProgress
        fields = [
            'id', 'due_date', 'interval', 'repetitions', 'ease_factor',
            'last_reviewed', 'is_due', 'created_at', 'updated_at'
        ]


class FlashcardSerializer(serializers.ModelSerializer):
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
            'front', 'back', 'explanation',
            'source',
            'progress',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['user', 'source_question_text', 'progress']

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


class FlashcardReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlashcardReview
        fields = ['id', 'rating', 'reviewed_at', 'previous_interval', 'next_interval']


# -------------------------
# SOCIAL & COMPETITION
# -------------------------

class FriendChallengeSerializer(serializers.ModelSerializer):
    challenger_name = serializers.CharField(source='challenger.first_name', read_only=True)
    challenged_name = serializers.CharField(source='challenged.first_name', read_only=True)

    class Meta:
        model = FriendChallenge
        fields = '__all__'
        read_only_fields = ['challenger', 'status', 'challenger_score', 'challenged_score', 'created_at', 'completed_at']


class BattleParticipantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    name = serializers.CharField(source='user.first_name', read_only=True)

    class Meta:
        model = BattleParticipant
        fields = '__all__'


class BrainBattleSerializer(serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.first_name', read_only=True)
    participants_count = serializers.SerializerMethodField()

    class Meta:
        model = BrainBattle
        fields = '__all__'
        # `code` is generated server-side and shared by the host; a client must never
        # be able to choose or overwrite it.
        read_only_fields = [
            'host', 'class_group', 'status', 'start_time', 'created_at', 'code',
        ]

    def get_participants_count(self, obj):
        return obj.participants.count()
