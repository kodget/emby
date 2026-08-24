import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from .models import BrainBattle, BattleParticipant
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user = get_user_model().objects.get(id=access_token['user_id'])
        return user
    except Exception:
        return None

class BattleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.battle_id = self.scope['url_route']['kwargs']['battle_id']
        self.room_group_name = f'battle_{self.battle_id}'

        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            user = await get_user_from_token(token)
            if user:
                self.scope['user'] = user

        if self.scope.get("user", None) is None or self.scope["user"].is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        participants = await self.get_leaderboard(self.battle_id)
        
        # Send current battle state
        battle_state = await self.get_battle_state(self.battle_id)
        await self.send(text_data=json.dumps({
            'type': 'battle_state',
            'state': battle_state,
            'participants': participants
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        user = self.scope["user"]

        if message_type == 'host_action':
            action = data.get('action')
            is_host = await self.is_host(self.battle_id, user.id)
            if not is_host:
                return
            
            if action == 'next_question':
                question_data = await self.advance_question(self.battle_id)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'broadcast_question',
                        'question_data': question_data
                    }
                )
            elif action == 'show_answer':
                answer_data = await self.get_current_answer(self.battle_id)
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
                await self.end_battle(self.battle_id)
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
            time_left_ms = data.get('time_left_ms', 0)
            
            # Check answer and calculate score
            points = await self.process_answer(self.battle_id, user.id, answer_index, time_left_ms)
            
            # Acknowledge to the user only
            await self.send(text_data=json.dumps({
                'type': 'answer_result',
                'points_earned': points
            }))
            
            # Optionally, notify host that a user answered (for real-time counting)
            # await self.channel_layer.group_send(self.room_group_name, {'type': 'participant_answered'})

    # Broadcast handlers
    async def broadcast_question(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_question',
            'question_data': event['question_data']
        }))

    async def broadcast_answer(self, event):
        await self.send(text_data=json.dumps({
            'type': 'show_answer',
            'answer_data': event['answer_data'],
            'participants': event['participants']
        }))
        
    async def broadcast_end(self, event):
        await self.send(text_data=json.dumps({
            'type': 'battle_ended',
            'participants': event['participants']
        }))

    # Database sync methods
    @database_sync_to_async
    def get_battle_state(self, battle_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            state = {
                'status': battle.status,
                'current_question_index': battle.current_question_index,
                'total_questions': len(battle.questions) if battle.questions else 0,
            }
            if battle.status == 'active' and battle.current_question_index >= 0 and battle.questions:
                if battle.current_question_index < len(battle.questions):
                    q = battle.questions[battle.current_question_index]
                    state['current_question'] = {
                        'question': q.get('question'),
                        'options': q.get('options')
                    }
            return state
        except ObjectDoesNotExist:
            return {}

    @database_sync_to_async
    def is_host(self, battle_id, user_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            return battle.host.id == user_id
        except ObjectDoesNotExist:
            return False

    @database_sync_to_async
    def advance_question(self, battle_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            battle.current_question_index += 1
            if battle.status != 'active':
                battle.status = 'active'
            battle.save()
            
            if battle.questions and battle.current_question_index < len(battle.questions):
                q = battle.questions[battle.current_question_index]
                return {
                    'index': battle.current_question_index,
                    'question': q.get('question'),
                    'options': q.get('options')
                }
            return None
        except ObjectDoesNotExist:
            return None

    @database_sync_to_async
    def get_current_answer(self, battle_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            if battle.questions and 0 <= battle.current_question_index < len(battle.questions):
                q = battle.questions[battle.current_question_index]
                return {
                    'correct_index': q.get('correct_index'),
                    'explanation': q.get('explanation')
                }
            return None
        except ObjectDoesNotExist:
            return None

    @database_sync_to_async
    def process_answer(self, battle_id, user_id, answer_index, time_left_ms):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            if not battle.questions or battle.current_question_index < 0:
                return 0
                
            q = battle.questions[battle.current_question_index]
            correct_index = q.get('correct_index')
            
            if answer_index == correct_index:
                # Calculate points: max 1000 at 0 response time (max time left), 0 if exhausted
                max_time_ms = float(battle.time_per_question * 1000)
                points = int((time_left_ms / max_time_ms) * 1000)
                points = max(0, min(1000, points))
                
                participant, _ = BattleParticipant.objects.get_or_create(battle_id=battle_id, user_id=user_id)
                participant.score += points
                participant.save()
                return points
            return 0
        except ObjectDoesNotExist:
            return 0

    @database_sync_to_async
    def end_battle(self, battle_id):
        try:
            battle = BrainBattle.objects.get(id=battle_id)
            battle.status = 'completed'
            battle.save()
        except ObjectDoesNotExist:
            pass

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
