from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from datetime import date
from django.utils import timezone


# -------------------------
# CURRICULUM STRUCTURE
# -------------------------
class Subject(models.Model):
    """Anatomy, Physiology, Biochemistry"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'anatomy'
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Block(models.Model):
    """Block within a subject (e.g., Block 1, Block 2)"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'anatomy-block-1'
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='blocks')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class SubBlock(models.Model):
    """Sub-block within a block (e.g., Gross Anatomy, Histology, Embryology)"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'gross-anatomy'
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='sub_blocks')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.block.name} - {self.name}"


class Topic(models.Model):
    """Topic within a sub-block or directly under a block"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'upper-limb'
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name='topics', null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='topics', null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        parent = self.sub_block or self.block
        return f"{parent.name if parent else 'No Parent'} - {self.name}"


# -------------------------
# SLIDES & MATERIALS
# -------------------------
class Slide(models.Model):
    """Individual slide/material for reading"""
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=200)
    
    # Link to curriculum hierarchy
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    
    # File information - stored in Cloudinary
    file = CloudinaryField('file', null=True, blank=True, resource_type='auto')
    file_url = models.URLField(blank=True)  # Legacy or external URLs
    file_type = models.CharField(max_length=20, default='pdf')  # pdf, pptx, docx
    page_count = models.IntegerField(default=0)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_slides')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def get_file_url(self):
        """Return Cloudinary URL if file exists, otherwise return file_url"""
        if self.file:
            return self.file.url
        return self.file_url
    
    @property
    def subject_name(self):
        """Return subject name if subject exists"""
        return self.subject.name if self.subject else None
    
    @property
    def block_name(self):
        """Return block name if block exists"""
        return self.block.name if self.block else None
    
    @property
    def sub_block_name(self):
        """Return sub-block name if sub-block exists"""
        return self.sub_block.name if self.sub_block else None
    
    @property
    def topic_name(self):
        """Return topic name if topic exists"""
        return self.topic.name if self.topic else None


class SlideContent(models.Model):
    """Extracted content from slides (text and images per page)"""
    slide = models.OneToOneField(Slide, on_delete=models.CASCADE, related_name='content', primary_key=True)
    
    # Extraction status
    is_extracted = models.BooleanField(default=False)
    extraction_error = models.TextField(blank=True)
    
    # Content stored as JSON
    # Format: {"total_pages": 10, "pages": [{"page_number": 1, "content": "text", "images": []}]}
    content_data = models.JSONField(default=dict, blank=True)
    
    # Metadata
    extracted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Content for {self.slide.title}"


class Material(models.Model):
    """Additional materials (videos, images, past questions, PDFs, etc.)"""
    MATERIAL_TYPES = [
        ('video', 'Video'),
        ('image', 'Image'),
        ('pdf', 'PDF Document'),
        ('pptx', 'PowerPoint'),
        ('docx', 'Word Document'),
        ('past_question', 'Past Question'),
        ('other', 'Other'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES)
    
    # Link to curriculum hierarchy
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='materials')
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='materials')
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name='materials', null=True, blank=True)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='materials', null=True, blank=True)
    
    # File information - stored in Cloudinary
    file = CloudinaryField('file', null=True, blank=True, resource_type='auto')
    file_url = models.URLField(blank=True)  # For external URLs (e.g., YouTube)
    file_size = models.BigIntegerField(default=0)  # in bytes
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_materials')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.material_type})"

    @property
    def get_file_url(self):
        """Return Cloudinary URL if file exists, otherwise return file_url"""
        if self.file:
            return self.file.url
        return self.file_url


