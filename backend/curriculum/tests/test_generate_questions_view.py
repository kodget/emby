"""
Tests for the generate_questions_view API endpoint

Tests cover:
- Slide validation
- Content validation
- Parameter validation
- Task queuing
- Idempotency
- Error handling

Requirements: 9.1, 9.4
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from curriculum.models import Slide, SlideContent, QuizQuestion, Subject, Block, Topic, SubBlock

User = get_user_model()


class GenerateQuestionsViewTestCase(TestCase):
    """Test suite for POST /api/quiz/generate_questions/ endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test curriculum structure
        self.subject = Subject.objects.create(
            id='anatomy',
            name='Anatomy'
        )
        
        self.block = Block.objects.create(
            id='anatomy-block-1',
            name='Block 1',
            subject=self.subject
        )
        
        self.sub_block = SubBlock.objects.create(
            id='gross-anatomy-subblock',
            name='Gross Anatomy SubBlock',
            block=self.block
        )
        
        self.topic = Topic.objects.create(
            id='gross-anatomy',
            name='Gross Anatomy',
            sub_block=self.sub_block,
            block=self.block
        )
        
        # Create test slide with content
        self.slide = Slide.objects.create(
            id='test-slide-1',
            title='Test Slide',
            file_type='pdf',
            uploaded_by=self.user,
            subject=self.subject,
            block=self.block,
            sub_block=self.sub_block,
            topic=self.topic
        )
        
        # Create slide content with sufficient text
        self.slide_content = SlideContent.objects.create(
            slide=self.slide,
            is_extracted=True,
            content_data={
                'text': 'This is a long medical text about anatomy. ' * 50,  # >100 chars
                'pages': [{'page_number': 1, 'image_url': 'http://example.com/page1.jpg'}],
                'total_pages': 1
            }
        )
        
        self.url = '/api/quiz/generate_questions/'

    def test_generate_questions_success(self):
        """Test successful question generation queuing"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-id-123'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'mcq_count': 5,
                'theory_count': 2,
                'difficulty': 'medium'
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['message'], 'Question generation queued')
            self.assertEqual(response.data['slide_id'], self.slide.id)
            self.assertEqual(response.data['task_id'], 'test-task-id-123')
            self.assertEqual(response.data['mcq_count'], 5)
            self.assertEqual(response.data['theory_count'], 2)
            self.assertEqual(response.data['difficulty'], 'medium')
            
            # Verify task was queued with correct parameters
            mock_delay.assert_called_once_with(
                slide_id=self.slide.id,
                mcq_count=5,
                theory_count=2,
                difficulty='medium'
            )

    def test_generate_questions_with_defaults(self):
        """Test question generation with default parameters"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-id-456'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['mcq_count'], 5)  # default
            self.assertEqual(response.data['theory_count'], 2)  # default
            self.assertEqual(response.data['difficulty'], 'medium')  # default

    def test_missing_slide_id(self):
        """Test error when slide_id is missing"""
        response = self.client.post(self.url, {
            'mcq_count': 5
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'slide_id is required')

    def test_slide_not_found(self):
        """Test error when slide doesn't exist"""
        response = self.client.post(self.url, {
            'slide_id': 'nonexistent-slide-id'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertIn('not found', response.data['error'].lower())

    def test_slide_no_content(self):
        """Test error when slide has no SlideContent"""
        slide_no_content = Slide.objects.create(
            id='slide-no-content',
            title='Slide Without Content',
            file_type='pdf',
            uploaded_by=self.user,
            subject=self.subject,
            block=self.block
        )
        
        response = self.client.post(self.url, {
            'slide_id': slide_no_content.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('content not found', response.data['error'].lower())

    def test_slide_insufficient_text(self):
        """Test error when slide content is too short"""
        slide_short = Slide.objects.create(
            id='slide-short',
            title='Short Slide',
            file_type='pdf',
            uploaded_by=self.user,
            subject=self.subject,
            block=self.block
        )
        
        SlideContent.objects.create(
            slide=slide_short,
            is_extracted=True,
            content_data={
                'text': 'Too short',  # <100 chars
                'pages': [],
                'total_pages': 0
            }
        )
        
        response = self.client.post(self.url, {
            'slide_id': slide_short.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('insufficient text', response.data['error'].lower())
        self.assertIn('content_length', response.data)

    def test_invalid_mcq_count(self):
        """Test error with invalid mcq_count"""
        response = self.client.post(self.url, {
            'slide_id': self.slide.id,
            'mcq_count': 'invalid'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('must be integers', response.data['error'])

    def test_negative_counts(self):
        """Test error with negative question counts"""
        response = self.client.post(self.url, {
            'slide_id': self.slide.id,
            'mcq_count': -5,
            'theory_count': 2
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('must be non-negative', response.data['error'])

    def test_zero_counts(self):
        """Test error when both counts are zero"""
        response = self.client.post(self.url, {
            'slide_id': self.slide.id,
            'mcq_count': 0,
            'theory_count': 0
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least one', response.data['error'].lower())

    def test_invalid_difficulty(self):
        """Test error with invalid difficulty level"""
        response = self.client.post(self.url, {
            'slide_id': self.slide.id,
            'difficulty': 'impossible'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('difficulty must be one of', response.data['error'].lower())

    def test_questions_already_exist(self):
        """Test idempotency - returns existing questions without queuing new task"""
        # Create existing questions
        QuizQuestion.objects.create(
            id='existing-mcq-1',
            question_type='mcq',
            question_text='Existing MCQ',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_option='A',
            source_slide=self.slide,
            subject=self.subject
        )
        
        QuizQuestion.objects.create(
            id='existing-theory-1',
            question_type='theory',
            question_text='Existing Theory',
            ideal_answer='Answer',
            source_slide=self.slide,
            subject=self.subject
        )
        
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            response = self.client.post(self.url, {
                'slide_id': self.slide.id
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['message'], 'Questions already exist for this slide')
            self.assertEqual(response.data['mcq_count'], 1)
            self.assertEqual(response.data['theory_count'], 1)
            self.assertTrue(response.data['already_exists'])
            
            # Verify task was NOT queued
            mock_delay.assert_not_called()

    def test_authentication_required(self):
        """Test that authentication is required"""
        self.client.force_authenticate(user=None)
        
        response = self.client.post(self.url, {
            'slide_id': self.slide.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_task_queuing_failure(self):
        """Test error handling when task queuing fails"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_delay.side_effect = Exception('Celery connection failed')
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn('error', response.data)
            self.assertIn('Failed to queue', response.data['error'])

    def test_only_mcq_questions(self):
        """Test generating only MCQ questions"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-mcq-only'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'mcq_count': 10,
                'theory_count': 0
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['mcq_count'], 10)
            self.assertEqual(response.data['theory_count'], 0)

    def test_only_theory_questions(self):
        """Test generating only theory questions"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-theory-only'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'mcq_count': 0,
                'theory_count': 5
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['mcq_count'], 0)
            self.assertEqual(response.data['theory_count'], 5)

    def test_easy_difficulty(self):
        """Test generating questions with easy difficulty"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-easy'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'difficulty': 'easy'
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['difficulty'], 'easy')

    def test_hard_difficulty(self):
        """Test generating questions with hard difficulty"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-hard'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'difficulty': 'hard'
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['difficulty'], 'hard')

    def test_large_question_counts(self):
        """Test generating large numbers of questions"""
        with patch('curriculum.tasks.generate_questions_task.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-large'
            mock_delay.return_value = mock_task
            
            response = self.client.post(self.url, {
                'slide_id': self.slide.id,
                'mcq_count': 50,
                'theory_count': 10
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['mcq_count'], 50)
            self.assertEqual(response.data['theory_count'], 10)
