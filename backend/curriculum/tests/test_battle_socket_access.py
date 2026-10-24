import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser, User
from django.test import TransactionTestCase
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import ClassGroup, Profile, School
from curriculum.consumers import BattleConsumer
from curriculum.models import BattleParticipant, BrainBattle, Subject


class BattleSocketAccessTests(TransactionTestCase):
    def setUp(self):
        school = School.objects.create(name='Socket school')
        self.groups = [ClassGroup.objects.create(school=school, set_name=f'Year {i}', code=f'99887{i}')
                       for i in range(2)]
        self.host = self.user('socket-host', 0)
        self.member = self.user('socket-member', 0)
        self.foreign = self.user('socket-foreign', 1)
        self.battle = BrainBattle.objects.create(title='Private battle', host=self.host,
            class_group=self.groups[0], status='active', current_question_index=0,
            questions=[{'question': 'Private question', 'options': ['A', 'B'], 'correct_index': 0}])
        BattleParticipant.objects.create(battle=self.battle, user=self.member)
        BattleParticipant.objects.create(battle=self.battle, user=self.foreign)

    def user(self, name, group):
        user = User.objects.create_user(name)
        user.profile.class_group = self.groups[group]
        user.profile.save()
        return user

    async def connect(self, user=None, token=None):
        app = ApplicationCommunicator(BattleConsumer.as_asgi(), {
            'type': 'websocket', 'path': f'/ws/battle/{self.battle.pk}/',
            'url_route': {'kwargs': {'battle_id': str(self.battle.pk)}},
            'query_string': f'token={token}'.encode() if token is not None else b'',
            'user': user or AnonymousUser(),
        })
        await app.send_input({'type': 'websocket.connect'})
        return app, await app.receive_output(timeout=5)

    async def disconnect(self, app):
        await app.send_input({'type': 'websocket.disconnect', 'code': 1000})
        await app.wait(timeout=5)

    async def assert_denied(self, user=None, token=None):
        app, message = await self.connect(user, token)
        self.assertEqual(message, {'type': 'websocket.close', 'code': 4403})
        await self.disconnect(app)

    def test_rejects_anonymous_invalid_refresh_and_inactive_credentials(self):
        async_to_sync(self.assert_denied)()
        async_to_sync(self.assert_denied)(self.host, 'invalid')
        async_to_sync(self.assert_denied)(self.host, '')
        async_to_sync(self.assert_denied)(token=str(RefreshToken.for_user(self.host)))
        token = str(AccessToken.for_user(self.host))
        User.objects.filter(pk=self.host.pk).update(is_active=False)
        async_to_sync(self.assert_denied)(self.host)
        async_to_sync(self.assert_denied)(token=token)

    def test_host_and_joined_class_member_can_receive_current_state(self):
        async def scenario(user=None, token=None):
            app, message = await self.connect(user, token)
            self.assertEqual(message['type'], 'websocket.accept')
            payload = json.loads((await app.receive_output(timeout=5))['text'])
            self.assertEqual(payload['state']['current_question']['question'], 'Private question')
            self.assertNotIn('correct_index', payload['state']['current_question'])
            await self.disconnect(app)
        async_to_sync(scenario)(self.host)
        async_to_sync(scenario)(token=str(AccessToken.for_user(self.member)))

    def test_class_membership_and_joining_are_both_required(self):
        async_to_sync(self.assert_denied)(self.foreign)
        async_to_sync(self.assert_denied)(self.user('not-joined', 0))
        self.member.profile.class_role = 'class_head'
        self.member.profile.save()
        async_to_sync(self.assert_denied)(self.member)
        ClassGroup.objects.filter(pk=self.groups[0].pk).update(is_active=False)
        async_to_sync(self.assert_denied)(self.host)

    def test_foreign_linked_source_is_hidden_even_in_same_class_battle(self):
        subject = Subject.objects.create(id='socket-foreign-subject', name='Foreign', class_group=self.groups[1])
        self.battle.linked_subject = subject
        self.battle.save()
        async_to_sync(self.assert_denied)(self.member)

    def test_class_change_blocks_every_broadcast_on_an_existing_connection(self):
        async def scenario(event_type):
            app, message = await self.connect(self.member)
            self.assertEqual(message['type'], 'websocket.accept')
            await app.receive_output(timeout=5)
            await database_sync_to_async(Profile.objects.filter(user=self.member).update)(class_group=self.groups[1])
            await get_channel_layer().group_send(f'battle_{self.battle.pk}', {
                'type': event_type, 'question_data': {'question': 'Secret'},
                'answer_data': {'correct_index': 0}, 'participants': [],
            })
            self.assertEqual((await app.receive_output(timeout=5))['type'], 'websocket.close')
            await self.disconnect(app)
        for event in ('broadcast_question', 'broadcast_answer', 'broadcast_end'):
            Profile.objects.filter(user=self.member).update(class_group=self.groups[0])
            async_to_sync(scenario)(event)

    def test_class_change_blocks_submissions_and_host_actions(self):
        async def scenario(user, payload):
            app, message = await self.connect(user)
            self.assertEqual(message['type'], 'websocket.accept')
            await app.receive_output(timeout=5)
            await database_sync_to_async(Profile.objects.filter(user=user).update)(class_group=self.groups[1])
            await app.send_input({'type': 'websocket.receive', 'text': json.dumps(payload)})
            self.assertEqual((await app.receive_output(timeout=5))['type'], 'websocket.close')
            await self.disconnect(app)
        async_to_sync(scenario)(self.member, {'type': 'submit_answer', 'answer_index': 0, 'time_left_ms': 20000})
        async_to_sync(scenario)(self.host, {'type': 'host_action', 'action': 'next_question'})
        self.assertEqual(BattleParticipant.objects.get(battle=self.battle, user=self.member).score, 0)
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.current_question_index, 0)

    def test_expired_token_or_removed_participant_stops_existing_broadcasts(self):
        token = str(AccessToken.for_user(self.member))
        async def scenario(expire):
            app, message = await self.connect(token=token)
            self.assertEqual(message['type'], 'websocket.accept')
            await app.receive_output(timeout=5)
            if not expire:
                await database_sync_to_async(BattleParticipant.objects.filter(user=self.member).delete)()
            with patch('curriculum.consumers.AccessToken', side_effect=TokenError('expired')) if expire else patch(
                    'curriculum.consumers.AccessToken', wraps=AccessToken):
                await get_channel_layer().group_send(f'battle_{self.battle.pk}', {
                    'type': 'broadcast_end', 'participants': [],
                })
                self.assertEqual((await app.receive_output(timeout=5))['type'], 'websocket.close')
            await self.disconnect(app)
        async_to_sync(scenario)(True)
        async_to_sync(scenario)(False)

    def test_malformed_messages_and_non_host_actions_do_not_mutate_battle(self):
        async def scenario():
            app, message = await self.connect(self.member)
            self.assertEqual(message['type'], 'websocket.accept')
            await app.receive_output(timeout=5)
            for payload in ('not-json', '[]', '{"type":"host_action","action":"next_question"}'):
                await app.send_input({'type': 'websocket.receive', 'text': payload})
                self.assertTrue(await app.receive_nothing())
            await self.disconnect(app)
        async_to_sync(scenario)()
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.current_question_index, 0)
