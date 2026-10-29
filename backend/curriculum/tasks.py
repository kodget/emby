"""
Celery tasks for async slide processing
"""
import logging
from celery import shared_task
from django.utils import timezone
from .services.ai_question_generator import AIQuestionGenerator, Gemini429Exception
from .services.ai_theory_evaluator import AITheoryEvaluator, theory_evaluator

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=450, time_limit=480, ignore_result=True)
def index_document_task(job_id):
    from .document_index import run
    return run(job_id)


@shared_task(ignore_result=True)
def recover_document_indexes_task():
    from .document_index import recover
    return recover()


@shared_task(soft_time_limit=450, time_limit=480, ignore_result=True)
def generate_assessment_draft_task(job_id):
    from .assessment_drafts import run
    return run(job_id)


@shared_task(ignore_result=True)
def recover_assessment_drafts_task():
    from .assessment_drafts import recovery
    return recovery()


@shared_task(soft_time_limit=450, time_limit=480, ignore_result=True)
def grade_saved_assessment_task(attempt_id):
    from .assessment_grading import run
    return run(attempt_id)


@shared_task(ignore_result=True)
def recover_assessment_grading_task():
    from .assessment_grading import recovery
    return recovery()


@shared_task(ignore_result=True)
def recover_slide_processing_task():
    from django.core.management import call_command
    call_command('recover_slide_processing', '--apply')


@shared_task(ignore_result=True)
def recover_standalone_decks_task():
    from django.core.management import call_command
    call_command('recover_standalone_decks', '--apply')


@shared_task(soft_time_limit=450, time_limit=480, ignore_result=True)
def process_standalone_deck_task(deck_id, token=None):
    from .models import SlideDeck
    from .views import SlideDeckViewSet
    deck = SlideDeck.objects.filter(pk=deck_id, class_group__isnull=False, asset__isnull=False).first()
    if deck is None:
        logger.warning('Standalone deck recovery skipped for missing or unowned deck.')
        return
    SlideDeckViewSet()._process_deck_async(deck, token=token)


def _extract_text_from_content(content_data: dict) -> str:
    from .services.document_extraction import content_text
    return content_text(content_data or {})


@shared_task(soft_time_limit=450, time_limit=480)
def process_slide_task(slide_id: str, local_file_path: str = None, token=None):
    from .slide_processing import process
    return process(slide_id, token=token, local_file_path=local_file_path)


