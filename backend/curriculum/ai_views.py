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
from datetime import timedelta
logger = logging.getLogger(__name__)
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .ai_service import slide_ai
from .models import FlashcardGenerationJob, Slide, SlideContent, SlideChatMessage, SlideDeck
from .class_access import visible, ClassContentReferences

# PRD §6.4.3 — keep the last 50 messages of context per student per slide.
MAX_HISTORY_MESSAGES = 50
MAX_DECK_CHAT_CONTEXT_CHARS = 48000
# PRD §6.4.3 — required safety disclaimer.
AI_DISCLAIMER = (
    "This is for educational purposes only and is not a substitute for clinical judgment."
)
from credits.services import CreditManager, InsufficientCreditsError

FLASHCARD_QUEUE_TIMEOUT = timedelta(minutes=2)


def _mark_flashcard_job_queue_failed(job_id):
    with transaction.atomic():
        job = FlashcardGenerationJob.objects.select_for_update().filter(
            pk=job_id,
            status='queued',
        ).first()
        if job is None:
            return
        refund_error = None
        try:
            with transaction.atomic():
                CreditManager.refund_credits(
                    job.user,
                    job.reservation.get('reserved_amount', 0),
                    action="REFUND_FLASHCARD_ERROR",
                    reservation_id=job.reservation.get('reservation_id', ''),
                )
        except Exception as error:
            refund_error = error
            logger.exception("Could not refund credits for flashcard job %s", job.pk)
        job.status = 'failed'
        job.error_message = (
            'The generation request could not be queued; contact support about your credits.'
            if refund_error else
            'The generation request could not be queued. Credits were refunded; please retry.'
        )
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])


def _dispatch_flashcard_job(job_id, slide_image_base64=None):
    from django.conf import settings
    from .tasks import generate_ai_flashcards_from_slide_task

    def enqueue():
        try:
            job = FlashcardGenerationJob.objects.select_related('user', 'slide').get(pk=job_id)
            generate_ai_flashcards_from_slide_task.delay(
                str(job.slide_id),
                job.user_id,
                job.requested_count,
                job.reservation,
                slide_image_base64,
                str(job.pk),
            )
        except Exception:
            logger.exception("Could not queue flashcard generation job %s", job_id)
            _mark_flashcard_job_queue_failed(job_id)
            raise

    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        import threading
        threading.Thread(target=enqueue, daemon=True).start()
    else:
        enqueue()


def has_premium_access(user):
    """Whether this user may use premium features.

    Delegates to accounts.permissions so entitlement is decided in exactly one place.
    The previous implementation read `profile.role`, a field that does not exist — the
    model has `platform_role` and `class_role`. In views.py that raised AttributeError
    whenever is_premium was False; in ai_views.py it was swallowed by an except clause,
    which silently denied premium AI to verified class heads. The clause was also
    redundant: Profile.is_premium already covers admins and verified class heads.
    """
    from accounts.permissions import can_access_premium_features

    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    return can_access_premium_features(profile)


def _messages_used_today(user):
    """Count the student's AI user-messages sent today (Africa/Lagos day)."""
    start_of_day = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return SlideChatMessage.objects.filter(
        user=user, role='user', created_at__gte=start_of_day
    ).count()


def _rag_context(slide, query, fallback_text):
    """Search saved page readings; never start extraction/model downloads in chat."""
    import heapq
    import re
    content = SlideContent.objects.filter(slide=slide).first()
    data = content.content_data if content and isinstance(content.content_data, dict) else {}
    terms = set(re.findall(r'[a-z0-9]{3,}', str(query).lower()))
    requested_pages = {int(number) for number in re.findall(r'page\s+(\d+)', str(query).lower())}
    candidates = []
    serial = 0
    for page in data.get('pages', []):
        text = page.get('text') or page.get('extracted_text') or ''
        for start in range(0, len(text), 1800):
            excerpt = text[start:start + 2200]
            score = len(terms & set(re.findall(r'[a-z0-9]{3,}', excerpt.lower())))
            score += 20 if page.get('page_number') in requested_pages else 0
            serial += 1
            row = (score, -serial, f"[Page {page.get('page_number', '?')}]\n{excerpt}")
            if len(candidates) < 3:
                heapq.heappush(candidates, row)
            elif row[:2] > candidates[0][:2]:
                heapq.heapreplace(candidates, row)
    if not candidates:
        from .ai_service import bounded_chat_source
        return bounded_chat_source(fallback_text, query)
    context = '\n\n'.join(row[2] for row in sorted(candidates, reverse=True))
    return 'Selected saved page excerpts; unprocessed pages and omitted details may be unavailable.\n' + context


