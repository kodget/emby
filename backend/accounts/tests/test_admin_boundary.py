from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import TestCase, RequestFactory
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from accounts.class_heads import request_review, review_class_head
from accounts.models import ClassGroup, ClassRole, School
from accounts.permissions import has_platform_admin_access
from accounts.serializers import ProfileSerializer
from curriculum.models import Subject
from learning.models import Notification


class AdminBoundaryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Admin boundary school')
        self.group = ClassGroup.objects.create(school=self.school, set_name='Year 1', code='678901')
        self.subject = Subject.objects.create(id='private-course', name='Private course', class_group=self.group)
        self.staff = User.objects.create_user('staff-only', password='isolated-password', is_staff=True)
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='curriculum'))
        self.platform = User.objects.create_user('platform-admin')
        self.platform.profile.platform_role = 'admin'
        self.platform.profile.save()
        self.superuser = User.objects.create_user('superuser', is_superuser=True, is_staff=True)
        self.applicant = User.objects.create_user('applicant')
        self.applicant.profile.class_group = self.group
        self.applicant.profile.class_role = ClassRole.CLASS_HEAD
        self.applicant.profile.save()
        self.api = APIClient()

    def test_staff_cannot_list_accounts_finances_classes_or_pending_reviews(self):
        self.api.force_authenticate(self.staff)
        for path in ('admin/analytics/', 'admin/users/', 'admin/curriculum/', 'admin/payments/',
                     'admin/schema/', 'class-head/pending/'):
            with self.subTest(path=path):
                self.assertEqual(self.api.get('/auth/' + path).status_code, 403)

    def test_staff_model_permissions_do_not_bypass_universal_admin(self):
        self.api.force_authenticate(self.staff)
        base = '/auth/admin/data/curriculum/subject/'
        for response in (self.api.get(base), self.api.get(base + self.subject.pk + '/'),
                         self.api.put(base + self.subject.pk + '/', {'name': 'Changed'}, format='json'),
                         self.api.delete(base + self.subject.pk + '/'),
                         self.api.post(base, {'id': 'forged', 'name': 'Forged'}, format='json')):
            self.assertEqual(response.status_code, 403)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Private course')
        self.assertFalse(Subject.objects.filter(pk='forged').exists())

    def test_staff_cannot_review_through_api_or_service(self):
        request_review(self.applicant.pk)
        self.api.force_authenticate(self.staff)
        self.assertEqual(self.api.post('/auth/class-head/verify/', {
            'user_id': self.applicant.pk, 'approved': True}, format='json').status_code, 403)
        with self.assertRaises(PermissionDenied):
            review_class_head(actor=self.staff, user_id=self.applicant.pk, approved=True)
        self.applicant.profile.refresh_from_db()
        self.assertFalse(self.applicant.profile.class_head_verified)

    def test_notifications_reach_only_active_platform_administrators(self):
        inactive = User.objects.create_user('inactive-admin', is_staff=True, is_superuser=True, is_active=False)
        request_review(self.applicant.pk)
        recipients = set(Notification.objects.values_list('user_id', flat=True))
        self.assertEqual(recipients, {self.platform.pk, self.superuser.pk})
        self.assertNotIn(inactive.pk, recipients)

    def test_nonstaff_platform_admin_can_review_and_read_admin_dashboard(self):
        request_review(self.applicant.pk)
        self.api.force_authenticate(self.platform)
        self.assertEqual(self.api.get('/auth/admin/curriculum/').status_code, 200)
        self.assertEqual(self.api.get('/auth/class-head/pending/').status_code, 200)
        self.assertEqual(self.api.post('/auth/class-head/verify/', {
            'user_id': self.applicant.pk, 'approved': True}, format='json').status_code, 200)

    def test_platform_role_does_not_skip_model_permissions(self):
        self.api.force_authenticate(self.platform)
        path = '/auth/admin/data/curriculum/subject/'
        self.assertEqual(self.api.get(path).status_code, 403)
        self.platform.user_permissions.add(Permission.objects.get(
            content_type__app_label='curriculum', codename='view_subject'))
        self.api.force_authenticate(User.objects.get(pk=self.platform.pk))
        self.assertEqual(self.api.get(path).status_code, 200)

    def test_superuser_keeps_universal_admin_access(self):
        self.api.force_authenticate(self.superuser)
        self.assertEqual(self.api.get('/auth/admin/data/curriculum/subject/').status_code, 200)

    def test_inactive_admins_are_denied_even_with_forced_authentication(self):
        self.superuser.is_active = False
        self.superuser.save()
        self.api.force_authenticate(self.superuser)
        self.assertEqual(self.api.get('/auth/admin/curriculum/').status_code, 403)
        self.assertFalse(has_platform_admin_access(self.superuser))
        self.assertFalse(ProfileSerializer(self.superuser.profile).data['is_platform_admin'])

    def test_profile_exposes_the_actual_admin_capability(self):
        for user, expected in ((self.staff, False), (self.platform, True), (self.superuser, True)):
            self.assertEqual(ProfileSerializer(user.profile).data['is_platform_admin'], expected)

    def test_django_admin_does_not_bypass_platform_role(self):
        self.client.force_login(self.staff)
        response = self.client.get('/admin/curriculum/subject/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
        self.assertNotContains(response, 'Private course', status_code=302)

    def test_django_admin_retains_its_staff_requirement(self):
        request = RequestFactory().get('/admin/')
        for user, expected in ((self.staff, False), (self.platform, False), (self.superuser, True)):
            request.user = user
            self.assertEqual(admin.site.has_permission(request), expected)
