import time
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.email_service import consume_verification_token, request_email_verification, send_transactional_email
from accounts.models import Profile


@override_settings(DEBUG=True)
class VerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('email-user', email='student@example.test')
        self.api = APIClient()

    def token(self):
        delivery = request_email_verification(self.user)
        self.assertTrue(delivery.sent)
        link = mail.outbox[-1].body.splitlines()[0].split('email: ', 1)[1]
        return parse_qs(urlsplit(link).query)['token'][0]

    def test_link_is_single_use_and_does_not_approve_class_head(self):
        token = self.token()
        self.assertTrue(consume_verification_token(token))
        self.assertFalse(consume_verification_token(token))
        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.email_verified)
        self.assertFalse(profile.class_head_verified)
        self.assertEqual(profile.email_verification_token, '')

    def test_database_stores_digest_not_bearer_token(self):
        token = self.token()
        stored = Profile.objects.get(user=self.user).email_verification_token
        self.assertNotEqual(stored, token)
        self.assertLessEqual(len(stored), 100)

    def test_expired_and_tampered_tokens_fail(self):
        token = self.token()
        with patch('django.core.signing.time.time', return_value=time.time() + 86401):
            self.assertFalse(consume_verification_token(token))
        self.assertFalse(consume_verification_token(token + 'tampered'))

    def test_email_change_invalidates_link(self):
        token = self.token()
        self.user.email = 'new@example.test'
        self.user.save()
        self.assertFalse(consume_verification_token(token))

    def test_resend_is_authenticated_and_throttled(self):
        self.assertEqual(self.api.post('/auth/resend-verification/').status_code, 401)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.post('/auth/resend-verification/').status_code, 200)
        response = self.api.post('/auth/resend-verification/')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_new_link_invalidates_old_link(self):
        token = self.token()
        with patch('accounts.email_service.time.time', return_value=time.time() + 61):
            new = self.token()
        self.assertFalse(consume_verification_token(token))
        self.assertTrue(consume_verification_token(new))

    def test_provider_failure_keeps_signup_and_reports_failure(self):
        with patch('accounts.email_service.send_mail', side_effect=RuntimeError('private credential')):
            response = self.api.post('/auth/signup/', {
                'email': 'signup@example.test', 'password': 'Strong-password-9283',
                'first_name': 'Test', 'last_name': 'Student',
            }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['email_status'], 'failed')
        self.assertNotIn('private credential', str(response.data))
        self.assertTrue(User.objects.filter(email='signup@example.test').exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_output_is_not_reported_as_sent(self):
        self.assertEqual(send_transactional_email('test', 'test', ['test@example.test']).status, 'unavailable')

    @override_settings(DEBUG=False)
    def test_in_memory_email_cannot_claim_delivery_in_production(self):
        self.assertEqual(send_transactional_email('test', 'test', ['test@example.test']).status, 'unavailable')

    def test_legacy_nonexpiring_token_is_rejected(self):
        Profile.objects.filter(user=self.user).update(email_verification_token='legacy-random-value')
        self.assertFalse(consume_verification_token('legacy-random-value'))
        self.assertTrue(request_email_verification(self.user).sent)