def _slide_text(slide):
    """Return the extracted text for a slide, or empty string."""
    try:
        sc = SlideContent.objects.get(slide=slide)
        data = sc.content_data if isinstance(sc.content_data, dict) else {}
        if isinstance(data.get('text'), str) and data['text'].strip():
            return data['text']
        return '\n\n'.join(str(page.get('text') or page.get('extracted_text') or '')
                           for page in data.get('pages', []) if isinstance(page, dict))
    except SlideContent.DoesNotExist:
        logger.warning(f"No content found for slide {slide.id}")
    return ""


def _deck_chat_context(deck):
    """Build a page-labelled, bounded context from the deck's extracted text."""
    if deck.processing_status != 'completed':
        return None, 'This document is not ready for AI chat yet. Please retry after processing completes.'

    page_rows = list(
        deck.pages.order_by('slide_number').values_list('slide_number', 'extracted_text')
    )
    pages = [(number, text.strip()) for number, text in page_rows if text and text.strip()]
    if not pages:
        return None, 'No readable text is available for this document yet. Retry text processing before using AI chat.'

    extraction = deck.text_extraction if isinstance(deck.text_extraction, dict) else {}
    missing = extraction.get('missing_pages', [])
    missing = missing if isinstance(missing, list) else []
    header = (
        f"Document extraction status: {extraction.get('status', 'unverified')}.\n"
        f"Pages with readable text: {len(pages)} of {deck.page_count or len(page_rows)}.\n"
    )
    if missing:
        header += f"Text extraction was incomplete on pages: {', '.join(map(str, missing))}.\n"

    labels = [f'[Page {number}]\n' for number, _ in pages]
    page_context = '\n\n'.join(label + text for label, (_, text) in zip(labels, pages))
    if len(header) + len(page_context) > MAX_DECK_CHAT_CONTEXT_CHARS:
        excerpt_note = 'Page text is excerpted to fit the model context; details outside these excerpts may be unavailable.\n'
        text_budget = (
            MAX_DECK_CHAT_CONTEXT_CHARS - len(header) - len(excerpt_note) - 1
            - sum(map(len, labels)) - (2 * (len(labels) - 1))
        )
        if text_budget < 0:
            return None, 'This document has too many pages to prepare chat context.'
        allocation = text_budget // len(pages)
        page_context = '\n\n'.join(
            label + text[:allocation] for label, (_, text) in zip(labels, pages)
        )
        header += excerpt_note

    return header + '\n' + page_context, None


class StudyResourceError(Exception):
    def __init__(self, message, status_code=502):
        self.status_code = status_code
        super().__init__(message)


