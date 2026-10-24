from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import CourseReadingCheckpoint, UserProgress
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.views import UserProgressViewSet
from learning.analytics_evidence import Evidence
from learning.models import LearningEvent, XPAward


class CourseReadingFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.slide.page_count = 3; self.slide.save()
        self.user.profile.class_role = 'student'; self.user.profile.save()

    def write(self, user=None, **kwargs):
        data = dict(slide_id=self.slide.pk, current_page=2, seconds=20, request_id=str(uuid.uuid4()))
        data.update(kwargs)
        data = {key: value for key, value in data.items() if value is not None}
        request = APIRequestFactory().post('/api/test/', data, format='json')
        force_authenticate(request, user or self.user)
        return UserProgressViewSet.as_view({'post': 'update_progress'})(request)


class CourseReadingProgressTests(CourseReadingFixture, TestCase):
    def test_short_intervals_carry_seconds_and_preserve_historical_minutes(self):
        UserProgress.objects.create(user=self.user, slide=self.slide, time_spent_minutes=7)
        for _ in range(4): self.assertEqual(self.write().status_code, 200)
        row = UserProgress.objects.get()
        self.assertEqual((row.time_spent_minutes, row.reading_seconds_remainder), (8, 20))
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 1.33)
        self.assertFalse(XPAward.objects.exists())

    def test_legacy_minutes_and_seconds_can_be_interleaved(self):
        self.write(seconds=40)
        result = self.write(seconds=None, request_id=None, time_spent_minutes=2)
        self.assertEqual(result.status_code, 200, result.data)
        self.write(seconds=20)
        row = UserProgress.objects.get()
        self.assertEqual((row.time_spent_minutes, row.reading_seconds_remainder), (3, 0))

    def test_late_replays_never_regress_the_saved_position(self):
        for seconds in (0, 20):
            key = str(uuid.uuid4())
            self.write(current_page=1, seconds=seconds, request_id=key)
            self.write(current_page=3, seconds=0)
            response = self.write(current_page=1, seconds=seconds, request_id=key)
            self.assertEqual(response.data['current_page'], 3)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(UserProgress.objects.get().reading_seconds_remainder, 20)

    def test_retry_of_a_legacy_ledger_entry_does_not_rewrite_the_page(self):
        key = str(uuid.uuid4())
        self.write(seconds=None, time_spent_minutes=1, request_id=key)
        CourseReadingCheckpoint.objects.all().delete()  # State before receipts were introduced.
        self.write(current_page=3, seconds=0)
        result = self.write(seconds=None, time_spent_minutes=1, request_id=key)
        self.assertEqual(result.data['current_page'], 3)
        self.assertEqual(UserProgress.objects.get().time_spent_minutes, 1)

    def test_receipt_survives_a_change_to_document_length(self):
        key = str(uuid.uuid4())
        self.write(current_page=3, request_id=key)
        self.slide.page_count = 2; self.slide.save()
        self.assertEqual(self.write(current_page=3, request_id=key).status_code, 200)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_conflicting_reuse_and_invalid_payloads_write_nothing(self):
        for data in ({'current_page': 4}, {'seconds': -1}, {'seconds': 301}, {'seconds': 1.5},
                     {'request_id': None}, {'request_id': 'bad'}, {'time_spent_minutes': 1}):
            with self.subTest(data=data): self.assertEqual(self.write(**data).status_code, 400)
        self.assertFalse(UserProgress.objects.exists())
        self.assertFalse(CourseReadingCheckpoint.objects.exists())
        key = str(uuid.uuid4())
        self.write(request_id=key)
        for changed in ({'seconds': 21}, {'current_page': 3}):
            self.assertEqual(self.write(request_id=key, **changed).status_code, 400)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_unaccepted_removed_page_has_specific_error_without_recording_time(self):
        self.slide.page_count = 2; self.slide.save()
        response = self.write(current_page=3)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'reading_page_unavailable')
        self.assertFalse(CourseReadingCheckpoint.objects.exists())
        self.assertFalse(LearningEvent.objects.exists())
        self.slide.page_count = 0; self.slide.save()
        self.assertNotIn('code', self.write(current_page=3).data)

    def test_failure_rolls_back_receipt_activity_and_seconds(self):
        with patch('curriculum.models.UserProgress.save', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError): self.write()
        self.assertFalse(CourseReadingCheckpoint.objects.exists())
        self.assertFalse(LearningEvent.objects.exists())
        self.assertFalse(UserProgress.objects.exists())

    def test_class_changes_reject_even_previously_accepted_receipts(self):
        key = str(uuid.uuid4())
        self.write(request_id=key)
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(self.write(request_id=key).status_code, 404)
        self.assertEqual(CourseReadingCheckpoint.objects.count(), 1)

    def test_same_receipt_identifier_is_independent_between_users(self):
        other = User.objects.create_user('course-reader-peer')
        other.profile.class_group = self.user.profile.class_group; other.profile.save()
        key = str(uuid.uuid4())
        self.assertEqual(self.write(request_id=key).status_code, 200)
        self.assertEqual(self.write(user=other, request_id=key).status_code, 200)
        self.assertEqual(CourseReadingCheckpoint.objects.count(), 2)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class CourseReadingConcurrencyTests(CourseReadingFixture, TransactionTestCase):
    def run_writes(self, keys):
        barrier = Barrier(2)
        def run(key):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                response = self.write(user=user, request_id=key, seconds=35)
                self.assertEqual(response.status_code, 200, response.data)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run, keys))

    def test_simultaneous_replays_count_once(self):
        key = str(uuid.uuid4())
        self.run_writes([key, key])
        self.assertEqual(CourseReadingCheckpoint.objects.count(), 1)
        self.assertEqual(UserProgress.objects.get().reading_seconds_remainder, 35)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_simultaneous_distinct_intervals_preserve_both(self):
        self.run_writes([str(uuid.uuid4()), str(uuid.uuid4())])
        row = UserProgress.objects.get()
        self.assertEqual((row.time_spent_minutes, row.reading_seconds_remainder), (1, 10))
        self.assertEqual(LearningEvent.objects.count(), 2)

