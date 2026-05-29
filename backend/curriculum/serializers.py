from rest_framework import serializers
from .models import (
    Subject, Block, Topic, Section, Slide, Material, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, UpcomingTest, QuizQuestion, Quiz, QuizAnswer,
    SlideDeck, SlidePage
)


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'order', 'created_at']


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name', 'description', 'order', 'created_at']


class TopicSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'order', 'sections', 'created_at']


class BlockSerializer(serializers.ModelSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Block
        fields = ['id', 'subject', 'name', 'description', 'order', 'topics', 'sections', 'created_at']


class SlideSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    section_name = serializers.CharField(source='section.name', read_only=True, allow_null=True)
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Slide
        fields = [
            'id', 'title', 'subject', 'subject_name', 'block', 'block_name',
            'topic', 'topic_name', 'section', 'section_name',
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
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    section_name = serializers.CharField(source='section.name', read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()
    id = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'material_type',
            'subject', 'subject_name', 'block', 'block_name',
            'topic', 'topic_name', 'section', 'section_name',
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


class ScheduleItemSerializer(serializers.ModelSerializer):
    slide_title = serializers.CharField(source='slide.title', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    
    class Meta:
        model = ScheduleItem
        fields = [
            'id', 'activity_type', 'title', 'slide', 'slide_title',
            'topic', 'topic_name', 'block', 'block_name',
            'scheduled_date', 'scheduled_time', 'estimated_minutes',
            'completed', 'completed_at', 'created_at', 'updated_at'
        ]


class UserStatsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    name = serializers.CharField(source='user.first_name', read_only=True)
    
    class Meta:
        model = UserStats
        fields = [
            'id', 'username', 'name', 'points', 'rank', 'current_streak',
            'longest_streak', 'school', 'set_name', 'public_profile',
            'public_rank', 'total_study_minutes', 'slides_completed', 'quizzes_taken'
        ]


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


class QuizQuestionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    
    class Meta:
        model = QuizQuestion
        fields = [
            'id', 'question_type', 'difficulty', 'subject', 'subject_name',
            'block', 'block_name', 'topic', 'topic_name',
            'question_text', 'explanation',
            'option_a', 'option_b', 'option_c', 'option_d', 'correct_option',
            'model_answer', 'source_type', 'created_at'
        ]


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
    topic_name = serializers.CharField(source='topic.name', read_only=True, allow_null=True)
    answers = QuizAnswerSerializer(many=True, read_only=True)
    questions_list = QuizQuestionSerializer(source='questions', many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'user', 'quiz_type', 'subject', 'subject_name',
            'block', 'block_name', 'topic', 'topic_name',
            'questions_list', 'total_questions', 'score',
            'completed', 'completed_at', 'created_at', 'answers'
        ]