# -------------------------
# USER PROGRESS
# -------------------------
class UserProgress(models.Model):
    """Track user progress on slides"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='user_progress')
    
    # Progress tracking
    current_page = models.IntegerField(default=1)
    total_pages = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    last_accessed = models.DateTimeField(auto_now=True)
    
    # Time tracking
    time_spent_minutes = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'slide']
        ordering = ['-last_accessed']

    def __str__(self):
        return f"{self.user.username} - {self.slide.title}"

    @property
    def progress_percentage(self):
        if self.total_pages == 0:
            return 0
        return int((self.current_page / self.total_pages) * 100)


class StudyProfile(models.Model):
    """User's personal study goals and configurations for the planner"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='study_profile')
    exam_date = models.DateField(null=True, blank=True)
    daily_study_minutes = models.IntegerField(default=120)
    
    # Store subject IDs or course codes they are focusing on
    target_subjects = models.ManyToManyField('Subject', blank=True, related_name='targeted_by_profiles')
    
    # JSON array of specific topic strings or IDs to focus on
    focus_areas = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Study Profile"


# -------------------------
# SCHEDULE & ACTIVITIES
# -------------------------
class ScheduleItem(models.Model):
    """User's scheduled study activities"""
    ACTIVITY_TYPES = [
        ('read', 'Read'),
        ('quiz', 'Quiz'),
        ('theory', 'Theory Questions'),
        ('flashcards', 'Flashcards'),
        ('steeplechase', 'Steeplechase'),
        ('histology', 'Histology'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedule_items')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    title = models.CharField(max_length=200)
    
    # Link to content
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, null=True, blank=True)
    
    # Scheduling
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    estimated_minutes = models.IntegerField(default=30)
    
    # Completion
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']

    def __str__(self):
        return f"{self.user.username} - {self.title} ({self.scheduled_date})"


# -------------------------
# GAMIFICATION
# -------------------------
class UserStats(models.Model):
    """User statistics and gamification data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stats')
    
    # Points and ranking
    points = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    
    # Streak tracking
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    # School and class info
    school = models.CharField(max_length=200, blank=True)
    set_name = models.CharField(max_length=100, blank=True)
    
    # Privacy settings
    public_profile = models.BooleanField(default=True)
    public_rank = models.BooleanField(default=True)
    
    # Usage tracking
    total_study_minutes = models.IntegerField(default=0)
    slides_completed = models.IntegerField(default=0)
    quizzes_taken = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.points} points"


# -------------------------
# COMMUNITY
# -------------------------
class CommunityPost(models.Model):
    """Community feed posts"""
    POST_TYPES = [
        ('achievement', 'Achievement'),
        ('question', 'Question'),
        ('discussion', 'Discussion'),
        ('resource', 'Resource'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    class_group = models.ForeignKey('accounts.ClassGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='community_posts')
    post_type = models.CharField(max_length=20, choices=POST_TYPES)
    content = models.TextField()
    
    # Optional links
    slide = models.ForeignKey(Slide, on_delete=models.SET_NULL, null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.SET_NULL, null=True, blank=True)
    topic = models.ForeignKey('Topic', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Engagement
    likes_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.post_type} ({self.created_at.date()})"


class PostLike(models.Model):
    """Track post likes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(CommunityPost, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'post']


class PostComment(models.Model):
    """Comments on posts"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(CommunityPost, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} on {self.post.id}"


# -------------------------
# TESTS & ASSESSMENTS
# -------------------------
class UpcomingTest(models.Model):
    """Scheduled tests and exams"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Link to curriculum
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='tests')
    sub_blocks = models.ManyToManyField(SubBlock, blank=True)
    
    # Scheduling
    test_date = models.DateField()
    test_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=60)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['test_date']

    def __str__(self):
        return f"{self.title} - {self.test_date}"


