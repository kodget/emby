from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.ai_policy import defer_automatic_ai, on_demand, DEFERRED_MESSAGE
from curriculum import document_index, slide_processing, views
from curriculum.models import SlideContent, DocumentIndexJob
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.tests.test_slide_processing import ProcessingFixture
from learning.generation_dispatch import request_generation, recover_generation_jobs
from learning.models import QuestionGenerationJob


class ManualAIPolicyTests(BankFixture, TestCase):
    def test_existing_pending_jobs_are_deferred_without_erasing_content(self):
        original = SlideContent.objects.get(slide=self.slide).content_data
        bank = QuestionGenerationJob.objects.create(slide=self.slide, status='pending')
        index = DocumentIndexJob.objects.create(slide=self.slide, status='pending')
        defer_automatic_ai(self.slide)
        self.assertTrue(on_demand(self.slide))
        bank.refresh_from_db(); index.refresh_from_db()
        self.assertEqual(bank.error, DEFERRED_MESSAGE)
        self.assertIsNone(bank.next_attempt_at)
        self.assertEqual(index.error_code, 'on_demand')
        self.assertIsNone(index.next_attempt_at)
        self.assertEqual(SlideContent.objects.get(slide=self.slide).content_data['pages'], original['pages'])
        with patch('curriculum.tasks.generate_question_bank_task.delay') as generate, \
             patch('curriculum.tasks.index_document_task.delay') as read:
            self.assertEqual(recover_generation_jobs(), {'published': 0})
            self.assertEqual(document_index.recover(), 0)
        generate.assert_not_called(); read.assert_not_called()

    def test_automatic_requests_do_not_create_jobs(self):
        defer_automatic_ai(self.slide)
        self.assertFalse(request_generation(self.slide))
        self.assertFalse(document_index.request_index(self.slide, force=True))
        self.assertFalse(QuestionGenerationJob.objects.exists())
        self.assertFalse(DocumentIndexJob.objects.exists())

    def test_student_can_request_a_deferred_bank_but_cannot_force_regeneration(self):
        from django.contrib.auth.models import User
        self.user.profile.class_role = 'student'; self.user.profile.save()
        self.slide.uploaded_by = User.objects.create_user('original-uploader')
        self.slide.save(update_fields=['uploaded_by'])
        QuestionGenerationJob.objects.create(slide=self.slide, status='pending')
        defer_automatic_ai(self.slide)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            response = self.api()
        self.assertEqual(response.status_code, 202, response.data)
        queue.assert_called_once_with(self.slide.pk)
        self.assertEqual(QuestionGenerationJob.objects.get(slide=self.slide).attempts, 0)
        self.assertEqual(self.api({'force': True}).status_code, 403)

    def test_explicit_ai_request_resumes_deferred_index(self):
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['pages'][0].update(text='', extraction_status='needs_ocr')
        content.content_data['text_extraction']['status'] = 'failed'
        content.save()
        DocumentIndexJob.objects.create(slide=self.slide, status='pending')
        defer_automatic_ai(self.slide)
        with patch('curriculum.tasks.index_document_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(document_index.request_index(self.slide, requested=True))
        job = DocumentIndexJob.objects.get(slide=self.slide)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.attempts, 0)
        queue.assert_called_once_with(job.pk)

    def test_student_can_prepare_manual_ai_but_cannot_rerender_or_access_another_class(self):
        from django.contrib.auth.models import User
        from accounts.models import ClassGroup
        self.user.profile.class_role = 'student'
        self.user.profile.save()
        self.slide.uploaded_by = User.objects.create_user('source-owner')
        self.slide.save(update_fields=['uploaded_by'])
        content = SlideContent.objects.get(slide=self.slide)
        content.content_data['pages'][0].update(text='', extraction_status='needs_ocr')
        content.content_data['text_extraction']['status'] = 'failed'
        content.save()

        def request(payload):
            req = APIRequestFactory().post('/api/test/', payload, format='json')
            force_authenticate(req, self.user)
            return views.reprocess_slide(req, slide_id=self.slide.pk)

        self.assertEqual(request({'index_only': True}).status_code, 403)
        defer_automatic_ai(self.slide)
        with patch('curriculum.tasks.index_document_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            response = request({'index_only': True})
        self.assertEqual(response.status_code, 202, response.data)
        self.assertTrue(response.data['queued'])
        queue.assert_called_once()
        with patch('curriculum.slide_processing.reserve') as reserve:
            self.assertEqual(request({}).status_code, 403)
        reserve.assert_not_called()

        self.user.profile.class_group = ClassGroup.objects.create(
            school=self.slide.class_group.school, set_name='Another class', code='123987')
        self.user.profile.save()
        with patch('curriculum.document_index.request_index') as index:
            self.assertEqual(request({'index_only': True}).status_code, 404)
        index.assert_not_called()


class ManualReadingTests(ProcessingFixture, TestCase):
    def test_render_and_read_do_not_start_ai_for_manual_imports(self):
        self.mocks()
        defer_automatic_ai(self.slide)
        for page in self.result['pages']:
            page.update(text='', extraction_status='needs_ocr')
        self.result['text_extraction'].update(status='failed', missing_pages=[1, 2])
        self.assertTrue(slide_processing.process(self.slide.pk)['reading_ready'])
        self.generate.assert_not_called()
        self.assertFalse(DocumentIndexJob.objects.exists())
        self.state.refresh_from_db()
        self.assertEqual(self.state.status, 'completed')
        request = APIRequestFactory().get('/api/test/')
        force_authenticate(request, self.user)
        with patch('curriculum.llm.chat') as ai:
            response = views.get_slide_content(request, self.slide.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['pages']), 2)
        self.assertEqual(response.data['ai_generation_mode'], 'on_demand')
        self.assertTrue(response.data['can_prepare_ai'])
        ai.assert_not_called()
