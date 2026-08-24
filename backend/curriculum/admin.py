from django.contrib import admin
from .models import (
    Subject, Block, SubBlock, Topic, Slide, UserProgress, ScheduleItem,
    UserStats, CommunityPost, PostComment, PostLike, UpcomingTest, QuizQuestion
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'order', 'created_at']
    list_editable = ['order']
    ordering = ['order']


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'name', 'order', 'created_at']
    list_filter = ['subject']
    list_editable = ['order']
    ordering = ['subject', 'order']


@admin.register(SubBlock)
class SubBlockAdmin(admin.ModelAdmin):
    list_display = ['id', 'block', 'name', 'order', 'created_at']
    list_filter = ['block__subject']
    list_editable = ['order']
    ordering = ['block', 'order']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['id', 'sub_block', 'block', 'name', 'order', 'created_at']
    list_filter = ['block__subject', 'sub_block']
    list_editable = ['order']
    ordering = ['block', 'order']


@admin.register(Slide)
class SlideAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'sub_block', 'block', 'uploaded_by', 'created_at']
    list_filter = ['sub_block__block__subject', 'file_type']
    search_fields = ['title', 'id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'slide', 'current_page', 'total_pages', 'completed', 'last_accessed']
    list_filter = ['completed', 'last_accessed']
    search_fields = ['user__username', 'slide__title']
    readonly_fields = ['last_accessed']


@admin.register(ScheduleItem)
class ScheduleItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'activity_type', 'scheduled_date', 'completed']
    list_filter = ['activity_type', 'completed', 'scheduled_date']
    search_fields = ['user__username', 'title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'points', 'rank', 'current_streak', 'school']
    list_filter = ['school', 'public_rank']
    search_fields = ['user__username', 'school']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-points']


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ['user', 'post_type', 'content_preview', 'likes_count', 'comments_count', 'created_at']
    list_filter = ['post_type', 'created_at']
    search_fields = ['user__username', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'content_preview', 'created_at']
    search_fields = ['user__username', 'content']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'created_at']
    readonly_fields = ['created_at']


@admin.register(UpcomingTest)
class UpcomingTestAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'test_date', 'test_time', 'created_by']
    list_filter = ['subject', 'test_date']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']
    filter_horizontal = ['sub_blocks']


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_type', 'difficulty', 'subject', 'sub_block', 'source_type', 'created_at']
    list_filter = ['question_type', 'difficulty', 'subject', 'source_type', 'created_at']
    search_fields = ['id', 'question_text', 'subject__name', 'sub_block__name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'question_type', 'difficulty', 'subject', 'block', 'sub_block')
        }),
        ('Question Content', {
            'fields': ('question_text', 'explanation')
        }),
        ('MCQ Options', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'question_options_order'),
            'classes': ('collapse',)
        }),
        ('Theory Question', {
            'fields': ('model_answer', 'ideal_answer', 'marking_rubric', 'maximum_marks'),
            'classes': ('collapse',)
        }),
        ('Source Information', {
            'fields': ('source_type', 'source_material', 'source_slide', 'source_text'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