# -------------------------
# STUDY TIME TRACKING
# -------------------------
class DailyStudySession(models.Model):
    """Track daily study time for weekly charts"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_sessions')
    date = models.DateField(default=date.today)
    minutes_studied = models.IntegerField(default=0)
    sessions_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.minutes_studied}min"


# -------------------------
# STEEPLECHASE SYSTEM
# -------------------------
class SteeplechaseQuestion(models.Model):
    """Image-based identification questions (Steeplechase)"""
    id = models.CharField(max_length=50, primary_key=True)
    
    # Curriculum links
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='steeplechase_questions', null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='steeplechase_questions', null=True, blank=True)
    
    # Question content
    image = CloudinaryField('image', resource_type='image', null=True, blank=True)
    image_url = models.URLField(blank=True)  # Local relative URL for now
    
    prompt = models.TextField()
    accepted_answers = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    
    # Extraction metadata
    source_file = models.CharField(max_length=200, blank=True)
    source_page = models.IntegerField(default=0)
    needs_review = models.BooleanField(default=False)
    review_reason = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['source_file', 'source_page', 'id']
        
    def __str__(self):
        return f"{self.id} - {self.prompt[:50]}"


# -------------------------
# QUIZ SYSTEM
# -------------------------
class QuizQuestion(models.Model):
    """Quiz questions (MCQ and Theory)"""
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('theory', 'Theory'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS, default='medium')
    
    # Link to curriculum
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    
    # Question content
    question_text = models.TextField()
    explanation = models.TextField(blank=True)  # Explanation for the answer
    
    # For MCQ
    option_a = models.CharField(max_length=500, blank=True)
    option_b = models.CharField(max_length=500, blank=True)
    option_c = models.CharField(max_length=500, blank=True)
    option_d = models.CharField(max_length=500, blank=True)
    correct_option = models.CharField(max_length=1, blank=True)  # A, B, C, or D
    
    # For Theory
    model_answer = models.TextField(blank=True)  # Model answer for theory questions
    
    # Source tracking
    source_type = models.CharField(max_length=20, choices=[
        ('past_question', 'Past Question'),
        ('ai_generated', 'AI Generated'),
        ('manual', 'Manual'),
    ], default='ai_generated')
    source_material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True)
    source_slide = models.ForeignKey(Slide, on_delete=models.SET_NULL, null=True, blank=True)

    # New fields for quiz examination system
    ideal_answer = models.TextField(blank=True, help_text='Ideal answer for theory questions - used by AI evaluation')
    marking_rubric = models.JSONField(default=list, blank=True, help_text='Structured marking criteria')
    maximum_marks = models.IntegerField(default=20, help_text='Maximum marks for theory questions')
    source_text = models.TextField(blank=True, help_text='Original slide text used to generate this question')
    question_options_order = models.JSONField(default=list, blank=True, help_text='Randomized option order')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.question_type.upper()} - {self.question_text[:50]}"


class Quiz(models.Model):
    """Quiz session"""
    id = models.CharField(max_length=50, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    
    # Quiz configuration
    quiz_type = models.CharField(max_length=10, choices=[('mcq', 'MCQ'), ('theory', 'Theory')])
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    
    questions = models.ManyToManyField(QuizQuestion, related_name='quizzes')
    total_questions = models.IntegerField(default=0)
    
    # Results
    score = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz_type.upper()} - {self.created_at.date()}"


class QuizAnswer(models.Model):
    """User's answer to a quiz question"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    
    # User's answer
    selected_option = models.CharField(max_length=1, blank=True)  # For MCQ
    text_answer = models.TextField(blank=True)  # For Theory
    
    is_correct = models.BooleanField(default=False)  # For MCQ
    ai_score = models.IntegerField(null=True, blank=True)  # For Theory (0-100)
    ai_feedback = models.TextField(blank=True)  # AI feedback for theory answers
    
    time_taken_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['quiz', 'question']
    
    def __str__(self):
        return f"{self.quiz.user.username} - Q{self.question.id}"


