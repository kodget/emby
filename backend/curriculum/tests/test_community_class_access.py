from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassGroup, ClassRole, School
from curriculum.models import Block, CommunityPost, PostComment, PostLike, Slide, Subject, Topic
from curriculum.views import CommunityPostViewSet


class CommunityClassAccessTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Community isolation school')
        self.groups = []
        self.users = []
        self.slides = []
        self.topics = []
        self.posts = []
        for number in (1, 2):
            group = ClassGroup.objects.create(school=school, set_name=f'Year {number}', code=f'65432{number}')
            user = User.objects.create_user(f'community-member-{number}')
            user.profile.class_group = group
            user.profile.save()
            subject = Subject.objects.create(id=f'community-subject-{number}', name='Course', class_group=group)
            block = Block.objects.create(id=f'community-block-{number}', name='Module', subject=subject)
            topic = Topic.objects.create(id=f'community-topic-{number}', name='Topic', block=block)
            slide = Slide.objects.create(id=f'community-slide-{number}', title='Class file', subject=subject,
                                         block=block, topic=topic, class_group=group, uploaded_by=user)
            post = CommunityPost.objects.create(user=user, class_group=group, post_type='resource',
                                                content=f'Private class {number} discussion', slide=slide, topic=topic)
            self.groups.append(group)
            self.users.append(user)
            self.slides.append(slide)
            self.topics.append(topic)
            self.posts.append(post)
        self.peer = User.objects.create_user('community-peer')
        self.peer.profile.class_group = self.groups[0]
        self.peer.profile.save()
        self.factory = APIRequestFactory()

    def request(self, action, *, method='get', data=None, user=None, post=None):
        request = getattr(self.factory, method)('/api/community/', data or {}, format='json')
        force_authenticate(request, user=user or self.users[0])
        view = CommunityPostViewSet.as_view({method: action})
        return view(request, **({'pk': post.pk} if post is not None else {}))

    def test_feed_and_detail_do_not_expose_other_classes(self):
        PostComment.objects.create(post=self.posts[1], user=self.users[1], content='Foreign class comment')
        response = self.request('list')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([post['id'] for post in response.data], [self.posts[0].pk])
        self.assertEqual(self.request('retrieve', post=self.posts[1]).status_code, 404)
        self.assertEqual(self.request('retrieve', post=self.posts[0], user=self.peer).status_code, 200)

    @patch('learning.notifications.schedule')
    def test_foreign_interactions_are_denied_before_mutation_or_notifications(self, schedule):
        for action, method, data in (
            ('like', 'post', {}), ('unlike', 'post', {}),
            ('comment', 'post', {'content': 'Intrusion'}),
            ('partial_update', 'patch', {'content': 'Intrusion'}), ('destroy', 'delete', {}),
        ):
            with self.subTest(action=action):
                self.assertEqual(self.request(action, method=method, data=data, post=self.posts[1]).status_code, 404)
        self.assertFalse(PostComment.objects.exists())
        self.assertFalse(PostLike.objects.exists())
        self.posts[1].refresh_from_db()
        self.assertEqual(self.posts[1].content, 'Private class 2 discussion')
        schedule.assert_not_called()

    def test_new_post_snapshots_actor_class_and_ignores_owner_spoofing(self):
        response = self.request('create', method='post', data={
            'post_type': 'resource', 'content': 'Shared with my class',
            'slide': self.slides[0].pk, 'topic': self.topics[0].pk,
            'class_group': self.groups[1].pk, 'user': self.users[1].pk,
        })
        self.assertEqual(response.status_code, 201)
        post = CommunityPost.objects.get(pk=response.data['id'])
        self.assertEqual(post.class_group, self.groups[0])
        self.assertEqual(post.user, self.users[0])

    def test_foreign_content_references_cannot_be_posted_or_updated(self):
        for field, foreign in (('slide', self.slides[1]), ('topic', self.topics[1])):
            with self.subTest(field=field):
                self.assertEqual(self.request('create', method='post', data={
                    'post_type': 'resource', 'content': 'Intrusion', field: foreign.pk,
                }).status_code, 404)
                self.assertEqual(self.request('partial_update', method='patch',
                    data={field: foreign.pk}, post=self.posts[0]).status_code, 404)
        self.assertEqual(CommunityPost.objects.count(), 2)

    def test_unassigned_and_inconsistent_historical_posts_stay_hidden(self):
        hidden = [CommunityPost.objects.create(user=self.users[0], post_type='discussion', content='Unknown owner')]
        hidden.append(CommunityPost.objects.create(user=self.users[0], class_group=self.groups[0],
            post_type='resource', content='Foreign slide', slide=self.slides[1]))
        hidden.append(CommunityPost.objects.create(user=self.users[0], class_group=self.groups[0],
            post_type='resource', content='Foreign topic', topic=self.topics[1]))
        self.assertEqual([post['id'] for post in self.request('list').data], [self.posts[0].pk])
        for post in hidden:
            self.assertEqual(self.request('retrieve', post=post).status_code, 404)
            self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_membership_changes_do_not_transfer_historical_posts(self):
        self.users[0].profile.class_group = self.groups[1]
        self.users[0].profile.save()
        self.assertEqual(self.request('retrieve', post=self.posts[0]).status_code, 404)
        self.assertEqual(self.request('retrieve', post=self.posts[0], user=self.peer).status_code, 200)
        self.posts[0].refresh_from_db()
        self.assertEqual(self.posts[0].class_group, self.groups[0])

    def test_missing_inactive_or_pending_membership_cannot_read_or_create_posts(self):
        for state in ('classless', 'inactive', 'pending'):
            with self.subTest(state=state):
                self.groups[0].is_active = state != 'inactive'
                self.groups[0].save()
                self.users[0].profile.class_group = None if state == 'classless' else self.groups[0]
                self.users[0].profile.class_role = ClassRole.CLASS_HEAD if state == 'pending' else ClassRole.STUDENT
                self.users[0].profile.save()
                self.assertEqual(self.request('list').data, [])
                self.assertEqual(self.request('create', method='post', data={
                    'post_type': 'discussion', 'content': 'No eligible class',
                }).status_code, 403)

    @patch('learning.notifications.schedule')
    def test_class_peers_can_comment_but_only_the_author_can_edit(self, schedule):
        response = self.request('comment', method='post', data={'content': 'Same class'},
                                user=self.peer, post=self.posts[0])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PostComment.objects.filter(post=self.posts[0], user=self.peer).exists())
        schedule.assert_called_once()
        self.assertEqual(self.request('partial_update', method='patch', data={'content': 'Not mine'},
                                     user=self.peer, post=self.posts[0]).status_code, 403)
        self.assertEqual(self.request('partial_update', method='patch', data={'content': 'Updated'},
                                     post=self.posts[0]).status_code, 200)

    def test_platform_admin_can_review_posts_from_all_classes(self):
        admin = User.objects.create_user('community-admin')
        admin.profile.platform_role = 'admin'
        admin.profile.save()
        self.assertEqual(self.request('retrieve', user=admin, post=self.posts[1]).status_code, 200)

