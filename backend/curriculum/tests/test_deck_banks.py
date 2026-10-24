from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup
from curriculum.models import SlideDeck, SlidePage, Slide, Block, Subject, QuizQuestion, SlideContent
from curriculum.views import SlideDeckViewSet
from curriculum.tests.test_bank_recovery import BankFixture, BODY, TEXT, mcq
from curriculum.services.ai_question_generator import AIQuestionGenerator
from learning.deck_banks import prepare_deck_bank
from learning.models import QuestionGenerationJob
from learning import generation as gen
from learning.bank_sources import eligible_questions


class DeckFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.block = Block.objects.create(id='deck-module', name='Module', subject=self.slide.subject)
        self.deck = SlideDeck.objects.create(id=self.slide.pk, title='Standalone document',
            class_group=self.slide.class_group, uploaded_by=self.user, original_file='', file_type='pdf',
            processing_status='completed', page_count=1,
            text_extraction={'version': 1, 'status': 'complete', 'total_pages': 1,
                'source_sha256': 'standalone-original', 'pages': [{'page_number': 1, 'extraction_status': 'complete'}]})
        SlidePage.objects.create(deck=self.deck, slide_number=1, extracted_text=BODY,
                                 image_url='https://storage.invalid/page.png', width=100, height=100)
        self.selection = {'subject': self.slide.subject_id, 'block': self.block.pk}

    def endpoint(self, method='post', data=None, action='question_bank'):
        request = getattr(APIRequestFactory(), method)('/api/test/', data or {}, format='json')
        force_authenticate(request, self.user)
        return SlideDeckViewSet.as_view({method: action})(request, id=self.deck.pk)

    def prepare(self):
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queued, self.captureOnCommitCallbacks(execute=True):
            response = self.endpoint(data=self.selection)
        self.assertEqual(response.status_code, 202, response.data)
        self.deck.refresh_from_db()
        return self.deck.curriculum_slide, queued


