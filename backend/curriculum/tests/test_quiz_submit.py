"""
Tests for Quiz Attempt Submit Endpoint (Task 5.1)

Tests the manual submit endpoint implementation:
- MCQ scoring logic
- Theory evaluation queuing
- Status transitions
- Timestamp management
- Response format
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
import uuid

from curriculum.models import (
    Subject, Block, SubBlock, Topic, QuizQuestion, QuizAttempt, QuizAttemptResponse
)


class QuizAttemptSubmitTestCase(TestCase):
    """Test suite for quiz attempt submission (Task 5.1)"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        # Create curriculum structure
        self.subject = Subject.objects.create(
            id='test-subject',
            name='Test Subject',
            order=1
        )
        
        self.block = Block.objects.create(
            id='test-block',
            subject=self.subject,
            name='Test Block',
            order=1
        )
        
        self.sub_block = SubBlock.objects.create(
            id='test-sub-block',
            block=self.block,
            name='Test SubBlock',
            order=1
        )
        self.topic = Topic.objects.create(
            id='test-topic',
            sub_block=self.sub_block,
            block=self.block,
            name='Test Topic',
            order=1
        )
        
        # Create MCQ questions
        self.mcq_questions = []
        for i in range(5):
            question = QuizQuestion.objects.create(
                id=f'mcq-{i+1}',
                question_type='mcq',
                difficulty='medium',
                subject=self.subject,
                block=self.block,
                sub_block=self.sub_block,
                question_text=f'MCQ Question {i+1}',
                option_a='Option A',
                option_b='Option B',
                option_c='Option C',
                option_d='Option D',
                correct_option='A',
                explanation=f'Explanation for question {i+1}'
            )
            self.mcq_questions.append(question)
        
        # Create theory questions
        self.theory_questions = []
        for i in range(2):
            question = QuizQuestion.objects.create(
                id=f'theory-{i+1}',
                question_type='theory',
                difficulty='medium',
                subject=self.subject,
                block=self.block,
                sub_block=self.sub_block,
                question_text=f'Theory Question {i+1}',
                ideal_answer=f'Ideal answer for theory question {i+1}',
                marking_rubric=[
                    {'criterion': 'Understanding', 'marks': 10},
                    {'criterion': 'Detail', 'marks': 10}
                ],
                maximum_marks=20
            )
            self.theory_questions.append(question)
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def create_attempt_with_responses(self, mcq_count=5, theory_count=0, answer_mcqs=True):
        """Helper method to create an attempt with responses"""
        # Create attempt
        attempt = QuizAttempt.objects.create(
            id=str(uuid.uuid4())[:12],
            user=self.user,
            subject=self.subject,
            block=self.block,
            sub_block=self.sub_block,
            exam_type='practice',
            is_timed=False,
            configuration={
                'mcq_count': mcq_count,
                'theory_count': theory_count,
                'difficulty': 'medium'
            },
            question_ids=[q.id for q in (self.mcq_questions[:mcq_count] + self.theory_questions[:theory_count])],
            status='in_progress',
            mcq_total=mcq_count,
            theory_total=theory_count,
            theory_grading_pending=(theory_count > 0)
        )
        
        # Create MCQ responses
        for i, question in enumerate(self.mcq_questions[:mcq_count]):
            response = QuizAttemptResponse.objects.create(
                attempt=attempt,
                question=question,
                ai_evaluation_status='na'
            )
            
            if answer_mcqs:
                # Answer correctly for first 3, incorrectly for rest
                if i < 3:
                    response.selected_option = 'A'  # Correct
                    response.is_correct = True
                else:
                    response.selected_option = 'B'  # Incorrect
                    response.is_correct = False
                response.answered_at = timezone.now()
                response.save()
        
        # Create theory responses
        for question in self.theory_questions[:theory_count]:
            QuizAttemptResponse.objects.create(
                attempt=attempt,
                question=question,
                text_answer='This is a sample theory answer.',
                ai_evaluation_status='pending',
                answered_at=timezone.now()
            )
        
        return attempt
    
    def test_submit_mcq_only_attempt(self):
        """Test submitting an MCQ-only attempt"""
        attempt = self.create_attempt_with_responses(mcq_count=5, theory_count=0)
        
        # Submit the attempt
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['status'], 'submitted')
        self.assertEqual(response.data['mcq_score'], 3)  # 3 correct answers
        self.assertEqual(response.data['mcq_total'], 5)
        self.assertEqual(response.data['mcq_percentage'], 60.0)
        self.assertEqual(response.data['overall_percentage'], 60.0)
        self.assertFalse(response.data['theory_grading_pending'])
        self.assertIsNotNone(response.data['submitted_at'])
        self.assertIsNotNone(response.data['time_taken_seconds'])
        
        # Verify database state
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'submitted')
        self.assertEqual(attempt.mcq_score, 3)
        self.assertIsNotNone(attempt.submitted_at)
        self.assertFalse(attempt.theory_grading_pending)
    
    def test_submit_mixed_attempt(self):
        """Test submitting a mixed MCQ + theory attempt"""
        attempt = self.create_attempt_with_responses(mcq_count=5, theory_count=2)
        
        # Submit the attempt
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['status'], 'submitted')
        self.assertEqual(response.data['mcq_score'], 3)
        self.assertEqual(response.data['mcq_total'], 5)
        self.assertEqual(response.data['theory_total'], 2)
        self.assertTrue(response.data['theory_grading_pending'])
        self.assertEqual(response.data['theory_grading_status'], 'pending')
        
        # Theory score should be None until grading completes
        self.assertIsNone(response.data['theory_score'])
        
        # Verify database state
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'submitted')
        self.assertTrue(attempt.theory_grading_pending)
        self.assertFalse(attempt.theory_grading_completed)
    
    def test_submit_already_submitted_attempt(self):
        """Test that submitting an already submitted attempt returns error"""
        attempt = self.create_attempt_with_responses(mcq_count=5, theory_count=0)
        
        # Submit once
        self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Try to submit again
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Should return error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('already submitted', response.data['error'].lower())
    
    def test_submit_with_no_answers(self):
        """Test submitting attempt with no answers provided"""
        attempt = self.create_attempt_with_responses(mcq_count=5, theory_count=0, answer_mcqs=False)
        
        # Submit the attempt
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Should still succeed but with 0 score
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mcq_score'], 0)
        self.assertEqual(response.data['overall_percentage'], 0.0)
    
    def test_submit_calculates_is_correct_properly(self):
        """Test that is_correct is calculated properly during submission"""
        attempt = self.create_attempt_with_responses(mcq_count=5, theory_count=0)
        
        # Manually set one response's is_correct to wrong value
        response = attempt.responses.first()
        response.selected_option = 'A'  # Correct answer
        response.is_correct = False  # But marked as incorrect
        response.save()
        
        # Submit should recalculate
        api_response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Verify is_correct was recalculated
        response.refresh_from_db()
        self.assertTrue(response.is_correct)
    
    def test_submit_theory_only_attempt(self):
        """Test submitting a theory-only attempt"""
        attempt = self.create_attempt_with_responses(mcq_count=0, theory_count=2)
        
        # Submit the attempt
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/submit/')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mcq_total'], 0)
        self.assertEqual(response.data['theory_total'], 2)
        self.assertTrue(response.data['theory_grading_pending'])
        
        # Overall percentage should be 0 until theory grading completes
        self.assertEqual(response.data['overall_percentage'], 0.0)


