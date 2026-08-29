"""Step 3 of the Steeplechase pipeline: turn analysis records into servable stations.

For each analysed photo this:

  * crops the image down to the specimen box, which is what removes the handwritten
    question paper, the bench, the floor and the station-number card from the frame,
  * re-expresses the marker coordinates relative to the CROP rather than the original,
    so the frontend can overlay the pin directly on what the student sees,
  * files the result under its practice mode and section,
  * decides whether the station is safe to serve or must be reviewed by a human first.

Nothing is invented here. A station is only auto-approved when the vision pass was
confident, produced an answer, and raised no blocking quality flag; everything else is
written out with needs_review set and is withheld from practice until a human clears it.

Output:
    public/steeplechase/stations/<mode>/<section>/<id>.jpg
    data/steeplechase/stations.json

Usage:
    python scripts/steeplechase/build_stations.py
"""
from __future__ import annotations

import json
import pathlib
import sys

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "steeplechase" / "raw"
ANALYSIS_DIR = ROOT / "data" / "steeplechase" / "analysis"
PUBLIC_DIR = ROOT / "public" / "steeplechase" / "stations"
ORIGINALS_DIR = ROOT / "public" / "steeplechase" / "originals"
STATIONS_JSON = ROOT / "data" / "steeplechase" / "stations.json"

# A station may be served to students only if the model was at least this sure.
APPROVE_CONFIDENCE = 0.6
# Crops smaller than this fraction of the frame are treated as a mis-detection.
MIN_CROP_AREA = 0.03
MAX_EDGE = 1400  # downscale for delivery; station photos are phone-sized originals
# Above this share of bright, colourless pixels a crop probably still shows the
# handwritten question sheet, so the station is sent for review instead of served.
PAPER_FRACTION_LIMIT = 0.22

# Quality problems that make a station unusable regardless of confidence.
BLOCKING_FLAGS = {"blurred", "very dark", "specimen mostly out of frame"}

MODE_BY_KIND = {
    "GROSS_ANATOMY": "steeplechase",
    "RADIOGRAPH": "steeplechase",
    "MODEL": "steeplechase",
    "HISTOLOGY": "histology",
}


def slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-") or "unclassified"


def clamp_box(bbox: dict, width: int, height: int) -> tuple[int, int, int, int] | None:
    """Convert a normalised bbox to safe pixel coordinates, or None if unusable."""
    try:
        x0, y0 = float(bbox["x0"]), float(bbox["y0"])
        x1, y1 = float(bbox["x1"]), float(bbox["y1"])
    except (KeyError, TypeError, ValueError):
        return None

    x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
    y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))

    if (x1 - x0) * (y1 - y0) < MIN_CROP_AREA:
        return None

    px = (int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height))
    if px[2] - px[0] < 40 or px[3] - px[1] < 40:
        return None
    return px


def remap_marker(marker: dict, box: tuple[int, int, int, int], w: int, h: int) -> dict:
    """Express a marker given in original-image space relative to the cropped image."""
    out = {
        "present": bool(marker.get("present")),
        "type": marker.get("type") or "none",
        "description": marker.get("description") or "",
        "x": None,
        "y": None,
    }
    mx, my = marker.get("x"), marker.get("y")
    if not out["present"] or mx is None or my is None:
        return out

    x0, y0, x1, y1 = box
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)
    nx = (float(mx) * w - x0) / cw
    ny = (float(my) * h - y0) / ch

    # A marker that falls outside the crop means the crop and the marker disagree;
    # keep the flag but drop the coordinates rather than draw a pin in the wrong place.
    if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
        out["description"] = (out["description"] + " (marker outside crop)").strip()
        return out

    out["x"] = round(nx, 4)
    out["y"] = round(ny, 4)
    return out


def paper_fraction(image: Image.Image) -> float:
    """Estimate how much of a crop is still white question paper.

    Printer paper is bright and almost colourless. Cadaveric tissue, dry bone and
    stained histology all carry noticeable colour, so a large bright-and-desaturated
    area is a strong hint that the crop failed to exclude the question sheet. This is
    only used to divert a station to human review, never to alter the image.
    """
    small = image.convert("HSV").resize((96, 96), Image.BILINEAR)
    pixels = list(small.getdata())
    if not pixels:
        return 0.0
    papery = sum(1 for _h, s, v in pixels if v > 200 and s < 42)
    return papery / len(pixels)


def build_accepted_answers(record: dict) -> list[str]:
    """Answers accepted for the free-text main question."""
    answers: list[str] = []
    for candidate in (record.get("main_answer"), record.get("structure")):
        if candidate and isinstance(candidate, str):
            text = candidate.strip()
            if text and text.lower() not in {a.lower() for a in answers}:
                answers.append(text)
    return answers


