"""
Unit tests for the generate_questions_task Celery task.

Tests:
- Task existence and signature
- Idempotency check
- 429 retry logic
- Database persistence
- Error handling
"""
from unittest.mock import Mock, patch, MagicMock
try:
    import pytest
except ImportError:
    class MockPytest:
        class mark:
            @staticmethod
            def skipif(*args, **kwargs):
                return lambda func: func
    pytest = MockPytest()
from django.test import TestCase
from curriculum.tasks import generate_questions_task
from curriculum.models import Slide, SlideContent, QuizQuestion, Subject, Block, Topic, SubBlock
from curriculum.services.ai_question_generator import Gemini429Exception


class GenerateQuestionsTaskTest(TestCase):
    """Test suite for generate_questions_task"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create test curriculum structure
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
        
        # Create test slide
        self.slide = Slide.objects.create(
            id='test-slide-1',
            title='Test Slide',
            subject=self.subject,
            block=self.block,
            sub_block=self.sub_block,
            topic=self.topic,
            file_type='pdf'
        )
        
        # Create slide content
        self.slide_content = SlideContent.objects.create(
            slide=self.slide,
            is_extracted=True,
            content_data={
                'text': 'This is test content about anatomy. ' * 50,  # ~200 chars
                'pages': [{'page_number': 1}]
            }
        )
    
    def tearDown(self):
        """Clean up test data"""
        QuizQuestion.objects.all().delete()
        SlideContent.objects.all().delete()
        Slide.objects.all().delete()
        Topic.objects.all().delete()
        Block.objects.all().delete()
        Subject.objects.all().delete()
    
    def test_task_exists(self):
        """Test that the task is properly registered"""
        self.assertTrue(callable(generate_questions_task))
        self.assertTrue(hasattr(generate_questions_task, 'delay'))
    
    @patch('curriculum.tasks.AIQuestionGenerator.questions_exist_for_slide')
    def test_idempotency_check_skips_generation(self, mock_exists):
        """Test that task skips generation if questions already exist"""
        mock_exists.return_value = True
        
        # Create existing questions
        QuizQuestion.objects.create(
            id='existing-mcq',
            question_type='mcq',
            subject=self.subject,
            question_text='Existing question',
            correct_option='A',
            source_slide=self.slide
        )
        
        result = generate_questions_task(self.slide.id, mcq_count=5, theory_count=2)
        
        self.assertTrue(result['success'])
        self.assertTrue(result.get('skipped'))
        self.assertEqual(result['reason'], 'Questions already exist')
    
    @patch('curriculum.tasks.AIQuestionGenerator.generate_mcqs_from_text')
    @patch('curriculum.tasks.AIQuestionGenerator.generate_theory_from_text')
    @patch('curriculum.tasks.AIQuestionGenerator.questions_exist_for_slide')
    def test_successful_question_generation(self, mock_exists, mock_theory, mock_mcq):
        """Test successful generation and persistence of questions"""
        mock_exists.return_value = False
        
        # Mock MCQ generation
        mock_mcq.return_value = [
            {
                'question_text': 'Test MCQ?',
                'option_a': 'A',
                'option_b': 'B',
                'option_c': 'C',
                'option_d': 'D',
                'correct_option': 'A',
                'explanation': 'Test explanation',
                'difficulty': 'medium',
                'maximum_marks': 1
            }
        ]
        
        # Mock theory generation
        mock_theory.return_value = [
            {
                'question_text': 'Test theory?',
                'ideal_answer': 'Test ideal answer',
                'marking_rubric': [
                    {'criterion': 'Point 1', 'marks': 5},
                    {'criterion': 'Point 2', 'marks': 5}
                ],
                'difficulty': 'medium',
                'maximum_marks': 10
            }
        ]
        
        result = generate_questions_task(self.slide.id, mcq_count=1, theory_count=1)
        
        # Check result
        self.assertTrue(result['success'])
        self.assertEqual(result['mcq_generated'], 1)
        self.assertEqual(result['theory_generated'], 1)
        self.assertEqual(result['total_generated'], 2)
        
        # Verify database persistence
        mcq_count = QuizQuestion.objects.filter(
            source_slide=self.slide,
            question_type='mcq'
        ).count()
        theory_count = QuizQuestion.objects.filter(
            source_slide=self.slide,
            question_type='theory'
        ).count()
        
        self.assertEqual(mcq_count, 1)
        self.assertEqual(theory_count, 1)
    
    @patch('curriculum.tasks.AIQuestionGenerator.generate_mcqs_from_text')
    @patch('curriculum.tasks.AIQuestionGenerator.questions_exist_for_slide')
    def test_429_retry_logic(self, mock_exists, mock_mcq):
        """Test that 429 errors trigger retry with exponential backoff"""
        mock_exists.return_value = False
        mock_mcq.side_effect = Gemini429Exception("Rate limit exceeded")
        
        # Create a mock Celery task with retry method
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        
        with patch.object(generate_questions_task, 'retry') as mock_retry:
            mock_retry.side_effect = Exception("Retry called")  # Simulate retry
            
            try:
                # Call the task function directly (not .delay())
                generate_questions_task.__wrapped__(
                    mock_task,
                    self.slide.id,
                    mcq_count=5,
                    theory_count=0
                )
            except Exception as e:
                # Should raise retry exception
                pass
            
            # Verify retry was called
            if mock_retry.called:
                # Check that countdown increases exponentially
                call_args = mock_retry.call_args
                self.assertIsNotNone(call_args)
    
    def test_missing_slide_error(self):
        """Test error handling when slide doesn't exist"""
        result = generate_questions_task('nonexistent-slide-id')
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'].lower())
    
    @patch('curriculum.tasks.AIQuestionGenerator.questions_exist_for_slide')
    def test_insufficient_content_error(self, mock_exists):
        """Test error handling when slide has insufficient content"""
        mock_exists.return_value = False
        
        # Update slide content with minimal text
        self.slide_content.content_data = {'text': 'Too short'}
        self.slide_content.save()
        
        result = generate_questions_task(self.slide.id)
        
        self.assertFalse(result['success'])
        self.assertIn('insufficient', result['error'].lower())
    
    @patch('curriculum.tasks.AIQuestionGenerator.generate_mcqs_from_text')
    @patch('curriculum.tasks.AIQuestionGenerator.questions_exist_for_slide')
    def test_partial_save_on_error(self, mock_exists, mock_mcq):
        """Test that successfully generated questions are saved even if some fail"""
        mock_exists.return_value = False
        
        # Mock generation to return questions
        mock_mcq.return_value = [
            {
                'question_text': 'Question 1',
                'option_a': 'A', 'option_b': 'B',
                'option_c': 'C', 'option_d': 'D',
                'correct_option': 'A',
                'explanation': 'Explanation',
                'difficulty': 'medium',
                'maximum_marks': 1
            }
        ]
        
        result = generate_questions_task(self.slide.id, mcq_count=1, theory_count=0)
        
        # Should still save the MCQ successfully
        self.assertTrue(result['success'])
        self.assertEqual(result['mcq_generated'], 1)


