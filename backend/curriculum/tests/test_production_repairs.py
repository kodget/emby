from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from accounts.models import Announcement, ClassGroup, ExamCountdown
from accounts.views import AnnouncementViewSet, ExamCountdownViewSet
from credits.models import CreditLot, CreditSource
from credits.services import CreditManager
from curriculum import ai_views
from curriculum.library_tutor import library_context
from curriculum.models import Block, BrainBattle, Flashcard, FlashcardProgress, Slide, SlideContent, SlideChatMessage, UserStats
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.tests.test_upload_receipts import UploadFixture
from curriculum.views import BrainBattleViewSet, UserStatsViewSet
from learning.models import Notification, NotificationPreference, NotificationType, PushSubscription
from learning import notifications


class ProductionRepairsTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.group = self.user.profile.class_group
        self.user.profile.class_role = 'student'
        self.user.profile.save()
        self.factory = APIRequestFactory()
        self.other_group = ClassGroup.objects.create(school=self.group.school, set_name='Year 2', code='654322')

    def request(self, handler, data=None, *, method='post', action=None, user=None, **kwargs):
        request = getattr(self.factory, method)('/api/test/', data or {}, format='json')
        force_authenticate(request, user or self.user)
        if action:
            handler = handler.as_view({method: action})
        return handler(request, **kwargs)

    def head(self):
        self.user.profile.class_role = 'class_head'
        self.user.profile.class_head_verified = True
        self.user.profile.save()

    def test_announcements_and_countdowns_take_class_from_authenticated_head(self):
        self.head()
        for view, data in ((AnnouncementViewSet, {'title': 'Lecture', 'content': 'Room 4'}),
                           (ExamCountdownViewSet, {'title': 'Exam', 'exam_date': str(timezone.localdate() + timedelta(days=3))})):
            response = self.request(view, {**data, 'class_group': self.other_group.pk}, action='create')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['class_group'], self.group.pk)

    def test_student_cannot_write_update_or_delete_class_notice(self):
        notice = Announcement.objects.create(class_group=self.group, created_by=self.user, title='Saved', content='Text')
        for method, action, data in [('post', 'create', {'title': 'New', 'content': 'Text'}),
                                     ('patch', 'partial_update', {'title': 'Changed'}), ('delete', 'destroy', {})]:
            response = self.request(AnnouncementViewSet, data, method=method, action=action, pk=notice.pk)
            self.assertEqual(response.status_code, 403)
        notice.refresh_from_db()
        self.assertEqual(notice.title, 'Saved')

    def test_announcement_survives_broker_outage_and_notifies_only_its_class(self):
        self.head()
        outsider = User.objects.create_user('other-class')
        outsider.profile.class_group = self.other_group
        outsider.profile.save()
        NotificationPreference.objects.create(user=self.user, quiet_hours_start=0, quiet_hours_end=0)
        with patch('learning.tasks.send_push_notification_task.delay', side_effect=RuntimeError('offline')), self.captureOnCommitCallbacks(execute=True):
            response = self.request(AnnouncementViewSet, {'title': 'Update', 'content': 'Hello'}, action='create')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Announcement.objects.filter(pk=response.data['id']).exists())
        notice = Notification.objects.get(user=self.user)
        self.assertIsNone(notice.dispatched_at)
        self.assertFalse(Notification.objects.filter(user=outsider).exists())
        with patch('learning.tasks.send_push_notification_task.delay') as push:
            notifications.dispatch_due()
            notifications.dispatch_due()
        push.assert_called_once()

    def test_privacy_is_persisted_and_public_endpoint_enforces_class(self):
        response = self.request(UserStatsViewSet, {'public_profile': False, 'public_rank': False}, method='patch', action='me')
        self.assertEqual(response.status_code, 200, response.data)
        viewer = User.objects.create_user('viewer')
        viewer.profile.class_group = self.group
        viewer.profile.save()
        response = self.request(UserStatsViewSet, method='get', action='public_profile', user=viewer, user_id=self.user.pk)
        self.assertEqual(response.status_code, 404)
        self.request(UserStatsViewSet, {'public_profile': True}, method='patch', action='me')
        response = self.request(UserStatsViewSet, method='get', action='public_profile', user=viewer, user_id=self.user.pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn('email', response.data)
        self.assertIsNone(response.data['points'])
        viewer.profile.class_group = self.other_group
        viewer.profile.save()
        self.assertEqual(self.request(UserStatsViewSet, method='get', action='public_profile', user=viewer, user_id=self.user.pk).status_code, 404)

    def test_library_search_excludes_other_class_and_bounds_context(self):
        other = Slide.objects.create(id='other-class', title='Secret', class_group=self.other_group)
        SlideContent.objects.create(slide=other, content_data={'text': 'DO NOT LEAK secret material'})
        context, sources, count = library_context(self.user, 'components')
        self.assertIn('components', context)
        self.assertNotIn('DO NOT LEAK', context)
        self.assertEqual(count, 1)
        self.assertLessEqual(len(sources), 12)
        self.assertLess(len(context), 30000)

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_google_login_reuses_existing_account_without_resetting_profile(self, verify):
        from accounts.views import google_login
        self.user.email = 'Existing@Example.Test'
        self.user.save()
        self.user.profile.onboarding_completed = True
        self.user.profile.save()
        verify.return_value = {'email': 'existing@example.test', 'email_verified': True}
        response = self.request(google_login, {'token': 'mock-google-token'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['is_new_user'])
        self.assertEqual(response.data['user']['user_id'], self.user.pk)
        self.assertEqual(response.data['user']['class_group'], self.group.pk)

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_google_login_rejects_unverified_and_inactive_accounts(self, verify):
        from accounts.views import google_login
        verify.return_value = {'email': 'unverified@example.test', 'email_verified': False}
        self.assertEqual(self.request(google_login, {'token': 'mock-token'}).status_code, 401)
        self.user.email = 'inactive@example.test'; self.user.is_active = False; self.user.save()
        verify.return_value = {'email': self.user.email, 'email_verified': True}
        self.assertEqual(self.request(google_login, {'token': 'mock-token'}).status_code, 403)

    @patch('curriculum.ai_views.slide_ai.chat', return_value={'response': 'From the slides [1]', 'total_tokens': 1000})
    def test_free_tutor_charges_credits_and_saves_class_scoped_history(self, provider):
        before = CreditManager.get_user_balance(self.user)
        response = self.request(ai_views.chat_with_slide, {'scope': 'library', 'message': 'Describe the components'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['balance'], before - 1)
        self.assertTrue(response.data['sources'])
        self.assertEqual(SlideChatMessage.objects.filter(library_class=self.group, user=self.user).count(), 2)
        self.user.profile.class_group = self.other_group
        self.user.profile.save()
        self.assertEqual(self.request(ai_views.chat_history, method='get').data['messages'], [])

    @patch('curriculum.ai_views.slide_ai.chat')
    def test_empty_library_is_not_charged(self, provider):
        SlideContent.objects.all().delete()
        with patch('curriculum.ai_views.CreditManager.reserve_credits') as reserve:
            response = self.request(ai_views.chat_with_slide, {'scope': 'library', 'message': 'Explain anatomy'})
        self.assertEqual(response.status_code, 409)
        reserve.assert_not_called()
        provider.assert_not_called()

    @patch('curriculum.ai_views.slide_ai.generate_resources', return_value={'mcqs': [{'question': 'Practice'}], 'total_tokens': 1000})
    def test_purchased_credits_unlock_generation_until_exhausted(self, provider):
        CreditLot.objects.create(user=self.user, source=CreditSource.PURCHASE, original_amount=1, remaining_amount=1)
        with patch.object(CreditManager, 'ensure_daily_allocation'):
            response = self.request(ai_views.generate_mcqs, {'slide_id': self.slide.pk})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['balance'], 0)
            response = self.request(ai_views.generate_mcqs, {'slide_id': self.slide.pk, 'refresh': True})
            self.assertEqual(response.status_code, 402, response.data)
            # Already-generated resources remain usable without charging again.
            self.assertEqual(self.request(ai_views.generate_mcqs, {'slide_id': self.slide.pk}).status_code, 200)
        provider.assert_called_once()

    @patch('curriculum.ai_views.slide_ai.generate_resources', side_effect=RuntimeError('provider offline'))
    def test_resource_failure_refunds_and_missing_text_never_calls_provider(self, provider):
        before = CreditManager.get_user_balance(self.user)
        response = self.request(ai_views.generate_resources, {'slide_id': self.slide.pk})
        self.assertEqual(response.status_code, 502, response.data)
        self.assertEqual(CreditManager.get_user_balance(self.user), before)
        SlideContent.objects.filter(slide=self.slide).update(content_data={})
        response = self.request(ai_views.generate_resources, {'slide_id': self.slide.pk})
        self.assertEqual(response.status_code, 409)
        provider.assert_called_once()

    @patch('curriculum.ai_service.generate_battle_questions')
    def test_manual_battle_needs_no_provider_or_credits_and_validates_answers(self, provider):
        payload = {'title': 'Manual battle', 'question_source': 'manual', 'manual_questions': [
            {'question': 'Which nerve?', 'options': ['A', 'B'], 'correct_index': 1}], 'time_per_question': 20}
        with patch('learning.credits.spend') as spend:
            response = self.request(BrainBattleViewSet, payload, action='create')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(BrainBattle.objects.get(pk=response.data['id']).questions[0]['correct_index'], 1)
        spend.assert_not_called(); provider.assert_not_called()
        payload['manual_questions'][0]['correct_index'] = 3
        self.assertEqual(self.request(BrainBattleViewSet, payload, action='create').status_code, 400)

    @patch('curriculum.ai_service.generate_battle_questions')
    def test_ai_battle_uses_purchased_wallet_until_exhausted(self, provider):
        provider.return_value = ([{'question': 'Which nerve?', 'options': ['A', 'B'], 'correct_index': 1}], 1000)
        CreditLot.objects.create(user=self.user, source=CreditSource.PURCHASE, original_amount=1, remaining_amount=1)
        payload = {'title': 'AI battle', 'question_source': 'ai', 'num_questions': 1}
        with patch.object(CreditManager, 'ensure_daily_allocation'), patch('learning.credits.spend') as legacy:
            response = self.request(BrainBattleViewSet, payload, action='create')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(CreditManager.get_user_balance(self.user), 0)
            self.assertEqual(self.request(BrainBattleViewSet, payload, action='create').status_code, 402)
        legacy.assert_not_called()
        provider.assert_called_once()
        self.assertEqual(BrainBattle.objects.count(), 1)
        self.assertIn('Source document', provider.call_args.kwargs['source_text'])

    def test_ai_battle_without_slide_content_is_not_charged(self):
        SlideContent.objects.all().delete()
        with patch('curriculum.ai_service.generate_battle_questions') as provider, patch.object(CreditManager, 'reserve_credits') as reserve:
            response = self.request(BrainBattleViewSet, {'title': 'No sources', 'num_questions': 1}, action='create')
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called(); reserve.assert_not_called()
        self.assertFalse(BrainBattle.objects.exists())

    @patch('curriculum.ai_service.generate_battle_questions', return_value=([], 1000))
    def test_invalid_ai_battle_refunds_wallet_and_removes_unplayable_lobby(self, provider):
        before = CreditManager.get_user_balance(self.user)
        response = self.request(BrainBattleViewSet, {'title': 'Failed', 'num_questions': 1}, action='create')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CreditManager.get_user_balance(self.user), before)
        self.assertFalse(BrainBattle.objects.exists())

    def test_battle_rejects_invalid_timer_before_generating(self):
        with patch('curriculum.ai_service.generate_battle_questions') as provider:
            for seconds in (0, -1, 301):
                response = self.request(BrainBattleViewSet, {'title': 'Bad timer', 'time_per_question': seconds}, action='create')
                self.assertEqual(response.status_code, 400)
        provider.assert_not_called()

    def test_flashcard_reminders_use_only_owners_review_progress(self):
        card = Flashcard.objects.create(user=self.user, front='Unreviewed by owner', back='Answer')
        outsider = User.objects.create_user('review-outsider')
        FlashcardProgress.objects.create(user=outsider, flashcard=card, due_date=timezone.now() + timedelta(days=30))
        notifications.build_for_user(self.user)
        self.assertIn('Unreviewed by owner', Notification.objects.get(type=NotificationType.FLASHCARDS_DUE).body)

    @override_settings(VAPID_PRIVATE_KEY='isolated-test-key')
    def test_push_retries_failed_devices_and_removes_expired_subscriptions(self):
        from learning.tasks import send_push_notification_task
        NotificationPreference.objects.create(user=self.user, browser_push_enabled=True)
        notice = Notification.objects.create(user=self.user, type=NotificationType.SYSTEM_MSG, title='Saved notice')
        devices = [PushSubscription.objects.create(user=self.user, endpoint=f'https://push.example.test/{index}',
            p256dh='test-public-key', auth='test-auth') for index in range(3)]

        class ExpiredResponse:
            status_code = 410

            def __bool__(self):
                return False

        class PushError(Exception):
            response = ExpiredResponse()

        push = Mock(side_effect=[None, OSError('transport offline'), PushError()])
        fake = SimpleNamespace(webpush=push, WebPushException=PushError)
        with patch.dict('sys.modules', {'pywebpush': fake}), patch.object(
            send_push_notification_task, 'retry', side_effect=RuntimeError('retry requested')) as retry:
            with self.assertRaisesMessage(RuntimeError, 'retry requested'):
                send_push_notification_task.run(str(notice.pk))
        self.assertEqual(retry.call_args.kwargs['kwargs']['subscription_ids'], [str(devices[1].pk)])
        self.assertFalse(PushSubscription.objects.filter(pk=devices[2].pk).exists())
        self.assertTrue(PushSubscription.objects.filter(pk=devices[0].pk).exists())

    @override_settings(VAPID_PRIVATE_KEY='isolated-test-key')
    def test_push_rechecks_preference_and_future_schedule(self):
        from learning.tasks import send_push_notification_task
        prefs = NotificationPreference.objects.create(user=self.user, browser_push_enabled=True, flashcards_enabled=False)
        notice = Notification.objects.create(user=self.user, type=NotificationType.FLASHCARDS_DUE, title='Review')
        PushSubscription.objects.create(user=self.user, endpoint='https://push.example.test/one', p256dh='key', auth='auth')
        push = Mock()
        with patch.dict('sys.modules', {'pywebpush': SimpleNamespace(webpush=push, WebPushException=OSError)}):
            send_push_notification_task.run(str(notice.pk))
            prefs.flashcards_enabled = True
            prefs.save()
            notice.scheduled_for = timezone.now() + timedelta(days=1)
            notice.save()
            send_push_notification_task.run(str(notice.pk))
        push.assert_not_called()

    def test_reminders_include_unreviewed_cards_and_class_exam_with_daily_dedupe(self):
        Flashcard.objects.create(user=self.user, front='Name the nerve', back='Femoral nerve')
        ExamCountdown.objects.create(class_group=self.group, created_by=self.user, title='Anatomy exam', exam_date=timezone.localdate() + timedelta(days=3))
        ExamCountdown.objects.create(class_group=self.other_group, created_by=self.user, title='Other exam', exam_date=timezone.localdate() + timedelta(days=3))
        notifications.build_for_user(self.user)
        notifications.build_for_user(self.user)
        self.assertEqual(Notification.objects.filter(type=NotificationType.EXAM_COUNTDOWN).count(), 1)
        self.assertIn('Name the nerve', Notification.objects.get(type=NotificationType.FLASHCARDS_DUE).body)
        self.assertFalse(Notification.objects.filter(title__contains='Other exam').exists())

    def test_quiet_hours_use_lagos_and_future_dispatch_waits(self):
        prefs = NotificationPreference.objects.create(user=self.user, quiet_hours_start=22, quiet_hours_end=7)
        local_night = timezone.localtime().replace(hour=22, minute=30)
        self.assertTrue(notifications._in_quiet_hours(prefs, local_night.astimezone(timezone.get_fixed_timezone(0))))
        self.assertEqual(timezone.localtime(notifications._next_allowed_time(prefs, local_night)).hour, 7)
        future = Notification.objects.create(user=self.user, type=NotificationType.SYSTEM_MSG, title='Future', scheduled_for=timezone.now() + timedelta(days=1))
        with patch('learning.tasks.send_push_notification_task.delay') as push:
            notifications.dispatch_due()
        push.assert_not_called()
        future.refresh_from_db(); self.assertIsNone(future.dispatched_at)


class UploadTopicTests(UploadFixture, TestCase):
    def test_one_title_creates_learn_topic_and_retry_keeps_same_topic(self):
        with patch('curriculum.views.upload_asset', side_effect=self.store):
            response = self.upload(title='One slide topic')
            self.assertEqual(response.status_code, 201, response.data)
            slide = Slide.objects.get(pk=response.data['id'])
            self.assertEqual(slide.topic.name, 'One slide topic')
            self.assertEqual(slide.topic.block_id, self.block.pk)
            repeated = self.upload(title='One slide topic')
            self.assertEqual(repeated.data['id'], slide.pk)

    def test_topic_creation_rolls_back_on_failed_upload(self):
        from curriculum.models import Topic
        with patch('curriculum.views.upload_asset', side_effect=self.store), patch(
            'curriculum.models.SlideProcessingStatus.objects.create', side_effect=RuntimeError('db failed')), patch(
            'cloudinary.uploader.destroy'):
            self.assertEqual(self.upload(title='Rollback topic').status_code, 503)
        self.assertFalse(Topic.objects.filter(name='Rollback topic').exists())
