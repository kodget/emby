import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from .models import BattleAnswer, BrainBattle, BattleParticipant
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.db.models import Q
from learning import battles as battle_service

@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user = get_user_model().objects.get(id=access_token['user_id'], is_active=True)
        return user
    except Exception:
        return None

class BattleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.battle_id = self.scope['url_route']['kwargs']['battle_id']
        self.room_group_name = f'battle_{self.battle_id}'

        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string, keep_blank_values=True)
        token = query_params.get('token', [None])[0]
        self.access_token = token
        if 'token' in query_params:
            # A rejected explicit credential must not fall back to a session user.
            self.scope['user'] = await get_user_from_token(token)

        if not await self.authorize():
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        self.joined_group = True

        await self.accept()

        participants = await self.get_leaderboard(self.battle_id)
        battle_state = await self.get_battle_state(self.battle_id, self.scope["user"].id)
        if not await self.authorize():
            return
        await self.send(text_data=json.dumps({
            'type': 'battle_state',
            'state': battle_state,
            'participants': participants
        }))

    async def disconnect(self, close_code):
        if getattr(self, 'joined_group', False):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            self.joined_group = False

    @database_sync_to_async
    def has_battle_access(self):
        from learning.views import _visible_battles
        scoped_user = self.scope.get('user')
        if not scoped_user or not scoped_user.is_authenticated:
            return False
        # Reload membership and account status; sockets can outlive either.
        user = get_user_model().objects.filter(pk=scoped_user.pk, is_active=True).first()
        if user is None:
            return False
        if self.access_token:
            try:
                token = AccessToken(self.access_token)
                if str(token['user_id']) != str(user.pk):
                    return False
            except Exception:
                return False
        return _visible_battles(user).filter(pk=self.battle_id).filter(
            Q(host=user) | Q(participants__user=user)
        ).exists()

    async def authorize(self):
        if await self.has_battle_access():
            return True
        if getattr(self, 'joined_group', False):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            self.joined_group = False
        await self.close(code=4403)
        return False

    async def receive(self, text_data):
        if not await self.authorize():
            return
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        message_type = data.get('type')
        user = self.scope["user"]

        if message_type == 'host_action':
            action = data.get('action')
            is_host = await self.is_host(self.battle_id, user.id)
            if not is_host:
                return
            
            if action == 'next_question':
                try:
                    question_data = await self.advance_question(self.battle_id, user.id)
                except battle_service.BattleError as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'battle_error', 'detail': str(exc), 'code': exc.code,
                    }))
                    return
                if question_data is not None:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'broadcast_question',
                            'question_data': question_data
                        }
                    )
                elif (await self.get_battle_state(self.battle_id, user.id)).get('status') == 'completed':
                    participants = await self.get_leaderboard(self.battle_id)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {'type': 'broadcast_end', 'participants': participants},
                    )
            elif action == 'show_answer':
                try:
                    answer_data = await self.get_current_answer(self.battle_id, user.id)
                except battle_service.BattleError as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'battle_error', 'detail': str(exc), 'code': exc.code,
                    }))
                    return
                participants = await self.get_leaderboard(self.battle_id)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'broadcast_answer',
                        'answer_data': answer_data,
                        'participants': participants
                    }
                )
            elif action == 'end_battle':
                try:
                    await self.end_battle(self.battle_id, user.id)
                except battle_service.BattleError as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'battle_error', 'detail': str(exc), 'code': exc.code,
                    }))
                    return
                participants = await self.get_leaderboard(self.battle_id)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'broadcast_end',
                        'participants': participants
                    }
                )

        elif message_type == 'submit_answer':
            answer_index = data.get('answer_index')
            try:
                answer_index = int(answer_index)
                battle = await self.get_battle(self.battle_id)
                question_index = int(
                    data.get('question_index', battle.current_question_index)
                )
                result = await self.process_answer(
                    self.battle_id, user.id, question_index, answer_index
                )
            except (TypeError, ValueError):
                await self.send(text_data=json.dumps({
                    'type': 'battle_error', 'detail': 'Choose a valid answer option.',
                    'code': 'invalid_answer',
                }))
                return
            except ObjectDoesNotExist:
                await self.send(text_data=json.dumps({
                    'type': 'battle_error', 'detail': 'Battle not found.',
                    'code': 'not_found',
                }))
                return
            except battle_service.BattleError as exc:
                await self.send(text_data=json.dumps({
                    'type': 'battle_error', 'detail': str(exc), 'code': exc.code,
                }))
                return
            await self.send(text_data=json.dumps({
                'type': 'answer_result',
                'points_earned': result['points'],
                'replayed': result['replayed'],
            }))

    # Broadcast handlers
    async def broadcast_question(self, event):
        if not await self.authorize():
            return
        await self.send(text_data=json.dumps({
            'type': 'new_question',
            'question_data': event['question_data']
        }))

    async def broadcast_answer(self, event):
        if not await self.authorize():
            return
        await self.send(text_data=json.dumps({
            'type': 'show_answer',
            'answer_data': event['answer_data'],
            'participants': event['participants']
        }))
        
    async def broadcast_end(self, event):
        if not await self.authorize():
            return
        await self.send(text_data=json.dumps({
            'type': 'battle_ended',
            'participants': event['participants']
        }))

    # Database sync methods
    @database_sync_to_async
    def get_battle_state(self, battle_id, user_id):
        try:
            with transaction.atomic():
                battle = BrainBattle.objects.select_for_update().get(id=battle_id)
                state = {
                    'status': battle.status,
                    'current_question_index': battle.current_question_index,
                    'total_questions': len(battle.questions) if battle.questions else 0,
                    'seconds_per_question': max(1, battle.time_per_question),
                }
                if battle.status == 'active' and battle.questions:
                    update_fields = []
                    if battle.current_question_index < 0:
                        battle.current_question_index = 0
                        update_fields.append('current_question_index')
                    if battle.current_question_index < len(battle.questions):
                        if battle.current_question_started_at is None:
                            battle.current_question_started_at = battle.start_time or timezone.now()
                            update_fields.append('current_question_started_at')
                        if update_fields:
                            battle.save(update_fields=update_fields)

                        q = battle.questions[battle.current_question_index]
                        state['current_question_index'] = battle.current_question_index
                        state['current_question'] = {
                            'question': q.get('question'),
                            'options': q.get('options')
                        }
                        elapsed = max(
                            0.0,
                            (timezone.now() - battle.current_question_started_at).total_seconds(),
                        )
                        state['remaining_ms'] = max(
                            0,
                            int((max(1, battle.time_per_question) - elapsed) * 1000),
                        )
                        state['question_revealed'] = battle.current_question_revealed_at is not None
                        if state['question_revealed']:
                            state['answer_data'] = {
                                'correct_index': battle_service._correct_index(q),
                                'explanation': q.get('explanation', ''),
                            }
                        existing_answer = BattleAnswer.objects.filter(
                            participant__battle=battle,
                            participant__user_id=user_id,
                            question_index=battle.current_question_index,
                        ).values('selected_index').first()
                        state['has_answered'] = existing_answer is not None
                        if existing_answer is not None:
                            state['selected_answer'] = existing_answer['selected_index']
            return state
        except ObjectDoesNotExist:
            return {}

    @database_sync_to_async
    def get_battle(self, battle_id):
        return BrainBattle.objects.get(pk=battle_id)

    @database_sync_to_async
    def is_host(self, battle_id, user_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            return battle.host.id == user_id
        except ObjectDoesNotExist:
            return False

    @database_sync_to_async
    def advance_question(self, battle_id, user_id):
        user = get_user_model().objects.get(pk=user_id)
        return battle_service.advance_question(user, battle_id)

    @database_sync_to_async
    def get_current_answer(self, battle_id, user_id):
        user = get_user_model().objects.get(pk=user_id)
        return battle_service.reveal_current_answer(user, battle_id)

    @database_sync_to_async
    def process_answer(self, battle_id, user_id, index, answer_index):
        user = get_user_model().objects.get(pk=user_id)
        battle = BrainBattle.objects.get(pk=battle_id)
        return battle_service.submit_answer(user, battle, index, answer_index)

    @database_sync_to_async
    def end_battle(self, battle_id, user_id):
        user = get_user_model().objects.get(pk=user_id)
        return battle_service.end_battle(user, battle_id)

    @database_sync_to_async
    def get_leaderboard(self, battle_id):
        participants = BattleParticipant.objects.filter(battle_id=battle_id).select_related('user__profile').order_by('-score', 'joined_at')[:5]
        return [
            {
                'id': p.user.id,
                'user_name': f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username,
                'score': p.score
            } for p in participants
        ]