@shared_task
def process_multiple_slides_task(slide_ids: list):
    """
    Process multiple slides in batch
    """
    results = {
        'total': len(slide_ids),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    for slide_id in slide_ids:
        try:
            result = process_slide_task.delay(slide_id)
            results['details'].append({
                'slide_id': slide_id,
                'task_id': result.id,
                'status': 'queued'
            })
        except Exception as e:
            logger.error(f"Failed to queue slide {slide_id}: {e}")
            results['failed'] += 1
            results['details'].append({
                'slide_id': slide_id,
                'status': 'error',
                'error': str(e)
            })
    
    return results


@shared_task
def cleanup_old_temp_files():
    """
    Periodic task to clean up old temporary files
    """
    import os
    import shutil
    import tempfile
    from datetime import datetime, timedelta
    
    temp_dir = tempfile.gettempdir()
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    cleaned = 0
    for item in os.listdir(temp_dir):
        if item.startswith('slide_') or item.startswith('slides_'):
            item_path = os.path.join(temp_dir, item)
            try:
                if os.path.isdir(item_path):
                    mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                    if mtime < cutoff_time:
                        shutil.rmtree(item_path, ignore_errors=True)
                        cleaned += 1
                        logger.info(f"Cleaned up old temp directory: {item_path}")
            except Exception as e:
                logger.error(f"Error cleaning {item_path}: {e}")
    
    logger.info(f"Cleanup complete: removed {cleaned} old temp directories")
    return {'cleaned': cleaned}



@shared_task(bind=True, max_retries=3)
def evaluate_theory_answers_task(self, attempt_id: str):
    """
    Evaluate theory question answers for a quiz attempt using AI.
    """
    from .models import QuizAttempt, QuizAttemptResponse
    from .services.ai_theory_evaluator import AITheoryEvaluator, Gemini429Exception
    
    logger.info(f"=== THEORY EVALUATION TASK START  attempt={attempt_id} ===")
    
    try:
        attempt = QuizAttempt.objects.get(id=attempt_id)
    except QuizAttempt.DoesNotExist:
        error_msg = f"Attempt {attempt_id} not found"
        logger.error(error_msg)
        return {'success': False, 'attempt_id': attempt_id, 'error': error_msg}
    
    from .assessment_history import is_historical
    if is_historical(attempt):
        return {'success': False, 'error': 'Historical attempts cannot be regraded without original question versions.'}
    if attempt.assessment_id or attempt.snapshot_class_id:
        return {'success': False, 'attempt_id': attempt_id, 'error': 'This attempt uses durable saved-rubric grading.'}

    theory_responses = QuizAttemptResponse.objects.filter(
        attempt=attempt,
        question__question_type='theory',
        text_answer__isnull=False
    ).exclude(text_answer='').select_related('question')
    
    if not theory_responses.exists():
        logger.info(f"No theory responses to evaluate for attempt {attempt_id}")
        attempt.theory_grading_pending = False
        attempt.theory_grading_completed = True
        attempt.save(update_fields=['theory_grading_pending', 'theory_grading_completed'])
        return {
            'success': True,
            'attempt_id': attempt_id,
            'theory_responses_evaluated': 0,
            'message': 'No theory responses to evaluate'
        }
    
    logger.info(f"Evaluating {theory_responses.count()} theory responses for attempt {attempt_id}")
    
    evaluated_count = 0
    total_theory_score = 0.0
    total_theory_max = 0.0
    
    try:
        for response in theory_responses:
            question = response.question
            response.ai_evaluation_status = 'processing'
            response.save(update_fields=['ai_evaluation_status'])
            
            result = AITheoryEvaluator.evaluate(
                question_text=question.question_text,
                student_answer=response.text_answer,
                ideal_answer=question.ideal_answer,
                marking_rubric=question.marking_rubric,
                maximum_marks=question.maximum_marks
            )
            
            if result.get('success'):
                response.ai_score = int(result.get('score', 0.0))
                response.ai_feedback = {"feedback": result.get('feedback', '')}
                response.ai_rubric_breakdown = result.get('rubric_breakdown', [])
                response.is_correct = response.ai_score >= (question.maximum_marks / 2.0)
                response.ai_evaluation_status = 'completed'
                response.answered_at = timezone.now()
                response.save()
                
                evaluated_count += 1
                total_theory_score += response.ai_score
                total_theory_max += question.maximum_marks
            else:
                response.ai_evaluation_status = 'failed'
                response.save(update_fields=['ai_evaluation_status'])
                logger.error(f"Failed to evaluate response {response.id}: {result.get('error')}")
        
        attempt.theory_score = int(total_theory_score)
        attempt.theory_total = len(theory_responses)
        
        # Calculate overall percentage
        total_mcq_max = attempt.mcq_total
        total_max_points = total_mcq_max + total_theory_max
        total_earned_points = attempt.mcq_score + attempt.theory_score
        
        if total_max_points > 0:
            attempt.overall_percentage = (total_earned_points / total_max_points) * 100
        else:
            attempt.overall_percentage = 0.0
            
        attempt.theory_grading_pending = False
        attempt.theory_grading_completed = True
        attempt.save()
        
        logger.info(f"=== THEORY EVALUATION TASK COMPLETE  attempt={attempt_id} evaluated={evaluated_count} ===")
        return {
            'success': True,
            'attempt_id': attempt_id,
            'theory_responses_evaluated': evaluated_count,
            'average_score': (total_theory_score / evaluated_count) if evaluated_count > 0 else 0.0
        }
        
    except Gemini429Exception as e:
        retry_num = self.request.retries
        countdown = 60 * (2 ** retry_num)
        logger.warning(f"Gemini API 429 during evaluation of attempt {attempt_id}. Retrying {retry_num+1}/3 in {countdown}s")
        raise self.retry(exc=e, countdown=countdown)
    except Exception as e:
        error_msg = f"Error in evaluation task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'attempt_id': attempt_id,
            'error': error_msg
        }


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_flashcards_task(self, attempt_id):
    """
    Celery task: generate flashcards for all incorrect responses in a quiz attempt.
    Called automatically after quiz submission — does not block the HTTP response.
    """
    try:
        from .services.flashcard_generator import generate_flashcards_for_attempt
        result = generate_flashcards_for_attempt(attempt_id)
        logger.info(
            f"generate_flashcards_task[{attempt_id}]: "
            f"created={result['created_count']}, "
            f"existing={result['existing_count']}, "
            f"errors={result['error_count']}"
        )
        return result
    except Exception as e:
        logger.error(f"generate_flashcards_task[{attempt_id}] failed: {e}", exc_info=True)
        raise self.retry(exc=e)

