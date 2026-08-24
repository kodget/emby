"""
Tests for curriculum: content extraction, slide rendering, AI service, quiz generation.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from .models import Subject, Block, Topic, Slide, SlideContent, QuizQuestion, Quiz, QuizAnswer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="testuser", role="student", is_premium=False):
    user = User.objects.create_user(username=username, password="pass")
    from accounts.models import Profile
    Profile.objects.get_or_create(user=user, defaults={"role": role})
    return user


def make_curriculum():
    subject = Subject.objects.create(id="anatomy", name="Anatomy")
    block = Block.objects.create(id="anatomy-b1", subject=subject, name="Block 1")
    topic = Topic.objects.create(id="gross-anatomy", block=block, name="Gross Anatomy")
    return subject, block, topic


def make_slide(subject, block, topic, title="Test Slide", file_url="http://example.com/test.pdf"):
    return Slide.objects.create(
        id="test-slide-1",
        title=title,
        subject=subject,
        block=block,
        topic=topic,
        file_url=file_url,
        file_type="pdf",
    )


def make_mcq(subject, block, topic):
    return QuizQuestion.objects.create(
        id="q-test-1",
        question_type="mcq",
        subject=subject,
        block=block,
        topic=topic,
        question_text="What is the brachial plexus?",
        option_a="A nerve network",
        option_b="A bone",
        option_c="A muscle",
        option_d="A vein",
        correct_option="A",
        explanation="The brachial plexus is a network of nerves.",
    )


# ---------------------------------------------------------------------------
# Content extractor tests
# ---------------------------------------------------------------------------

class ContentExtractorTest(TestCase):

    @patch("curriculum.content_extractor.requests.get")
    def test_extract_text_from_pdf(self, mock_get):
        mock_get.return_value = MagicMock(content=b"%PDF-fake", status_code=200)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample anatomy text"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("fitz.open", return_value=mock_doc):
            from curriculum.content_extractor import extract_text_from_slide
            pages = extract_text_from_slide("http://example.com/test.pdf", "pdf")
        self.assertIsInstance(pages, list)

    def test_get_slide_full_text_empty(self):
        from curriculum.content_extractor import get_slide_full_text
        with patch("curriculum.content_extractor.extract_text_from_slide", return_value=[]):
            result = get_slide_full_text("http://example.com/test.pdf", "pdf")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# Slide rendering + SlideContent caching
# ---------------------------------------------------------------------------

class SlideContentCachingTest(TestCase):

    def setUp(self):
        self.subject, self.block, self.topic = make_curriculum()
        self.slide = make_slide(self.subject, self.block, self.topic)
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_slide_content_cached_on_second_request(self):
        fake_content = {
            "total_pages": 2,
            "pages": [
                {"page_number": 1, "image_url": "http://cdn.example.com/p1.jpg",
                 "width": 800, "height": 600, "text_blocks": [{"text": "Hello"}]},
                {"page_number": 2, "image_url": "http://cdn.example.com/p2.jpg",
                 "width": 800, "height": 600, "text_blocks": []},
            ],
        }

        with patch("curriculum.slide_renderer.render_slide_pages", return_value=fake_content) as mock_render:
            resp1 = self.client.get(f"/api/slides/{self.slide.id}/content/")
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(mock_render.call_count, 1)

            resp2 = self.client.get(f"/api/slides/{self.slide.id}/content/")
            self.assertEqual(resp2.status_code, 200)
            # Second call must NOT call render_slide_pages again (cache hit)
            self.assertEqual(mock_render.call_count, 1)
            self.assertTrue(resp2.data["cached"])

    def test_slide_not_found_returns_404(self):
        resp = self.client.get("/api/slides/nonexistent/content/")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# AI service unit tests (mocked Claude)
# ---------------------------------------------------------------------------

def _mock_gemini(response_text):
    """Helper: patch google.generativeai so _call() returns response_text."""
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    return mock_genai


class AIServiceTest(TestCase):

    def test_grade_theory_answer_parses_response(self):
        payload = '{"score": 75, "feedback": "Good answer.", "key_points_missed": ["vasa vasorum"]}'
        with patch("curriculum.ai_service.genai", _mock_gemini(payload)), \
             self.settings(GEMINI_API_KEY="fake-key"):
            from curriculum.ai_service import grade_theory_answer
            result = grade_theory_answer("Describe the aorta.", "The aorta is...", "The aorta carries blood.")
        self.assertEqual(result["score"], 75)
        self.assertIn("feedback", result)

    def test_grade_theory_handles_bad_json(self):
        with patch("curriculum.ai_service.genai", _mock_gemini("Not valid JSON at all")), \
             self.settings(GEMINI_API_KEY="fake-key"):
            from curriculum.ai_service import grade_theory_answer
            result = grade_theory_answer("Q", "A", "Student answer")
        self.assertIn("score", result)  # falls back gracefully

    def test_ai_tutor_returns_reply(self):
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "The femur is the largest bone."
        mock_chat.send_message.return_value = mock_response
        mock_model.start_chat.return_value = mock_chat
        mock_genai.GenerativeModel.return_value = mock_model

        with patch("curriculum.ai_service.genai", mock_genai), \
             self.settings(GEMINI_API_KEY="fake-key"):
            from curriculum.ai_service import ai_tutor_chat
            result = ai_tutor_chat("What is the femur?")
        self.assertEqual(result["reply"], "The femur is the largest bone.")

    def test_generate_questions_returns_structured_data(self):
        payload = {
            "mcqs": [{
                "question": "What is the femur?",
                "option_a": "Largest bone", "option_b": "Smallest bone",
                "option_c": "A muscle", "option_d": "A tendon",
                "correct_option": "A", "explanation": "Femur is the largest bone."
            }],
            "theory": [{"question": "Describe the femur.", "model_answer": "The femur is..."}]
        }
        with patch("curriculum.ai_service.genai", _mock_gemini(json.dumps(payload))), \
             self.settings(GEMINI_API_KEY="fake-key"):
            from curriculum.ai_service import generate_questions_from_text
            result = generate_questions_from_text("Femur text...", "Anatomy", "Gross Anatomy")
        self.assertEqual(len(result["mcqs"]), 1)
        self.assertEqual(len(result["theory"]), 1)


# ---------------------------------------------------------------------------
# Question generator (DB integration)
# ---------------------------------------------------------------------------

class QuestionGeneratorTest(TestCase):

    def setUp(self):
        self.subject, self.block, self.topic = make_curriculum()
        self.slide = make_slide(self.subject, self.block, self.topic)

    @patch("curriculum.question_generator.generate_questions_from_text")
    @patch("curriculum.question_generator.get_slide_full_text")
    def test_generates_and_saves_questions(self, mock_text, mock_gen):
        mock_text.return_value = "Some slide text about the femur."
        mock_gen.return_value = {
            "mcqs": [{
                "question": "Q1?", "option_a": "A", "option_b": "B",
                "option_c": "C", "option_d": "D",
                "correct_option": "A", "explanation": "Explanation."
            }],
            "theory": [{"question": "Describe Q1.", "model_answer": "Answer."}],
        }

        from curriculum.question_generator import generate_questions_from_slide
        result = generate_questions_from_slide(self.slide, num_mcq=1, num_theory=1)

        self.assertEqual(result["created_mcq"], 1)
        self.assertEqual(result["created_theory"], 1)
        self.assertIsNone(result["error"])
        self.assertEqual(QuizQuestion.objects.filter(source_slide=self.slide).count(), 2)

    @patch("curriculum.question_generator.get_slide_full_text")
    def test_returns_error_when_no_text(self, mock_text):
        mock_text.return_value = "   "

        from curriculum.question_generator import generate_questions_from_slide
        result = generate_questions_from_slide(self.slide)
        self.assertIsNotNone(result["error"])


# ---------------------------------------------------------------------------
# Quiz views
# ---------------------------------------------------------------------------

class QuizViewTest(TestCase):

    def setUp(self):
        self.subject, self.block, self.topic = make_curriculum()
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.question = make_mcq(self.subject, self.block, self.topic)

    def test_generate_quiz_no_questions_returns_404(self):
        QuizQuestion.objects.all().delete()
        resp = self.client.post("/api/quiz/generate/", {
            "quiz_type": "mcq",
            "subject": "anatomy",
            "num_questions": 5,
        }, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_generate_quiz_creates_quiz(self):
        resp = self.client.post("/api/quiz/generate/", {
            "quiz_type": "mcq",
            "subject": "anatomy",
            "num_questions": 1,
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.data)

    def test_submit_mcq_answer_correct(self):
        quiz = Quiz.objects.create(
            id="q-test", user=self.user, quiz_type="mcq",
            subject=self.subject, total_questions=1,
        )
        quiz.questions.set([self.question])

        resp = self.client.post("/api/quiz/answer/", {
            "quiz_id": quiz.id,
            "question_id": self.question.id,
            "selected_option": "A",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["is_correct"])

    def test_complete_quiz_calculates_score(self):
        quiz = Quiz.objects.create(
            id="q-complete", user=self.user, quiz_type="mcq",
            subject=self.subject, total_questions=1,
        )
        quiz.questions.set([self.question])
        QuizAnswer.objects.create(quiz=quiz, question=self.question, selected_option="A", is_correct=True)

        resp = self.client.post(f"/api/quiz/{quiz.id}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["completed"])
        self.assertEqual(resp.data["score"], 1)


# ---------------------------------------------------------------------------
# Quiz attempt endpoints (Task 4.4 - Answer saving endpoint)
# ---------------------------------------------------------------------------

class QuizAttemptAnswerSavingTest(TestCase):
    """Test cases for the submit_answer endpoint in QuizAttemptViewSet"""
    
    def setUp(self):
        self.subject, self.block, self.topic = make_curriculum()
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test questions
        self.mcq_question = QuizQuestion.objects.create(
            id="mcq-test-1",
            question_type="mcq",
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            question_text="What is the largest bone in the human body?",
            option_a="Femur",
            option_b="Tibia",
            option_c="Humerus", 
            option_d="Radius",
            correct_option="A",
            explanation="The femur is the largest bone."
        )
        
        self.theory_question = QuizQuestion.objects.create(
            id="theory-test-1",
            question_type="theory",
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            question_text="Describe the structure and function of the femur.",
            model_answer="The femur is a long bone that supports body weight and enables locomotion.",
            maximum_marks=20
        )
        
        # Create test attempt
        from curriculum.models import QuizAttempt, QuizAttemptResponse
        self.attempt = QuizAttempt.objects.create(
            id="attempt-test-1",
            user=self.user,
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            exam_type="practice",
            is_timed=False,
            status="in_progress",
            question_ids=[str(self.mcq_question.id), str(self.theory_question.id)],
            mcq_total=1,
            theory_total=1
        )
        
        # Create response records
        QuizAttemptResponse.objects.create(
            attempt=self.attempt,
            question=self.mcq_question,
            ai_evaluation_status='na'
        )
        QuizAttemptResponse.objects.create(
            attempt=self.attempt,
            question=self.theory_question,
            ai_evaluation_status='pending'
        )
    
    def test_submit_mcq_answer_success(self):
        """Test successful MCQ answer submission"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "A"
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["message"], "Answer saved successfully")
        self.assertEqual(resp.data["response"]["selected_option"], "A")
        self.assertTrue(resp.data["response"]["is_correct"])
    
    def test_submit_theory_answer_success(self):
        """Test successful theory answer submission"""
        theory_text = "The femur is the longest and strongest bone in the human body, located in the thigh."
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.theory_question.id),
            "text_answer": theory_text
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["response"]["text_answer"], theory_text)
        self.assertIsNone(resp.data["response"]["is_correct"])  # Theory questions don't have immediate correctness
        self.assertEqual(resp.data["response"]["ai_evaluation_status"], "pending")
    
    def test_submit_answer_invalid_question_id(self):
        """Test submission with invalid question ID"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": "invalid-question-id",
            "selected_option": "A"
        }, format="json")
        
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Question does not belong to this attempt", resp.data["error"])
    
    def test_submit_answer_missing_question_id(self):
        """Test submission without question_id"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "selected_option": "A"
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["error"], "question_id is required")
    
    def test_submit_mcq_invalid_option(self):
        """Test MCQ submission with invalid option"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "X"
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("selected_option must be A, B, C, or D", resp.data["error"])
    
    def test_submit_mcq_missing_option(self):
        """Test MCQ submission without selected_option"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("selected_option is required for MCQ questions", resp.data["error"])
    
    def test_submit_theory_missing_text(self):
        """Test theory submission without text_answer"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.theory_question.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("text_answer is required for theory questions", resp.data["error"])
    
    def test_submit_answer_completed_attempt(self):
        """Test submission to completed attempt (should fail)"""
        self.attempt.status = "submitted"
        self.attempt.save()
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "A"
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot submit answers to completed attempts", resp.data["error"])
    
    def test_submit_answer_expired_attempt(self):
        """Test submission to expired timed attempt"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Make the attempt timed and expired
        self.attempt.is_timed = True
        self.attempt.deadline = timezone.now() - timedelta(minutes=5)  # 5 minutes ago
        self.attempt.save()
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "A"
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Time limit exceeded", resp.data["error"])
        
        # Check that attempt status was updated to expired
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "expired")
    
    def test_submit_answer_updates_timestamps(self):
        """Test that submission updates answered_at and attempt updated_at"""
        from django.utils import timezone
        
        original_updated = self.attempt.updated_at
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "B"
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        
        # Check response timestamp
        response_obj = self.attempt.responses.get(question=self.mcq_question)
        self.assertIsNotNone(response_obj.answered_at)
        
        # Check attempt timestamp update
        self.attempt.refresh_from_db()
        self.assertGreater(self.attempt.updated_at, original_updated)
    
    def test_submit_answer_autosave_functionality(self):
        """Test that answers can be updated (autosave functionality)"""
        # First submission
        resp1 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "A"
        }, format="json")
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.data["response"]["is_correct"])
        
        # Second submission (update)
        resp2 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/submit_answer/", {
            "question_id": str(self.mcq_question.id),
            "selected_option": "B"
        }, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.data["response"]["is_correct"])
        
        # Verify database was updated
        response_obj = self.attempt.responses.get(question=self.mcq_question)
        self.assertEqual(response_obj.selected_option, "B")
        self.assertFalse(response_obj.is_correct)


