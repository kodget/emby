import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Accept the connection first to allow the client to send the auth token
        self.user = AnonymousUser()
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            from rest_framework_simplejwt.tokens import UntypedToken
            from rest_framework_simplejwt.authentication import JWTAuthentication
            
            # Validate token
            UntypedToken(token)
            
            # Get user
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except Exception as e:
            logger.error(f"WebSocket auth failed: {e}")
            return None

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            
            if data.get('type') == 'auth':
                token = data.get('token')
                if not token:
                    await self.close(code=4000)
                    return
                    
                user = await self.get_user_from_token(token)
                
                if user and not user.is_anonymous:
                    self.user = user
                    self.room_group_name = f"user_{self.user.id}_notifications"
                    
                    # Join room group
                    await self.channel_layer.group_add(
                        self.room_group_name,
                        self.channel_name
                    )
                    
                    # Confirm auth successful
                    await self.send(text_data=json.dumps({
                        'type': 'auth_success'
                    }))
                else:
                    # Invalid token
                    await self.close(code=4001)
                    
        except json.JSONDecodeError:
            pass

    # Receive message from room group
    async def notification_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': message
        }))