def _get_or_generate_resources(slide, user, slide_image_base64=None, force_refresh=False):
    """
    Return generated study resources for a slide, caching them on SlideContent
    so we don't re-call the LLM on every request (persistence — Goal #3).
    Deducts AI credits only if generation actually happens.
    """
    sc, _ = SlideContent.objects.get_or_create(slide=slide)
    cached = (sc.content_data or {}).get('resources') if isinstance(sc.content_data, dict) else None
    if cached and not force_refresh:
        return cached

    text = _slide_text(slide)
    if not text.strip():
        raise StudyResourceError('No extracted slide text is available yet. Finish slide processing before generating resources.', 409)

    # Reserve credits since we need to generate
    reservation = CreditManager.reserve_credits(user, "GENERATE_RESOURCES")

    slide_context = {
        'title': slide.title,
        'text': text,
        'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General',
    }
    try:
        resources = slide_ai.generate_resources(
            slide_context=slide_context, slide_image_base64=slide_image_base64, return_usage=True)
        if not isinstance(resources, dict) or not resources or resources.get('error'):
            raise StudyResourceError('The AI provider could not generate study resources. Please retry.')
        with transaction.atomic():
            sc = SlideContent.objects.select_for_update().get(pk=sc.pk)
            CreditManager.commit_usage(user, reservation, resources.get('total_tokens', 0))
            data = sc.content_data if isinstance(sc.content_data, dict) else {}
            data['resources'] = resources
            sc.content_data = data
            sc.save(update_fields=['content_data', 'updated_at'])
    except Exception:
        CreditManager.refund_credits(
            user, reservation['reserved_amount'], action="REFUND_RESOURCE_ERROR",
            reservation_id=reservation['reservation_id'],
        )
        raise StudyResourceError('Study resources could not be generated or saved. Credits were refunded; please retry.') from None

    return resources


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
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
    # Daily and purchased AI credits both fund generation; cached resources are free.
    
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
            slide = visible(Slide, request.user).get(id=slide_id)
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
        try:
            resources = _get_or_generate_resources(slide, request.user, slide_image_base64, force_refresh=force)
        except InsufficientCreditsError as e:
            return Response({'error': str(e), 'insufficient_credits': True}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except StudyResourceError as e:
            return Response({'error': str(e)}, status=e.status_code)

        return Response({
            'textbooks': resources.get('textbooks', []),
            'balance': CreditManager.get_user_balance(request.user)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Textbook suggestions API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
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
    # CreditManager enforces affordability when generation is needed.
    
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
            slide = visible(Slide, request.user).get(id=slide_id)
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

        try:
            resources = _get_or_generate_resources(
                slide, request.user, slide_image_base64, force_refresh=False
            )
        except InsufficientCreditsError as e:
            return Response({'error': str(e), 'insufficient_credits': True}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except StudyResourceError as e:
            return Response({'error': str(e)}, status=e.status_code)
            
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
                return Response({
                    'videos': real_videos[:5], 
                    'source': 'youtube_api',
                    'balance': CreditManager.get_user_balance(request.user)
                }, status=status.HTTP_200_OK)

        # Fallback: AI-suggested search queries (no real API key configured)
        return Response({
            'videos': ai_suggestions,
            'source': 'ai_suggestions',
            'balance': CreditManager.get_user_balance(request.user)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Video suggestions API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
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
    # CreditManager enforces affordability when generation is needed.
    
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
            slide = visible(Slide, request.user).get(id=slide_id)
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
        try:
            resources = _get_or_generate_resources(slide, request.user, slide_image_base64, force_refresh=force)
        except InsufficientCreditsError as e:
            return Response({'error': str(e), 'insufficient_credits': True}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except StudyResourceError as e:
            return Response({'error': str(e)}, status=e.status_code)

        return Response({
            'mcqs': resources.get('mcqs', []),
            'balance': CreditManager.get_user_balance(request.user)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"MCQ generation API error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
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
        deck_id = request.data.get('deck_id')
        message = request.data.get('message')
        slide_image_base64 = request.data.get('slide_image_base64')
        conversation_history = request.data.get('conversation_history')
        page_number = request.data.get('page_number')
        if page_number is not None and (type(page_number) is not int or page_number < 1):
            return Response({'error': 'page_number must be a positive integer.'}, status=400)
        library = request.data.get('scope') == 'library'

        if (library and (slide_id or deck_id)) or (not library and bool(slide_id) == bool(deck_id)):
            return Response(
                {'error': 'Provide exactly one of slide_id or deck_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message or not str(message).strip():
            return Response(
                {'error': 'message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(message, str) or len(message) > 4000:
            return Response({'error': 'Keep your question under 4,000 characters.'}, status=400)

        slide = None
        deck = None
        library_sources = []
        if library:
            from .library_tutor import library_context
            from .class_access import member_class
            history_scope = {'slide__isnull': True, 'deck__isnull': True,
                             'library_class': member_class(request.user)}
            recent_questions = SlideChatMessage.objects.filter(user=request.user, role='user',
                **history_scope).order_by('-created_at').values_list('content', flat=True)[:2]
            query = str(message) + '\n' + '\n'.join(recent_questions)
            context_text, library_sources, document_count = library_context(request.user, query)
            if not context_text:
                return Response({'error': 'AI is still preparing your class library. Open a document to ask about the page on screen, or try again shortly.'}, status=409)
            slide_context = {'context_scope': 'library', 'title': 'Your class slide library', 'text': context_text}
        elif deck_id:
            deck = visible(SlideDeck, request.user).filter(pk=deck_id).first()
            if deck is None:
                return Response({'error': f'Document {deck_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            context_text, context_error = _deck_chat_context(deck)
            if context_error and page_number is None:
                return Response({'error': context_error}, status=status.HTTP_409_CONFLICT)
            history_scope = {'deck': deck}
            slide_context = {
                'context_scope': 'deck',
                'title': deck.title,
                'text': context_text or '',
                'total_slides': deck.page_count or deck.pages.count(),
            }
        else:
            slide = visible(Slide, request.user).filter(pk=slide_id).first()
            if slide is None:
                return Response({'error': f'Slide {slide_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            slide_text = _slide_text(slide)
            context_text = _rag_context(slide, f'{message} page {page_number or ""}', slide_text)
            history_scope = {'slide': slide}
            slide_context = {
                'slide_index': 1,
                'total_slides': slide.page_count or 1,
                'title': slide.title,
                'text': context_text,
                'course': slide.topic_name if hasattr(slide, 'topic_name') else 'General'
            }

        if page_number is not None and not library:
            slide_context['slide_index'] = page_number
            from .document_index import source_data, page_image, IndexUnavailable
            from . import llm
            source = deck or slide
            page = next((p for p in source_data(source).get('pages', [])
                         if p.get('page_number') == page_number), None)
            if page is None:
                return Response({'error': 'This page is not ready to read yet.'}, status=409)
            if llm.supports_vision():
                try:
                    slide_image_base64 = page_image(source, page)
                except IndexUnavailable:
                    return Response({'error': 'The slide image could not be loaded. Please retry.'}, status=503)
                slide_context['image_page'] = page_number
            elif not slide_context.get('text'):
                return Response({'error': 'AI is preparing this document. Please try again shortly.'}, status=409)
        if not library and not slide_context.get('text') and not slide_image_base64:
            return Response({'error': 'AI is preparing this document. Please try again shortly.'}, status=409)

        # Deck chat always restores server-persisted history; it does not trust client-supplied context.
        if library or deck or not conversation_history:
            history_qs = SlideChatMessage.objects.filter(
                user=request.user, **history_scope
            ).order_by('-created_at')[:MAX_HISTORY_MESSAGES]
            conversation_history = [
                {'role': m.role, 'content': m.content}
                for m in reversed(list(history_qs))
            ]

        # Reserve only after source access, extraction, and history have been verified.
        try:
            reservation = CreditManager.reserve_credits(request.user, "CHAT")
        except InsufficientCreditsError as e:
            return Response(
                {'error': str(e), 'insufficient_credits': True},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # Call AI service
        try:
            result = slide_ai.chat(
                user_message=message,
                slide_context=slide_context,
                slide_image_base64=slide_image_base64,
                conversation_history=conversation_history,
                return_usage=True
            )
        except Exception:
            logger.exception('Chat provider failed')
            result = {'error': 'provider_failed'}

        if (not isinstance(result, dict) or 'error' in result or not isinstance(result.get('response'), str)
                or not result['response'].strip()):
            CreditManager.refund_credits(
                request.user, reservation['reserved_amount'], action="REFUND_CHAT_ERROR",
                reservation_id=reservation['reservation_id'],
            )
            if isinstance(result, dict) and result.get('error_code') == 'rate_limited':
                retry_after = max(1, int(result.get('retry_after', 60)))
                return Response({'error': result['error'], 'retry_after': retry_after}, status=429,
                                headers={'Retry-After': str(retry_after)})
            if isinstance(result, dict) and result.get('error_code') == 'request_too_large':
                return Response({'error': result['error']}, status=413)
            return Response(
                {'error': 'The AI provider could not complete the request. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY
            )
            
        try:
            save_scope = {'library_class': history_scope['library_class']} if library else history_scope
            with transaction.atomic():
                SlideChatMessage.objects.create(
                    user=request.user, **save_scope, role='user', content=str(message)
                )
                SlideChatMessage.objects.create(
                    user=request.user, **save_scope, role='assistant',
                    content=result.get('response', ''), sources=library_sources
                )
                CreditManager.commit_usage(request.user, reservation, result.get('total_tokens', 0))
        except Exception:
            logger.exception("Failed to persist chat for %s %s", 'deck' if deck else 'slide', deck_id or slide_id)
            try:
                CreditManager.refund_credits(
                    request.user, reservation['reserved_amount'], action="REFUND_CHAT_PERSISTENCE_ERROR",
                    reservation_id=reservation['reservation_id'],
                )
            except Exception:
                logger.exception("Failed to refund chat reservation after persistence failure")
            return Response(
                {'error': 'The chat could not be saved. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        result['disclaimer'] = AI_DISCLAIMER
        result['balance'] = CreditManager.get_user_balance(request.user)
        if library:
            result['sources'] = library_sources
            result['documents_searched'] = document_count

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
@permission_classes([IsAuthenticated, ClassContentReferences])
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
            slide = visible(Slide, request.user).get(id=slide_id)
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
        try:
            resources = _get_or_generate_resources(slide, request.user, slide_image_base64, force_refresh=force)
        except InsufficientCreditsError as e:
            return Response({'error': str(e), 'insufficient_credits': True}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except StudyResourceError as e:
            return Response({'error': str(e)}, status=e.status_code)

        if 'error' in resources:
            logger.error(f"Resource generation failed: {resources['error']}")
        
        resources['balance'] = CreditManager.get_user_balance(request.user)
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
@permission_classes([IsAuthenticated, ClassContentReferences])
def chat_history(request):
    """
    GET/DELETE /api/ai/chat/history/?slide_id=... or ?deck_id=...

    When both identifiers are omitted, operates on general chat history.
    """
    slide_id = request.query_params.get('slide_id')
    deck_id = request.query_params.get('deck_id')
    if slide_id and deck_id:
        return Response(
            {'error': 'Provide only one of slide_id or deck_id'},
            status=status.HTTP_400_BAD_REQUEST
        )

    qs = SlideChatMessage.objects.filter(user=request.user)
    if deck_id:
        deck = visible(SlideDeck, request.user).filter(pk=deck_id).first()
        if deck is None:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        qs = qs.filter(deck=deck)
    elif slide_id:
        qs = qs.filter(slide_id=slide_id)
    else:
        from .class_access import member_class
        qs = qs.filter(slide__isnull=True, deck__isnull=True, library_class=member_class(request.user))

    if request.method == 'DELETE':
        deleted, _ = qs.delete()
        return Response({'deleted': deleted}, status=status.HTTP_200_OK)

    messages = qs.order_by('-created_at')[:MAX_HISTORY_MESSAGES]
    data = [
        {
            'role': m.role,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
            'sources': m.sources,
        }
        for m in reversed(list(messages))
    ]
    return Response({'messages': data, 'disclaimer': AI_DISCLAIMER}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def generate_flashcards(request):
    """
    Generate AI-powered Flashcards for a slide (Premium Feature).
    It triggers a Celery task that generates and saves the flashcards for the user.
    
    Request body:
    {
        "slide_id": "123",
        "count": 5 // Optional
    }
    """
    slide_id = request.data.get('slide_id')
    count = request.data.get('count', 5)
    slide_image_base64 = request.data.get('slide_image_base64')

    if not slide_id:
        return Response({'error': 'slide_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(count, bool):
        return Response({'error': 'count must be an integer from 1 to 20'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        count = int(count)
    except (TypeError, ValueError):
        return Response({'error': 'count must be an integer from 1 to 20'}, status=status.HTTP_400_BAD_REQUEST)
    if count < 1 or count > 20:
        return Response({'error': 'count must be an integer from 1 to 20'}, status=status.HTTP_400_BAD_REQUEST)

    slide = visible(Slide, request.user).get(pk=slide_id)
    active_job = FlashcardGenerationJob.objects.filter(
        user=request.user,
        slide=slide,
        status__in=['queued', 'running'],
    ).first()
    if active_job is not None:
        return Response({
            'message': 'Flashcard generation is already in progress',
            'job_id': str(active_job.pk),
            'balance': CreditManager.get_user_balance(request.user),
        }, status=status.HTTP_202_ACCEPTED)

    try:
        reservation = CreditManager.reserve_credits(request.user, "GENERATE_FLASHCARDS")
    except InsufficientCreditsError as e:
        return Response(
            {'error': str(e), 'insufficient_credits': True},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )
    
    try:
        with transaction.atomic():
            job = FlashcardGenerationJob.objects.create(
                user=request.user,
                slide=slide,
                requested_count=count,
                reservation=reservation,
            )
    except IntegrityError:
        CreditManager.refund_credits(
            request.user,
            reservation['reserved_amount'],
            action="REFUND_FLASHCARD_ERROR",
            reservation_id=reservation['reservation_id'],
        )
        active_job = FlashcardGenerationJob.objects.filter(
            user=request.user,
            slide=slide,
            status__in=['queued', 'running'],
        ).first()
        if active_job is not None:
            return Response({
                'message': 'Flashcard generation is already in progress',
                'job_id': str(active_job.pk),
                'balance': CreditManager.get_user_balance(request.user),
            }, status=status.HTTP_202_ACCEPTED)
        logger.exception("Could not create flashcard generation job for slide %s", slide_id)
        return Response(
            {'error': 'Could not create flashcard generation job'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        _dispatch_flashcard_job(job.pk, slide_image_base64)
        
        return Response({
            'message': 'Flashcard generation started',
            'job_id': str(job.pk),
            'balance': CreditManager.get_user_balance(request.user)
        }, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error("Flashcard generation API error for job %s: %s", job.pk, e)
        return Response(
            {
                'message': 'Generation could not be queued. Check the saved request status for details.',
                'job_id': str(job.pk),
                'balance': CreditManager.get_user_balance(request.user),
            },
            status=status.HTTP_202_ACCEPTED,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, ClassContentReferences])
def flashcard_generation_status(request, job_id):
    now = timezone.now()
    should_requeue = False
    with transaction.atomic():
        job = FlashcardGenerationJob.objects.select_for_update().filter(
            pk=job_id,
            user=request.user,
            slide__in=visible(Slide, request.user),
        ).first()
        if job is None:
            return Response({'error': 'Generation request not found'}, status=status.HTTP_404_NOT_FOUND)
        queued_too_long = (
            job.status == 'queued'
            and ((job.next_attempt_at is not None and job.next_attempt_at <= now)
                 or (job.next_attempt_at is None and job.updated_at <= now - FLASHCARD_QUEUE_TIMEOUT))
        )
        worker_lease_expired = (
            job.status == 'running'
            and job.processing_lease_until is not None
            and job.processing_lease_until <= now
        )
        if queued_too_long or worker_lease_expired:
            job.status = 'queued'
            job.next_attempt_at = None
            job.processing_lease_until = None
            job.processing_token = None
            job.updated_at = now
            job.save(update_fields=[
                'status', 'next_attempt_at', 'processing_lease_until', 'processing_token', 'updated_at',
            ])
            should_requeue = True
    if should_requeue:
        try:
            _dispatch_flashcard_job(job.pk)
        except Exception as error:
            logger.warning("Flashcard job %s could not be requeued: %s", job.pk, error)
        job.refresh_from_db()
    return Response({
        'job_id': str(job.pk),
        'status': job.status,
        'requested_count': job.requested_count,
        'generated_count': job.generated_count,
        'error': job.error_message or None,
        'completed_at': job.completed_at,
        'next_attempt_at': job.next_attempt_at,
    }, status=status.HTTP_200_OK)
