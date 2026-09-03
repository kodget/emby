"""
Bulk question generation for uploaded slides.

When a slide finishes processing it should end up with 50 MCQs and 10 theory questions
in the bank, generated once, in the background. Students practising later read from that
bank; the AI is not called again.

Three things this handles that the previous 5-question task did not:

  * **Batching.** Asking a model for 50 MCQs in one call produces repetitive, shallow
    questions and risks truncation. Generation runs in small batches and accumulates.
  * **Not duplicating.** A QuestionGenerationJob row is claimed with a locked status
    transition, so a retry, a duplicate signal or a second worker cannot generate the
    same set twice. Work already saved is counted and only the shortfall is generated.
  * **Text that actually exists.** Slide content is written in two different shapes
    depending on which pipeline processed it; both are handled.
"""

from __future__ import annotations

import logging
import uuid

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Questions per model call. Small enough to stay coherent and well within output limits.
MCQ_BATCH = 10
THEORY_BATCH = 5
MIN_TEXT_CHARS = 200


def slide_text(slide) -> str:
    """Best available text for a slide, whichever pipeline produced its content.

    `SlideContent.content_data` is written as `{"text": ...}` by the Celery pipeline and
    as `{"pages": [{"text": ...}]}` by the on-demand renderer, so neither shape can be
    assumed. Falls back to rendered page text when no combined blob exists.
    For scanned / image-only PDFs, uses vision LLM to extract text from page images.
    """
    from curriculum.models import SlideContent, SlidePage

    content = SlideContent.objects.filter(slide=slide).first()
    if content and isinstance(content.content_data, dict):
        data = content.content_data

        text = (data.get("text") or "").strip()
        # Filter out pages that are purely PAGE BREAK markers
        clean_text = "\n".join(
            line for line in text.splitlines()
            if line.strip() and line.strip() != "---PAGE BREAK---"
        ).strip()
        if len(clean_text) >= MIN_TEXT_CHARS:
            return clean_text

        pages = data.get("pages") or []
        joined = "\n\n".join(
            (p.get("text") or p.get("content") or "").strip()
            for p in pages
            if isinstance(p, dict)
        ).strip()
        if len(joined) >= MIN_TEXT_CHARS:
            return joined

        # For image-only slides: try vision extraction from stored page image URLs
        image_urls = [
            p.get("image_url") for p in pages
            if isinstance(p, dict) and p.get("image_url")
        ]
        if image_urls:
            extracted = _extract_text_via_vision(image_urls[:3], slide)  # limit to first 3 pages
            if extracted and len(extracted) >= MIN_TEXT_CHARS:
                # Persist so future calls skip vision
                try:
                    data["text"] = extracted
                    content.content_data = data
                    content.save(update_fields=["content_data", "updated_at"])
                    logger.info("Persisted vision-extracted text (%d chars) for slide %s", len(extracted), slide.id)
                except Exception:
                    pass
                return extracted

    # Last resort: text extracted per rendered page.
    page_text = "\n\n".join(
        SlidePage.objects.filter(deck__id=getattr(slide, "id", None))
        .exclude(extracted_text="")
        .values_list("extracted_text", flat=True)
    ).strip()
    return page_text


def _extract_text_via_vision(image_urls: list, slide) -> str:
    """Download slide page images and extract text using the vision LLM.

    Used as a fallback for scanned PDF slides that have no embedded text.
    Returns empty string if vision is unavailable or extraction fails.
    """
    import base64
    import urllib.request

    try:
        from curriculum.llm import chat_with_image, supports_vision
        if not supports_vision():
            logger.info("Vision LLM not configured; cannot extract text for slide %s", slide.id)
            return ""
    except Exception as exc:
        logger.warning("Could not import vision LLM: %s", exc)
        return ""

    page_texts = []
    for url in image_urls:
        try:
            if not url.startswith("http"):
                # Should never happen with Cloudinary-stored images; skip rather than
                # making a useless http://localhost request in production.
                logger.warning("Skipping non-absolute image URL for vision OCR: %s", url)
                continue

            with urllib.request.urlopen(url, timeout=10) as resp:
                image_b64 = base64.b64encode(resp.read()).decode()

            prompt = (
                "You are a medical exam content extractor. "
                "Extract ALL readable text from this slide image exactly as written. "
                "Include headings, body text, labels, and captions. "
                "Do NOT summarise — output the raw text only."
            )
            extracted = chat_with_image(prompt=prompt, image_b64=image_b64, max_tokens=2048)
            if extracted and extracted.strip():
                page_texts.append(extracted.strip())
        except Exception as exc:
            logger.warning("Vision extraction failed for image %s: %s", url, exc)
            continue


    return "\n\n".join(page_texts)


