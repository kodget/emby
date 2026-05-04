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
