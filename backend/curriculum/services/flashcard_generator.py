"""
Flashcard Generator Service

Automatically creates flashcards from incorrect quiz answers.
Prevents duplicate cards using the database UniqueConstraint on
(user, source_question) where source = "quiz_mistake".
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def _build_back_text(question) -> str:
    """Build the back (answer) text for a question."""
    if question.question_type == "mcq":
        option_map = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }
        correct_letter = question.correct_option.upper() if question.correct_option else ""
        correct_text = option_map.get(correct_letter, "")
        if correct_text:
            return f"{correct_letter}. {correct_text}"
        return correct_letter
    elif question.question_type == "theory":
        return question.ideal_answer or question.model_answer or "See explanation."
    return ""


def create_flashcard_from_missed_question(user, question, attempt=None):
    """
    Create a flashcard for a missed quiz question, or return the existing one.

    Returns:
        (flashcard, created) -- created is True if a new card was made
    """
    from curriculum.models import Flashcard, FlashcardProgress

    # Build flashcard content
    front = question.question_text
    back = _build_back_text(question)
    explanation = question.explanation or question.ideal_answer or ""

    try:
        flashcard, created = Flashcard.objects.get_or_create(
            user=user,
            source_question=question,
            source="quiz_mistake",
            defaults={
                "front": front,
                "back": back,
                "explanation": explanation,
                "subject": question.subject,
                "block": question.block,
                "sub_block": getattr(question, "sub_block", None),
                "topic": getattr(question, "topic", None),
            },
        )

        if not created:
            logger.info(
                f"Flashcard already exists for user={user.id} question={question.id}"
            )
        else:
            logger.info(
                f"Created flashcard id={flashcard.id} for user={user.id} question={question.id}"
            )

        # Ensure a FlashcardProgress record exists
        progress, progress_created = FlashcardProgress.objects.get_or_create(
            user=user,
            flashcard=flashcard,
            defaults={"due_date": timezone.now()},
        )

        if not progress_created and flashcard.progress_records.filter(
            user=user, due_date__lt=timezone.now()
        ).exists():
            # Card already overdue -- keep existing due_date (user should review it)
            pass

        return flashcard, created

    except Exception as e:
        logger.error(
            f"Error creating flashcard for user={user.id} question={question.id}: {e}"
        )
        return None, False


def generate_flashcards_for_attempt(attempt_id: str) -> dict:
    """
    Generate flashcards for all incorrect responses in a quiz attempt.

    Args:
        attempt_id: The QuizAttempt primary key

    Returns:
        dict with created_count, existing_count, error_count
    """
    from curriculum.models import QuizAttempt, QuizAttemptResponse

    created_count = 0
    existing_count = 0
    error_count = 0

    try:
        attempt = QuizAttempt.objects.select_related("user").get(id=attempt_id)
    except QuizAttempt.DoesNotExist:
        logger.error(f"QuizAttempt {attempt_id} not found for flashcard generation")
        return {"created_count": 0, "existing_count": 0, "error_count": 1}

    user = attempt.user

    # Get all responses for this attempt
    responses = QuizAttemptResponse.objects.select_related(
        "question",
        "question__subject",
        "question__block",
    ).filter(attempt=attempt)

    for response in responses:
        question = response.question
        is_missed = False

        if question.question_type == "mcq":
            # is_correct may be None if user never answered
            is_missed = response.is_correct is False

        elif question.question_type == "theory":
            if response.ai_score is not None and question.maximum_marks:
                score_pct = (response.ai_score / question.maximum_marks) * 100
                is_missed = score_pct < 60.0
            else:
                # Unanswered theory or not yet graded -- do not auto-create card
                is_missed = False

        if not is_missed:
            continue

        flashcard, created = create_flashcard_from_missed_question(
            user=user,
            question=question,
            attempt=attempt,
        )

        if flashcard is None:
            error_count += 1
        elif created:
            created_count += 1
        else:
            existing_count += 1

    logger.info(
        f"Flashcard generation for attempt {attempt_id}: "
        f"created={created_count}, existing={existing_count}, errors={error_count}"
    )

    return {
        "created_count": created_count,
        "existing_count": existing_count,
        "error_count": error_count,
    }
