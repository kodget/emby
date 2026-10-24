from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum.models import SlideDeck, SlidePage, DeckReadingProgress, DeckReadingCheckpoint, UserProgress
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.views import SlideDeckViewSet
from learning.analytics_evidence import Evidence
from learning.models import LearningEvent, XPAward
from learning.progress_evidence import summary


class DeckReadingFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.deck = SlideDeck.objects.create(id='reader-deck', title='Reader', file_type='pdf',
            class_group=self.user.profile.class_group, uploaded_by=self.user, processing_status='completed', page_count=3)
        for number in range(1, 4):
            SlidePage.objects.create(deck=self.deck, slide_number=number, image_url=f'/test-{number}.png')
        self.user.profile.class_role = 'student'; self.user.profile.save()

    def request(self, data=None, user=None):
        request = (APIRequestFactory().post('/api/test/', data, format='json') if data is not None
                   else APIRequestFactory().get('/api/test/'))
        force_authenticate(request, user or self.user)
        # Supply the same action-specific permissions as DRF's router.
        view = SlideDeckViewSet.as_view({'get': 'reading_progress', 'post': 'reading_progress'},
                                       **SlideDeckViewSet.reading_progress.kwargs)
        return view(request, id=self.deck.pk)

    def write(self, **kwargs):
        data = dict(current_page=2, seconds=20, request_id=str(uuid.uuid4()))
        data.update(kwargs)
        return self.request(data)


class DeckReadingProgressTests(DeckReadingFixture, TestCase):
    def test_read_is_read_only_and_students_can_save_their_own_position(self):
        self.assertEqual(self.request().data['current_page'], 1)
        self.assertFalse(DeckReadingProgress.objects.exists())
        result = self.write(current_page=3, seconds=0)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertTrue(result.data['completed'])
        self.assertEqual(self.request().data['current_page'], 3)
        self.assertFalse(LearningEvent.objects.exists())
        self.assertFalse(XPAward.objects.exists())
        self.assertEqual(summary(self.user)['slides_completed'], 1)

    def test_short_reading_intervals_are_saved_without_rounding_or_xp(self):
        for _ in range(3):
            self.assertEqual(self.write().status_code, 200)
        self.assertEqual(DeckReadingProgress.objects.get().total_seconds, 60)
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 1)
        self.assertEqual(summary(self.user)['total_study_minutes'], 1)
        self.assertFalse(XPAward.objects.exists())

    def test_completion_rechecks_current_page_count_and_processing_state(self):
        self.write(current_page=3, seconds=0)
        self.deck.page_count = 4; self.deck.save()
        self.assertFalse(self.request().data['completed'])
        self.assertEqual(summary(self.user)['slides_completed'], 0)
        self.deck.page_count = 3; self.deck.processing_status = 'processing'; self.deck.save()
        self.assertFalse(self.request().data['completed'])
        self.assertEqual(summary(self.user)['slides_completed'], 0)

    def test_deck_and_curriculum_bridge_count_as_one_completed_document(self):
        self.deck.curriculum_slide = self.slide; self.deck.save()
        UserProgress.objects.create(user=self.user, slide=self.slide, current_page=3, total_pages=3, completed=True)
        self.write(current_page=3, seconds=0)
        self.assertEqual(summary(self.user)['slides_completed'], 1)

    def test_replaying_old_time_or_position_does_not_move_the_latest_page_backwards(self):
        for seconds in (0, 20):
            key = str(uuid.uuid4())
            first = self.write(current_page=1, seconds=seconds, request_id=key)
            self.assertEqual(first.status_code, 200)
            self.write(current_page=3, seconds=0)
            replay = self.write(current_page=1, seconds=seconds, request_id=key)
            self.assertEqual(replay.data['current_page'], 3)
        self.assertEqual(DeckReadingProgress.objects.get().total_seconds, 20)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_reusing_request_id_with_different_values_rejects_the_write(self):
        key = str(uuid.uuid4())
        self.write(request_id=key)
        result = self.write(request_id=key, seconds=25)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(DeckReadingProgress.objects.get().total_seconds, 20)

    def test_accepted_receipt_replays_after_page_removal_or_reprocessing(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.write(current_page=3, request_id=key).status_code, 200)
        self.deck.pages.filter(slide_number=3).delete()
        self.deck.page_count = 2; self.deck.save()
        response = self.write(current_page=3, request_id=key)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['current_page'], 2)
        self.deck.processing_status = 'processing'; self.deck.save()
        self.assertEqual(self.write(current_page=3, request_id=key).status_code, 200)
        self.assertEqual(self.write(current_page=3, seconds=21, request_id=key).status_code, 400)
        self.assertEqual(DeckReadingProgress.objects.get().total_seconds, 20)
        self.assertEqual(LearningEvent.objects.count(), 1)

    def test_unaccepted_removed_page_is_distinct_from_temporary_processing(self):
        self.deck.pages.filter(slide_number=2).delete()
        response = self.write()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'reading_page_unavailable')
        self.assertFalse(DeckReadingCheckpoint.objects.exists())
        self.assertFalse(LearningEvent.objects.exists())
        self.deck.processing_status = 'processing'; self.deck.save()
        self.assertNotIn('code', self.write().data)

    def test_invalid_pages_times_and_request_ids_create_no_evidence(self):
        for data in ({'current_page': 0}, {'current_page': 4}, {'seconds': -1},
                     {'seconds': 301}, {'seconds': 1.5}, {'request_id': 'bad'}):
            with self.subTest(data=data): self.assertEqual(self.write(**data).status_code, 400)
        SlidePage.objects.filter(deck=self.deck, slide_number=2).delete()
        self.assertEqual(self.write().status_code, 400)
        self.deck.processing_status = 'processing'; self.deck.save()
        self.assertEqual(self.write(current_page=1).status_code, 400)
        self.assertFalse(DeckReadingCheckpoint.objects.exists())
        self.assertFalse(DeckReadingProgress.objects.exists())
        self.assertFalse(LearningEvent.objects.exists())

    def test_checkpoint_and_progress_roll_back_if_activity_write_fails(self):
        with patch('learning.events.record', side_effect=RuntimeError('simulated database failure')):
            with self.assertRaises(RuntimeError): self.write()
        self.assertFalse(DeckReadingCheckpoint.objects.exists())
        self.assertFalse(DeckReadingProgress.objects.exists())
        self.assertEqual(self.write().status_code, 200)

    def test_account_and_class_changes_do_not_expose_saved_position_or_activity(self):
        self.write()
        other = User.objects.create_user('reader-peer')
        other.profile.class_group = self.user.profile.class_group; other.profile.save()
        self.assertEqual(self.request(user=other).data['total_seconds'], 0)
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(self.request().status_code, 404)
        self.assertEqual(self.write().status_code, 404)
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 0)
        self.assertEqual(DeckReadingProgress.objects.count(), 1)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class DeckReadingConcurrencyTests(DeckReadingFixture, TransactionTestCase):
    def test_simultaneous_replays_count_one_checkpoint_and_activity(self):
        barrier = Barrier(2)
        data = dict(current_page=2, seconds=20, request_id=str(uuid.uuid4()))
        def run(_):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                response = self.request(data, user=user)
                self.assertEqual(response.status_code, 200, response.data)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run, range(2)))
        self.assertEqual(DeckReadingCheckpoint.objects.count(), 1)
        self.assertEqual(DeckReadingProgress.objects.get().total_seconds, 20)
        self.assertEqual(LearningEvent.objects.count(), 1)
