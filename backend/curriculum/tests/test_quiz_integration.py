"""
Integration test for complete quiz attempt flow (Task 5.1)

This test verifies the complete end-to-end flow:
1. Create an attempt
2. Submit answers for all questions
3. Submit the attempt
4. Verify scoring and status transitions
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from curriculum.models import Subject, Block, SubBlock, Topic, QuizQuestion


class QuizAttemptIntegrationTestCase(TestCase):
    """End-to-end integration test for quiz attempt flow"""
    
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
            id='anatomy',
            name='Anatomy',
            order=1
        )
        
        self.block = Block.objects.create(
            id='anatomy-block-1',
            subject=self.subject,
            name='Block 1',
            order=1
        )
        
        self.sub_block = SubBlock.objects.create(
            id='gross-anatomy-subblock',
            block=self.block,
            name='Gross Anatomy SubBlock',
            order=1
        )
        
        self.topic = Topic.objects.create(
            id='gross-anatomy',
            sub_block=self.sub_block,
            block=self.block,
            name='Gross Anatomy',
            order=1
        )
        
        # Create test questions
        for i in range(10):
            QuizQuestion.objects.create(
                id=f'mcq-{i+1}',
                question_type='mcq',
                difficulty='medium',
                subject=self.subject,
                block=self.block,
                sub_block=self.sub_block,
                question_text=f'What is the answer to question {i+1}?',
                option_a='Correct answer',
                option_b='Wrong answer 1',
                option_c='Wrong answer 2',
                option_d='Wrong answer 3',
                correct_option='A',
                explanation=f'Explanation for question {i+1}'
            )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_complete_quiz_flow(self):
        """Test complete quiz flow from creation to submission"""
        
        # 1. CREATE ATTEMPT
        create_response = self.client.post('/api/quiz-attempts/', {
            'subject': 'anatomy',
            'block': 'anatomy-block-1',
            'topic': 'gross-anatomy-subblock',
            'exam_type': 'practice',
            'is_timed': False,
            'configuration': {
                'mcq_count': 5,  # Changed from 10 to 5 (free tier limit)
                'theory_count': 0,
                'difficulty': 'medium'
            }
        }, format='json')
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        attempt_id = create_response.data['id']
        self.assertEqual(create_response.data['status'], 'in_progress')
        self.assertEqual(len(create_response.data['questions']), 5)  # Updated expected count
        
        # 2. SUBMIT ANSWERS
        questions = create_response.data['questions']
        
        # Answer first 3 correctly, last 2 incorrectly
        for i, question in enumerate(questions):
            if i < 3:
                # Correct answer
                answer_response = self.client.post(
                    f'/api/quiz-attempts/{attempt_id}/submit_answer/',
                    {
                        'question_id': question['id'],
                        'selected_option': 'A'  # Correct option
                    }
                )
            else:
                # Incorrect answer
                answer_response = self.client.post(
                    f'/api/quiz-attempts/{attempt_id}/submit_answer/',
                    {
                        'question_id': question['id'],
                        'selected_option': 'B'  # Incorrect option
                    }
                )
            
            self.assertEqual(answer_response.status_code, status.HTTP_200_OK)
            self.assertTrue(answer_response.data['success'])
        
        # 3. SUBMIT ATTEMPT
        submit_response = self.client.post(f'/api/quiz-attempts/{attempt_id}/submit/')
        
        # 4. VERIFY SUBMISSION RESPONSE
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertTrue(submit_response.data['success'])
        self.assertEqual(submit_response.data['status'], 'submitted')
        
        # 5. VERIFY SCORING
        self.assertEqual(submit_response.data['mcq_score'], 3)
        self.assertEqual(submit_response.data['mcq_total'], 5)  # Updated
        self.assertEqual(submit_response.data['mcq_percentage'], 60.0)
        self.assertEqual(submit_response.data['overall_percentage'], 60.0)
        
        # 6. VERIFY METADATA
        self.assertFalse(submit_response.data['theory_grading_pending'])
        self.assertIsNotNone(submit_response.data['submitted_at'])
        self.assertIsNotNone(submit_response.data['time_taken_seconds'])
        self.assertGreaterEqual(submit_response.data['time_taken_seconds'], 0)  # Can be 0 in fast tests
        
        # 7. VERIFY IDEMPOTENCY - Second submission should fail
        second_submit = self.client.post(f'/api/quiz-attempts/{attempt_id}/submit/')
        self.assertEqual(second_submit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', second_submit.data)
    
    def test_quiz_flow_with_partial_answers(self):
        """Test quiz submission with some questions unanswered"""
        
        # 1. Create attempt
        create_response = self.client.post('/api/quiz-attempts/', {
            'subject': 'anatomy',
            'exam_type': 'practice',
            'is_timed': False,
            'configuration': {
                'mcq_count': 5,
                'theory_count': 0,
                'difficulty': 'medium'
            }
        }, format='json')
        
        attempt_id = create_response.data['id']
        questions = create_response.data['questions']
        
        # 2. Answer only first 3 questions
        for question in questions[:3]:
            self.client.post(
                f'/api/quiz-attempts/{attempt_id}/submit_answer/',
                {
                    'question_id': question['id'],
                    'selected_option': 'A'
                }
            )
        
        # 3. Submit attempt with unanswered questions
        submit_response = self.client.post(f'/api/quiz-attempts/{attempt_id}/submit/')
        
        # 4. Verify submission succeeds
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_response.data['mcq_score'], 3)
        self.assertEqual(submit_response.data['mcq_total'], 5)
        self.assertEqual(submit_response.data['mcq_percentage'], 60.0)
    
    def test_quiz_flow_with_flagged_questions(self):
        """Test quiz flow with question flagging"""
        
        # 1. Create attempt
        create_response = self.client.post('/api/quiz-attempts/', {
            'subject': 'anatomy',
            'exam_type': 'practice',
            'is_timed': False,
            'configuration': {
                'mcq_count': 5,
                'theory_count': 0,
                'difficulty': 'medium'
            }
        }, format='json')
        
        attempt_id = create_response.data['id']
        questions = create_response.data['questions']
        
        # 2. Answer all questions
        for question in questions:
            self.client.post(
                f'/api/quiz-attempts/{attempt_id}/submit_answer/',
                {
                    'question_id': question['id'],
                    'selected_option': 'A'
                }
            )
        
        # 3. Flag some questions
        self.client.post(
            f'/api/quiz-attempts/{attempt_id}/toggle_flag/',
            {'question_id': questions[0]['id']}
        )
        self.client.post(
            f'/api/quiz-attempts/{attempt_id}/toggle_flag/',
            {'question_id': questions[2]['id']}
        )
        
        # 4. Submit attempt
        submit_response = self.client.post(f'/api/quiz-attempts/{attempt_id}/submit/')
        
        # 5. Verify submission succeeds (flags don't affect scoring)
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_response.data['mcq_score'], 5)