@transaction.atomic
def claim_job(slide, *, force: bool = False):
    """Take ownership of a slide's generation job, or return None if not runnable.

    The status transition happens under a row lock, so exactly one caller can move a
    job into RUNNING. Everyone else gets None and exits quietly.
    """
    from .models import QuestionGenerationJob

    job, _ = QuestionGenerationJob.objects.get_or_create(slide=slide)
    job = QuestionGenerationJob.objects.select_for_update().get(pk=job.pk)

    if job.status == QuestionGenerationJob.Status.RUNNING and not force:
        logger.info("Generation already running for slide %s", slide.id)
        return None
    if job.status == QuestionGenerationJob.Status.COMPLETED and not force:
        return None
    if job.attempts >= QuestionGenerationJob.MAX_ATTEMPTS and not force:
        logger.warning("Slide %s exhausted generation attempts", slide.id)
        return None

    job.status = QuestionGenerationJob.Status.RUNNING
    job.attempts += 1
    job.started_at = timezone.now()
    job.error = ""
    job.save(update_fields=["status", "attempts", "started_at", "error", "updated_at"])
    return job


def existing_counts_by_difficulty(slide, question_type: str) -> dict[str, int]:
    """How many questions of each difficulty this slide already has."""
    from curriculum.models import QuizQuestion
    from django.db.models import Count

    qs = QuizQuestion.objects.filter(source_slide=slide, question_type=question_type)
    counts = qs.values('difficulty').annotate(count=Count('id'))
    return {c['difficulty']: c['count'] for c in counts}


def _save_mcqs(slide, rows: list[dict], text: str) -> int:
    from curriculum.models import QuizQuestion

    saved = 0
    for row in rows:
        try:
            if not row.get("question_text") or not row.get("correct_option"):
                continue
            QuizQuestion.objects.create(
                id=f"q_{uuid.uuid4().hex[:12]}",
                question_type="mcq",
                difficulty=row.get("difficulty", "medium"),
                subject=slide.subject,
                block=slide.block,
                sub_block=slide.sub_block,
                question_text=row["question_text"],
                option_a=row.get("option_a", ""),
                option_b=row.get("option_b", ""),
                option_c=row.get("option_c", ""),
                option_d=row.get("option_d", ""),
                correct_option=str(row["correct_option"]).strip().upper()[:1],
                explanation=row.get("explanation", ""),
                maximum_marks=row.get("maximum_marks", 1),
                source_type="ai_generated",
                source_slide=slide,
                source_text=text[:1000],
            )
            saved += 1
        except Exception:  # noqa: BLE001 - one bad row must not lose the batch
            logger.exception("Could not save a generated MCQ for slide %s", slide.id)
    return saved


def _save_theory(slide, rows: list[dict], text: str) -> int:
    from curriculum.models import QuizQuestion

    saved = 0
    for row in rows:
        try:
            if not row.get("question_text"):
                continue
            QuizQuestion.objects.create(
                id=f"q_{uuid.uuid4().hex[:12]}",
                question_type="theory",
                difficulty=row.get("difficulty", "medium"),
                subject=slide.subject,
                block=slide.block,
                sub_block=slide.sub_block,
                question_text=row["question_text"],
                ideal_answer=row.get("ideal_answer", ""),
                model_answer=row.get("ideal_answer", ""),
                marking_rubric=row.get("marking_rubric", []),
                maximum_marks=row.get("maximum_marks", 20),
                explanation="",
                source_type="ai_generated",
                source_slide=slide,
                source_text=text[:1000],
            )
            saved += 1
        except Exception:  # noqa: BLE001
            logger.exception("Could not save a generated theory question for slide %s", slide.id)
    return saved


