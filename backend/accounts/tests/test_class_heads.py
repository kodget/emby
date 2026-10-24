from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.class_heads import request_review, review_class_head
from accounts.models import ClassGroup, ClassRole, Profile, School
from accounts.permissions import can_manage_class, can_upload_slides
from accounts.serializers import ProfileSerializer
from credits.config import get_user_credit_tier
from learning.models import Notification


class AccountFixture:
    def setUp(self):
        self.school = School.objects.create(name="Test medical school")
        self.group = ClassGroup.objects.create(school=self.school, set_name="Year 1", code="123456")
        self.admin = User.objects.create_user("reviewer", is_staff=True, is_superuser=True)
        self.api = APIClient()

    def applicant(self, name, *, group=None):
        user = User.objects.create_user(name, email=f"{name}@example.test")
        profile = user.profile
        profile.class_role = ClassRole.CLASS_HEAD
        profile.school = self.school
        profile.set_name = "Year 1"
        profile.class_group = group or self.group
        profile.onboarding_completed = True
        profile.save()
        request_review(user.pk)
        return user


class ClassHeadTests(AccountFixture, TestCase):
    def test_request_is_pending_and_has_one_persistent_notification_per_admin(self):
        user = self.applicant("pending")
        request_review(user.pk)
        profile = Profile.objects.get(user=user)
        self.assertTrue(profile.class_head_verification_requested)
        self.assertFalse(profile.class_head_verified)
        self.assertEqual(Notification.objects.filter(user=self.admin).count(), 1)
        self.assertFalse(self.group.class_heads.filter(pk=user.pk).exists())

    def test_three_approved_heads_and_idempotent_retry(self):
        users = [self.applicant(f"head-{index}") for index in range(4)]
        for user in users[:3]:
            review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        profile, changed = review_class_head(actor=self.admin, user_id=users[0].pk, approved=True)
        self.assertFalse(changed)
        self.assertEqual(self.group.class_heads.count(), 3)
        with self.assertRaises(ValidationError):
            review_class_head(actor=self.admin, user_id=users[3].pk, approved=True)
        users[3].profile.refresh_from_db()
        self.assertFalse(users[3].profile.class_head_verified)
        self.assertTrue(users[3].profile.class_head_verification_requested)

    def test_reject_removes_membership_records_actor_and_allows_new_request(self):
        user = self.applicant("reject")
        review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        profile, _ = review_class_head(actor=self.admin, user_id=user.pk, approved=False,
                                       rejection_reason="Wrong class")
        self.assertFalse(self.group.class_heads.filter(pk=user.pk).exists())
        self.assertEqual(profile.class_head_reviewed_by, self.admin)
        self.assertIsNotNone(profile.class_head_reviewed_at)
        count = Notification.objects.count()
        _, changed = review_class_head(actor=self.admin, user_id=user.pk, approved=False,
                                       rejection_reason="Wrong class")
        self.assertFalse(changed)
        self.assertEqual(Notification.objects.count(), count)
        profile, changed = request_review(user.pk)
        self.assertTrue(changed)
        self.assertEqual(profile.class_head_rejection_reason, "")
        self.assertEqual(profile.class_head_request_version, 2)

    def test_approval_is_independent_of_email_verification(self):
        user = self.applicant("independent")
        profile, _ = review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        self.assertFalse(profile.email_verified)
        self.assertTrue(profile.class_head_verified)

    def test_unauthorized_api_and_nonboolean_decision_are_rejected(self):
        user = self.applicant("unauthorized")
        self.api.force_authenticate(user)
        self.assertEqual(self.api.post('/auth/class-head/verify/', {'user_id': user.pk, 'approved': True}, format='json').status_code, 403)
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.post('/auth/class-head/verify/', {'user_id': user.pk, 'approved': 'false'}, format='json').status_code, 400)
        self.assertFalse(Profile.objects.get(user=user).class_head_verified)

    def test_profile_id_does_not_replace_user_identity(self):
        user = self.applicant("identity")
        Profile.objects.filter(user=user).update(id=5000)
        profile = Profile.objects.get(user=user)
        data = ProfileSerializer(profile).data
        self.assertEqual(data['id'], 5000)
        self.assertEqual(data['user_id'], user.pk)
        self.api.force_authenticate(self.admin)
        response = self.api.post('/auth/class-head/verify/', {'user_id': data['user_id'], 'approved': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['user']['id'], 5000)

    def test_pending_head_cannot_upload_even_with_stale_capability_or_receive_head_credits(self):
        user = self.applicant("limited")
        profile = Profile.objects.get(user=user)
        profile.class_capabilities = ['SLIDE_UPLOADER']
        profile.save()
        user = User.objects.get(pk=user.pk)
        self.assertFalse(can_manage_class(user.profile))
        self.assertFalse(can_upload_slides(user.profile))
        self.assertEqual(get_user_credit_tier(user)[3], 'free')

    def test_inactive_class_or_account_cannot_be_approved(self):
        user = self.applicant("inactive")
        self.group.is_active = False
        self.group.save()
        with self.assertRaises(ValidationError):
            review_class_head(actor=self.admin, user_id=user.pk, approved=True)

    def test_class_code_cannot_move_approved_privileges(self):
        user = self.applicant("move")
        review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        other = ClassGroup.objects.create(school=self.school, set_name="Year 2", code="654321")
        self.api.force_authenticate(user)
        response = self.api.post('/auth/class/join/', {'class_code': other.code}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Profile.objects.get(user=user).class_group_id, self.group.pk)

    def test_admin_fields_and_universal_admin_cannot_bypass_approval(self):
        user = self.applicant("bypass")
        self.assertIn('class_head_verified', admin.site._registry[Profile].readonly_fields)
        self.assertIn('class_heads', admin.site._registry[ClassGroup].readonly_fields)
        self.api.force_authenticate(self.admin)
        for route, payload in [
            (f'/auth/admin/data/accounts/profile/{user.profile.pk}/', {'class_head_verified': True}),
            (f'/auth/admin/data/accounts/classgroup/{self.group.pk}/', {'class_heads': [user.pk]}),
            (f'/auth/admin/data/auth/user/{user.pk}/', {'managed_classes': [self.group.pk]}),
        ]:
            with self.subTest(route=route):
                self.assertEqual(self.api.put(route, payload, format='json').status_code, 400)
        self.assertFalse(Profile.objects.get(user=user).class_head_verified)

    def test_universal_admin_redacts_authentication_tokens(self):
        self.api.force_authenticate(self.admin)
        response = self.api.get(f'/auth/admin/data/auth/user/{self.admin.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('password', response.data)

    def test_reactivation_cannot_add_fourth_active_head(self):
        inactive = self.applicant('old-head')
        review_class_head(actor=self.admin, user_id=inactive.pk, approved=True)
        inactive.is_active = False
        inactive.save()
        for index in range(3):
            user = self.applicant(f'current-{index}')
            review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        self.api.force_authenticate(self.admin)
        response = self.api.put(f'/auth/admin/data/auth/user/{inactive.pk}/', {'is_active': True}, format='json')
        self.assertEqual(response.status_code, 400)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)


class OnboardingTests(AccountFixture, TestCase):
    def test_retry_does_not_duplicate_registration_notifications_or_email(self):
        user = User.objects.create_user('new-head', email='new@example.test')
        self.api.force_authenticate(user)
        data = {'class_role': 'class_head', 'school_name': self.school.name, 'set_name': 'Year 1'}
        with patch('accounts.onboarding.send_transactional_email') as send:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.api.post('/auth/onboarding/submit/', data, format='json')
                second = self.api.post('/auth/onboarding/submit/', data, format='json')
            self.assertEqual(first.status_code, 200, first.data)
            self.assertEqual(second.status_code, 200, second.data)
            send.assert_called_once()
            self.assertIn(self.group.code, send.call_args.args[1])
        self.assertEqual(Notification.objects.filter(user=self.admin).count(), 1)
        self.assertFalse(Profile.objects.get(user=user).class_head_verified)

    def test_completed_onboarding_cannot_change_role_or_class(self):
        user = self.applicant('replay')
        review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        self.api.force_authenticate(user)
        response = self.api.post('/auth/onboarding/submit/', {
            'class_role': 'class_head', 'school_name': self.school.name, 'set_name': 'Other class',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Profile.objects.get(user=user).class_group_id, self.group.pk)

    def test_invalid_answers_do_not_partially_complete_onboarding(self):
        user = User.objects.create_user('invalid-response')
        self.api.force_authenticate(user)
        response = self.api.post('/auth/onboarding/submit/', {
            'class_role': 'class_head', 'school_name': 'Not created', 'set_name': 'Year 1',
            'responses': [{'question_id': '9999', 'answer': 'Test'}],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Profile.objects.get(user=user).onboarding_completed)
        self.assertFalse(School.objects.filter(name='Not created').exists())


class ConcurrentApprovalTests(AccountFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_administrators_cannot_both_take_last_slot(self):
        for index in range(2):
            user = self.applicant(f'existing-{index}')
            review_class_head(actor=self.admin, user_id=user.pk, approved=True)
        candidates = [self.applicant(f'candidate-{index}').pk for index in range(2)]
        start = Barrier(2)
        def approve(user_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.admin.pk)
                start.wait(timeout=10)
                review_class_head(actor=actor, user_id=user_id, approved=True)
                return 'approved'
            except ValidationError:
                return 'full'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(approve, candidates))
        self.assertCountEqual(outcomes, ['approved', 'full'])
        self.assertEqual(Profile.objects.filter(class_group=self.group, class_head_verified=True, user__is_active=True).count(), 3)
        self.assertEqual(self.group.class_heads.count(), 3)
