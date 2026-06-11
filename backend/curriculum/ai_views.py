"""
AI API Views - Slide-Aware Chat and Resources

ENDPOINTS:
- POST /api/chat - Slide-aware AI chat
- POST /api/resources - Generate resources for a slide
- POST /api/ai/textbook-suggestions/ - Premium: Generate textbook suggestions
- POST /api/ai/video-suggestions/ - Premium: Generate video suggestions
- POST /api/ai/generate-mcqs/ - Premium: Generate MCQs
"""

import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .ai_service import slide_ai
from .models import Slide, SlideContent, SlideChatMessage

logger = logging.getLogger(__name__)

# PRD §6.4.3 / §7.1 — free tier is capped at 20 AI messages per day; premium unlimited.
FREE_DAILY_MESSAGE_LIMIT = 20
# PRD §6.4.3 — keep the last 50 messages of context per student per slide.
MAX_HISTORY_MESSAGES = 50
# PRD §6.4.3 — required safety disclaimer.
AI_DISCLAIMER = (
    "This is for educational purposes only and is not a substitute for clinical judgment."
)


def has_premium_access(user):
    """Check if user has premium access (Premium User OR Class Head)"""
    try:
        profile = user.profile
        return profile.is_premium or profile.role == 'Class Head'
    except AttributeError:
        return False


def _messages_used_today(user):
    """Count the student's AI user-messages sent today (Africa/Lagos day)."""
    start_of_day = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return SlideChatMessage.objects.filter(
        user=user, role='user', created_at__gte=start_of_day
    ).count()


def _rag_context(slide, query, fallback_text):
    """
    Try to retrieve the most relevant slide chunks for the query (RAG).
    Falls back to the provided full text if RAG is unavailable or has no chunks.
    """
    try:
        from .rag_service import rag_service
        context = rag_service.get_context_for_query(slide, query, max_chunks=5)
        if context and context.strip():
            return context
    except Exception as e:  # torch/sentence-transformers missing, no chunks, etc.
        logger.info(f"RAG unavailable for slide {slide.id}, using raw text: {e}")
    return fallback_text


def _slide_text(slide):
    """Return the extracted text for a slide, or empty string."""
    try:
        sc = SlideContent.objects.get(slide=slide)
        if sc.content_data and 'text' in sc.content_data:
            return sc.content_data['text']
    except SlideContent.DoesNotExist:
        logger.warning(f"No content found for slide {slide.id}")
    return ""


