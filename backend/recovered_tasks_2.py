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