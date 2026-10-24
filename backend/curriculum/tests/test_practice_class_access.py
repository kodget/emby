import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup, ClassRole
from curriculum.models import Subject, Block, SpotStation, StudyProfile
from curriculum.views import SteeplechaseQuestionViewSet, StudyProfileViewSet
from learning import practice, views, analytics
from learning.models import PracticeSession, PracticeAttempt, PracticeRoundUsage, PracticeMode


class PracticeClassAccessTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Practice school')
        self.users, self.groups, self.subjects, self.blocks = [], [], [], []
        for i in range(2):
            group = ClassGroup.objects.create(school=school, set_name=f'Year {i}', code=f'78901{i}')
            user = User.objects.create_user(f'practice-student-{i}')
            user.profile.class_group = group
            user.profile.subscription_tier = 'premium'
            user.profile.subscription_expires_at = timezone.now() + timezone.timedelta(days=1)
            user.profile.save()
            subject = Subject.objects.create(id=f'practice-subject-{i}', name=f'Course {i}', class_group=group)
            block = Block.objects.create(id=f'practice-block-{i}', name=f'Module {i}', subject=subject)
            self.users.append(user); self.groups.append(group); self.subjects.append(subject); self.blocks.append(block)
        self.admin = User.objects.create_user('practice-admin', is_superuser=True)
        self.factory = APIRequestFactory()
        self.shared = self.station('shared', is_shared=True)
        self.own = self.station('own', subject=self.subjects[0], block=self.blocks[0])
        self.foreign = self.station('foreign', subject=self.subjects[1], block=self.blocks[1], region='THORAX')

    def station(self, pk, **kwargs):
        defaults = dict(prompt=f'Identify {pk}', image_url=f'https://example.test/{pk}.jpg',
                        accepted_answers=['nerve'], is_approved=True, region='UPPER_LIMB')
        defaults.update(kwargs)
        return SpotStation.objects.create(id=pk, **defaults)

    def request(self, handler, *, user=None, method='get', data=None, action=None, **kwargs):
        req = getattr(self.factory, method)('/api/test/', data or {}, format='json')
        force_authenticate(req, user=user or self.users[0])
        if action:
            handler = handler.as_view({method: action})
        return handler(req, **kwargs)

    def session(self, stations, **kwargs):
        return PracticeSession.objects.create(user=self.users[0], mode=PracticeMode.STEEPLECHASE,
            station_ids=[s.pk for s in stations], total_stations=len(stations), **kwargs)

    def test_approved_shared_catalogue_is_visible_to_both_classes(self):
        for user in self.users:
            self.assertTrue(practice.station_pool(user, PracticeMode.STEEPLECHASE).filter(pk=self.shared.pk).exists())
        self.assertFalse(practice.station_pool(self.users[0], PracticeMode.STEEPLECHASE).filter(pk=self.foreign.pk).exists())

    def test_mixed_class_parents_and_unassigned_stations_are_hidden(self):
        self.station('mixed', subject=self.subjects[0], block=self.blocks[1])
        self.station('unassigned')
        ids = set(practice.playable_stations(self.users[0]).values_list('pk', flat=True))
        self.assertEqual(ids, {'shared', 'own'})

    def test_unapproved_under_review_or_incomplete_stations_are_not_playable(self):
        for pk, extra in (('unapproved', {'is_approved': False}), ('review', {'needs_review': True}),
                          ('no-answer', {'accepted_answers': []}), ('no-image', {'image_url': ''}),
                          ('no-prompt', {'prompt': ''})):
            self.station(pk, is_shared=True, **extra)
        self.assertEqual(practice.playable_stations(self.users[0]).count(), 2)

    def test_classless_inactive_and_pending_accounts_cannot_use_shared_catalogue(self):
        user = self.users[0]
        for field, value in (('class_group', None), ('class_role', ClassRole.CLASS_HEAD)):
            setattr(user.profile, field, value)
            user.profile.save()
            self.assertEqual(practice.playable_stations(user).count(), 0)
            self.assertEqual(self.request(views.practice_start, method='post').status_code, 403)
            user.profile.class_group = self.groups[0]
        user.profile.class_role = ClassRole.STUDENT
        user.profile.save()
        self.groups[0].is_active = False; self.groups[0].save()
        user.profile.class_group = self.groups[0]
        self.assertEqual(practice.playable_stations(user).count(), 0)
        self.assertFalse(PracticeSession.objects.exists())
        self.assertFalse(PracticeRoundUsage.objects.exists())

    def test_options_counts_and_sections_do_not_include_foreign_sources(self):
        response = self.request(views.practice_options)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['entitlement']['stations_available'], 2)
        self.assertEqual([s['code'] for s in response.data['sections']], ['UPPER_LIMB'])

    def test_start_selects_only_allowed_stations_and_omits_answers(self):
        response = self.request(views.practice_start, method='post', data={'count': 40})
        self.assertEqual(response.status_code, 201, response.data)
        session = PracticeSession.objects.get()
        self.assertEqual(set(session.station_ids), {'shared', 'own'})
        self.assertNotIn('accepted_answers', response.data['station'])
        self.assertNotIn('explanation', response.data['station'])

    def test_malformed_sections_fail_without_recording_a_round(self):
        response = self.request(views.practice_start, method='post', data={'sections': {'foreign': True}})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PracticeSession.objects.exists())

    def test_legacy_crud_lists_only_playable_sources_and_denies_foreign_detail(self):
        response = self.request(SteeplechaseQuestionViewSet, action='list')
        self.assertEqual({q['id'] for q in response.data}, {'shared', 'own'})
        response = self.request(SteeplechaseQuestionViewSet, action='retrieve', pk=self.foreign.pk)
        self.assertEqual(response.status_code, 404)

    def test_students_cannot_create_edit_or_delete_catalogue_questions(self):
        for method, action, extra in (('post', 'create', {}), ('patch', 'partial_update', {'pk': self.shared.pk}),
                                      ('delete', 'destroy', {'pk': self.shared.pk})):
            response = self.request(SteeplechaseQuestionViewSet, method=method, action=action,
                                    data={'id': 'forged', 'prompt': 'Changed'}, **extra)
            self.assertEqual(response.status_code, 403)
        self.shared.refresh_from_db()
        self.assertEqual(self.shared.prompt, 'Identify shared')

    def test_platform_admin_can_review_unpublished_questions(self):
        row = self.station('draft', is_approved=False)
        response = self.request(SteeplechaseQuestionViewSet, user=self.admin, method='patch',
            action='partial_update', pk=row.pk, data={'prompt': 'Reviewed prompt'})
        self.assertEqual(response.status_code, 200, response.data)

    def test_old_class_sessions_cannot_read_answer_finish_or_show_results(self):
        session = self.session([self.foreign])
        for handler, method, extra in ((views.practice_station, 'get', {'index': 0}),
                                      (views.practice_answer, 'post', {}),
                                      (views.practice_complete, 'post', {}), (views.practice_results, 'get', {})):
            response = self.request(handler, method=method, session_id=session.pk, **extra)
            self.assertEqual(response.status_code, 404)
        self.assertFalse(PracticeAttempt.objects.exists())

    def test_service_rechecks_sources_even_when_given_an_old_session_object(self):
        session = self.session([self.own])
        self.own.is_approved = False; self.own.save()
        for operation in (lambda: practice.submit_attempt(session, self.own.pk),
                          lambda: practice.complete_session(session), lambda: practice.results(session)):
            with self.assertRaises(practice.PracticeError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 404)

    def test_malformed_sessions_or_foreign_attempt_rows_cannot_leak_results(self):
        bad = self.session([self.shared])
        PracticeAttempt.objects.create(session=bad, station=self.foreign)
        malformed = self.session([self.shared]); malformed.station_ids = {'bad': 'shape'}; malformed.save()
        self.assertEqual(practice.visible_sessions(self.users[0]).count(), 0)

    def test_history_and_practice_analytics_hide_old_class_sessions(self):
        own = self.session([self.own], status='completed', completed_at=timezone.now())
        self.session([self.foreign], status='completed', completed_at=timezone.now())
        response = self.request(views.practice_history)
        self.assertEqual([r['session_id'] for r in response.data], [str(own.pk)])
        self.assertEqual(analytics.practice_summary(self.users[0])[PracticeMode.STEEPLECHASE]['rounds'], 1)

    @patch('learning.practice.events.record')
    def test_shared_session_keeps_working_after_moving_to_another_active_class(self, record):
        session = self.session([self.shared])
        self.users[0].profile.class_group = self.groups[1]; self.users[0].profile.save()
        result = practice.submit_attempt(session, self.shared.pk, main_answer='nerve')
        self.assertTrue(result['main']['correct'])
        self.assertEqual(practice.complete_session(session)['status'], 'completed')

    def test_deleting_private_course_cannot_turn_a_station_into_shared_content(self):
        with self.assertRaises(ProtectedError):
            self.subjects[0].delete()
        self.own.refresh_from_db()
        self.assertEqual(self.own.subject, self.subjects[0])
        with self.assertRaises(IntegrityError), transaction.atomic():
            SpotStation.objects.filter(pk=self.own.pk).update(is_shared=True)

    def test_study_profile_hides_old_course_references_without_deleting_preferences(self):
        profile = StudyProfile.objects.create(user=self.users[0], daily_study_minutes=60)
        profile.target_subjects.set(self.subjects)
        response = self.request(StudyProfileViewSet, action='retrieve', pk=profile.pk)
        self.assertEqual(response.data['target_subjects'], [self.subjects[0].pk])
        self.assertEqual(response.data['daily_study_minutes'], 60)
        self.assertEqual(profile.target_subjects.count(), 2)
        response = self.request(StudyProfileViewSet, action='partial_update', method='patch', pk=profile.pk,
                                data={'target_subjects': [self.subjects[1].pk]})
        self.assertEqual(response.status_code, 400)

    def import_rows(self, rows, **options):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stations.json'
            path.write_text(json.dumps(rows), encoding='utf-8')
            call_command('import_stations', path=str(path), stdout=StringIO(), **options)

    def import_record(self, pk='catalogue'):
        return {'id': pk, 'kind': 'GROSS_ANATOMY', 'prompt': 'Identify the structure',
                'image_url': '/steeplechase/catalogue.jpg', 'accepted_answers': ['nerve'], 'is_approved': True}

    def test_catalogue_publication_requires_explicit_flag_and_dry_run_does_not_publish(self):
        self.import_rows([self.import_record()])
        self.assertFalse(SpotStation.objects.get(pk='catalogue').is_shared)
        self.import_rows([self.import_record()], publish_shared=True, dry_run=True)
        self.assertFalse(SpotStation.objects.get(pk='catalogue').is_shared)
        self.import_rows([self.import_record()], publish_shared=True)
        self.assertTrue(SpotStation.objects.get(pk='catalogue').is_shared)

    def test_catalogue_import_cannot_replace_a_private_class_station(self):
        with self.assertRaises(CommandError):
            self.import_rows([self.import_record(self.own.pk)], publish_shared=True)
        self.own.refresh_from_db()
        self.assertFalse(self.own.is_shared)
        self.assertEqual(self.own.prompt, 'Identify own')

    def test_catalogue_purge_preserves_private_questions(self):
        self.import_rows([self.import_record()], purge=True)
        self.assertTrue(SpotStation.objects.filter(pk=self.own.pk).exists())
        self.assertFalse(SpotStation.objects.filter(pk=self.shared.pk).exists())

    def test_catalogue_purge_refuses_to_delete_attempt_history(self):
        session = self.session([self.shared])
        attempt = PracticeAttempt.objects.create(session=session, station=self.shared)
        with self.assertRaises(CommandError):
            self.import_rows([self.import_record()], purge=True)
        self.assertTrue(PracticeAttempt.objects.filter(pk=attempt.pk).exists())

    def test_catalogue_purge_protects_sessions_before_the_first_answer(self):
        self.session([self.shared])
        for dry_run in (True, False):
            with self.assertRaises(CommandError):
                self.import_rows([self.import_record()], purge=True, dry_run=dry_run)
        self.assertTrue(SpotStation.objects.filter(pk=self.shared.pk).exists())