def _get_or_generate_resources(slide, slide_image_base64=None, force_refresh=False):
    """
    Return generated study resources for a slide, caching them on SlideContent
    so we don't re-call the LLM on every request (persistence — Goal #3).
    """
    sc, _ = SlideContent.objects.get_or_create(slide=slide)
    cached = (sc.content_data or {}).get('resources') if isinstance(sc.content_data, dict) else None
    if cached and not force_refresh:
        return cached

    slide_context = {
        'title': slide.title,
        'text': (sc.content_data or {}).get('text', '') if isinstance(sc.content_data, dict) else '',
        'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General',
    }
    resources = slide_ai.generate_resources(
        slide_context=slide_context,
        slide_image_base64=slide_image_base64,
    )

    # Only cache successful generations
    if resources and not resources.get('error'):
        data = sc.content_data if isinstance(sc.content_data, dict) else {}
        data['resources'] = resources
        sc.content_data = data
        sc.save(update_fields=['content_data', 'updated_at'])

    return resources


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def textbook_suggestions(request):
    """
    Generate AI-powered textbook suggestions for a slide (Premium Feature)
    
    Request body:
    {
        "slide_id": "123",
        "slide_image_base64": "base64_encoded_image_data"  // Optional
    }
    
    Response:
    {
        "textbooks": [
            {
                "title": "Textbook name",
                "author": "Author", 
                "chapter": "Chapter name",
                "reason": "Why this is relevant"
            }
        ]
    }
    """
    # Check premium access
    if not has_premium_access(request.user):
        return Response(
            {'error': 'Premium access required', 'premium_required': True},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        slide_id = request.data.get('slide_id')
        slide_image_base64 = request.data.get('slide_image_base64')
        
        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response(
                {'error': f'Slide {slide_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get slide content
        slide_text = ""
        try:
            slide_content = SlideContent.objects.get(slide=slide)
            if slide_content.content_data and 'text' in slide_content.content_data:
                slide_text = slide_content.content_data['text']
        except SlideContent.DoesNotExist:
            logger.warning(f"No content found for slide {slide_id}")
        
        # Build slide context
        slide_context = {
            'title': slide.title,
            'text': slide_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }
        
        # Generate resources and extract textbooks
        logger.info(f"Generating textbook suggestions for slide {slide_id}")

        force = str(request.data.get('refresh', '')).lower() in ('1', 'true', 'yes')
        resources = _get_or_generate_resources(slide, slide_image_base64, force_refresh=force)

        return Response({
            'textbooks': resources.get('textbooks', [])
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Textbook suggestions API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def video_suggestions(request):
    """
    Generate AI-powered video suggestions for a slide (Premium Feature)
    
    Request body:
    {
        "slide_id": "123",
        "slide_image_base64": "base64_encoded_image_data"  // Optional
    }
    
    Response:
    {
        "videos": [
            {
                "title": "Video title",
                "query": "YouTube search query",
                "reason": "Why this video helps"
            }
        ]
    }
    """
    # Check premium access
    if not has_premium_access(request.user):
        return Response(
            {'error': 'Premium access required', 'premium_required': True},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        slide_id = request.data.get('slide_id')
        slide_image_base64 = request.data.get('slide_image_base64')
        
        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response(
                {'error': f'Slide {slide_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get slide content
        slide_text = ""
        try:
            slide_content = SlideContent.objects.get(slide=slide)
            if slide_content.content_data and 'text' in slide_content.content_data:
                slide_text = slide_content.content_data['text']
        except SlideContent.DoesNotExist:
            logger.warning(f"No content found for slide {slide_id}")
        
        # Build slide context
        slide_context = {
            'title': slide.title,
            'text': slide_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }
        
        # Generate AI search-query suggestions for this slide
        logger.info(f"Generating video suggestions for slide {slide_id}")

        resources = slide_ai.generate_resources(
            slide_context=slide_context,
            slide_image_base64=slide_image_base64
        )
        ai_suggestions = resources.get('youtube', [])

        # Upgrade to REAL YouTube Data API results when configured (PRD §6.3.5)
        from . import youtube_service
        if youtube_service.is_configured():
            real_videos = []
            seen_ids = set()
            # Use the AI-suggested queries (fall back to the slide title) to drive search
            queries = [s.get('query') or s.get('title') for s in ai_suggestions if s]
            queries = [q for q in queries if q] or [slide.title]
            for query in queries[:3]:
                hits = youtube_service.search_videos(query, max_results=3) or []
                for v in hits:
                    if v['video_id'] not in seen_ids:
                        seen_ids.add(v['video_id'])
                        real_videos.append(v)
                if len(real_videos) >= 5:
                    break
            if real_videos:
                return Response({'videos': real_videos[:5], 'source': 'youtube_api'},
                                status=status.HTTP_200_OK)

        # Fallback: AI-suggested search queries (no real API key configured)
        return Response({
            'videos': ai_suggestions,
            'source': 'ai_suggestions'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Video suggestions API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_mcqs(request):
    """
    Generate AI-powered MCQs for a slide (Premium Feature)
    
    Request body:
    {
        "slide_id": "123",
        "slide_image_base64": "base64_encoded_image_data"  // Optional
    }
    
    Response:
    {
        "mcqs": [
            {
                "question": "Question text",
                "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                "correct": 0,  // Index of correct answer
                "explanation": "Why this is correct"
            }
        ]
    }
    """
    # Check premium access
    if not has_premium_access(request.user):
        return Response(
            {'error': 'Premium access required', 'premium_required': True},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        slide_id = request.data.get('slide_id')
        slide_image_base64 = request.data.get('slide_image_base64')
        
        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response(
                {'error': f'Slide {slide_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get slide content
        slide_text = ""
        try:
            slide_content = SlideContent.objects.get(slide=slide)
            if slide_content.content_data and 'text' in slide_content.content_data:
                slide_text = slide_content.content_data['text']
        except SlideContent.DoesNotExist:
            logger.warning(f"No content found for slide {slide_id}")
        
        # Build slide context
        slide_context = {
            'title': slide.title,
            'text': slide_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }
        
        # Generate resources and extract MCQs
        logger.info(f"Generating MCQs for slide {slide_id}")

        force = str(request.data.get('refresh', '')).lower() in ('1', 'true', 'yes')
        resources = _get_or_generate_resources(slide, slide_image_base64, force_refresh=force)

        return Response({
            'mcqs': resources.get('mcqs', [])
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"MCQ generation API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_slide(request):
    """
    Chat with AI about the current slide
    
    Request body:
    {
        "slide_id": "123",
        "message": "Explain the brachial plexus",
        "slide_image_base64": "base64_encoded_image_data",  // Optional
        "conversation_history": [  // Optional - previous messages for this slide
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
    }
    
    Response:
    {
        "response": "AI response text",
        "sources": ["Source 1", "Source 2"],  // Optional
        "youtube": {...},  // Optional
    }
    """
    try:
        # Get request data
        slide_id = request.data.get('slide_id')
        message = request.data.get('message')
        slide_image_base64 = request.data.get('slide_image_base64')
        conversation_history = request.data.get('conversation_history')

        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message or not str(message).strip():
            return Response(
                {'error': 'message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce daily free-tier limit (PRD §7.1)
        is_premium = has_premium_access(request.user)
        if not is_premium:
            used = _messages_used_today(request.user)
            if used >= FREE_DAILY_MESSAGE_LIMIT:
                return Response(
                    {
                        'error': (
                            f'Daily free limit of {FREE_DAILY_MESSAGE_LIMIT} AI messages reached. '
                            'Upgrade to Premium for unlimited chat.'
                        ),
                        'premium_required': True,
                        'limit': FREE_DAILY_MESSAGE_LIMIT,
                        'used': used,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response(
                {'error': f'Slide {slide_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get slide content (text)
        slide_text = ""
        try:
            slide_content = SlideContent.objects.get(slide=slide)
            if slide_content.content_data and 'text' in slide_content.content_data:
                slide_text = slide_content.content_data['text']
        except SlideContent.DoesNotExist:
            logger.warning(f"No content found for slide {slide_id}")

        # RAG: retrieve the most relevant slide chunks for this question,
        # falling back to the full extracted text when RAG is unavailable.
        context_text = _rag_context(slide, message, slide_text)

        # Conversation history: use what the client sent, otherwise restore from DB
        if not conversation_history:
            history_qs = SlideChatMessage.objects.filter(
                user=request.user, slide=slide
            ).order_by('-created_at')[:MAX_HISTORY_MESSAGES]
            conversation_history = [
                {'role': m.role, 'content': m.content}
                for m in reversed(list(history_qs))
            ]

        # Build slide context
        slide_context = {
            'slide_index': 1,
            'total_slides': slide.page_count or 1,
            'title': slide.title,
            'text': context_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }

        # Call AI service
        logger.info(f"Processing chat for slide {slide_id}: {str(message)[:50]}...")

        result = slide_ai.chat(
            user_message=message,
            slide_context=slide_context,
            slide_image_base64=slide_image_base64,
            conversation_history=conversation_history
        )

        if 'error' in result and not result.get('response'):
            return Response(
                {'error': result['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Persist the exchange (PRD §6.4.3)
        try:
            SlideChatMessage.objects.create(
                user=request.user, slide=slide, role='user', content=str(message)
            )
            SlideChatMessage.objects.create(
                user=request.user, slide=slide, role='assistant',
                content=result.get('response', '')
            )
        except Exception as persist_err:
            logger.error(f"Failed to persist chat for slide {slide_id}: {persist_err}")

        result['disclaimer'] = AI_DISCLAIMER
        if not is_premium:
            result['messages_remaining'] = max(
                0, FREE_DAILY_MESSAGE_LIMIT - _messages_used_today(request.user)
            )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_resources(request):
    """
    Generate study resources for a slide
    
    Request body:
    {
        "slide_id": "123",
        "slide_image_base64": "base64_encoded_image_data"  // Optional
    }
    
    Response:
    {
        "youtube": [
            {
                "title": "Video title",
                "query": "Search query",
                "reason": "Why helpful"
            }
        ],
        "textbooks": [
            {
                "title": "Textbook",
                "author": "Author",
                "chapter": "Chapter",
                "reason": "Why relevant"
            }
        ],
        "mcqs": [
            {
                "question": "Question",
                "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
                "correct": 0,
                "explanation": "Explanation"
            }
        ]
    }
    """
    try:
        # Get request data
        slide_id = request.data.get('slide_id')
        slide_image_base64 = request.data.get('slide_image_base64')
        
        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            return Response(
                {'error': f'Slide {slide_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get slide content (text)
        slide_text = ""
        try:
            slide_content = SlideContent.objects.get(slide=slide)
            if slide_content.content_data and 'text' in slide_content.content_data:
                slide_text = slide_content.content_data['text']
        except SlideContent.DoesNotExist:
            logger.warning(f"No content found for slide {slide_id}")
        
        # Build slide context
        slide_context = {
            'title': slide.title,
            'text': slide_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }
        
        # Generate resources
        logger.info(f"Generating resources for slide {slide_id}")

        force = str(request.data.get('refresh', '')).lower() in ('1', 'true', 'yes')
        resources = _get_or_generate_resources(slide, slide_image_base64, force_refresh=force)

        if 'error' in resources:
            logger.error(f"Resource generation failed: {resources['error']}")
        
        return Response(resources, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Resources API error: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_history(request):
    """
    GET  /api/ai/chat/history/?slide_id=...  -> last 50 messages for the student+slide
    DELETE /api/ai/chat/history/?slide_id=... -> clear the conversation

    slide_id is optional; when omitted, operates on general (slide-less) chat.
    """
    slide_id = request.query_params.get('slide_id')

    qs = SlideChatMessage.objects.filter(user=request.user)
    if slide_id:
        qs = qs.filter(slide_id=slide_id)
    else:
        qs = qs.filter(slide__isnull=True)

    if request.method == 'DELETE':
        deleted, _ = qs.delete()
        return Response({'deleted': deleted}, status=status.HTTP_200_OK)

    messages = qs.order_by('-created_at')[:MAX_HISTORY_MESSAGES]
    data = [
        {
            'role': m.role,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
        }
        for m in reversed(list(messages))
    ]
    return Response({'messages': data, 'disclaimer': AI_DISCLAIMER}, status=status.HTTP_200_OK)