def generate_for_slide(slide, *, force: bool = False) -> dict:
    """Fill a slide's question bank to target, in batches. Safe to call repeatedly."""
    from curriculum.services.ai_question_generator import AIQuestionGenerator
    from .models import QuestionGenerationJob

    job = claim_job(slide, force=force)
    if job is None:
        return {"slide_id": slide.id, "skipped": True, "reason": "not runnable"}

    text = slide_text(slide)
    if len(text) < MIN_TEXT_CHARS:
        job.status = QuestionGenerationJob.Status.FAILED
        job.error = f"Only {len(text)} characters of slide text; need {MIN_TEXT_CHARS}."
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
        return {"slide_id": slide.id, "success": False, "error": job.error}

    mcq_counts = existing_counts_by_difficulty(slide, "mcq")
    theory_counts = existing_counts_by_difficulty(slide, "theory")
    topic = getattr(slide, "topic", None)

    # MCQs target: 20 easy, 20 medium, 10 hard (total 50)
    mcq_targets = {"easy": 20, "medium": 20, "hard": 10}
    mcq_have = sum(mcq_counts.values())

    for difficulty, target in mcq_targets.items():
        have_diff = mcq_counts.get(difficulty, 0)
        while have_diff < target:
            want = min(MCQ_BATCH, target - have_diff)
            try:
                rows = AIQuestionGenerator.generate_mcqs_from_text(
                    text=text, slide=slide, topic=topic, count=want, difficulty=difficulty
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("MCQ batch failed for slide %s (%s): %s", slide.id, difficulty, exc)
                job.error = str(exc)[:2000]
                break
            
            made = _save_mcqs(slide, rows or [], text)
            if made == 0:
                logger.warning("MCQ batch returned nothing for slide %s (%s); stopping", slide.id, difficulty)
                break
            
            have_diff += made
            mcq_counts[difficulty] = have_diff
            mcq_have += made
            job.mcq_generated = mcq_have
            job.save(update_fields=["mcq_generated", "updated_at"])

    # Theory target: 4 hard, 4 medium, 2 easy (total 10)
    theory_targets = {"easy": 2, "medium": 4, "hard": 4}
    theory_have = sum(theory_counts.values())

    for difficulty, target in theory_targets.items():
        have_diff = theory_counts.get(difficulty, 0)
        while have_diff < target:
            want = min(THEORY_BATCH, target - have_diff)
            try:
                rows = AIQuestionGenerator.generate_theory_from_text(
                    text=text, slide=slide, topic=topic, count=want, difficulty=difficulty
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Theory batch failed for slide %s (%s): %s", slide.id, difficulty, exc)
                job.error = str(exc)[:2000]
                break

            made = _save_theory(slide, rows or [], text)
            if made == 0:
                logger.warning("Theory batch returned nothing for slide %s (%s); stopping", slide.id, difficulty)
                break
            
            have_diff += made
            theory_counts[difficulty] = have_diff
            theory_have += made
            job.theory_generated = theory_have
            job.save(update_fields=["theory_generated", "updated_at"])

    job.mcq_generated = mcq_have
    job.theory_generated = theory_have
    job.finished_at = timezone.now()
    
    # Check if we hit targets based on quotas
    mcq_done = all(mcq_counts.get(d, 0) >= t for d, t in mcq_targets.items())
    theory_done = all(theory_counts.get(d, 0) >= t for d, t in theory_targets.items())
    job.status = (
        QuestionGenerationJob.Status.COMPLETED
        if (mcq_done and theory_done)
        else QuestionGenerationJob.Status.PARTIAL
        if (mcq_have or theory_have)
        else QuestionGenerationJob.Status.FAILED
    )
    job.save()

    logger.info(
        "Generation for slide %s finished: %s MCQ, %s theory (%s)",
        slide.id, mcq_have, theory_have, job.status,
    )
    return {
        "slide_id": slide.id,
        "success": job.status != QuestionGenerationJob.Status.FAILED,
        "status": job.status,
        "mcq_generated": mcq_have,
        "theory_generated": theory_have,
        "progress_percent": job.progress_percent,
    }
