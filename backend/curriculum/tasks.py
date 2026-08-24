"""
Celery tasks for async slide processing
"""
import logging
from celery import shared_task
from django.utils import timezone
from .services.ai_question_generator import AIQuestionGenerator, Gemini429Exception
from .services.ai_theory_evaluator import AITheoryEvaluator, theory_evaluator

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_slide_task(self, slide_id: str):
    """
    Async task to process a slide after upload
    
    PIPELINE: ANY FILE → PPTX → PDF → IMAGES
    
    Args:
        slide_id: ID of the slide to process
        
    Returns:
        dict: Processing results
    """
    from .models import Slide, SlideProcessingStatus, SlideContent
    from .services.slide_conversion_pipeline import SlideConversionPipeline
    import cloudinary.uploader
    
    try:
        # Get slide
        try:
            slide = Slide.objects.get(id=slide_id)
        except Slide.DoesNotExist:
            logger.error(f"Slide {slide_id} not found")
            return {'success': False, 'error': 'Slide not found'}
        
        # Get Cloudinary URL
        cloudinary_url = slide.file_url if slide.file_url else (slide.file.url if slide.file else None)
        if not cloudinary_url:
            logger.error(f"Slide {slide_id} has no file URL")
            return {'success': False, 'error': 'No file URL found'}
        
        # Update status to processing
        status_obj, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
        status_obj.status = 'processing'
        status_obj.started_at = timezone.now()
        status_obj.error_message = ''
        status_obj.save()
        
        logger.info(f"=== STARTING SLIDE PROCESSING ===")
        logger.info(f"Slide ID: {slide_id}")
        logger.info(f"Title: {slide.title}")
        logger.info(f"File URL: {cloudinary_url}")
        logger.info(f"File Type: {slide.file_type}")
        
        # Run the conversion pipeline
        result = SlideConversionPipeline.process_slide(
            cloudinary_url=cloudinary_url,
            slide_id=slide_id,
            original_file_type=slide.file_type or 'pdf'
        )
        
        # Handle result
        if result['success']:
            logger.info(f"✓ Pipeline completed successfully")
            
            # Update slide page count
            slide.page_count = result['page_count']
            slide.save(update_fields=['page_count'])
            
            # Store images in Cloudinary and get URLs
            logger.info(f"Uploading {len(result['image_paths'])} images to Cloudinary...")
            pages = []  # frontend shape: [{page_number, image_url, width, height}]

            for idx, image_path in enumerate(result['image_paths'], 1):
                try:
                    cloudinary_result = cloudinary.uploader.upload(
                        image_path,
                        folder=f"emby/slides/{slide_id}",
                        public_id=f"page_{idx:04d}",
                        resource_type='image',
                        format='jpg',
                        quality='auto:best',
                        timeout=60
                    )
                    pages.append({
                        'page_number': idx,
                        'image_url': cloudinary_result['secure_url'],
                        'width': cloudinary_result.get('width', 1280),
                        'height': cloudinary_result.get('height', 960),
                    })
                    logger.info(f"✓ Uploaded page {idx} to Cloudinary")
                except Exception as e:
                    logger.error(f"Failed to upload page {idx}: {e}")

            # Store in database
            slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
            slide_content.content_data = {
                'text': result.get('text_content', ''),
                'pages': pages,
                'total_pages': len(pages),
                'page_count': len(pages),
            }
            slide_content.is_extracted = True
            slide_content.extracted_at = timezone.now()
            slide_content.save()
            
            # Update processing status
            status_obj.status = 'completed'
            status_obj.completed_at = timezone.now()
            status_obj.error_message = ''
            status_obj.save()
            
            logger.info(f"✓✓✓ SLIDE {slide_id} SUCCESSFULLY PROCESSED ✓✓✓")
            
            return {
                'success': True,
                'slide_id': slide_id,
                'page_count': result['page_count'],
                'image_urls': pages
            }
        
        else:
            # Pipeline failed
            error_message = result.get('error', 'Unknown error')
            logger.error(f"✗ Pipeline failed: {error_message}")
            
            status_obj.status = 'failed'
            status_obj.error_message = error_message
            status_obj.completed_at = timezone.now()
            status_obj.save()
            
            return {
                'success': False,
                'slide_id': slide_id,
                'error': error_message
            }
        
    except Exception as e:
        logger.error(f"Task error for slide {slide_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        try:
            status_obj = SlideProcessingStatus.objects.get(slide_id=slide_id)
            status_obj.status = 'failed'
            status_obj.error_message = str(e)
            status_obj.completed_at = timezone.now()
            status_obj.save()
        except:
            pass
        
        # Retry the task
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for slide {slide_id}")
            return {'success': False, 'error': f'Max retries exceeded: {str(e)}'}


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
def generate_questions_task(self, slide_id: str, mcq_count: int = 5, theory_count: int = 2, difficulty: str = 'medium'):
    """
    Generate questions from slide content.
    """
    from .models import Slide, SlideContent, QuizQuestion
    from .services.ai_question_generator import AIQuestionGenerator, Gemini429Exception
    import uuid
    
    logger.info(f"=== QUESTION GENERATION TASK START  slide={slide_id} mcq={mcq_count} theory={theory_count} ===")
    
    try:
        slide = Slide.objects.select_related('subject', 'block', 'sub_block', 'topic').get(id=slide_id)
    except Slide.DoesNotExist:
        error_msg = f"Slide {slide_id} not found"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    if AIQuestionGenerator.questions_exist_for_slide(slide_id):
        logger.info(f"Questions already exist for slide {slide_id}, skipping generation")
        existing_mcq = QuizQuestion.objects.filter(source_slide=slide, question_type='mcq').count()
        existing_theory = QuizQuestion.objects.filter(source_slide=slide, question_type='theory').count()
        return {
            'success': True,
            'slide_id': slide_id,
            'mcq_generated': existing_mcq,
            'theory_generated': existing_theory,
            'skipped': True,
            'reason': 'Questions already exist'
        }
    
    try:
        slide_content = SlideContent.objects.get(slide=slide)
        text = slide_content.content_data.get('text', '')
        
        if not text or len(text.strip()) < 100:
            error_msg = f"Insufficient text content for slide {slide_id} ({len(text)} chars)"
            logger.warning(error_msg)
            return {
                'success': False,
                'slide_id': slide_id,
                'error': error_msg,
                'mcq_generated': 0,
                'theory_generated': 0
            }
    except SlideContent.DoesNotExist:
        error_msg = f"No content found for slide {slide_id}"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    logger.info(f"Generating questions from {len(text)} chars of content for slide '{slide.title}'")
    
    mcq_questions = []
    theory_questions = []
    
    try:
        if mcq_count > 0:
            logger.info(f"Generating {mcq_count} MCQ questions...")
            mcq_questions = AIQuestionGenerator.generate_mcqs_from_text(
                text=text,
                slide=slide,
                topic=slide.topic,
                count=mcq_count,
                difficulty=difficulty
            )
            logger.info(f"Generated {len(mcq_questions)} MCQ questions")
        
        if theory_count > 0:
            logger.info(f"Generating {theory_count} theory questions...")
            theory_questions = AIQuestionGenerator.generate_theory_from_text(
                text=text,
                slide=slide,
                topic=slide.topic,
                count=theory_count,
                difficulty=difficulty
            )
            logger.info(f"Generated {len(theory_questions)} theory questions")
            
    except Gemini429Exception as e:
        retry_num = self.request.retries
        countdown = 60 * (2 ** retry_num)
        logger.warning(f"Rate limit hit for slide {slide_id}. Retry {retry_num + 1}/{self.max_retries} in {countdown}s")
        raise self.retry(exc=e, countdown=countdown)
    except Exception as e:
        error_msg = f"Error generating questions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'slide_id': slide_id,
            'error': error_msg,
            'mcq_generated': 0,
            'theory_generated': 0
        }
        
    saved_mcq = 0
    saved_theory = 0
    
    try:
        for mcq_data in mcq_questions:
            try:
                question_id = f"q_{uuid.uuid4().hex[:12]}"
                QuizQuestion.objects.create(
                    id=question_id,
                    question_type='mcq',
                    difficulty=mcq_data.get('difficulty', difficulty),
                    subject=slide.subject,
                    block=slide.block,
                    sub_block=slide.sub_block,
                    question_text=mcq_data['question_text'],
                    option_a=mcq_data['option_a'],
                    option_b=mcq_data['option_b'],
                    option_c=mcq_data['option_c'],
                    option_d=mcq_data['option_d'],
                    correct_option=mcq_data['correct_option'],
                    explanation=mcq_data.get('explanation', ''),
                    maximum_marks=mcq_data.get('maximum_marks', 1),
                    source_type='ai_generated',
                    source_slide=slide,
                    source_text=text[:1000],
                )
                saved_mcq += 1
            except Exception as e:
                logger.error(f"Failed to save MCQ question: {e}")
                
        for theory_data in theory_questions:
            try:
                question_id = f"q_{uuid.uuid4().hex[:12]}"
                QuizQuestion.objects.create(
                    id=question_id,
                    question_type='theory',
                    difficulty=theory_data.get('difficulty', difficulty),
                    subject=slide.subject,
                    block=slide.block,
                    sub_block=slide.sub_block,
                    question_text=theory_data['question_text'],
                    ideal_answer=theory_data.get('ideal_answer', ''),
                    model_answer=theory_data.get('ideal_answer', ''),
                    marking_rubric=theory_data.get('marking_rubric', []),
                    maximum_marks=theory_data.get('maximum_marks', 20),
                    explanation='',
                    source_type='ai_generated',
                    source_slide=slide,
                    source_text=text[:1000],
                )
                saved_theory += 1
            except Exception as e:
                logger.error(f"Failed to save theory question: {e}")
                
        logger.info(f"=== QUESTION GENERATION COMPLETE  slide={slide_id}  MCQ={saved_mcq}/{len(mcq_questions)}  Theory={saved_theory}/{len(theory_questions)} ===")
        return {
            'success': True,
            'slide_id': slide_id,
            'mcq_generated': saved_mcq,
            'theory_generated': saved_theory,
            'total_generated': saved_mcq + saved_theory
        }
    except Exception as e:
        error_msg = f"Database error saving questions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'slide_id': slide_id,
            'error': error_msg,
            'mcq_generated': saved_mcq,
            'theory_generated': saved_theory
        }


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