@shared_task
def recover_flashcard_generation_task():
    from .flashcard_dispatch import recover_flashcard_jobs
    return recover_flashcard_jobs()


@shared_task(bind=True, max_retries=3)
def generate_ai_flashcards_from_slide_task(self, slide_id: str, user_id: int, count: int = 5, reservation: dict = None, slide_image_base64: str = None, job_id: str = None):
    """
    Generate flashcards from slide content using AI.
    """
    from .models import Slide, Flashcard, FlashcardProgress, FlashcardGenerationJob
    from credits.services import CreditManager
    from .services.ai_flashcard_generator import AIFlashcardGenerator
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.db import transaction
    from datetime import timedelta
    import uuid
    from .class_access import visible
    from learning.generation import extracted_source
    User = get_user_model()
    
    logger.info(f"=== AI FLASHCARD GENERATION TASK START slide={slide_id} user={user_id} count={count} ===")
    job = None
    processing_token = None
    exhausted = False
    if job_id and job is None:
        with transaction.atomic():
            job = FlashcardGenerationJob.objects.select_for_update().filter(pk=job_id).first()
            if job is None:
                logger.error("Flashcard generation job %s was not found.", job_id)
                return {'success': False, 'slide_id': slide_id, 'error': 'Generation request was not found.'}
            if job.status in ('failed', 'completed'):
                return {
                    'success': job.status == 'completed',
                    'slide_id': slide_id,
                    'generated_count': job.generated_count,
                    'error': job.error_message or None,
                }
            now = timezone.now()
            if job.next_attempt_at and job.next_attempt_at > now:
                return {'success': False, 'slide_id': slide_id, 'in_progress': True}
            if (
                job.status == 'running'
                and job.processing_lease_until is not None
                and job.processing_lease_until > now
            ):
                return {'success': True, 'slide_id': slide_id, 'in_progress': True}
            processing_token = uuid.uuid4()
            job.status = 'running'
            job.error_message = ''
            job.processing_token = processing_token
            job.processing_lease_until = now + timedelta(minutes=12)
            job.next_attempt_at = None
            exhausted = job.attempts >= 3
            job.attempts += 1
            job.save(update_fields=[
                'status', 'error_message', 'processing_token',
                'processing_lease_until', 'next_attempt_at', 'attempts', 'updated_at',
            ])
            reservation = job.reservation or reservation
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        error_msg = f"User {user_id} not found"
        logger.error(error_msg)
        if job:
            job.status = 'failed'
            job.error_message = 'The account for this generation request is unavailable.'
            job.completed_at = timezone.now()
            job.processing_lease_until = None
            job.processing_token = None
            job.save(update_fields=[
                'status', 'error_message', 'completed_at',
                'processing_lease_until', 'processing_token', 'updated_at',
            ])
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}

    def failed(error_msg):
        with transaction.atomic():
            current_job = None
            if job:
                current_job = FlashcardGenerationJob.objects.select_for_update().filter(
                    pk=job.pk,
                    processing_token=processing_token,
                    status='running',
                ).first()
                if current_job is None:
                    logger.warning(
                        "Ignoring failure from superseded flashcard job worker %s",
                        job.pk,
                    )
                    return {'success': False, 'slide_id': slide_id, 'error': 'Generation worker was superseded.'}
            if reservation:
                CreditManager.refund_credits(
                    user, reservation['reserved_amount'], action="REFUND_FLASHCARD_ERROR",
                    reservation_id=reservation['reservation_id'],
                )
            if current_job:
                current_job.status = 'failed'
                current_job.error_message = error_msg[:500]
                current_job.completed_at = timezone.now()
                current_job.processing_lease_until = None
                current_job.processing_token = None
                current_job.save(update_fields=[
                    'status', 'error_message', 'completed_at',
                    'processing_lease_until', 'processing_token', 'updated_at',
                ])
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}

    if exhausted:
        return failed('Generation stopped after repeated worker interruptions. Saved cards are preserved; please retry.')

    slide = visible(Slide, user).select_related(
        'subject', 'block', 'sub_block', 'topic'
    ).filter(pk=slide_id).first()
    if slide is None:
        error_msg = f"Slide {slide_id} not found or is no longer available"
        logger.warning(error_msg)
        return failed(error_msg)

    existing_count = Flashcard.objects.filter(
        user=user, source='ai', source_slide=slide
    ).count()
    remaining_count = max(0, count - existing_count)
    if not remaining_count:
        with transaction.atomic():
            current_job = None
            if job:
                current_job = FlashcardGenerationJob.objects.select_for_update().filter(
                    pk=job.pk,
                    processing_token=processing_token,
                    status='running',
                ).first()
                if current_job is None:
                    return {'success': False, 'slide_id': slide_id, 'error': 'Generation worker was superseded.'}
            if reservation:
                if current_job and current_job.tokens_used:
                    CreditManager.commit_usage(user, reservation, current_job.tokens_used)
                else:
                    CreditManager.refund_credits(
                        user, reservation['reserved_amount'], action="REFUND_FLASHCARD_ERROR",
                        reservation_id=reservation['reservation_id'],
                    )
            if current_job:
                current_job.status = 'completed'
                current_job.generated_count = existing_count
                current_job.completed_at = timezone.now()
                current_job.processing_lease_until = None
                current_job.processing_token = None
                current_job.save(update_fields=[
                    'status', 'generated_count', 'completed_at',
                    'processing_lease_until', 'processing_token', 'updated_at',
                ])
        return {
            'success': True,
            'slide_id': slide_id,
            'user_id': user_id,
            'generated_count': 0,
            'existing_count': existing_count,
        }
    
    try:
        text, source_digest = extracted_source(slide.pk)
    except Exception as e:
        logger.error("Could not load verified flashcard source for slide %s: %s", slide_id, e, exc_info=True)
        return failed("Verified source text could not be loaded. Please retry.")
    if not source_digest or not text:
        error_msg = f"Complete, verified source text is unavailable for slide {slide_id}; retry extraction first."
        logger.warning(error_msg)
        return failed(error_msg)
    if len(text.strip()) < 100 and not slide_image_base64:
        error_msg = f"Insufficient text content for slide {slide_id} ({len(text.strip())} chars)."
        logger.warning(error_msg)
        return failed(error_msg)
    
    from .llm import LLMRateLimited
    try:
        from learning.source_sampling import assessment_source
        from .llm import generation_batch_size
        batch_count = generation_batch_size(min(5, remaining_count)) if job else remaining_count
        flashcards_data, tokens = AIFlashcardGenerator.generate_flashcards_from_text(
            text=assessment_source(text, count=batch_count, seed=str(processing_token)),
            slide=slide,
            topic=slide.topic,
            count=batch_count,
            slide_image_base64=None,
            return_usage=True,
            exclude_fronts=list(Flashcard.objects.filter(user=user, source='ai', source_slide=slide)
                                .order_by('-pk').values_list('front', flat=True)[:20]),
        )
    except LLMRateLimited as error:
        if not job:
            return failed('The AI provider is temporarily busy. Please retry shortly.')
        with transaction.atomic():
            current = FlashcardGenerationJob.objects.select_for_update().filter(
                pk=job.pk, processing_token=processing_token, status='running').first()
            if current is None:
                return {'success': False, 'slide_id': slide_id, 'error': 'Generation worker was superseded.'}
            current.status = 'queued'
            current.next_attempt_at = timezone.now() + timedelta(seconds=max(1, error.retry_after))
            current.attempts = max(0, current.attempts - 1)
            current.error_message = 'Waiting for AI capacity. Your flashcards will continue automatically.'
            current.processing_lease_until = current.processing_token = None
            current.save()
        return {'success': False, 'slide_id': slide_id, 'in_progress': True}
    except Exception as e:
        error_msg = f"Error generating flashcards: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return failed(error_msg)
    if not flashcards_data and (not job or job.attempts >= 3):
        return failed("No flashcards could be generated from this slide.")

    saved_count = 0
    try:
        with transaction.atomic():
            current_job = None
            if job:
                current_job = FlashcardGenerationJob.objects.select_for_update().filter(
                    pk=job.pk,
                    processing_token=processing_token,
                    status='running',
                ).first()
                if current_job is None:
                    return {'success': False, 'slide_id': slide_id, 'error': 'Generation worker was superseded.'}
            for flashcard_data in flashcards_data[:batch_count]:
                flashcard, created = Flashcard.objects.get_or_create(
                    user=user,
                    source='ai',
                    source_slide=slide,
                    front=flashcard_data['front'],
                    defaults={
                        'back': flashcard_data['back'],
                        'explanation': flashcard_data.get('explanation', ''),
                        'subject': slide.subject,
                        'block': slide.block,
                        'sub_block': slide.sub_block,
                        'topic': slide.topic,
                    }
                )
                if created:
                    saved_count += 1
                FlashcardProgress.objects.get_or_create(
                    user=user,
                    flashcard=flashcard,
                    defaults={'due_date': timezone.now()},
                )
            existing_total = Flashcard.objects.filter(
                user=user, source='ai', source_slide=slide
            ).count()
            if current_job:
                current_job.tokens_used += tokens
                current_job.attempts = 0 if saved_count else current_job.attempts
                continuing = existing_total < count and current_job.attempts < 3
                current_job.status = 'queued' if continuing else 'completed'
                current_job.generated_count = existing_total
                current_job.completed_at = None if continuing else timezone.now()
                current_job.next_attempt_at = timezone.now() + timedelta(seconds=10) if continuing else None
                current_job.error_message = 'Saved cards are ready. More will be prepared automatically.' if continuing else ''
                current_job.processing_lease_until = None
                current_job.processing_token = None
                current_job.save(update_fields=[
                    'status', 'generated_count', 'completed_at',
                    'processing_lease_until', 'processing_token', 'next_attempt_at',
                    'attempts', 'tokens_used', 'error_message', 'updated_at',
                ])
            if reservation and (not current_job or current_job.status == 'completed'):
                CreditManager.commit_usage(user, reservation, current_job.tokens_used if current_job else tokens)
    except Exception as e:
        error_msg = f"Error saving generated flashcards: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return failed(error_msg)
            
    logger.info(f"=== AI FLASHCARD GENERATION COMPLETE slide={slide_id} saved={saved_count}/{len(flashcards_data)} ===")
    
    result = {
        'success': True,
        'slide_id': slide_id,
        'user_id': user_id,
        'generated_count': saved_count,
        'existing_count': existing_total,
    }
    return result



