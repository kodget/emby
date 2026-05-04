"""
Tests for past question upload and processing pipeline.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User

from pastquestions.models import PastQuestionUpload
from curriculum.models import Subject, Block, Topic, QuizQuestion


def make_user(username="pquser"):
    user = User.objects.create_user(username=username, password="pass")
    from accounts.models import Profile
    Profile.objects.get_or_create(user=user, defaults={"role": "class_head"})
    return user


def make_curriculum():
    subject = Subject.objects.create(id="physiology", name="Physiology")
    block = Block.objects.create(id="physio-b1", subject=subject, name="Block 1")
    topic = Topic.objects.create(id="cell-physio", block=block, name="Cell Physiology")
    return subject, block, topic


class PastQuestionUploadModelTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.subject, self.block, self.topic = make_curriculum()

    def test_creates_upload(self):
        upload = PastQuestionUpload.objects.create(
            uploaded_by=self.user,
            subject=self.subject,
            block=self.block,
            topic=self.topic,
            file_content="Question 1: What is osmosis?",
            file_name="physio_pq.txt",
        )
        self.assertFalse(upload.processed)
        self.assertEqual(str(upload.subject), "Physiology")


class PastQuestionServiceTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.subject, self.block, self.topic = make_curriculum()

    @patch("curriculum.question_generator.generate_questions_from_past_question_text")
    def test_process_upload_creates_questions(self, mock_gen):
        mock_gen.return_value = {"created_mcq": 3, "created_theory": 2, "error": None}

        upload = PastQuestionUpload.objects.create(
            uploaded_by=self.user,
            subject=self.subject,
            file_content="Past exam questions about cell physiology...",
        )

        from pastquestions.services import process_past_question_upload
        result = process_past_question_upload(upload.id)

        self.assertEqual(result["created_mcq"], 3)
        self.assertEqual(result["created_theory"], 2)
        self.assertIsNone(result["error"])

        upload.refresh_from_db()
        self.assertTrue(upload.processed)

    @patch("curriculum.question_generator.generate_questions_from_past_question_text")
    def test_process_empty_content_skips_ai(self, mock_gen):
        upload = PastQuestionUpload.objects.create(
            uploaded_by=self.user,
            file_content="   ",
        )

        from pastquestions.services import process_past_question_upload
        result = process_past_question_upload(upload.id)

        mock_gen.assert_not_called()
        self.assertIsNotNone(result["error"])

    def test_process_missing_upload_returns_error(self):
        from pastquestions.services import process_past_question_upload
        result = process_past_question_upload(999999)
        self.assertIsNotNone(result["error"])


class PastQuestionViewTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.subject, self.block, self.topic = make_curriculum()

    @patch("pastquestions.views.process_past_question_upload")
    def test_upload_endpoint_creates_upload(self, mock_proc):
        mock_proc.return_value = {"created_mcq": 5, "created_theory": 2, "error": None}
        resp = self.client.post(
            "/pastquestions/upload/",
            data=json.dumps({
                "content": "Q1: What is osmosis? A) Movement of water B) ...",
                "subject_id": "physiology",
                "file_name": "physio_pq.txt",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertEqual(data["created_mcq"], 5)
        self.assertTrue(PastQuestionUpload.objects.exists())

    def test_upload_requires_content(self):
        resp = self.client.post(
            "/pastquestions/upload/",
            data=json.dumps({"subject_id": "physiology"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("pastquestions.views.process_past_question_upload")
    def test_status_endpoint(self, mock_proc):
        mock_proc.return_value = {"created_mcq": 2, "created_theory": 1, "error": None}
        upload = PastQuestionUpload.objects.create(
            uploaded_by=self.user,
            file_content="Q1...",
            processed=True,
        )
        resp = self.client.get(f"/pastquestions/status/{upload.id}/")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["processed"])
