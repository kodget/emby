"""Step 1 of the Steeplechase pipeline: pull every station photo out of the source PDFs.

The previous implementation (curriculum/management/commands/extract_steeplechase.py)
only kept an image when a nearby text block happened to match one of two regexes, which
silently dropped roughly two thirds of the source material. This step is deliberately
dumb and lossless: extract every embedded image, de-duplicate by content hash (several
of the source PDFs are byte-identical re-uploads of each other), drop obvious junk
(tiny logos, thin slivers), and record provenance for every survivor.

Output:
    data/steeplechase/raw/<sha12>.<ext>
    data/steeplechase/raw_manifest.json

Usage:
    python scripts/steeplechase/extract_images.py
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys

import fitz  # PyMuPDF
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "steeple"
OUT_DIR = ROOT / "data" / "steeplechase" / "raw"
MANIFEST = ROOT / "data" / "steeplechase" / "raw_manifest.json"

# A station photo is a phone camera shot: big, and roughly landscape or portrait.
# Anything much smaller than this is a logo, a scan artefact or a page decoration.
MIN_PIXELS = 220_000          # ~470x470
MIN_EDGE = 300
MAX_ASPECT = 3.2              # reject thin slivers / banner strips


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    stats = {"scanned": 0, "too_small": 0, "bad_aspect": 0, "duplicate": 0, "broken": 0}

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            for img_index, img in enumerate(doc[page_index].get_images(full=True)):
                stats["scanned"] += 1
                xref = img[0]
                try:
                    base = doc.extract_image(xref)
                    raw = base["image"]
                    ext = base["ext"]
                    im = Image.open(io.BytesIO(raw))
                    w, h = im.size
                except Exception:
                    stats["broken"] += 1
                    continue

                if w * h < MIN_PIXELS or min(w, h) < MIN_EDGE:
                    stats["too_small"] += 1
                    continue
                if max(w, h) / max(1, min(w, h)) > MAX_ASPECT:
                    stats["bad_aspect"] += 1
                    continue

                digest = hashlib.sha256(raw).hexdigest()[:12]
                if digest in seen:
                    stats["duplicate"] += 1
                    seen[digest]["also_seen_in"].append(
                        f"{pdf_path.name}#p{page_index + 1}"
                    )
                    continue

                out_name = f"{digest}.{ext}"
                (OUT_DIR / out_name).write_bytes(raw)
                seen[digest] = {
                    "id": digest,
                    "file": out_name,
                    "width": w,
                    "height": h,
                    "source_pdf": pdf_path.name,
                    "source_page": page_index + 1,
                    "source_index": img_index,
                    "also_seen_in": [],
                }
        doc.close()

    manifest = sorted(seen.values(), key=lambda r: (r["source_pdf"], r["source_page"]))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"kept {len(manifest)} unique station photos")
    for k, v in stats.items():
        print(f"  {k:12} {v}")
    print(f"-> {OUT_DIR}")
    print(f"-> {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
