    # ── 1. Load slide and check if it exists ────────────────────────────────
    try:
        slide = Slide.objects.select_related('subject', 'block', 'sub_block', 'topic').get(id=slide_id)
    except Slide.DoesNotExist:
        error_msg = f"Slide {slide_id} not found"
        logger.error(error_msg)
        return {'success': False, 'slide_id': slide_id, 'error': error_msg}
    
    # ── 2. Idempotency check - skip if questions already exist ──────────────
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
    
    # ── 3. Get slide content text ───────────────────────────────────────────
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
    
    # ── 4. Generate questions with 429 retry handling ───────────────────────
    mcq_questions = []
    theory_questions = []
    
    try:
        # Generate MCQ questions
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
        
        # Generate theory questions
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
        # 429 rate limit error - retry with exponential backoff
        retry_num = self.request.retries
        countdown = 60 * (2 ** retry_num)  # 60s, 120s, 240s
        
        logger.warning(
            f"Rate limit hit for slide {slide_id}. "
            f"Retry {retry_num + 1}/{self.max_retries} in {countdown}s"
        )
        
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=countdown)
    
    except Exception as e:
        error_msg = f"Error generating questions: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        return {
            'success': False,
            'slide_id': slide_id,
            'error': error_msg,
            'mcq_generated': 0,
            'theory_generated': 0
        }
    
    # ── 5. Save generated questions to database ─────────────────────────────
    saved_mcq = 0
    saved_theory = 0
    
    try:
        # Save MCQ questions
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
                    source_text=text[:1000],  # Store first 1000 chars as audit trail
                )
                saved_mcq += 1
            except Exception as e:
                logger.error(f"Failed to save MCQ question: {e}")
        
        # Save theory questions
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
                    model_answer=theory_data.get('ideal_answer', ''),  # Duplicate for backward compatibility
                    marking_rubric=theory_data.get('marking_rubric', []),
                    maximum_marks=theory_data.get('maximum_marks', 20),
                    explanation='',  # Theory questions don't have explanations
                    source_type='ai_generated',
                    source_slide=slide,
                    source_text=text[:1000],
                )
                saved_theory += 1
            except Exception as e:
                logger.error(f"Failed to save theory question: {e}")
        
        logger.info(
            f"=== QUESTION GENERATION COMPLETE  slide={slide_id}  "
            f"MCQ={saved_mcq}/{len(mcq_questions)}  Theory={saved_theory}/{len(theory_questions)} ==="
        )
        
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