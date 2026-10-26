from pathlib import Path
from datetime import timedelta
import tempfile
import uuid
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from accounts.models import School, ClassGroup
from curriculum.models import Subject, Slide, SlideContent, SlideDeck, MediaAsset, UserProgress, UserStats, DailyStudySession
from curriculum import views
from curriculum.tests.test_document_rendering import make_document, downloaded_bytes
from learning.models import ActivityType, LearningEvent, XPAward
from learning.analytics_evidence import Evidence


class ReadingTests(TestCase):
    def setUp(self):
        queue = patch('curriculum.tasks.generate_question_bank_task.delay')
        queue.start()
        self.addCleanup(queue.stop)
        school = School.objects.create(name='Reader school')
        self.group = ClassGroup.objects.create(school=school, set_name='Year 1', code='345678')
        self.user = User.objects.create_user('reader')
        self.user.profile.class_group = self.group
        self.user.profile.save()
        self.subject = Subject.objects.create(id='reading', name='Reading', class_group=self.group)
        self.slide = Slide.objects.create(id='reading-slide', title='Lecture', file_type='pdf', page_count=3,
            subject=self.subject, class_group=self.group, uploaded_by=self.user,
            file_url='https://storage.invalid/lecture.pdf')
        self.factory = APIRequestFactory()

    def request(self, handler, data=None, action=None, **kwargs):
        req = self.factory.post('/api/test/', data, format='json') if data is not None else self.factory.get('/api/test/', kwargs.pop('query', {}))
        force_authenticate(req, self.user)
        if action:
            handler = handler.as_view({'post' if data is not None else 'get': action})
        return handler(req, **kwargs)

    def progress(self, **kwargs):
        return self.request(views.UserProgressViewSet, action='update_progress', data={
            'slide_id': self.slide.pk, 'current_page': 2, 'total_pages': 99, **kwargs})

    def test_page_position_persists_and_uses_the_actual_document_length(self):
        self.assertEqual(self.progress().status_code, 200)
        row = UserProgress.objects.get()
        self.assertEqual((row.current_page, row.total_pages, row.completed), (2, 3, False))
        response = self.request(views.UserProgressViewSet, action='list', query={'slide': self.slide.pk})
        self.assertEqual(response.data[0]['current_page'], 2)
        self.assertEqual(self.progress(current_page=3).status_code, 200)
        row.refresh_from_db()
        self.assertTrue(row.completed)

    def test_invalid_pages_and_minutes_do_not_write_progress(self):
        for payload in ({'current_page': 0}, {'current_page': -1}, {'current_page': 4},
                        {'current_page': 'invalid'}, {'time_spent_minutes': -1}, {'time_spent_minutes': 'invalid'}):
            self.assertEqual(self.progress(**payload).status_code, 400)
        self.assertFalse(UserProgress.objects.exists())

    def test_unprocessed_document_is_not_marked_complete(self):
        self.slide.page_count = 0; self.slide.save()
        self.assertEqual(self.progress().status_code, 400)
        self.assertFalse(UserProgress.objects.exists())

    def test_page_only_writes_do_not_duplicate_study_minutes(self):
        self.assertEqual(self.progress(time_spent_minutes=1).status_code, 200)
        for page in (1, 2, 3):
            self.progress(current_page=page)
        self.assertEqual(UserProgress.objects.get().time_spent_minutes, 1)
        self.assertEqual(DailyStudySession.objects.get().minutes_studied, 1)
        self.assertEqual(UserStats.objects.get(user=self.user).total_study_minutes, 1)
        self.assertEqual(Evidence(self.user, 7).overview()['study_minutes'], 1)
        self.assertEqual(LearningEvent.objects.get().activity, ActivityType.RESOURCE_STUDIED)
        self.assertFalse(XPAward.objects.exists())

    def test_replayed_reading_request_does_not_add_minutes_twice(self):
        request_id = str(uuid.uuid4())
        for _ in range(2):
            self.assertEqual(self.progress(time_spent_minutes=1, request_id=request_id).status_code, 200)
        self.assertEqual(UserProgress.objects.get().time_spent_minutes, 1)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(DailyStudySession.objects.get().sessions_count, 1)
        self.assertEqual(self.progress(time_spent_minutes=2, request_id=request_id).status_code, 400)
        self.assertEqual(UserProgress.objects.get().time_spent_minutes, 1)

    def test_failed_progress_save_rolls_back_related_activity(self):
        with patch('curriculum.models.UserProgress.save', side_effect=RuntimeError('storage failure')):
            with self.assertRaises(RuntimeError):
                self.progress(time_spent_minutes=1, request_id=str(uuid.uuid4()))
        self.assertFalse(LearningEvent.objects.exists())
        self.assertFalse(DailyStudySession.objects.exists())

    def test_manual_log_is_validated_retry_safe_and_visible_in_weekly_report(self):
        request_id = str(uuid.uuid4())
        data = {'minutes': 12, 'request_id': request_id}
        for _ in range(2):
            response = self.request(views.log_study_time, data=data)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['total_today'], 12)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertFalse(XPAward.objects.exists())
        weekly = self.request(views.get_weekly_study_data).data
        self.assertEqual(weekly['total_minutes'], 12)
        self.assertEqual(weekly['week_data'][-1]['minutes'], 12)
        self.assertEqual(len(weekly['week_data']), 7)
        self.assertEqual(self.request(views.log_study_time, data={**data, 'minutes': 13}).status_code, 400)

    def test_invalid_manual_logs_do_not_write_activity(self):
        for data in ({}, {'minutes': 0}, {'minutes': -1}, {'minutes': 1441}, {'minutes': 'bad'},
                     {'minutes': 1, 'date': 'bad'}, {'minutes': 1, 'request_id': 'bad'},
                     {'minutes': 1, 'date': (timezone.localdate()+timedelta(days=1)).isoformat()}):
            with self.subTest(data=data):
                self.assertEqual(self.request(views.log_study_time, data=data).status_code, 400)
        self.assertFalse(LearningEvent.objects.exists())

    def test_manual_retry_after_midnight_keeps_the_original_study_date(self):
        now = timezone.now()
        payload = {'minutes': 5, 'request_id': str(uuid.uuid4())}
        with patch('django.utils.timezone.now', return_value=now):
            self.assertEqual(self.request(views.log_study_time, data=payload).status_code, 200)
        with patch('django.utils.timezone.now', return_value=now+timedelta(days=1)):
            response = self.request(views.log_study_time, data=payload)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['total_overall'], 5)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(DailyStudySession.objects.get().date, timezone.localdate(now))

    def test_refresh_streak_does_not_create_activity_for_visiting_the_app(self):
        for _ in range(2):
            response = self.request(views.UserStatsViewSet, action='update_streak', data={})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(UserStats.objects.get(user=self.user).current_streak, 0)
        self.assertFalse(LearningEvent.objects.exists())
        self.progress(time_spent_minutes=1)
        self.request(views.UserStatsViewSet, action='update_streak', data={})
        self.assertEqual(UserStats.objects.get(user=self.user).current_streak, 1)

    def test_weekly_report_ignores_stale_daily_cache(self):
        DailyStudySession.objects.create(user=self.user, date=timezone.localdate(), minutes_studied=999)
        response = self.request(views.get_weekly_study_data)
        self.assertEqual(response.data['total_minutes'], 0)

    def test_rejected_class_access_cannot_read_or_write_saved_position(self):
        self.progress()
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(self.progress().status_code, 404)
        self.assertEqual(self.request(views.UserProgressViewSet, action='list').data, [])

    def asset(self, **kwargs):
        return MediaAsset.objects.create(class_group=self.group, uploaded_by=self.user,
            public_id=f'fixture/{MediaAsset.objects.count()}.jpg', resource_type='image',
            delivery_type='authenticated', format='jpg', **kwargs)

    def test_on_demand_reader_stores_all_real_pages_and_then_uses_cache(self):
        with tempfile.TemporaryDirectory(prefix='emby-fixture-') as directory:
            raw = make_document(directory, 'pdf').read_bytes()
        with patch('curriculum.services.slide_conversion_pipeline._download_from_cloudinary', side_effect=downloaded_bytes(raw)) as download, patch(
                'curriculum.private_media.upload_asset', side_effect=lambda *a, **kw: self.asset()) as upload:
            first = self.request(views.get_slide_content, slide_id=self.slide.pk)
            second = self.request(views.get_slide_content, slide_id=self.slide.pk)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['total_pages'], 3)
        self.assertEqual([page['page_number'] for page in first.data['pages']], [1, 2, 3])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(upload.call_count, 3)
        download.assert_called_once()
        self.assertTrue(SlideContent.objects.get(slide=self.slide).is_extracted)

    def test_partial_page_storage_never_creates_a_successful_reader_cache(self):
        with tempfile.TemporaryDirectory(prefix='emby-fixture-') as directory:
            raw = make_document(directory, 'pdf').read_bytes()
        with patch('curriculum.services.slide_conversion_pipeline._download_from_cloudinary', side_effect=downloaded_bytes(raw)), patch(
                'curriculum.slide_renderer._upload_page_image', side_effect=['asset-first', None]):
            response = self.request(views.get_slide_content, slide_id=self.slide.pk)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(SlideContent.objects.get(slide=self.slide).is_extracted)

    def test_standalone_deck_upload_can_read_rendered_files_before_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='emby-fixture-') as directory:
            raw = make_document(directory, 'pdf').read_bytes()
        deck = SlideDeck.objects.create(id='read-deck', title='Deck', file_type='pdf',
            class_group=self.group, uploaded_by=self.user, file_size=len(raw), asset=self.asset())
        paths = []
        def store(path, **kwargs):
            self.assertTrue(Path(path).is_file())
            paths.append(path)
            return self.asset()
        with patch('requests.get', return_value=Mock(status_code=200, iter_content=Mock(return_value=[raw]))), patch('curriculum.deck_processing.upload_asset', side_effect=store):
            views.SlideDeckViewSet()._process_deck_async(deck)
        deck.refresh_from_db()
        self.assertEqual(deck.processing_status, 'completed')
        self.assertEqual(deck.pages.count(), 3)
        self.assertTrue(all(not Path(path).exists() for path in paths))
