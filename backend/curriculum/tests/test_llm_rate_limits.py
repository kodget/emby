"""Provider cooldowns must not become immediate retries or long worker sleeps."""
from datetime import datetime, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from curriculum import llm
from curriculum.services.ai_question_generator import _generate, RateLimitExceeded


def response(status=200, *, headers=None, message=''):
    return SimpleNamespace(status_code=status, headers=headers or {}, text=message,
                           json=lambda: {'choices': [{'message': {'content': 'OK'}, 'finish_reason': 'stop'}],
                                         'usage': {'total_tokens': 10}})


class ProviderCooldownTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.primary = llm.Provider('groq', 'https://groq.invalid/v1', 'inert-primary-key', 'primary', '')
        self.backup = llm.Provider('backup', 'https://backup.invalid/v1', 'inert-backup-key', 'backup', '')

    def test_groq_daily_limit_duration_is_preserved_when_header_missing(self):
        error = response(429, message='tokens per day (TPD): Limit 200000, Used 199868, Requested 2664. '
                                     'Please try again in 18m13.823999999s.')
        self.assertEqual(llm._retry_delay(error), 1094)
        self.assertEqual(llm._retry_delay(response(429, message='Please try again in 1h2m3.1s.')), 3724)

    def test_interactive_timeout_tries_backup_without_repeated_long_waits(self):
        with patch.object(llm, 'providers', return_value=[self.primary, self.backup]), patch.object(
                llm.requests, 'post', side_effect=[llm.requests.Timeout('timed out'), response()]) as post, patch.object(
                llm.time, 'sleep') as sleep:
            self.assertEqual(llm.chat([{'role': 'user', 'content': 'Question'}], timeout=25, attempts=1), 'OK')
        self.assertEqual(post.call_count, 2)
        self.assertTrue(all(call.kwargs['timeout'] == 25 for call in post.call_args_list))
        sleep.assert_not_called()

    def test_retry_after_seconds_and_http_date_are_supported(self):
        self.assertEqual(llm._retry_delay(response(429, headers={'Retry-After': '1093.824'})), 1094)
        now = datetime(2026, 10, 27, tzinfo=timezone.utc).timestamp()
        date = format_datetime(datetime.fromtimestamp(now+120, tz=timezone.utc), usegmt=True)
        with patch.object(llm.time, 'time', return_value=now):
            self.assertEqual(llm._retry_delay(response(429, headers={'Retry-After': date})), 120)
        self.assertEqual(llm._retry_delay(response(429, headers={'Retry-After': 'NaN'})), 60)

    def test_exhausted_provider_is_called_once_then_skipped_until_cooldown_expires(self):
        with patch.object(llm, 'providers', return_value=[self.primary]), \
             patch.object(llm.requests, 'post', side_effect=[response(429, headers={'Retry-After': '1094'}), response()]) as post, \
             patch.object(llm.time, 'sleep') as sleep, patch.object(llm.time, 'time', return_value=1000) as clock:
            for _ in range(2):
                with self.assertRaises(llm.LLMRateLimited) as caught:
                    llm.chat([{'role': 'user', 'content': 'Test'}])
                self.assertEqual(caught.exception.retry_after, 1094)
            self.assertEqual(post.call_count, 1)
            sleep.assert_not_called()
            clock.return_value = 2095
            self.assertEqual(llm.chat([{'role': 'user', 'content': 'Test'}]), 'OK')
            self.assertEqual(post.call_count, 2)

    def test_healthy_backup_still_serves_requests_during_primary_cooldown(self):
        with patch.object(llm, 'providers', return_value=[self.primary, self.backup]), \
             patch.object(llm.requests, 'post', side_effect=[response(429, headers={'Retry-After': '1100'}), response(), response()]) as post, \
             patch.object(llm.time, 'sleep') as sleep:
            self.assertEqual(llm.chat([]), 'OK')
            self.assertEqual(llm.chat([]), 'OK')
            self.assertEqual(post.call_count, 3)
            sleep.assert_not_called()

    def test_all_exhausted_providers_report_earliest_available_retry(self):
        with patch.object(llm, 'providers', return_value=[self.primary, self.backup]), \
             patch.object(llm.requests, 'post', side_effect=[response(429, headers={'Retry-After': '1100'}),
                                                            response(429, headers={'Retry-After': '600'})]):
            with self.assertRaises(llm.LLMRateLimited) as caught:
                llm.chat([])
        self.assertEqual(caught.exception.retry_after, 600)

    def test_question_generator_keeps_provider_retry_delay(self):
        with patch.object(llm, 'chat', side_effect=llm.LLMRateLimited(retry_after=1094)):
            with self.assertRaises(RateLimitExceeded) as caught:
                _generate(['Generate a question'])
        self.assertEqual(caught.exception.retry_after, 1094)

    def test_oversized_output_is_reduced_immediately_and_reused_without_cooldown(self):
        error = response(429, message='Request too large for model on output tokens per minute (OTPM): '
                         'Limit 1000, Requested 1471. Reduce max_tokens and try again.')
        budgets = []
        def post(url, **kwargs):
            budgets.append(kwargs['json']['max_completion_tokens'])
            return error if len(budgets) == 1 else response()
        with patch.object(llm, 'providers', return_value=[self.primary]), \
                patch.object(llm.requests, 'post', side_effect=post), patch.object(llm.time, 'sleep') as sleep:
            self.assertEqual(llm.chat([], max_tokens=2048, attempts=1), 'OK')
            self.assertEqual(llm.chat([], max_tokens=6000, attempts=1), 'OK')
        self.assertEqual(budgets, [2048, 900, 900])
        sleep.assert_not_called()
        with patch.object(llm, 'providers', return_value=[self.primary]):
            self.assertEqual(llm.generation_batch_size(5), 2)
            self.assertEqual(llm.generation_batch_size(1), 1)

    def test_repeated_output_rejection_tries_backup_instead_of_scheduling_forever(self):
        error = response(429, message='Request too large on output tokens per minute (OTPM): Limit 1000')
        with patch.object(llm, 'providers', return_value=[self.primary, self.backup]), patch.object(
                llm.requests, 'post', side_effect=[error, error, response()]) as post:
            self.assertEqual(llm.chat([], attempts=1), 'OK')
        self.assertEqual(post.call_count, 3)

    def test_ordinary_output_quota_exhaustion_still_waits(self):
        error = response(429, message='Rate limit reached on output tokens per minute (OTPM): '
                         'Limit 1000, Used 990, Requested 100. Please try again in 30s.')
        with patch.object(llm, 'providers', return_value=[self.primary]), \
                patch.object(llm.requests, 'post', return_value=error) as post:
            with self.assertRaises(llm.LLMRateLimited) as caught:
                llm.chat([])
        self.assertEqual(caught.exception.retry_after, 30)
        post.assert_called_once()
