"""
Management command: fix_stuck_slides

Finds every Slide whose generation_status is 'in_progress' or 'failed'
(meaning the background task crashed before it could mark itself done),
resets them to 'completed' if they already have questions, or re-queues
question bank generation for those that don't.

Run on production after deploying the generate_question_bank_task fix:

    python manage.py fix_stuck_slides
    python manage.py fix_stuck_slides --dry-run     # preview only
    python manage.py fix_stuck_slides --force       # regenerate even completed slides
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q


class Command(BaseCommand):
    help = "Reset stuck slides and re-queue question bank generation where needed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be done without making changes.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-queue generation even for slides that already have questions.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process all slides (not just stuck ones).",
        )

    def handle(self, *args, **options):
        from curriculum.models import Slide, QuizQuestion
        from curriculum.tasks import generate_question_bank_task
        from learning.models import QuestionGenerationJob

        dry_run = options["dry_run"]
        force = options["force"]
        process_all = options["all"]

        if process_all:
            slides = Slide.objects.all()
        else:
            slides = Slide.objects.filter(
                generation_status__in=["in_progress", "failed", "pending"]
            )

        total = slides.count()
        self.stdout.write(f"Found {total} slide(s) to inspect.")

        reset_count = 0
        queued_count = 0
        skipped_count = 0

        for slide in slides.iterator():
            mcq_count = QuizQuestion.objects.filter(
                source_slide=slide, question_type="mcq"
            ).count()

            if mcq_count > 0 and not force:
                # Has questions — just fix the stuck status
                if slide.generation_status != "completed":
                    self.stdout.write(
                        f"  [{slide.id}] Has {mcq_count} MCQs but status={slide.generation_status} "
                        f"→ resetting to 'completed'"
                    )
                    if not dry_run:
                        slide.generation_status = "completed"
                        slide.save(update_fields=["generation_status"])
                        # Also mark the job completed
                        QuestionGenerationJob.objects.filter(slide=slide).update(
                            status=QuestionGenerationJob.Status.COMPLETED
                        )
                    reset_count += 1
                else:
                    skipped_count += 1
            else:
                # No questions (or force) — reset job and re-queue generation
                self.stdout.write(
                    f"  [{slide.id}] status={slide.generation_status}, mcqs={mcq_count} "
                    f"-> {'(dry-run) would queue' if dry_run else 'queuing'} generation"
                )
                if not dry_run:
                    # Reset job so claim_job() will pick it up
                    QuestionGenerationJob.objects.filter(slide=slide).update(
                        status=QuestionGenerationJob.Status.PENDING,
                        error="",
                    )
                    # Reset slide status to pending so frontend shows a spinner
                    slide.generation_status = "in_progress"
                    slide.save(update_fields=["generation_status"])
                    # Queue the Celery task
                    try:
                        generate_question_bank_task.delay(str(slide.id), force=force)
                        queued_count += 1
                    except Exception as exc:
                        self.stderr.write(
                            f"  ERROR queuing task for {slide.id}: {exc}"
                        )
                else:
                    queued_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone{'(dry-run)' if dry_run else ''}. "
                f"Reset: {reset_count}, Queued: {queued_count}, Skipped: {skipped_count}"
            )
        )
