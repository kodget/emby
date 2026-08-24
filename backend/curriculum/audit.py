"""
Audit logging for critical quiz system operations.

Tracks attempt creation, submission, scoring, and AI evaluation events.
Records subscription limit enforcement for compliance.
"""

import logging
import json
from datetime import datetime
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Create dedicated audit logger
audit_logger = logging.getLogger('audit.quiz')


class QuizAuditLogger:
    """Centralized audit logging for quiz system operations."""
    
    @staticmethod
    def log_attempt_created(user, attempt, config_data):
        """Log quiz attempt creation with configuration."""
        audit_logger.info("Quiz attempt created", extra={
            'event_type': 'attempt_created',
            'user_id': user.id,
            'username': user.username,
            'attempt_id': attempt.id,
            'exam_type': attempt.exam_type,
            'is_timed': attempt.is_timed,
            'duration_minutes': attempt.duration_minutes,
            'mcq_count': config_data.get('mcq_count', 0),
            'theory_count': config_data.get('theory_count', 0),
            'difficulty': config_data.get('difficulty'),
            'subject': attempt.subject.name if attempt.subject else None,
            'block': attempt.block.name if attempt.block else None,
            'topic': attempt.topic.name if attempt.topic else None,
            'is_premium': hasattr(user, 'profile') and user.profile.is_premium,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_answer_submitted(user, attempt, question, answer_data, is_update=False):
        """Log answer submission or update."""
        event_type = 'answer_updated' if is_update else 'answer_submitted'
        
        # Sanitize answer data (don't log the actual answers for privacy)
        sanitized_data = {
            'question_id': question.id,
            'question_type': question.question_type,
            'has_answer': bool(answer_data.get('selected_option') or answer_data.get('text_answer')),
            'answer_length': len(answer_data.get('text_answer', '')) if answer_data.get('text_answer') else 0,
        }
        
        audit_logger.info(f"Answer {event_type.split('_')[1]}", extra={
            'event_type': event_type,
            'user_id': user.id,
            'username': user.username,
            'attempt_id': attempt.id,
            'answer_data': sanitized_data,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_question_flagged(user, attempt, question_id, is_flagged):
        """Log question flagging/unflagging."""
        action = 'flagged' if is_flagged else 'unflagged'
        
        audit_logger.info(f"Question {action}", extra={
            'event_type': f'question_{action}',
            'user_id': user.id,
            'username': user.username,
            'attempt_id': attempt.id,
            'question_id': question_id,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_attempt_submitted(user, attempt, submission_type='manual'):
        """Log quiz attempt submission."""
        audit_logger.info("Quiz attempt submitted", extra={
            'event_type': 'attempt_submitted',
            'user_id': user.id,
            'username': user.username,
            'attempt_id': attempt.id,
            'submission_type': submission_type,  # 'manual' or 'auto'
            'mcq_score': attempt.mcq_score,
            'mcq_total': attempt.mcq_total,
            'theory_total': attempt.theory_total,
            'flagged_questions_count': len(attempt.flagged_questions) if attempt.flagged_questions else 0,
            'time_taken_seconds': (timezone.now() - attempt.created_at).total_seconds(),
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_mcq_scoring_completed(attempt, scoring_results):
        """Log MCQ scoring completion."""
        audit_logger.info("MCQ scoring completed", extra={
            'event_type': 'mcq_scoring_completed',
            'attempt_id': attempt.id,
            'user_id': attempt.user.id,
            'correct_answers': scoring_results.get('correct', 0),
            'total_mcq': scoring_results.get('total', 0),
            'mcq_percentage': scoring_results.get('percentage', 0),
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_theory_evaluation_started(attempt, question_ids):
        """Log start of AI theory evaluation."""
        audit_logger.info("Theory evaluation started", extra={
            'event_type': 'theory_evaluation_started',
            'attempt_id': attempt.id,
            'user_id': attempt.user.id,
            'theory_question_count': len(question_ids),
            'question_ids': question_ids,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_theory_evaluation_completed(attempt, evaluation_results):
        """Log completion of AI theory evaluation."""
        # Sanitize results (don't log detailed feedback for privacy)
        sanitized_results = []
        for result in evaluation_results:
            sanitized_results.append({
                'question_id': result.get('question_id'),
                'success': result.get('success', False),
                'score': result.get('score'),
                'max_score': result.get('max_score'),
                'has_feedback': bool(result.get('feedback')),
                'evaluation_time_seconds': result.get('evaluation_time_seconds', 0),
            })
        
        audit_logger.info("Theory evaluation completed", extra={
            'event_type': 'theory_evaluation_completed',
            'attempt_id': attempt.id,
            'user_id': attempt.user.id,
            'theory_score': attempt.theory_score,
            'theory_total_possible': attempt.theory_total * 10,  # Assuming 10 points per theory question
            'overall_percentage': attempt.overall_percentage,
            'evaluation_results': sanitized_results,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_theory_evaluation_failed(attempt, error_message):
        """Log failed AI theory evaluation."""
        audit_logger.error("Theory evaluation failed", extra={
            'event_type': 'theory_evaluation_failed',
            'attempt_id': attempt.id,
            'user_id': attempt.user.id,
            'error_message': str(error_message),
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_subscription_limit_enforced(user, limit_type, requested, allowed):
        """Log subscription limit enforcement."""
        audit_logger.warning("Subscription limit enforced", extra={
            'event_type': 'subscription_limit_enforced',
            'user_id': user.id,
            'username': user.username,
            'limit_type': limit_type,  # 'mcq_count', 'theory_count', 'total_questions', 'concurrent_attempts'
            'requested': requested,
            'allowed': allowed,
            'is_premium': hasattr(user, 'profile') and user.profile.is_premium,
            'subscription_tier': getattr(user.profile, 'subscription_tier', 'free') if hasattr(user, 'profile') else 'free',
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_ai_rate_limit_hit(service_name, attempt_id=None, retry_count=0):
        """Log AI service rate limit encounters."""
        audit_logger.warning("AI service rate limit hit", extra={
            'event_type': 'ai_rate_limit_hit',
            'service_name': service_name,  # 'question_generation', 'theory_evaluation'
            'attempt_id': attempt_id,
            'retry_count': retry_count,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_premium_feature_accessed(user, feature_name, attempt_id=None):
        """Log access to premium-only features."""
        audit_logger.info("Premium feature accessed", extra={
            'event_type': 'premium_feature_accessed',
            'user_id': user.id,
            'username': user.username,
            'feature_name': feature_name,  # 'missed_questions', 'detailed_analysis', 'mock_exam', etc.
            'attempt_id': attempt_id,
            'is_premium': hasattr(user, 'profile') and user.profile.is_premium,
            'timestamp': timezone.now().isoformat(),
        })
    
    @staticmethod
    def log_security_event(user, event_type, details):
        """Log security-related events."""
        audit_logger.critical("Security event detected", extra={
            'event_type': f'security_{event_type}',
            'user_id': user.id if user else None,
            'username': user.username if user else None,
            'details': details,
            'ip_address': getattr(user, 'last_known_ip', None) if user else None,
            'user_agent': getattr(user, 'last_user_agent', None) if user else None,
            'timestamp': timezone.now().isoformat(),
        })


# Convenience functions for common audit events
def audit_attempt_created(user, attempt, config_data):
    """Convenience function for logging attempt creation."""
    QuizAuditLogger.log_attempt_created(user, attempt, config_data)

def audit_answer_submitted(user, attempt, question, answer_data, is_update=False):
    """Convenience function for logging answer submission."""
    QuizAuditLogger.log_answer_submitted(user, attempt, question, answer_data, is_update)

def audit_attempt_submitted(user, attempt, submission_type='manual'):
    """Convenience function for logging attempt submission."""
    QuizAuditLogger.log_attempt_submitted(user, attempt, submission_type)

def audit_subscription_limit_enforced(user, limit_type, requested, allowed):
    """Convenience function for logging subscription limit enforcement."""
    QuizAuditLogger.log_subscription_limit_enforced(user, limit_type, requested, allowed)

def audit_premium_feature_accessed(user, feature_name, attempt_id=None):
    """Convenience function for logging premium feature access."""
    QuizAuditLogger.log_premium_feature_accessed(user, feature_name, attempt_id)


# Integration with Django logging system
# Add this to Django settings.py:
"""
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'audit': {
            'format': '[{asctime}] {name} {levelname}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/audit.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'audit',
        },
        'audit_console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'audit',
        },
    },
    'loggers': {
        'audit.quiz': {
            'handlers': ['audit_file', 'audit_console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
"""