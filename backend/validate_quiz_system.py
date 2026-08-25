#!/usr/bin/env python3
"""
Comprehensive system validation for Quiz Examination System.

Tests end-to-end workflows, subscription enforcement, and system performance.
"""

import os
import sys
import django
import time
import json
from datetime import datetime, timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from curriculum.models import (
    Subject, Block, Topic, QuizQuestion, QuizAttempt, 
    QuizAttemptResponse
)

User = get_user_model()


class SystemValidator:
    """Comprehensive system validation suite."""
    
    def __init__(self):
        self.client = Client()
        self.errors = []
        self.warnings = []
        self.test_results = []
        
    def log_error(self, test_name, error):
        """Log a validation error."""
        self.errors.append(f"❌ {test_name}: {error}")
        
    def log_warning(self, test_name, warning):
        """Log a validation warning."""
        self.warnings.append(f"⚠️  {test_name}: {warning}")
        
    def log_success(self, test_name, message="Passed"):
        """Log a successful test."""
        self.test_results.append(f"✅ {test_name}: {message}")
    
    def validate_database_setup(self):
        """Validate database models and relationships."""
        print("🔍 Validating database setup...")
        
        try:
            # Check if models can be imported and have expected fields
            assert hasattr(QuizAttempt, 'question_ids')
            assert hasattr(QuizAttempt, 'deadline') 
            assert hasattr(QuizAttemptResponse, 'ai_evaluation_status')
            self.log_success("Database Models", "All models have required fields")
        except Exception as e:
            self.log_error("Database Models", f"Model validation failed: {e}")
            
    def cleanup_test_data(self):
        """Clean up any leftover test data from previous runs."""
        print("🧹 Cleaning up leftover test data...")
        User.objects.filter(username__in=['testuser', 'quizuser', 'freeuser']).delete()
        Subject.objects.filter(name__in=['Test Subject', 'Anatomy']).delete()
        QuizQuestion.objects.filter(id__startswith='test-q-').delete()
            
        try:
            # Check if we can create test data
            subject = Subject.objects.get_or_create(id='test-sub-1', name='Test Subject')[0]
            question = QuizQuestion.objects.create(
                id='test-q-db-1',
                subject=subject,
                question_type='mcq',
                difficulty='medium',
                question_text='Test question?',
                option_a='A', option_b='B', option_c='C', option_d='D',
                correct_option='A'
            )
            question.delete()  # Cleanup
            self.log_success("Database Write", "Can create and delete test data")
        except Exception as e:
            self.log_error("Database Write", f"Cannot write to database: {e}")
    
    def validate_api_endpoints(self):
        """Validate core API endpoints are accessible."""
        print("🔍 Validating API endpoints...")
        
        # Create test user
        try:
            user = User.objects.create_user(
                username='test@example.com',
                email='test@example.com', 
                password='testpass123'
            )
            
            # Login
            login_response = self.client.post('/auth/login/', {
                'email': 'test@example.com',
                'password': 'testpass123'
            }, content_type='application/json')
            
            if login_response.status_code == 200:
                token = login_response.json().get('tokens', {}).get('access')
                if token:
                    self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
                    self.log_success("Authentication", "Login successful")
                else:
                    self.log_error("Authentication", "No token returned")
                    return
            else:
                self.log_error("Authentication", f"Login failed: {login_response.status_code}")
                return
                
        except Exception as e:
            self.log_error("User Creation", f"Cannot create test user: {e}")
            return
        
        # Test endpoints
        endpoints = [
            ('GET', '/api/subjects/', 'Subjects List'),
            ('GET', '/api/quiz-attempts/', 'Quiz Attempts List'),
        ]
        
        for method, url, name in endpoints:
            try:
                if method == 'GET':
                    response = self.client.get(url)
                else:
                    response = self.client.post(url, {})
                    
                if response.status_code < 500:
                    self.log_success(f"API {name}", f"{method} {url} accessible")
                else:
                    self.log_error(f"API {name}", f"{method} {url} returned {response.status_code}")
            except Exception as e:
                self.log_error(f"API {name}", f"Exception: {e}")
                
        # Cleanup
        user.delete()
    
    def validate_quiz_workflow(self):
        """Test complete quiz creation -> answer -> submit workflow."""
        print("🔍 Validating quiz workflow...")
        
        try:
            # Setup test data
            user = User.objects.create_user(
                username='quiz@example.com',
                email='quiz@example.com',
                password='testpass123'
            )
            
            subject = Subject.objects.get_or_create(id='test-sub-anat', name='Anatomy')[0]
            
            # Create test questions
            questions = []
            for i in range(3):
                q = QuizQuestion.objects.create(
                    id=f'test-q-wf-{i}',
                    subject=subject,
                    question_type='mcq',
                    difficulty='medium',
                    question_text=f'Test question {i+1}?',
                    option_a='Option A', option_b='Option B', 
                    option_c='Option C', option_d='Option D',
                    correct_option='A'
                )
                questions.append(q)
            
            # Login
            login_response = self.client.post('/auth/login/', {
                'email': 'quiz@example.com',
                'password': 'testpass123'
            }, content_type='application/json')
            
            token = login_response.json().get('tokens', {}).get('access')
            self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
            
            # 1. Create Quiz Attempt
            create_data = {
                'subject': subject.id,
                'exam_type': 'practice',
                'is_timed': False,
                'configuration': {
                    'mcq_count': 3,
                    'theory_count': 0,
                    'difficulty': 'medium'
                }
            }
            
            create_response = self.client.post('/api/quiz-attempts/', 
                                             create_data, 
                                             content_type='application/json')
            
            if create_response.status_code == 201:
                attempt_data = create_response.json()
                attempt_id = attempt_data['id']
                self.log_success("Quiz Creation", f"Created attempt {attempt_id}")
            else:
                self.log_error("Quiz Creation", f"Failed with status {create_response.status_code}")
                return
                
            # 2. Submit Answers
            quiz_questions = attempt_data.get('questions', [])
            for question in quiz_questions[:2]:  # Answer 2 out of 3
                answer_response = self.client.post(
                    f'/api/quiz-attempts/{attempt_id}/submit_answer/',
                    {
                        'question_id': question['id'],
                        'selected_option': 'A'
                    },
                    content_type='application/json'
                )
                
                if answer_response.status_code == 200:
                    self.log_success("Answer Submission", f"Answered question {question['id']}")
                else:
                    self.log_error("Answer Submission", f"Failed for question {question['id']}")
            
            # 3. Submit Quiz
            submit_response = self.client.post(f'/api/quiz-attempts/{attempt_id}/submit/')
            
            if submit_response.status_code == 200:
                submit_data = submit_response.json()
                mcq_score = submit_data.get('mcq_score', 0)
                self.log_success("Quiz Submission", f"Submitted with score {mcq_score}")
            else:
                self.log_error("Quiz Submission", f"Failed with status {submit_response.status_code}")
                
            # 4. Get Results  
            result_response = self.client.get(f'/api/quiz-attempts/{attempt_id}/result/')
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                percentage = result_data.get('overall_percentage', 0)
                self.log_success("Results Retrieval", f"Got results: {percentage}%")
            else:
                self.log_error("Results Retrieval", f"Failed with status {result_response.status_code}")
                
        except Exception as e:
            self.log_error("Quiz Workflow", f"Exception during workflow: {e}")
        finally:
            # Cleanup
            QuizQuestion.objects.filter(subject__name='Anatomy').delete()
            Subject.objects.filter(name='Anatomy').delete()
            User.objects.filter(username='quizuser').delete()
    
    def validate_subscription_enforcement(self):
        """Test subscription limits are properly enforced."""
        print("🔍 Validating subscription enforcement...")
        
        try:
            # Create free tier user (no premium profile)
            user = User.objects.create_user(
                username='free@example.com',
                email='free@example.com',
                password='testpass123'
            )
            
            subject = Subject.objects.get_or_create(id='test-sub-2', name='Test Subject')[0]
            
            # Create enough questions for testing
            for i in range(10):
                QuizQuestion.objects.create(
                    id=f'test-q-sub-{i}',
                    subject=subject,
                    question_type='mcq',
                    difficulty='medium',
                    question_text=f'Question {i}?',
                    option_a='A', option_b='B', option_c='C', option_d='D',
                    correct_option='A'
                )
            
            # Login
            login_response = self.client.post('/auth/login/', {
                'email': 'free@example.com',
                'password': 'testpass123'
            }, content_type='application/json')
            
            token = login_response.json().get('tokens', {}).get('access')
            self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
            
            # Test MCQ limit (free tier should be limited to 5)
            over_limit_data = {
                'subject': subject.id,
                'exam_type': 'practice',
                'is_timed': False,
                'configuration': {
                    'mcq_count': 10,  # Over free limit of 5
                    'theory_count': 0,
                    'difficulty': 'medium'
                }
            }
            
            limit_response = self.client.post('/api/quiz-attempts/', 
                                            over_limit_data,
                                            content_type='application/json')
            
            if limit_response.status_code == 403:
                error_data = limit_response.json()
                if error_data.get('upgrade_required'):
                    self.log_success("Subscription Limits", "MCQ limit properly enforced")
                else:
                    self.log_error("Subscription Limits", "403 returned but no upgrade_required flag")
            else:
                self.log_error("Subscription Limits", f"Expected 403, got {limit_response.status_code}")
                
        except Exception as e:
            self.log_error("Subscription Enforcement", f"Exception: {e}")
        finally:
            # Cleanup
            QuizQuestion.objects.filter(subject__name='Test Subject').delete()
            Subject.objects.filter(name='Test Subject').delete()
            User.objects.filter(username='freeuser').delete()
    
    def validate_performance(self):
        """Check system performance under load."""
        print("🔍 Validating system performance...")
        
        # Test question loading performance
        start_time = time.time()
        try:
            questions = list(QuizQuestion.objects.all()[:100])
            load_time = time.time() - start_time
            
            if load_time < 1.0:
                self.log_success("Query Performance", f"Loaded 100 questions in {load_time:.2f}s")
            else:
                self.log_warning("Query Performance", f"Slow query: {load_time:.2f}s for 100 questions")
                
        except Exception as e:
            self.log_error("Query Performance", f"Failed to load questions: {e}")
    
    def run_all_validations(self):
        """Run all validation tests."""
        print("🚀 Starting comprehensive system validation...\n")
        
        start_time = time.time()
        
        # In Django 1.10+, ALLOWED_HOSTS is checked in test client if DEBUG is False
        # We need to temporarily add 'testserver' to ALLOWED_HOSTS or disable the check
        from django.conf import settings
        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append('testserver')
        
        self.cleanup_test_data()
        
        self.validate_database_setup()
        self.validate_api_endpoints() 
        self.validate_quiz_workflow()
        self.validate_subscription_enforcement()
        self.validate_performance()
        
        total_time = time.time() - start_time
        
        # Print results
        print(f"\n📊 Validation Results (completed in {total_time:.1f}s):")
        print("=" * 60)
        
        for result in self.test_results:
            print(result)
            
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(warning)
                
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(error)
        
        print("\n" + "=" * 60)
        
        if self.errors:
            print(f"❌ VALIDATION FAILED: {len(self.errors)} errors found")
            return False
        elif self.warnings:
            print(f"⚠️  VALIDATION PASSED WITH WARNINGS: {len(self.warnings)} warnings")
            return True
        else:
            print("✅ ALL VALIDATIONS PASSED")
            return True


def main():
    """Main validation entry point."""
    validator = SystemValidator()
    success = validator.run_all_validations()
    
    if not success:
        sys.exit(1)
        
    print("\n🎉 Quiz Examination System is ready for production!")


if __name__ == '__main__':
    main()