class DeckBankTests(DeckFixture, TestCase):
    def test_explicit_association_reuses_original_and_pages_without_matching_ids(self):
        source, queue = self.prepare()
        self.assertNotEqual(source.pk, self.slide.pk)
        self.assertEqual(source.class_group_id, self.deck.class_group_id)
        self.assertEqual((source.subject_id, source.block_id), (self.slide.subject_id, self.block.pk))
        self.assertEqual(gen.slide_text(source), TEXT)
        self.assertEqual(SlideContent.objects.get(slide=source).content_data['pages'][0]['image_url'], 'https://storage.invalid/page.png')
        queue.assert_called_once_with(source.pk)
        self.assertFalse(QuestionGenerationJob.objects.filter(slide=self.slide).exists())

    def test_duplicate_submission_reuses_source_and_does_not_redispatch(self):
        source, _ = self.prepare()
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            response = self.endpoint(data=self.selection)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['queued'])
        self.assertEqual(response.data['slide_id'], source.pk)
        self.assertEqual(QuestionGenerationJob.objects.count(), 1)
        queue.assert_not_called()

    def test_generated_bank_completes_with_five_of_each_difficulty_and_is_readable_by_class(self):
        source, _ = self.prepare()
        with patch.object(AIQuestionGenerator, 'generate_mcqs_from_text', side_effect=self.rows('mcq')), patch.object(
                AIQuestionGenerator, 'generate_theory_from_text', side_effect=self.rows('theory')):
            self.assertTrue(gen.generate_for_slide(source)['success'])
        self.user.profile.class_role = 'student'; self.user.profile.save()
        response = self.endpoint('get')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['can_generate'])
        self.assertEqual(response.data['question_bank']['mcq_by_difficulty'], {'easy': 5, 'medium': 5, 'hard': 5})
        self.assertEqual(self.endpoint(data={'force': True}).status_code, 403)

    def test_other_class_cannot_read_or_prepare_the_bank(self):
        school = School.objects.create(name='Other school')
        group = ClassGroup.objects.create(school=school, set_name='Other class', code='987654')
        self.user.profile.class_group = group; self.user.profile.save()
        self.assertEqual(self.endpoint('get').status_code, 404)
        self.assertEqual(self.endpoint(data=self.selection).status_code, 404)
        self.assertFalse(QuestionGenerationJob.objects.exists())

    def test_another_uploader_cannot_assign_someone_elses_deck(self):
        from django.contrib.auth.models import User
        other = User.objects.create_user('other-deck-uploader')
        SlideDeck.objects.filter(pk=self.deck.pk).update(uploaded_by=other)
        self.assertEqual(self.endpoint(data=self.selection).status_code, 403)

    def test_mismatched_parent_and_missing_assignment_leave_no_source(self):
        other = Subject.objects.create(id='other-course', name='Other course', class_group=self.deck.class_group)
        self.assertEqual(self.endpoint(data={'subject': other.pk, 'block': self.block.pk}).status_code, 400)
        self.assertEqual(self.endpoint(data={}).status_code, 400)
        self.assertFalse(QuestionGenerationJob.objects.exists())
        self.deck.refresh_from_db(); self.assertIsNone(self.deck.curriculum_slide_id)

    def test_foreign_course_and_foreign_page_asset_cannot_enter_the_bank(self):
        from curriculum.models import MediaAsset
        school = School.objects.create(name='Foreign school')
        group = ClassGroup.objects.create(school=school, set_name='Foreign class', code='123987')
        course = Subject.objects.create(id='foreign-course', name='Foreign course', class_group=group)
        self.assertEqual(self.endpoint(data={**self.selection, 'subject': course.pk}).status_code, 404)
        asset = MediaAsset.objects.create(class_group=group, uploaded_by=self.user, public_id='foreign/page',
                                         resource_type='image', delivery_type='authenticated')
        self.deck.pages.update(asset=asset)
        with patch('curriculum.tasks.generate_question_bank_task.delay') as queue, self.captureOnCommitCallbacks(execute=True):
            response = self.endpoint(data=self.selection)
        self.assertEqual(response.status_code, 400)
        self.deck.refresh_from_db()
        self.assertIsNone(self.deck.curriculum_slide_id)
        self.assertEqual(Slide.objects.count(), 1)
        self.assertFalse(QuestionGenerationJob.objects.exists())
        queue.assert_not_called()

    def test_cannot_replace_association_or_pass_arbitrary_source_identifier(self):
        source, _ = self.prepare()
        other = Block.objects.create(id='other-module', name='Other module', subject=source.subject)
        self.assertEqual(self.endpoint(data={'block': other.pk}).status_code, 400)
        self.assertEqual(self.endpoint(data={'curriculum_slide': self.slide.pk}).status_code, 400)
        self.deck.refresh_from_db(); self.assertEqual(self.deck.curriculum_slide_id, source.pk)

    def test_incomplete_processing_and_invalid_retry_flag_are_rejected(self):
        self.assertEqual(self.endpoint(data={**self.selection, 'force': 'true'}).status_code, 400)
        self.deck.processing_status = 'processing'; self.deck.save()
        self.assertEqual(self.endpoint(data=self.selection).status_code, 400)
        self.assertFalse(QuestionGenerationJob.objects.exists())

    def test_source_change_fences_old_worker_and_retry_refreshes_canonical_cache(self):
        source, _ = self.prepare()
        job = gen.claim_job(source)
        gen.save_batch(job, source, [mcq()], TEXT, 'mcq', 'easy', 1)
        self.deck.pages.update(extracted_text=BODY + ' New source fact.')
        self.assertFalse(eligible_questions(QuizQuestion.objects.all()).exists())
        with self.assertRaises(gen.LostLease):
            gen.save_batch(job, source, [mcq(2)], TEXT, 'mcq', 'easy', 1)
        self.expire(job)
        with patch('curriculum.tasks.generate_question_bank_task.delay'), self.captureOnCommitCallbacks(execute=True):
            response = self.endpoint(data={'force': True})
        self.assertEqual(response.status_code, 202)
        self.assertIn('New source fact.', gen.slide_text(source))
        self.assertEqual(QuizQuestion.objects.count(), 1)

    def test_deletion_removes_only_linked_source_and_preserves_question_history(self):
        source, _ = self.prepare()
        job = gen.claim_job(source)
        gen.save_batch(job, source, [mcq()], TEXT, 'mcq', 'easy', 1)
        response = self.endpoint('delete', action='destroy')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Slide.objects.filter(pk=source.pk).exists())
        self.assertTrue(Slide.objects.filter(pk=self.slide.pk).exists())
        self.assertIsNone(QuizQuestion.objects.get().source_slide_id)
        self.assertFalse(eligible_questions(QuizQuestion.objects.all()).exists())


@skipUnless(connection.vendor == 'postgresql', 'Row-lock race requires disposable PostgreSQL')
class DeckBankConcurrencyTests(DeckFixture, TransactionTestCase):
    def test_racing_initial_requests_create_only_one_source_and_job(self):
        barrier = Barrier(2)
        def request():
            close_old_connections()
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                return prepare_deck_bank(self.deck.pk, user, self.selection)[1]['slide_id']
            finally:
                close_old_connections()
        # Replace the module's task object: Celery's proxy resolves per thread,
        # so patching its .delay attribute in the parent does not isolate workers.
        with patch('curriculum.tasks.generate_question_bank_task') as task, ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(lambda _: request(), range(2)))
        self.assertEqual(len(set(result)), 1)
        self.assertEqual(QuestionGenerationJob.objects.count(), 1)
        task.delay.assert_called_once()