# -------------------------
# SLIDE DECK & PAGE RENDERING
# -------------------------
class SlideDeck(models.Model):
    """Uploaded document (PDF, PPTX, DOCX, PPT)"""
    PROCESSING_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('pptx', 'PowerPoint PPTX'),
        ('ppt', 'PowerPoint PPT'),
        ('docx', 'Word Document'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=200)
    
    # Original file
    original_file = CloudinaryField('original_file', resource_type='auto')
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    file_size = models.BigIntegerField(default=0)  # in bytes
    
    # Converted formats (stored in Cloudinary)
    converted_pptx = CloudinaryField('converted_pptx', null=True, blank=True, resource_type='auto')
    converted_pdf = CloudinaryField('converted_pdf', null=True, blank=True, resource_type='auto')
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_decks')
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='pending')
    processing_error = models.TextField(blank=True)
    
    # Stats
    page_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.file_type})"
    
    @property
    def is_processing(self):
        return self.processing_status == 'processing'
    
    @property
    def is_completed(self):
        return self.processing_status == 'completed'
    
    @property
    def has_failed(self):
        return self.processing_status == 'failed'


class SlidePage(models.Model):
    """Rendered page from a slide deck"""
    deck = models.ForeignKey(SlideDeck, on_delete=models.CASCADE, related_name='pages')
    
    slide_number = models.IntegerField()  # 1-based page number
    
    # Rendered image (stored in Cloudinary)
    image = CloudinaryField('image', resource_type='image')
    image_url = models.URLField(blank=True)  # Fallback URL
    
    # Image dimensions
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    
    # Extracted text from this page
    extracted_text = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['deck', 'slide_number']
        ordering = ['slide_number']
    
    def __str__(self):
        return f"{self.deck.title} - Page {self.slide_number}"
    
    @property
    def get_image_url(self):
        """Return Cloudinary URL if image exists, otherwise return image_url"""
        if self.image:
            return self.image.url
        return self.image_url


# -------------------------
# RAG SYSTEM - CHUNKS & EMBEDDINGS
# -------------------------
class SlideChunk(models.Model):
    """Text chunks from slides for RAG retrieval"""
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()  # Order of chunk in the slide
    text = models.TextField()  # The actual text content
    page_number = models.IntegerField(null=True, blank=True)  # Source page
    word_count = models.IntegerField(default=0)
    
    # Embedding vector stored as JSON array
    embedding = models.JSONField(null=True, blank=True)  # Store as list of floats
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['slide', 'chunk_index']
        indexes = [
            models.Index(fields=['slide', 'chunk_index']),
        ]
    
    def __str__(self):
        return f"{self.slide.title} - Chunk {self.chunk_index}"


class SlideChatMessage(models.Model):
    """
    Persisted AI chat history, scoped per student per slide (PRD Â§6.4.3).
    Used to restore conversation context and to enforce daily free-tier limits.
    """
    ROLES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slide_chat_messages')
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)

    role = models.CharField(max_length=10, choices=ROLES)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['user', 'slide', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} [{self.role}] {self.content[:40]}"


class SlideProcessingStatus(models.Model):
    """Track which slides have been chunked and embedded"""
    slide = models.OneToOneField(Slide, on_delete=models.CASCADE, related_name='processing_status', primary_key=True)
    
    # Processing status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')
    
    # RAG processing status
    is_chunked = models.BooleanField(default=False)
    is_embedded = models.BooleanField(default=False)
    chunk_count = models.IntegerField(default=0)
    
    # Content extraction status
    content_extracted = models.BooleanField(default=False)
    rag_processed = models.BooleanField(default=False)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.slide.title} - Status: {self.status}, Chunked: {self.is_chunked}, Embedded: {self.is_embedded}"

