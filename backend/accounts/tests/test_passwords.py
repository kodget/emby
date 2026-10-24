import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.passwords import request_password_reset, reset_password_with_token


class ResetFixture:
    def setUp(self):
        self.user = User.objects.create_user('reset-user', email='reset@example.test', password='Original-83-safe')
        self.api = APIClient()

    def token(self):
        request_password_reset(self.user.email)
        link = mail.outbox[-1].body.splitlines()[0].split('password: ', 1)[1]
        return parse_qs(urlsplit(link).query)['token'][0]


@override_settings(DEBUG=True, PASSWORD_RESET_TIMEOUT=3600)
class PasswordResetTests(ResetFixture, TestCase):
    def test_single_use_token_changes_password_and_clears_its_digest(self):
        token = self.token()
        stored = Profile.objects.get(user=self.user).password_reset_token
        self.assertNotEqual(token, stored)
        self.assertLessEqual(len(stored), 100)
        reset_password_with_token(token, 'New-safe-password-382')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-safe-password-382'))
        self.assertFalse(Profile.objects.get(user=self.user).password_reset_token)
        with self.assertRaises(ValidationError):
            reset_password_with_token(token, 'Another-password-422')

    def test_known_unknown_inactive_and_failed_email_have_same_public_response(self):
        known = self.api.post('/auth/forgot-password/', {'email': self.user.email})
        unknown = self.api.post('/auth/forgot-password/', {'email': 'unknown@example.test'})
        self.assertEqual((known.status_code, known.data), (unknown.status_code, unknown.data))
        self.assertEqual(known.status_code, 200)
        self.assertNotIn('has been sent', known.data['message'])
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.api.post('/auth/forgot-password/', {'email': self.user.email}).data, known.data)
        self.user.is_active = True
        self.user.save()
        Profile.objects.filter(user=self.user).update(password_reset_token='')
        with patch('accounts.email_service.send_mail', side_effect=RuntimeError('secret-provider-detail')):
            failed = self.api.post('/auth/forgot-password/', {'email': self.user.email})
        self.assertEqual(failed.data, known.data)
        self.assertNotIn('secret-provider-detail', str(failed.data))

    def test_resend_cooldown_and_newest_link(self):
        token = self.token()
        request_password_reset(self.user.email)
        self.assertEqual(len(mail.outbox), 1)
        with patch('accounts.passwords.time.time', return_value=time.time() + 61):
            newer = self.token()
        with self.assertRaises(ValidationError):
            reset_password_with_token(token, 'New-safe-password-382')
        reset_password_with_token(newer, 'New-safe-password-382')

    def test_expired_and_tampered_links_fail(self):
        token = self.token()
        with patch('django.core.signing.time.time', return_value=time.time() + 3601):
            with self.assertRaises(ValidationError):
                reset_password_with_token(token, 'New-safe-password-382')
        with self.assertRaises(ValidationError):
            reset_password_with_token(token + 'tampered', 'New-safe-password-382')

    def test_email_or_password_change_invalidates_existing_link(self):
        for field, value in [('email', 'changed@example.test'), ('password', 'Another-safe-848')]:
            with self.subTest(field=field):
                Profile.objects.filter(user=self.user).update(password_reset_token='')
                token = self.token()
                if field == 'password':
                    self.user.set_password(value)
                else:
                    self.user.email = value
                self.user.save()
                with self.assertRaises(ValidationError):
                    reset_password_with_token(token, 'New-safe-password-382')

    def test_missing_expiry_and_legacy_tokens_are_rejected(self):
        token = self.token()
        Profile.objects.filter(user=self.user).update(password_reset_token_expires=None)
        with self.assertRaises(ValidationError):
            reset_password_with_token(token, 'New-safe-password-382')
        Profile.objects.filter(user=self.user).update(password_reset_token='old-unbounded-token')
        with self.assertRaises(ValidationError):
            reset_password_with_token('old-unbounded-token', 'New-safe-password-382')

    def test_duplicate_email_does_not_reset_arbitrarily_selected_account(self):
        User.objects.create_user('duplicate', email=self.user.email)
        request_password_reset(self.user.email)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(Profile.objects.get(user=self.user).password_reset_token)

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}])
    def test_invalid_password_preserves_link_and_atomic_failure_preserves_old_password(self):
        token = self.token()
        with self.assertRaises(ValidationError):
            reset_password_with_token(token, 'short')
        with patch.object(Profile, 'save', side_effect=RuntimeError('database failure')):
            with self.assertRaises(RuntimeError):
                reset_password_with_token(token, 'New-safe-password-382')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Original-83-safe'))
        reset_password_with_token(token, 'New-safe-password-382')

    def test_malformed_payloads_return_validation_errors(self):
        for data in ({}, {'token': [], 'new_password': {}}, {'token': 'bad', 'new_password': 'valid-password-482'}):
            self.assertEqual(self.api.post('/auth/reset-password/', data, format='json').status_code, 400)


@override_settings(DEBUG=True, PASSWORD_RESET_TIMEOUT=3600)
class ConcurrentPasswordResetTests(ResetFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_requests_can_only_consume_the_link_once(self):
        token = self.token()
        barrier = Barrier(2)
        def consume(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                reset_password_with_token(token, f'New-password-{index}-483')
                return 'reset'
            except ValidationError:
                return 'used'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(consume, range(2))), ['reset', 'used'])