@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=None,
    time_limit=None,
)
def generate_question_bank_task(self, slide_id: str, force: bool = False):
    """Fill a slide's question bank with 15 MCQs (5 easy, 5 medium, 5 hard) and 10 theory questions.

    Runs in the background after upload so the uploader never waits on it. The work is
    idempotent and resumable: learning.generation claims a locked job row, counts what
    already exists, and only generates the shortfall.
    """
    from .models import Slide
    from learning.generation import generate_for_slide

    slide = Slide.objects.select_related("subject", "block", "sub_block", "topic").filter(
        id=slide_id
    ).first()
    if slide is None:
        logger.error("generate_question_bank_task: slide %s not found", slide_id)
        return {"success": False, "error": "slide not found"}

    # Status writes belong to the leased generator. A late task must not overwrite
    # the state published by a newer worker after its lease expires.
    return generate_for_slide(slide, force=force)


@shared_task
def send_due_notifications_task():
    """Periodic sweep that creates the notifications students are due.

    Idempotent by design: dedupe keys and the per-student daily budget mean running this
    every 30 minutes produces at most a handful of rows a day per student.
    """
    from learning import notifications

    result = notifications.run_for_all()
    logger.info(
        "Notification sweep: %s created for %s students",
        result["notifications_created"], result["users_notified"],
    )
    return result