# -------------------------
# QUIZ EXAMINATION SYSTEM
# -------------------------
class QuizAttempt(models.Model):
    """Formal quiz/examination attempt with timing and configuration"""
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("submitted", "Submitted"),
        ("auto_submitted", "Auto-Submitted"),
        ("expired", "Expired"),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")
    
    # Configuration
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="quiz_attempts", null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="quiz_attempts", null=True, blank=True)
    sub_block = models.ForeignKey(SubBlock, on_delete=models.CASCADE, related_name="quiz_attempts", null=True, blank=True)
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name="quiz_attempts", null=True, blank=True)
    
    # Exam type and configuration
    exam_type = models.CharField(max_length=20, choices=[
        ("practice", "Practice"),
        ("timed", "Timed Exam"),
        ("untimed", "Untimed Exam"),
        ("mock", "Mock Exam"),
        ("formal", "Formal Exam"),
    ])
    is_timed = models.BooleanField(default=False)
    duration_minutes = models.IntegerField(null=True, blank=True)
    
    # Question configuration stored as JSON
    configuration = models.JSONField(default=dict)
    
    # Ordered question IDs to preserve randomization
    question_ids = models.JSONField(default=list, help_text="Ordered list of question IDs")
    flagged_questions = models.JSONField(default=list, help_text="List of flagged question IDs")
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    
    # Scoring
    mcq_score = models.IntegerField(default=0)
    mcq_total = models.IntegerField(default=0)
    theory_score = models.IntegerField(default=0)
    theory_total = models.IntegerField(default=0)
    overall_percentage = models.FloatField(default=0.0)
    
    # Theory evaluation status
    theory_grading_pending = models.BooleanField(default=False)
    theory_grading_completed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["status", "deadline"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.exam_type} - {self.created_at.date()}"
    
    @property
    def is_expired(self):
        """Check if timed exam has expired"""
        if self.is_timed and self.deadline and self.status == "in_progress":
            from django.utils import timezone
            return timezone.now() > self.deadline
        return False
    
    @property
    def theory_grading_complete(self):
        """Check if all theory questions have been graded"""
        return not self.theory_grading_pending or self.theory_grading_completed

class QuizAttemptResponse(models.Model):
    """Individual question response within a quiz attempt"""
    AI_EVALUATION_STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    
    # MCQ Response
    selected_option = models.CharField(max_length=1, blank=True, help_text="A, B, C, or D for MCQ questions")
    is_correct = models.BooleanField(null=True, blank=True, help_text="True/False for MCQ, null for theory")
    
    # Theory Response
    text_answer = models.TextField(blank=True, help_text="Written answer for theory questions")
    
    # AI Evaluation (for theory questions)
    ai_evaluation_status = models.CharField(max_length=20, choices=AI_EVALUATION_STATUS, default="pending")
    ai_score = models.IntegerField(null=True, blank=True, help_text="AI-assigned score out of maximum marks")
    ai_feedback = models.JSONField(default=dict, blank=True, help_text="Structured AI feedback")
    ai_rubric_breakdown = models.JSONField(default=list, blank=True, help_text="Detailed rubric scoring breakdown")
    ai_evaluation_attempts = models.IntegerField(default=0, help_text="Number of AI evaluation retry attempts")
    
    # Metadata
    answered_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ["attempt", "question"]
        indexes = [
            models.Index(fields=["attempt", "question"]),
            models.Index(fields=["attempt", "ai_evaluation_status"]),
            models.Index(fields=["question", "is_correct"]),
        ]
    
    def __str__(self):
        return f"{self.attempt.user.username} - {self.question.id}"
    
    @property
    def needs_ai_evaluation(self):
        """Check if response needs AI evaluation"""
        return (
            self.question.question_type == "theory" 
            and self.text_answer.strip() 
            and self.ai_evaluation_status == "pending"
        )
    
    @property
    def is_ai_evaluation_complete(self):
        """Check if AI evaluation is complete"""
        return self.ai_evaluation_status == "completed"


