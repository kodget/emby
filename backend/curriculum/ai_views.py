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
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .ai_service import slide_ai
from .models import Slide, SlideContent

logger = logging.getLogger(__name__)


def has_premium_access(user):
    """Check if user has premium access (Premium User OR Class Head)"""
    try:
        profile = user.profile
        return profile.is_premium or profile.role == 'Class Head'
    except AttributeError:
        return False


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
        
        resources = slide_ai.generate_resources(
            slide_context=slide_context,
            slide_image_base64=slide_image_base64
        )
        
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
        
        # Generate resources and extract videos
        logger.info(f"Generating video suggestions for slide {slide_id}")
        
        resources = slide_ai.generate_resources(
            slide_context=slide_context,
            slide_image_base64=slide_image_base64
        )
        
        return Response({
            'videos': resources.get('youtube', [])
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
        
        resources = slide_ai.generate_resources(
            slide_context=slide_context,
            slide_image_base64=slide_image_base64
        )
        
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
        conversation_history = request.data.get('conversation_history', [])
        
        if not slide_id:
            return Response(
                {'error': 'slide_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not message:
            return Response(
                {'error': 'message is required'},
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
            'slide_index': 1,  # TODO: Get actual index from slide position
            'total_slides': slide.page_count or 1,
            'title': slide.title,
            'text': slide_text,
            'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
        }
        
        # Call AI service
        logger.info(f"Processing chat for slide {slide_id}: {message[:50]}...")
        
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
        
        resources = slide_ai.generate_resources(
            slide_context=slide_context,
            slide_image_base64=slide_image_base64
        )
        
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
