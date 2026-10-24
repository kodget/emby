import json
import tempfile
from io import StringIO
from pathlib import Path
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup, ClassRole
from curriculum import views, ai_views
from curriculum.class_access import visible
from curriculum.models import (Subject, Block, SubBlock, Topic, Slide, SlideContent, Material,
    SlideDeck, SlidePage, QuizQuestion, QuizAttempt, Quiz, QuizAnswer, Flashcard, ScheduleItem, UpcomingTest,
    SlideChatMessage)
from curriculum.quiz_views import QuizAttemptViewSet
from curriculum.upload_views import delete_file
from learning.selection import select_questions


class ClassAccessTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Medical school')
        self.groups = [ClassGroup.objects.create(school=school, set_name=f'Year {i}', code=f'12345{i}') for i in (1, 2)]
        self.users = []
        self.subjects = []
        self.blocks = []
        self.slides = []
        self.questions = []
        for i, group in enumerate(self.groups):
            user = User.objects.create_user(f'student-{i}')
            user.profile.class_group = group
            user.profile.save()
            self.users.append(user)
            subject = Subject.objects.create(id=f'subject-{i}', name=f'Course {i}', class_group=group)
            self.subjects.append(subject)
            block = Block.objects.create(id=f'block-{i}', name='Module', subject=subject)
            self.blocks.append(block)
            slide = Slide.objects.create(id=f'slide-{i}', title=f'Private file {i}', subject=subject,
                                         block=block, class_group=group, uploaded_by=user)
            self.slides.append(slide)
            SlideContent.objects.create(slide=slide, is_extracted=True,
                content_data={'total_pages': 1, 'pages': [{'page_number': 1, 'text': f'Class {i} secret'}]})
            self.questions.append(QuizQuestion.objects.create(id=f'question-{i}', question_type='mcq',
                question_text=f'Private question {i}', subject=subject, block=block, source_slide=slide, source_type='manual'))
        self.factory = APIRequestFactory()

    def request(self, handler, *, user=None, method='get', data=None, action=None, **kwargs):
        request = getattr(self.factory, method)('/api/test/', data or {}, format='json')
        force_authenticate(request, user=user or self.users[0])
        if action:
            handler = handler.as_view({method: action})
        return handler(request, **kwargs)

    def test_list_and_direct_slide_access_are_class_scoped(self):
        response = self.request(views.SlideViewSet, action='list')
        self.assertEqual([row['id'] for row in response.data], ['slide-0'])
        self.assertEqual(self.request(views.SlideViewSet, action='retrieve', pk='slide-1').status_code, 404)
        self.assertEqual(self.request(views.SlideViewSet, action='retrieve', pk='slide-0').status_code, 200)

    def test_course_lists_and_direct_parent_access_are_class_scoped(self):
        response = self.request(views.SubjectViewSet, action='list')
        self.assertEqual([row['id'] for row in response.data], ['subject-0'])
        self.assertEqual(self.request(views.BlockViewSet, action='retrieve', pk='block-1').status_code, 404)

    def test_legacy_unassigned_content_is_not_shared(self):
        Slide.objects.create(id='legacy', title='Unknown owner', subject=self.subjects[0], uploaded_by=self.users[0])
        self.assertEqual(self.request(views.SlideViewSet, action='retrieve', pk='legacy').status_code, 404)
        self.assertTrue(Slide.objects.filter(pk='legacy').exists())

    def test_member_of_class_can_read_another_members_uploaded_content(self):
        peer = User.objects.create_user('peer')
        peer.profile.class_group = self.groups[0]
        peer.profile.save()
        self.assertEqual(self.request(views.SlideViewSet, action='retrieve', pk='slide-0', user=peer).status_code, 200)

    def test_changing_uploader_membership_does_not_move_the_file(self):
        self.users[0].profile.class_group = self.groups[1]
        self.users[0].profile.save()
        self.assertEqual(self.request(views.SlideViewSet, action='retrieve', pk='slide-0').status_code, 404)
        self.slides[0].refresh_from_db()
        self.assertEqual(self.slides[0].class_group, self.groups[0])

    def test_inactive_class_classless_and_pending_heads_have_no_library(self):
        user = self.users[0]
        for change in ('inactive', 'classless', 'pending'):
            with self.subTest(change=change):
                self.groups[0].is_active = change != 'inactive'
                self.groups[0].save()
                user.profile.class_group = None if change == 'classless' else self.groups[0]
                user.profile.class_role = ClassRole.CLASS_HEAD if change == 'pending' else ClassRole.STUDENT
                user.profile.save()
                self.assertEqual(self.request(views.SlideViewSet, action='list').data, [])

    def test_extracted_pages_and_processing_status_reject_foreign_ids(self):
        for handler in (views.get_slide_content, views.slide_processing_status):
            self.assertEqual(self.request(handler, slide_id='slide-1').status_code, 404)
        response = self.request(views.get_slide_content, slide_id='slide-0')
        self.assertEqual(response.data['pages'][0]['text'], 'Class 0 secret')

    @patch('curriculum.ai_views.CreditManager.reserve_credits')
    def test_all_ai_entry_points_reject_foreign_ids_before_credit_or_provider_work(self, reserve):
        for handler in (ai_views.textbook_suggestions, ai_views.video_suggestions, ai_views.generate_mcqs,
                        ai_views.chat_with_slide, ai_views.generate_resources, ai_views.generate_flashcards):
            response = self.request(handler, method='post', data={'slide_id': 'slide-1', 'message': 'Explain'})
            self.assertEqual(response.status_code, 404, (handler.__name__, response.data))
        reserve.assert_not_called()

    @patch('curriculum.ai_views.CreditManager.reserve_credits')
    def test_missing_slide_does_not_reserve_flashcard_credits(self, reserve):
        self.assertEqual(self.request(ai_views.generate_flashcards, method='post').status_code, 400)
        reserve.assert_not_called()

    @patch('curriculum.ai_views.CreditManager.commit_usage')
    @patch('curriculum.ai_views.CreditManager.refund_credits')
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'reservation', 'reserved_amount': 3})
    @patch('curriculum.ai_views._rag_context', return_value='slide context')
    @patch('curriculum.ai_views.slide_ai.chat', return_value={
        'response': "I'm having a little trouble right now. Please try again in a moment.",
        'error': 'provider unavailable',
    })
    def test_failed_chat_provider_refunds_credits_and_does_not_persist_exchange(
        self, chat, rag_context, reserve, refund, commit,
    ):
        response = self.request(
            ai_views.chat_with_slide,
            method='post',
            data={'slide_id': 'slide-0', 'message': 'Explain this slide'},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['error'], 'The AI provider could not complete the request. Please try again.')
        refund.assert_called_once_with(
            self.users[0], 3, action='REFUND_CHAT_ERROR',
            reservation_id='reservation',
        )
        commit.assert_not_called()
        self.assertFalse(SlideChatMessage.objects.filter(user=self.users[0], slide=self.slides[0]).exists())

    def test_chat_history_foreign_id_is_rejected(self):
        for method in ('get', 'delete'):
            self.assertEqual(self.request(ai_views.chat_history, method=method, data={'slide_id': 'slide-1'}).status_code, 404)

    @patch('curriculum.ai_views.CreditManager.reserve_credits')
    def test_deck_chat_rejects_foreign_decks_before_reserving_credits(self, reserve):
        foreign_deck = SlideDeck.objects.create(
            id='foreign-deck',
            title='Private document',
            class_group=self.groups[1],
            uploaded_by=self.users[1],
            file_type='pdf',
        )
        response = self.request(
            ai_views.chat_with_slide,
            method='post',
            data={'deck_id': foreign_deck.pk, 'message': 'Summarize this document'},
        )
        self.assertEqual(response.status_code, 404)
        reserve.assert_not_called()

    def test_deck_pages_are_shared_only_with_same_class(self):
        deck = SlideDeck.objects.create(id='deck', title='Private deck', class_group=self.groups[1],
                                        uploaded_by=self.users[1], original_file='original', file_type='pdf')
        SlidePage.objects.create(deck=deck, slide_number=1, extracted_text='Private text', image='',
                                 image_url='https://example.test/page.jpg')
        self.assertEqual(self.request(views.SlideDeckViewSet, action='pages', id='deck').status_code, 404)
        self.assertEqual(self.request(views.SlideDeckViewSet, action='pages', id='deck', user=self.users[1]).status_code, 200)

    def test_cross_class_write_references_fail_before_upload(self):
        user = self.users[0]
        user.profile.class_role = ClassRole.MATERIAL_UPLOADER
        user.profile.save()
        response = self.request(views.SlideViewSet, action='create', method='post',
                                data={'title': 'Intrusion', 'subject': 'subject-1', 'block': 'block-1'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Slide.objects.filter(title='Intrusion').exists())

    def test_client_cannot_choose_another_owning_class(self):
        user = self.users[0]
        user.profile.class_role = ClassRole.MATERIAL_UPLOADER
        user.profile.save()
        response = self.request(views.SlideViewSet, action='create', method='post',
            data={'title': 'New file', 'subject': 'subject-0', 'block': 'block-0', 'class_group': self.groups[1].pk})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Slide.objects.get(pk=response.data['id']).class_group, self.groups[0])

    def test_practice_selection_and_attempt_creation_never_draw_foreign_questions(self):
        # This is an access test: both classes need genuinely usable questions.
        from curriculum.tests.test_bank_recovery import mcq
        for index, question in enumerate(self.questions):
            values = mcq(index)
            values.pop('source_page'); values.pop('source_quote')
            for field, value in values.items():
                setattr(question, field, value)
            question.save()
        chosen = select_questions(self.users[0], count=10)
        self.assertEqual([q.pk for q in chosen], ['question-0'])
        response = self.request(QuizAttemptViewSet, action='create', method='post',
            data={'exam_type': 'mock', 'configuration': {'mcq_count': 10, 'theory_count': 0, 'difficulty': 'medium'}})
        # New mocks require an explicit scope and cannot silently return a short exam.
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(QuizAttempt.objects.exists())
        foreign = self.request(QuizAttemptViewSet, action='create', method='post', data={'slide': 'slide-1'})
        self.assertEqual(foreign.status_code, 404)

    def test_old_attempt_containing_foreign_question_is_not_replayed(self):
        QuizAttempt.objects.create(id='old-attempt', user=self.users[0], question_ids=['question-1'])
        self.assertEqual(self.request(QuizAttemptViewSet, action='retrieve', pk='old-attempt').status_code, 404)
        self.assertEqual(self.request(QuizAttemptViewSet, action='list').data, [])

    def test_malformed_cross_class_question_source_is_excluded(self):
        self.questions[0].source_slide = self.slides[1]
        self.questions[0].save()
        self.assertEqual(list(visible(QuizQuestion, self.users[0])), [])

    def test_empty_attempt_with_foreign_parent_is_hidden(self):
        QuizAttempt.objects.create(id='old', user=self.users[0], block=self.blocks[1])
        self.assertEqual(self.request(QuizAttemptViewSet, action='retrieve', pk='old').status_code, 404)

    def test_legacy_quiz_history_hides_foreign_answers(self):
        quiz = Quiz.objects.create(id='old', user=self.users[0], quiz_type='mcq', completed=True)
        quiz.questions.add(self.questions[0])
        QuizAnswer.objects.create(quiz=quiz, question=self.questions[1])
        self.assertEqual(self.request(views.get_quiz_history).data, [])

    def test_legacy_quiz_rejects_answer_outside_selected_questions(self):
        quiz = Quiz.objects.create(id='old', user=self.users[0], quiz_type='mcq')
        response = self.request(views.submit_quiz_answer, method='post',
            data={'quiz_id': quiz.pk, 'question_id': self.questions[0].pk, 'selected_option': 'A'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(QuizAnswer.objects.exists())

    def test_retired_quiz_and_mock_attempt_scope_alias(self):
        sub = SubBlock.objects.create(id='sub', block=self.blocks[0], name='Submodule')
        self.questions[0].sub_block = sub
        self.questions[0].save()
        response = self.request(views.generate_quiz, method='post', data={'topic': sub.pk})
        self.assertEqual(response.status_code, 410, response.data)
        response = self.request(QuizAttemptViewSet, action='create', method='post', data={'exam_type': 'mock', 'topic': sub.pk})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_mock_topic_scope_rejected_in_favour_of_explicit_submodule(self):
        topic = Topic.objects.create(id='topic', name='Specific topic', block=self.blocks[0])
        self.slides[0].topic = topic
        self.slides[0].save()
        QuizQuestion.objects.create(id='sibling', question_type='mcq', subject=self.subjects[0],
                                    block=self.blocks[0], question_text='Sibling content')
        response = self.request(QuizAttemptViewSet, action='create', method='post', data={'exam_type': 'mock', 'topic': topic.pk})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_old_class_flashcards_and_schedule_are_hidden(self):
        Flashcard.objects.create(user=self.users[0], subject=self.subjects[1], front='Private', back='Answer')
        ScheduleItem.objects.create(user=self.users[0], slide=self.slides[1], title='Private',
                                    activity_type='read', scheduled_date=date.today())
        self.assertEqual(self.request(views.FlashcardViewSet, action='list').data, [])
        self.assertEqual(self.request(views.ScheduleItemViewSet, action='list').data, [])
        stats = self.request(views.FlashcardViewSet, action='stats')
        self.assertEqual(stats.status_code, 200)
        recommendation = self.request(views.ai_study_recommendations)
        self.assertEqual(recommendation.status_code, 200, recommendation.data)
        self.assertEqual(recommendation.data['study_plan_items'], [])

    def test_upcoming_tests_scope_and_student_write_restriction(self):
        for subject in self.subjects:
            UpcomingTest.objects.create(subject=subject, title=subject.name, test_date=date.today())
        response = self.request(views.UpcomingTestViewSet, action='list')
        self.assertEqual([row['subject'] for row in response.data], [self.subjects[0].pk])
        self.assertEqual(self.request(views.UpcomingTestViewSet, action='create', method='post',
            data={'title': 'Unauthorized', 'subject': self.subjects[0].pk, 'test_date': str(date.today())}).status_code, 403)

    @patch('curriculum.tasks.process_slide_task.delay')
    def test_uploader_cannot_reprocess_a_peers_file(self, dispatch):
        peer = User.objects.create_user('other-uploader')
        peer.profile.class_group = self.groups[0]
        peer.profile.class_role = ClassRole.MATERIAL_UPLOADER
        peer.profile.save()
        response = self.request(views.reprocess_slide, user=peer, method='post', slide_id=self.slides[0].pk)
        self.assertEqual(response.status_code, 403)
        dispatch.assert_not_called()

    @patch('cloudinary.uploader.destroy')
    def test_uploader_cannot_delete_arbitrary_storage_public_id(self, destroy):
        self.users[0].profile.class_role = ClassRole.MATERIAL_UPLOADER
        self.users[0].profile.save()
        response = self.request(delete_file, method='delete', data={'public_id': 'other-class/file'})
        self.assertEqual(response.status_code, 403)
        destroy.assert_not_called()

    def test_ownership_manifest_dry_run_apply_and_idempotent_retry(self):
        subject = Subject.objects.create(id='unassigned-course', name='Legacy course')
        block = Block.objects.create(id='unassigned-module', subject=subject, name='Legacy module')
        slide = Slide.objects.create(id='unassigned-file', title='Legacy file', subject=subject, block=block)
        manifest = {'subjects': {subject.pk: self.groups[0].pk}, 'slides': {slide.pk: self.groups[0].pk}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps(manifest))
            call_command('assign_content_classes', manifest=str(path), stdout=StringIO())
            slide.refresh_from_db()
            self.assertIsNone(slide.class_group_id)
            for _ in range(2):
                call_command('assign_content_classes', manifest=str(path), apply=True,
                             confirm_writes_paused=True, stdout=StringIO())
            slide.refresh_from_db()
            self.assertEqual(slide.class_group, self.groups[0])
            manifest['slides'][slide.pk] = self.groups[1].pk
            path.write_text(json.dumps(manifest))
            with self.assertRaises(CommandError):
                call_command('assign_content_classes', manifest=str(path), apply=True,
                             confirm_writes_paused=True, stdout=StringIO())

    def test_manifest_rejects_wrong_parent_class_without_partial_writes(self):
        Slide.objects.create(id='unknown', title='Legacy', subject=self.subjects[0], block=self.blocks[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps({'slides': {'unknown': self.groups[1].pk}}))
            with self.assertRaises(CommandError):
                call_command('assign_content_classes', manifest=str(path), apply=True,
                             confirm_writes_paused=True, stdout=StringIO())
        self.assertIsNone(Slide.objects.get(pk='unknown').class_group_id)