@shared_task(bind=True, max_retries=3)
def generate_ai_flashcards_from_slide_task(self, slide_id: str, user_id: int, count: int = 5):
    """
    Generate flashcards from slide content using AI.
    """
    from .models import Slide, SlideContent, Flashcard, FlashcardProgress
    from .services.ai_flashcard_generator import AIFlashcardGenerator
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    User = get_user_model()
    
    logger.info(f"=== AI FLASHCARD GENERATION TASK START slide={slide_id} user={user_id} count={count} ===")
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        error_msg = f"User {user_id} not found"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}

    try:
        slide = Slide.objects.select_related('subject', 'block', 'sub_block', 'topic').get(id=slide_id)
    except Slide.DoesNotExist:
        error_msg = f"Slide {slide_id} not found"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    try:
        slide_content = SlideContent.objects.get(slide=slide)
        text = slide_content.content_data.get('text', '')
        
        if not text or len(text.strip()) < 100:
            error_msg = f"Insufficient text content for slide {slide_id} ({len(text)} chars)"
            logger.warning(error_msg)
            return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    except SlideContent.DoesNotExist:
        error_msg = f"No content found for slide {slide_id}"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    try:
        flashcards_data = AIFlashcardGenerator.generate_flashcards_from_text(
            text=text,
            slide=slide,
            topic=slide.topic,
            count=count
        )
    except Exception as e:
        error_msg = f"Error generating flashcards: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Note: if it's Gemini429Exception, we could retry here if we imported it
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    saved_count = 0
    
    for flashcard_data in flashcards_data:
        try:
            flashcard, created = Flashcard.objects.get_or_create(
                user=user,
                front=flashcard_data['front'],
                defaults={
                    'back': flashcard_data['back'],
                    'explanation': flashcard_data.get('explanation', ''),
                    'subject': slide.subject,
                    'block': slide.block,
                    'sub_block': slide.sub_block,
                    'topic': slide.topic,
                    'source': 'ai_generated',
                }
            )
            if created:
                saved_count += 1
                FlashcardProgress.objects.create(
                    user=user,
                    flashcard=flashcard,
                    due_date=timezone.now()
                )
        except Exception as e:
            logger.error(f"Failed to save AI generated flashcard: {e}")
            
    logger.info(f"=== AI FLASHCARD GENERATION COMPLETE slide={slide_id} saved={saved_count}/{len(flashcards_data)} ===")
    
    return {
        'success': True,
        'slide_id': slide_id,
        'user_id': user_id,
        'generated_count': saved_count
    }

