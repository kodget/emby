from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from datetime import date


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


class Topic(models.Model):
    """Topic within a block (e.g., Gross Anatomy, Histology, Embryology)"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'gross-anatomy'
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.block.name} - {self.name}"


class Section(models.Model):
    """Section within a topic (e.g., Upper Limb, Lower Limb within Gross Anatomy Block 1)"""
    id = models.CharField(max_length=50, primary_key=True)  # e.g., 'upper-limb'
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='sections', null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='sections', null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        parent = self.topic or self.block
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
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    section = models.ForeignKey('Section', on_delete=models.CASCADE, related_name='slides', null=True, blank=True)
    
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
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='materials', null=True, blank=True)
    section = models.ForeignKey('Section', on_delete=models.CASCADE, related_name='materials', null=True, blank=True)
    
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


# -------------------------
# SCHEDULE & ACTIVITIES
# -------------------------
class ScheduleItem(models.Model):
    """User's scheduled study activities"""
    ACTIVITY_TYPES = [
        ('read', 'Read'),
        ('quiz', 'Quiz'),
        ('flashcards', 'Flashcards'),
        ('steeplechase', 'Steeplechase'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedule_items')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    title = models.CharField(max_length=200)
    
    # Link to content
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, null=True, blank=True)
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
    post_type = models.CharField(max_length=20, choices=POST_TYPES)
    content = models.TextField()
    
    # Optional links
    slide = models.ForeignKey(Slide, on_delete=models.SET_NULL, null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    
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
    topics = models.ManyToManyField(Topic, blank=True)
    
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
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    
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
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    
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
