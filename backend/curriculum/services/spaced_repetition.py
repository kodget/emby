"""
Spaced Repetition Service - SM-2 variant algorithm.

Rating -> behaviour:
  again -> due in 10 minutes, interval resets to 0
  hard  -> due in 1 day, interval stays or halves, ease decreases
  good  -> SM-2 progression, ease stays
  easy  -> SM-2 with bonus, ease increases
"""
from datetime import timedelta
from django.utils import timezone


def calculate_next_review(
    rating: str,
    current_interval: int,
    current_ease_factor: float,
    current_repetitions: int,
) -> dict:
    """
    Calculate the next spaced repetition state after a review.

    Args:
        rating: One of 'again', 'hard', 'good', 'easy'
        current_interval: Current interval in days
        current_ease_factor: Current ease factor (SM-2, starts at 2.5)
        current_repetitions: Number of consecutive successful reviews

    Returns:
        dict with keys:
            next_interval (int days)
            next_ease_factor (float)
            next_repetitions (int)
            due_date (datetime)
            interval_minutes (int, for sub-day intervals)
    """
    now = timezone.now()
    ease = current_ease_factor
    interval = current_interval
    repetitions = current_repetitions

    if rating == "again":
        # Failed -- reset to beginning
        next_interval = 0
        next_ease = max(1.3, ease - 0.2)
        next_repetitions = 0
        due_date = now + timedelta(minutes=10)
        interval_minutes = 10

    elif rating == "hard":
        # Partial recall -- small forward step, ease penalty
        next_ease = max(1.3, ease - 0.15)
        if repetitions == 0:
            next_interval = 1
        else:
            next_interval = max(1, int(interval * 1.2))
        next_repetitions = max(0, repetitions)
        due_date = now + timedelta(days=next_interval)
        interval_minutes = next_interval * 24 * 60

    elif rating == "good":
        # Standard SM-2
        if repetitions == 0:
            next_interval = 1
        elif repetitions == 1:
            next_interval = 3
        else:
            next_interval = max(1, round(interval * ease))
        next_ease = ease
        next_repetitions = repetitions + 1
        due_date = now + timedelta(days=next_interval)
        interval_minutes = next_interval * 24 * 60

    elif rating == "easy":
        # Easy -- SM-2 with ease bonus
        if repetitions == 0:
            next_interval = 4
        elif repetitions == 1:
            next_interval = 7
        else:
            next_interval = max(1, round(interval * ease * 1.3))
        next_ease = min(4.0, ease + 0.15)
        next_repetitions = repetitions + 1
        due_date = now + timedelta(days=next_interval)
        interval_minutes = next_interval * 24 * 60

    else:
        raise ValueError(f"Invalid rating: '{rating}'. Must be one of: again, hard, good, easy")

    return {
        "next_interval": next_interval,
        "next_ease_factor": round(next_ease, 4),
        "next_repetitions": next_repetitions,
        "due_date": due_date,
        "interval_minutes": interval_minutes,
    }