def main() -> int:
    if not ANALYSIS_DIR.exists():
        print("No analysis directory; run analyze_stations.py first.")
        return 1

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)

    stations: list[dict] = []
    stats = {
        "analysed": 0, "skipped_not_station": 0, "built": 0,
        "approved": 0, "needs_review": 0, "no_crop": 0, "missing_image": 0,
    }

    for path in sorted(ANALYSIS_DIR.glob("*.json")):
        stats["analysed"] += 1
        record = json.loads(path.read_text(encoding="utf-8"))
        source = record.get("_source", {})
        station_id = source.get("id") or path.stem

        kind = record.get("station_kind") or "OTHER"
        if not record.get("is_station") or kind not in MODE_BY_KIND:
            stats["skipped_not_station"] += 1
            continue

        img_path = RAW_DIR / source.get("file", "")
        if not img_path.exists():
            stats["missing_image"] += 1
            continue

        with Image.open(img_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            w, h = im.size

            box = clamp_box(record.get("specimen_bbox") or {}, w, h)
            cropped_ok = box is not None
            if not cropped_ok:
                stats["no_crop"] += 1
                box = (0, 0, w, h)

            station_img = im.crop(box)
            station_img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            papery = paper_fraction(station_img)

            mode = MODE_BY_KIND[kind]
            section = (
                record.get("histology_topic", "UNKNOWN")
                if kind == "HISTOLOGY"
                else record.get("region", "UNKNOWN")
            )
            out_dir = PUBLIC_DIR / mode / slugify(section)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{station_id}.jpg"
            station_img.save(out_file, "JPEG", quality=88, optimize=True)

            # Keep a copy of the uncropped frame so a reviewer can check the crop.
            original_copy = ORIGINALS_DIR / f"{station_id}.jpg"
            if not original_copy.exists():
                review_img = im.copy()
                review_img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
                review_img.save(original_copy, "JPEG", quality=80, optimize=True)

        marker = remap_marker(record.get("marker") or {}, box, w, h)
        answers = build_accepted_answers(record)
        flags = [str(f) for f in (record.get("quality_flags") or [])]
        confidence = float(record.get("confidence") or 0.0)

        blocking = any(
            any(bad in flag.lower() for bad in BLOCKING_FLAGS) for flag in flags
        )
        paper_left = papery > PAPER_FRACTION_LIMIT
        if paper_left:
            flags.append(f"possible question paper in frame ({papery:.0%} bright area)")

        approved = bool(
            answers
            and confidence >= APPROVE_CONFIDENCE
            and not record.get("needs_review")
            and not blocking
            and not paper_left
            and cropped_ok
        )

        review_bits = []
        if record.get("review_reason"):
            review_bits.append(str(record["review_reason"]))
        if not cropped_ok:
            review_bits.append("Specimen crop box was unusable; showing the full frame.")
        if not answers:
            review_bits.append("No answer could be determined.")
        if blocking:
            review_bits.append("Blocking quality flag on the photograph.")
        if paper_left:
            review_bits.append("Crop may still include the question paper.")

        supporting = record.get("supporting_question") or {}
        if supporting.get("enabled") and len(supporting.get("options") or []) != 4:
            supporting = {"enabled": False}

        stations.append(
            {
                "id": station_id,
                "kind": kind,
                "mode": mode,
                "region": record.get("region", "UNKNOWN"),
                "histology_topic": record.get("histology_topic", "UNKNOWN"),
                "specimen_label": record.get("specimen_label") or "",
                "image_url": f"/steeplechase/stations/{mode}/{slugify(section)}/{station_id}.jpg",
                "original_image_url": f"/steeplechase/originals/{station_id}.jpg",
                "crop_box": {
                    "x0": round(box[0] / w, 4), "y0": round(box[1] / h, 4),
                    "x1": round(box[2] / w, 4), "y1": round(box[3] / h, 4),
                },
                "marker": marker,
                "structure": record.get("structure") or "",
                "prompt": record.get("main_question")
                or "Identify the structure indicated by the marker.",
                "accepted_answers": answers,
                "explanation": record.get("main_explanation") or "",
                "supporting_question": supporting,
                "true_false_question": record.get("true_false") or {"enabled": False},
                "transcribed_question": record.get("transcribed_question") or "",
                "station_number": record.get("station_number"),
                "source_file": source.get("source_pdf", ""),
                "source_page": source.get("source_page", 0),
                "confidence": confidence,
                "needs_review": not approved,
                "review_reason": " ".join(review_bits),
                "quality_flags": flags,
                "is_approved": approved,
            }
        )
        stats["built"] += 1
        stats["approved" if approved else "needs_review"] += 1

    STATIONS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATIONS_JSON.write_text(
        json.dumps(stations, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("Steeplechase / Histology station build")
    for key, value in stats.items():
        print(f"  {key:22} {value}")

    by_mode: dict[str, dict[str, int]] = {}
    for s in stations:
        bucket = by_mode.setdefault(s["mode"], {})
        section = s["histology_topic"] if s["mode"] == "histology" else s["region"]
        bucket[section] = bucket.get(section, 0) + 1
    print("\n  breakdown:")
    for mode, sections in sorted(by_mode.items()):
        print(f"    {mode}: {sum(sections.values())}")
        for section, count in sorted(sections.items(), key=lambda kv: -kv[1]):
            print(f"      {section:22} {count}")

    print(f"\n-> {STATIONS_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
