"""
Database query optimizations for quiz system.

Adds select_related and prefetch_related for efficient question loading.
Optimizes scoring queries with bulk operations.
"""

from django.db import models
from django.db.models import Prefetch


class OptimizedQuizAttemptQuerySet(models.QuerySet):
    """Optimized QuerySet for QuizAttempt with efficient related data loading."""
    
    def with_questions(self):
        """Efficiently load attempt with all related questions and responses."""
        return self.select_related(
            'user', 'subject', 'block', 'topic'
        ).prefetch_related(
            # Prefetch responses with their questions
            Prefetch(
                'responses',
                queryset=QuizAttemptResponse.objects.select_related('question')
                    .order_by('question__question_type', 'id')
            ),
            # Prefetch questions directly for the attempt
            Prefetch(
                'questions',
                queryset=QuizQuestion.objects.select_related('subject', 'block', 'topic')
                    .order_by('question_type', 'id')
            )
        )
    
    def with_basic_info(self):
        """Load attempts with just user and subject info for listings."""
        return self.select_related('user', 'subject', 'block', 'topic')
    
    def active_attempts(self):
        """Get active (in progress) attempts."""
        return self.filter(status='in_progress')
    
    def completed_attempts(self):
        """Get completed attempts with results."""
        return self.filter(status__in=['submitted', 'graded'])


class OptimizedQuizQuestionQuerySet(models.QuerySet):
    """Optimized QuerySet for QuizQuestion with hierarchy data."""
    
    def with_hierarchy(self):
        """Load questions with subject/block/topic info."""
        return self.select_related('subject', 'block', 'topic')
    
    def for_practice(self, slide_id=None):
        """Load questions optimized for practice mode."""
        qs = self.with_hierarchy()
        if slide_id:
            qs = qs.filter(source_slide_id=slide_id)
        return qs.order_by('?')  # Random order for practice
    
    def mcq_questions(self):
        """Filter to MCQ questions only."""
        return self.filter(question_type='mcq')
    
    def theory_questions(self):
        """Filter to theory questions only."""
        return self.filter(question_type='theory')


# Add these managers to the models
def add_optimized_managers():
    """Add optimized managers to QuizAttempt and QuizQuestion models."""
    from .models import QuizAttempt, QuizQuestion
    
    # Add custom managers
    QuizAttempt.add_to_class('optimized', OptimizedQuizAttemptQuerySet.as_manager())
    QuizQuestion.add_to_class('optimized', OptimizedQuizQuestionQuerySet.as_manager())


# Bulk operations for scoring
def bulk_update_responses(attempt, response_updates):
    """
    Efficiently update multiple responses at once.
    
    Args:
        attempt: QuizAttempt instance
        response_updates: List of (response_id, update_dict) tuples
    """
    from .models import QuizAttemptResponse
    
    updates = []
    for response_id, data in response_updates:
        response = QuizAttemptResponse(id=response_id, **data)
        updates.append(response)
    
    if updates:
        QuizAttemptResponse.objects.bulk_update(
            updates, 
            fields=['selected_option', 'text_answer', 'is_correct', 'score', 'updated_at']
        )


def bulk_score_mcq_responses(attempt):
    """
    Efficiently score all MCQ responses for an attempt using bulk operations.
    
    Returns:
        dict: {'correct': int, 'total': int, 'percentage': float}
    """
    from .models import QuizAttemptResponse
    
    # Get all MCQ responses for this attempt with questions
    mcq_responses = list(
        QuizAttemptResponse.objects
        .filter(attempt=attempt, question__question_type='mcq')
        .select_related('question')
    )
    
    correct_count = 0
    updates = []
    
    for response in mcq_responses:
        question = response.question
        is_correct = (
            response.selected_option and 
            response.selected_option.strip().upper() == question.correct_option.strip().upper()
        )
        
        if is_correct:
            correct_count += 1
        
        # Prepare for bulk update
        response.is_correct = is_correct
        updates.append(response)
    
    # Bulk update all responses
    if updates:
        QuizAttemptResponse.objects.bulk_update(updates, ['is_correct'])
    
    total_mcq = len(mcq_responses)
    percentage = (correct_count / total_mcq * 100) if total_mcq > 0 else 0
    
    return {
        'correct': correct_count,
        'total': total_mcq,
        'percentage': percentage
    }


# Caching utilities
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

def cache_question_counts():
    """Cache question counts by subject/difficulty for quick availability checks."""
    from .models import QuizQuestion
    from django.db.models import Count
    
    cache_key = "question_counts_by_subject_difficulty"
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        counts = (
            QuizQuestion.objects
            .values('subject__name', 'difficulty', 'question_type')
            .annotate(count=Count('id'))
            .order_by('subject__name', 'difficulty', 'question_type')
        )
        
        # Organize into nested dict structure
        organized = {}
        for item in counts:
            subject = item['subject__name'] or 'Unknown'
            difficulty = item['difficulty']
            q_type = item['question_type']
            count = item['count']
            
            if subject not in organized:
                organized[subject] = {}
            if difficulty not in organized[subject]:
                organized[subject][difficulty] = {}
            
            organized[subject][difficulty][q_type] = count
        
        # Cache for 5 minutes
        cache.set(cache_key, organized, 300)
        cached_data = organized
    
    return cached_data


def invalidate_question_cache():
    """Invalidate cached question counts when questions are added/removed."""
    cache.delete("question_counts_by_subject_difficulty")


# Performance monitoring decorator
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def monitor_performance(operation_name):
    """Decorator to monitor database operation performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration > 1.0:  # Log slow operations (>1s)
                    logger.warning(
                        f"Slow operation: {operation_name} took {duration:.2f}s",
                        extra={'operation': operation_name, 'duration': duration}
                    )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed operation: {operation_name} failed after {duration:.2f}s: {e}",
                    extra={'operation': operation_name, 'duration': duration, 'error': str(e)}
                )
                raise
        return wrapper
    return decorator