"""Import processed Steeplechase / Histology stations into the database.

Reads data/steeplechase/stations.json, produced by scripts/steeplechase/build_stations.py,
and upserts each record into SpotStation.

The import is idempotent and non-destructive by default: re-running it updates existing
rows in place rather than wiping the table, so a human reviewer's approvals and answer
corrections survive a re-import. Pass --reset-approvals to let the pipeline's own
verdict win again, or --purge to clear the bank first.

    python manage.py import_stations
    python manage.py import_stations --dry-run
    python manage.py import_stations --only histology
"""

from __future__ import annotations

import json
import pathlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import AnatomicalRegion, HistologyTopic, SpotStation

DEFAULT_PATH = (
    pathlib.Path(__file__).resolve().parents[4] / "data" / "steeplechase" / "stations.json"
)

VALID_REGIONS = {c for c, _ in AnatomicalRegion.choices}
VALID_TOPICS = {c for c, _ in HistologyTopic.choices}
VALID_KINDS = {c for c, _ in SpotStation.Kind.choices}


class Command(BaseCommand):
    help = "Import processed Steeplechase and Histology stations from stations.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", default=str(DEFAULT_PATH), help="Path to stations.json"
        )
        parser.add_argument(
            "--only",
            choices=["steeplechase", "histology"],
            help="Import only one practice mode",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Delete every existing station before importing",
        )
        parser.add_argument(
            "--reset-approvals",
            action="store_true",
            help="Let the pipeline's approval verdict overwrite human review decisions",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would change, write nothing"
        )

    def handle(self, *args, **options):
        path = pathlib.Path(options["path"])
        if not path.exists():
            raise CommandError(
                f"{path} not found. Run scripts/steeplechase/build_stations.py first."
            )

        records = json.loads(path.read_text(encoding="utf-8"))
        if options["only"]:
            records = [r for r in records if r.get("mode") == options["only"]]

        if not records:
            self.stdout.write(self.style.WARNING("Nothing to import."))
            return

        created = updated = skipped = 0
        approved = 0

        with transaction.atomic():
            if options["purge"] and not options["dry_run"]:
                deleted, _ = SpotStation.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Purged {deleted} existing rows"))

            existing = {
                s.id: s for s in SpotStation.objects.filter(
                    id__in=[r["id"] for r in records]
                )
            }

            for record in records:
                station_id = record.get("id")
                if not station_id or not record.get("prompt"):
                    skipped += 1
                    continue

                kind = record.get("kind")
                if kind not in VALID_KINDS:
                    skipped += 1
                    continue

                region = record.get("region") or "UNKNOWN"
                topic = record.get("histology_topic") or "UNKNOWN"

                fields = {
                    "kind": kind,
                    "region": region if region in VALID_REGIONS else "UNKNOWN",
                    "histology_topic": topic if topic in VALID_TOPICS else "UNKNOWN",
                    "image_url": record.get("image_url", ""),
                    "original_image_url": record.get("original_image_url", ""),
                    "specimen_label": (record.get("specimen_label") or "")[:200],
                    "crop_box": record.get("crop_box") or {},
                    "marker": record.get("marker") or {},
                    "structure": (record.get("structure") or "")[:200],
                    "prompt": record.get("prompt", ""),
                    "accepted_answers": record.get("accepted_answers") or [],
                    "explanation": record.get("explanation") or "",
                    "supporting_question": record.get("supporting_question") or {},
                    "true_false_question": record.get("true_false_question") or {},
                    "transcribed_question": record.get("transcribed_question") or "",
                    "station_number": record.get("station_number"),
                    "source_file": (record.get("source_file") or "")[:200],
                    "source_page": record.get("source_page") or 0,
                    "confidence": record.get("confidence") or 0.0,
                    "needs_review": bool(record.get("needs_review")),
                    "review_reason": record.get("review_reason") or "",
                    "quality_flags": record.get("quality_flags") or [],
                    "is_approved": bool(record.get("is_approved")),
                }

                current = existing.get(station_id)
                if current is not None and not options["reset_approvals"]:
                    # Preserve a human's decision and any hand-corrected answer.
                    fields["is_approved"] = current.is_approved
                    fields["needs_review"] = current.needs_review
                    if current.accepted_answers and current.is_approved:
                        fields["accepted_answers"] = current.accepted_answers

                if fields["is_approved"]:
                    approved += 1

                if options["dry_run"]:
                    created += current is None
                    updated += current is not None
                    continue

                _, was_created = SpotStation.objects.update_or_create(
                    id=station_id, defaults=fields
                )
                created += was_created
                updated += not was_created

            if options["dry_run"]:
                transaction.set_rollback(True)

        verb = "Would import" if options["dry_run"] else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {created} new, {updated} updated, {skipped} skipped "
                f"({approved} approved for practice)"
            )
        )

        if not options["dry_run"]:
            self._summarise()

    def _summarise(self) -> None:
        self.stdout.write("\nStation bank:")
        for kind, label in SpotStation.Kind.choices:
            qs = SpotStation.objects.filter(kind=kind)
            total = qs.count()
            if not total:
                continue
            playable = qs.filter(is_approved=True).count()
            self.stdout.write(f"  {label}: {playable} playable / {total} total")

        pending = SpotStation.objects.filter(needs_review=True).count()
        if pending:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  {pending} station(s) need human review before they can be served. "
                    f"Review them in Django admin under Spot stations."
                )
            )