class QuizAttemptAutoSubmitTestCase(TestCase):
    """Test suite for quiz attempt auto-submission (Task 5.2)"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create curriculum structure
        self.subject = Subject.objects.create(id='test-subject', name='Test Subject')
        self.block = Block.objects.create(id='test-block', subject=self.subject, name='Test Block')
        self.sub_block = SubBlock.objects.create(id='test-sub-block', block=self.block, name='Test SubBlock')
        self.topic = Topic.objects.create(id='test-topic', sub_block=self.sub_block, block=self.block, name='Test Topic')
        
        # Create a test MCQ question
        self.question = QuizQuestion.objects.create(
            id='mcq-1',
            question_type='mcq',
            difficulty='medium',
            subject=self.subject,
            question_text='Test MCQ Question',
            option_a='A', option_b='B', option_c='C', option_d='D',
            correct_option='A'
        )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_auto_submit_within_buffer(self):
        """Test auto-submit within 30-second buffer is allowed"""
        now = timezone.now()
        deadline = now - timedelta(seconds=15)  # 15 seconds past deadline
        
        # Create timed attempt
        attempt = QuizAttempt.objects.create(
            id=str(uuid.uuid4())[:12],
            user=self.user,
            subject=self.subject,
            exam_type='timed',
            is_timed=True,
            duration_minutes=30,
            deadline=deadline,
            configuration={'mcq_count': 1, 'theory_count': 0, 'difficulty': 'medium'},
            question_ids=[self.question.id],
            status='in_progress',
            mcq_total=1,
            theory_total=0
        )
        
        # Create response
        QuizAttemptResponse.objects.create(
            attempt=attempt,
            question=self.question,
            selected_option='A',
            is_correct=True,
            ai_evaluation_status='na'
        )
        
        # Auto-submit should succeed
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/auto_submit/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'auto_submitted')
        
        # Verify database state
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'auto_submitted')
    
    def test_auto_submit_beyond_buffer(self):
        """Test auto-submit beyond 30-second buffer is rejected"""
        now = timezone.now()
        deadline = now - timedelta(seconds=35)  # 35 seconds past deadline (beyond buffer)
        
        # Create timed attempt
        attempt = QuizAttempt.objects.create(
            id=str(uuid.uuid4())[:12],
            user=self.user,
            subject=self.subject,
            exam_type='timed',
            is_timed=True,
            duration_minutes=30,
            deadline=deadline,
            configuration={'mcq_count': 1, 'theory_count': 0, 'difficulty': 'medium'},
            question_ids=[self.question.id],
            status='in_progress',
            mcq_total=1,
            theory_total=0
        )
        
        # Auto-submit should fail
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/auto_submit/')
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('error', response.data)
        self.assertIn('expired', response.data['error'].lower())
        
        # Status should remain in_progress
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'in_progress')
    
    def test_auto_submit_untimed_attempt(self):
        """Test auto-submit works for untimed attempts"""
        # Create untimed attempt
        attempt = QuizAttempt.objects.create(
            id=str(uuid.uuid4())[:12],
            user=self.user,
            subject=self.subject,
            exam_type='practice',
            is_timed=False,
            configuration={'mcq_count': 1, 'theory_count': 0, 'difficulty': 'medium'},
            question_ids=[self.question.id],
            status='in_progress',
            mcq_total=1,
            theory_total=0
        )
        
        # Create response
        QuizAttemptResponse.objects.create(
            attempt=attempt,
            question=self.question,
            selected_option='A',
            is_correct=True,
            ai_evaluation_status='na'
        )
        
        # Auto-submit should succeed (no deadline check for untimed)
        response = self.client.post(f'/api/quiz-attempts/{attempt.id}/auto_submit/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'auto_submitted')