# -------------------------
# FLASHCARD SYSTEM
# -------------------------
class Flashcard(models.Model):
    """A user's flashcard — created manually or auto-generated from quiz mistakes."""

    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("quiz_mistake", "Quiz Mistake"),
        ("ai", "AI Generated"),
        ("pdf", "PDF"),
        ("lecture_note", "Lecture Note"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flashcards")

    # Curriculum links (optional)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name="flashcards")
    block = models.ForeignKey(Block, on_delete=models.SET_NULL, null=True, blank=True, related_name="flashcards")
    sub_block = models.ForeignKey(SubBlock, on_delete=models.SET_NULL, null=True, blank=True, related_name="flashcards")
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="flashcards")

    # Source quiz question (for auto-generated cards)
    source_question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_flashcards",
    )

    front = models.TextField()
    back = models.TextField()
    explanation = models.TextField(blank=True)

    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="manual")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One auto-generated card per user per source question (quiz mistakes only)
            models.UniqueConstraint(
                fields=["user", "source_question"],
                condition=models.Q(source="quiz_mistake"),
                name="unique_quiz_mistake_flashcard_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "source"]),
            models.Index(fields=["user", "subject"]),
            models.Index(fields=["user", "topic"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.front[:50]} ({self.source})"


class FlashcardProgress(models.Model):
    """SM-2 spaced repetition state for a user's flashcard."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flashcard_progress")
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name="progress_records")

    due_date = models.DateTimeField(default=timezone.now)
    interval = models.IntegerField(default=0)        # days until next review
    repetitions = models.IntegerField(default=0)     # successful reviews in a row
    ease_factor = models.FloatField(default=2.5)     # SM-2 ease factor
    last_reviewed = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "flashcard"]
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["user", "due_date"]),
        ]

    def __str__(self):
        return f"{self.user.username} — card {self.flashcard_id} due {self.due_date.date()}"

    @property
    def is_due(self):
        return timezone.now() >= self.due_date


class FlashcardReview(models.Model):
    """History record of a single review session for analytics."""

    RATING_CHOICES = [
        ("again", "Again"),
        ("hard", "Hard"),
        ("good", "Good"),
        ("easy", "Easy"),
    ]

    progress = models.ForeignKey(FlashcardProgress, on_delete=models.CASCADE, related_name="reviews")
    rating = models.CharField(max_length=10, choices=RATING_CHOICES)
    reviewed_at = models.DateTimeField(auto_now_add=True)
    previous_interval = models.IntegerField(default=0)
    next_interval = models.IntegerField(default=0)

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"{self.progress.user.username} — {self.rating} — {self.reviewed_at.date()}"


# -------------------------
# SOCIAL & COMPETITION (PHASE 4)
# -------------------------
class FriendChallenge(models.Model):
    """1-on-1 friend challenges."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]

    challenger = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_challenges')
    challenged = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_challenges')
    topic = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    challenger_score = models.IntegerField(default=0)
    challenged_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.challenger.username} vs {self.challenged.username} - {self.status}"


class BrainBattle(models.Model):
    """Live synchronous class-wide quizzes."""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('mixed', 'Mixed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    topic = models.CharField(max_length=200, blank=True, help_text="Topic for AI question generation")
    
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='mixed')
    time_per_question = models.IntegerField(default=20, help_text="Seconds per question")
    
    linked_subject = models.ForeignKey('Subject', on_delete=models.SET_NULL, null=True, blank=True, related_name='battles')
    linked_block = models.ForeignKey('Block', on_delete=models.SET_NULL, null=True, blank=True, related_name='battles')
    linked_sub_block = models.ForeignKey('SubBlock', on_delete=models.SET_NULL, null=True, blank=True, related_name='battles')
    linked_topic = models.ForeignKey('Topic', on_delete=models.SET_NULL, null=True, blank=True, related_name='battles')

    questions = models.JSONField(default=list, blank=True, help_text="List of AI-generated questions")
    current_question_index = models.IntegerField(default=-1, help_text="-1 means not started")
    
    class_group = models.ForeignKey('accounts.ClassGroup', on_delete=models.CASCADE, related_name='brain_battles')
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_battles')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    start_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.class_group.name})"


class BattleParticipant(models.Model):
    """Tracks a user's participation and score in a BrainBattle."""
    battle = models.ForeignKey(BrainBattle, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='battle_participations')
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['battle', 'user']
        ordering = ['-score', 'joined_at']

    def __str__(self):
        return f"{self.user.username} in {self.battle.title} - Score: {self.score}"