# ---------------------------------------------------------------------------
# AI tutor endpoint
# ---------------------------------------------------------------------------

class AITutorEndpointTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_ai_tutor_returns_reply(self):
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "The femur is the largest bone."
        mock_chat.send_message.return_value = mock_response
        mock_model.start_chat.return_value = mock_chat
        mock_genai.GenerativeModel.return_value = mock_model

        with patch("curriculum.ai_service.genai", mock_genai), \
             patch("django.conf.settings.GEMINI_API_KEY", "fake-key"):
            resp = self.client.post("/api/ai/tutor/", {"message": "What is the femur?"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("reply", resp.data)

    def test_ai_tutor_requires_message(self):
        resp = self.client.post("/api/ai/tutor/", {}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Quiz attempt flag toggle endpoint (Task 4.5)
# ---------------------------------------------------------------------------

class QuizAttemptFlagToggleTest(TestCase):
    """Test cases for the toggle_flag endpoint in QuizAttemptViewSet (Task 4.5)"""
    
    def setUp(self):
        self.subject, self.block, self.topic = make_curriculum()
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test questions
        self.question1 = QuizQuestion.objects.create(
            id="flag-q1",
            question_type="mcq",
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            question_text="Question 1?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="A",
            explanation="Explanation 1"
        )
        
        self.question2 = QuizQuestion.objects.create(
            id="flag-q2",
            question_type="theory",
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            question_text="Question 2?",
            model_answer="Answer 2",
            maximum_marks=20
        )
        
        # Create test attempt with multiple questions
        from curriculum.models import QuizAttempt
        self.attempt = QuizAttempt.objects.create(
            id="flag-attempt-1",
            user=self.user,
            subject=self.subject,
            exam_type="practice",
            status="in_progress",
            question_ids=[str(self.question1.id), str(self.question2.id)],
            flagged_questions=[],  # Start with no flagged questions
            mcq_total=1,
            theory_total=1
        )
    
    def test_flag_question_success(self):
        """Test successfully flagging a question"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["message"], "Question flagged")
        self.assertIn(str(self.question1.id), resp.data["flagged_questions"])
        self.assertEqual(resp.data["flagged_count"], 1)
        
        # Verify database was updated
        self.attempt.refresh_from_db()
        self.assertIn(str(self.question1.id), self.attempt.flagged_questions)
    
    def test_unflag_question_success(self):
        """Test successfully unflagging a previously flagged question"""
        # First, flag the question
        self.attempt.flagged_questions = [str(self.question1.id)]
        self.attempt.save()
        
        # Now unflag it
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["message"], "Question unflagged")
        self.assertNotIn(str(self.question1.id), resp.data["flagged_questions"])
        self.assertEqual(resp.data["flagged_count"], 0)
        
        # Verify database was updated
        self.attempt.refresh_from_db()
        self.assertNotIn(str(self.question1.id), self.attempt.flagged_questions)
    
    def test_toggle_multiple_questions(self):
        """Test flagging multiple questions"""
        # Flag question 1
        resp1 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data["flagged_count"], 1)
        
        # Flag question 2
        resp2 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question2.id)
        }, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["flagged_count"], 2)
        self.assertIn(str(self.question1.id), resp2.data["flagged_questions"])
        self.assertIn(str(self.question2.id), resp2.data["flagged_questions"])
        
        # Unflag question 1
        resp3 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.data["flagged_count"], 1)
        self.assertNotIn(str(self.question1.id), resp3.data["flagged_questions"])
        self.assertIn(str(self.question2.id), resp3.data["flagged_questions"])
    
    def test_flag_question_missing_question_id(self):
        """Test flagging without providing question_id"""
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {}, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["error"], "question_id is required")
    
    def test_flag_question_invalid_question_id(self):
        """Test flagging with question_id not belonging to this attempt"""
        other_question = QuizQuestion.objects.create(
            id="flag-q-other",
            question_type="mcq",
            subject=self.subject,
            question_text="Other question?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="A"
        )
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(other_question.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Question does not belong to this attempt", resp.data["error"])
    
    def test_flag_question_completed_attempt(self):
        """Test flagging in completed attempt (should fail)"""
        self.attempt.status = "submitted"
        self.attempt.save()
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot flag questions in completed attempts", resp.data["error"])
        self.assertEqual(resp.data["current_status"], "submitted")
    
    def test_flag_question_auto_submitted_attempt(self):
        """Test flagging in auto-submitted attempt (should fail)"""
        self.attempt.status = "auto_submitted"
        self.attempt.save()
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot flag questions in completed attempts", resp.data["error"])
    
    def test_flag_question_expired_attempt(self):
        """Test flagging in expired attempt (should fail)"""
        self.attempt.status = "expired"
        self.attempt.save()
        
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot flag questions in completed attempts", resp.data["error"])
    
    def test_flag_updates_last_activity_timestamp(self):
        """Test that flagging updates the attempt's updated_at timestamp"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Set original timestamp to earlier
        original_time = timezone.now() - timedelta(minutes=10)
        self.attempt.updated_at = original_time
        self.attempt.save()
        
        # Flag a question
        resp = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        self.assertEqual(resp.status_code, 200)
        
        # Verify timestamp was updated
        self.attempt.refresh_from_db()
        self.assertGreater(self.attempt.updated_at, original_time)
    
    def test_flag_question_idempotent_toggle(self):
        """Test that toggling flag is idempotent (flag -> unflag -> flag)"""
        question_id = str(self.question1.id)
        
        # Initial state: not flagged
        self.assertEqual(len(self.attempt.flagged_questions), 0)
        
        # First toggle: flag
        resp1 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": question_id
        }, format="json")
        self.assertEqual(resp1.data["message"], "Question flagged")
        self.assertEqual(resp1.data["flagged_count"], 1)
        
        # Second toggle: unflag
        resp2 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": question_id
        }, format="json")
        self.assertEqual(resp2.data["message"], "Question unflagged")
        self.assertEqual(resp2.data["flagged_count"], 0)
        
        # Third toggle: flag again
        resp3 = self.client.post(f"/api/quiz-attempts/{self.attempt.id}/toggle_flag/", {
            "question_id": question_id
        }, format="json")
        self.assertEqual(resp3.data["message"], "Question flagged")
        self.assertEqual(resp3.data["flagged_count"], 1)
    
    def test_flag_question_user_ownership(self):
        """Test that users can only flag questions in their own attempts"""
        # Create another user
        other_user = make_user(username="otheruser")
        
        # Create attempt for other user
        from curriculum.models import QuizAttempt
        other_attempt = QuizAttempt.objects.create(
            id="other-attempt",
            user=other_user,
            subject=self.subject,
            exam_type="practice",
            status="in_progress",
            question_ids=[str(self.question1.id)],
            flagged_questions=[]
        )
        
        # Try to flag question in other user's attempt (should fail via get_object filtering)
        resp = self.client.post(f"/api/quiz-attempts/{other_attempt.id}/toggle_flag/", {
            "question_id": str(self.question1.id)
        }, format="json")
        
        # Should get 404 because get_queryset filters by user
        self.assertEqual(resp.status_code, 404)