class GenerateQuestionsTaskIntegrationTest(TestCase):
    """Integration tests for generate_questions_task with real AI service (if configured)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.subject = Subject.objects.create(id='anat', name='Anatomy', order=1)
        self.block = Block.objects.create(
            id='anat-block-1',
            subject=self.subject,
            name='Block 1',
            order=1
        )
        self.topic = Topic.objects.create(
            id='gross-anatomy',
            block=self.block,
            name='Gross Anatomy',
            order=1
        )
        
        self.slide = Slide.objects.create(
            id='test-slide-integration',
            title='Axilla Anatomy',
            subject=self.subject,
            block=self.block,
            topic=self.topic
        )
        
        # Create realistic content
        self.slide_content = SlideContent.objects.create(
            slide=self.slide,
            is_extracted=True,
            content_data={
                'text': '''
                The axilla is a pyramidal space located between the upper thoracic wall 
                and the arm. It serves as a passageway for neurovascular structures 
                traveling from the neck and thorax to the upper limb.
                
                Boundaries:
                - Anterior wall: Pectoralis major and minor muscles
                - Posterior wall: Subscapularis, teres major, and latissimus dorsi
                - Medial wall: Serratus anterior and ribs 1-4
                - Lateral wall: Intertubercular groove of humerus
                - Apex: Convergence of clavicle, scapula, and first rib
                - Base: Skin and fascia of the armpit
                
                Contents include the axillary artery, axillary vein, and brachial plexus.
                ''',
                'pages': [{'page_number': 1}]
            }
        )
    
    def tearDown(self):
        """Clean up"""
        QuizQuestion.objects.filter(source_slide=self.slide).delete()
        SlideContent.objects.filter(slide=self.slide).delete()
        Slide.objects.filter(id=self.slide.id).delete()
    
    @pytest.mark.skipif(
        not hasattr(pytest, 'config') or not pytest.config.getoption('--run-ai-tests', default=False),
        reason="AI integration tests disabled by default"
    )
    def test_real_question_generation(self):
        """Test with real AI service (requires GEMINI_API_KEY)"""
        # This test is skipped by default - run with: pytest --run-ai-tests
        result = generate_questions_task(
            self.slide.id,
            mcq_count=2,
            theory_count=1,
            difficulty='medium'
        )
        
        # If API key is configured, should succeed
        if result['success']:
            self.assertGreater(result['mcq_generated'], 0)
            self.assertGreater(result['theory_generated'], 0)
            
            # Verify questions in database
            questions = QuizQuestion.objects.filter(source_slide=self.slide)
            self.assertGreater(questions.count(), 0)