@shared_task(bind=True, max_retries=10, default_retry_delay=30)
def analyze_quiz_attempt_task(self, attempt_id):
    """
    Generate deep performance analysis for formal assessments and mock exams.
    Waits for theory grading to finish before proceeding.
    """
    from .models import QuizAttempt
    from .services.flashcard_generator import generate_flashcards_for_attempt
    from .llm import chat
    import json
    import time
    
    try:
        attempt = QuizAttempt.objects.select_related('user').get(id=attempt_id)
        from .assessment_history import is_historical
        if is_historical(attempt):
            return {'success': False, 'error': 'Historical attempts cannot receive analysis from current question versions.'}
        if attempt.assessment_id or attempt.snapshot_class_id:
            return {'success': False, 'error': 'Formal snapshot analysis is not available yet.'}
        
        if attempt.theory_grading_pending:
            logger.info(f"Analyze task for {attempt_id} waiting on theory grading...")
            raise self.retry(countdown=30)
            
        # 1. Generate Flashcards for missed questions
        try:
            generate_flashcards_for_attempt(attempt_id)
        except Exception as e:
            logger.error(f"Error generating flashcards in analysis task: {e}")
            
        # 2. Build analysis prompt
        # We need to give the AI context about what the user missed.
        missed_responses = attempt.responses.filter(is_correct=False).select_related('question', 'question__sub_block')
        
        missed_text = ""
        for i, r in enumerate(missed_responses[:20]): # Limit to 20 for prompt size
            missed_text += f"\nQ{i+1}: {r.question.text}\nType: {r.question.question_type}\nTopic: {r.question.sub_block.name if r.question.sub_block else 'General'}\n"
            
        prompt = f"""
        You are an expert tutor. Analyze the student's performance on this quiz and provide actionable insights.
        Quiz Type: {attempt.exam_type}
        Score: {attempt.overall_percentage:.1f}%
        Total MCQ: {attempt.mcq_total} (Got {attempt.mcq_score} correct)
        Total Theory: {attempt.theory_total} (Got {attempt.theory_score} points)
        
        Missed Concepts / Questions (Sample):
        {missed_text}
        
        Provide a JSON response with exactly these keys:
        - "insights": A string analyzing their performance and what these mistakes reveal about their understanding.
        - "next_steps": A string with 2-3 specific, actionable recommendations on what to study next.
        - "weakest_topics": A list of strings identifying the weakest topic(s).
        
        Return ONLY valid JSON.
        """
        
        response_text = chat([{"role": "user", "content": prompt}], max_tokens=1000)
        
        # Clean response
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        try:
            analysis_data = json.loads(clean_text)
            attempt.analysis_data = analysis_data
            attempt.save(update_fields=['analysis_data'])
            logger.info(f"Successfully generated analysis for attempt {attempt_id}")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI analysis JSON for {attempt_id}: {response_text}")
            
        return {'success': True}
        
    except QuizAttempt.DoesNotExist:
        logger.error(f"QuizAttempt {attempt_id} not found in analyze task.")
        return {'success': False, 'error': 'Not found'}
    except Exception as e:
        logger.error(f"Error in analyze_quiz_attempt_task: {e}")
        # Retry only for known transient errors if needed, else fail.
        if "Retry" in str(e) or "429" in str(e):
             raise self.retry(exc=e)
        return {'success': False, 'error': str(e)}
