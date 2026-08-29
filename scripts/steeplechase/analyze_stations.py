"""Step 2 of the Steeplechase pipeline: understand each station photo.

For every de-duplicated photo produced by extract_images.py this asks a vision model to:

  * decide whether the photo is actually an anatomy station at all,
  * locate the anatomical specimen and give a crop box that EXCLUDES the handwritten
    question paper, the bench, the floor and any hands holding the specimen,
  * transcribe the handwritten question paper,
  * locate the pin / arrow / thread / tag marking the structure under test,
  * name the marked structure and write a short teaching explanation,
  * classify the station into one of the eight anatomical regions,
  * author one supporting MCQ and (where it makes sense) one true/false item.

The prompt is written to refuse rather than invent: anything the model cannot read or
identify confidently comes back null with `needs_review` set, so bad anatomy never
reaches a student. Results are cached per image id, so the script is resumable and
re-running it costs nothing for already-analysed photos.

Output:
    data/steeplechase/analysis/<id>.json

Usage:
    OPENAI_API_KEY=... python scripts/steeplechase/analyze_stations.py [--limit N] [--ids a,b,c]
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import io
import json
import mimetypes
import os
import pathlib
import re
import sys
import threading
import time

import requests
from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "steeplechase" / "raw"
MANIFEST = ROOT / "data" / "steeplechase" / "raw_manifest.json"
OUT_DIR = ROOT / "data" / "steeplechase" / "analysis"

# Vision runs on Groq by default, on the same key and quota as the rest of the platform.
#
# Model choice matters more than it looks. qwen3.6-27b is multimodal but is a *reasoning*
# model: on this task it spends 4,000+ tokens in <think> and is truncated before it ever
# emits the record, and raising the ceiling pushes the request past Groq's 8,000
# tokens-per-minute limit. qwen3.8-27b answers directly in ~600 tokens, so it is the one
# that actually fits the budget. Gemini and OpenAI remain available for anyone with quota.
PROVIDER = os.getenv("EMBY_VISION_PROVIDER", "groq").lower()
_DEFAULT_MODEL = {
    "groq": "qwen/qwen3.8-27b",
    "gemini": "gemini-3.5-flash",
    "openai": "gpt-5.4-mini",
}
MODEL = os.getenv("EMBY_VISION_MODEL", _DEFAULT_MODEL.get(PROVIDER, "qwen/qwen3.8-27b"))

GROQ_BASE = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
# Longest edge sent to a vision model. See _downscaled_jpeg_b64 for why this is small.
VISION_MAX_EDGE = int(os.getenv("EMBY_VISION_MAX_EDGE", "640"))
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

REGIONS = [
    "UPPER_LIMB", "LOWER_LIMB", "THORAX", "ABDOMEN",
    "PELVIS", "PERINEUM", "HEAD_NECK", "NEUROANATOMY", "UNKNOWN",
]

# The source PDFs mix gross-anatomy steeplechase stations with histology spots and the
# occasional radiograph, so the analyser routes each photo to the right practice mode
# rather than forcing everything into Steeplechase.
KINDS = ["GROSS_ANATOMY", "HISTOLOGY", "RADIOGRAPH", "MODEL", "OTHER"]

HISTOLOGY_TOPICS = [
    "EPITHELIUM", "CONNECTIVE_TISSUE", "MUSCLE", "NERVOUS_TISSUE", "BLOOD",
    "CARTILAGE_BONE", "LYMPHOID", "CARDIOVASCULAR", "RESPIRATORY",
    "GASTROINTESTINAL", "LIVER_PANCREAS", "URINARY", "MALE_REPRODUCTIVE",
    "FEMALE_REPRODUCTIVE", "ENDOCRINE", "SKIN", "SPECIAL_SENSES", "UNKNOWN",
]

SYSTEM = """You are a consultant anatomist preparing an OSPE / steeplechase question bank \
for second-year medical students. You are looking at photographs taken in a dissection hall.

A typical photograph contains a cadaveric prosection, an isolated bone, a plastinated or \
preserved organ, a model, or a printed radiograph, resting on a bench, a wooden board or a \
tray. Beside or under it there is usually a sheet of white paper with a handwritten question, \
and often a printed or handwritten station number. The structure being tested is usually \
indicated by a pin, a coloured-headed dressmaker pin, an arrow, a length of thread or string, \
a paper tag, or a painted mark.

Your job is to turn each photograph into one clean, self-contained exam station.

RULES YOU MUST FOLLOW:

1. NEVER invent anatomy. If you cannot confidently identify the specimen or the marked \
structure from what is actually visible, set the relevant field to null, set needs_review \
to true, and explain what is unclear in review_reason. A null answer is correct behaviour; \
a plausible guess is a serious error because students will revise from it.

2. specimen_bbox must tightly enclose ONLY the anatomical specimen. Deliberately EXCLUDE \
the white question paper, handwritten answers, the station number card, the surrounding \
bench, floor tiles, walls, and any hand or fingers holding the specimen, unless excluding \
the hand would also cut off part of the specimen. Coordinates are fractions of the image \
width and height, origin at the top-left, so 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0. \
Leave a small margin (about 2%) around the specimen so it does not look cropped too tight.

3. Transcribe the handwritten question exactly as written into transcribed_question, \
correcting only obvious spelling and OCR-style slips. If there is no legible paper, use null.

4. marker.x and marker.y are the normalised centre of the pin head / arrow tip / thread \
end / tag IN THE ORIGINAL UNCROPPED IMAGE. Set marker.present to false if nothing marks a \
specific structure.

5. main_question should be the question a student is actually asked at this station. Prefer \
the transcribed handwritten question when it is legible and sensible; otherwise write the \
natural question for the marker, e.g. "Identify the structure indicated by the pin."

6. supporting_question must be a genuinely different, higher-order question about the same \
region or structure (relations, blood supply, innervation, function, clinical relevance) \
with exactly four options, exactly one of which is correct. Do not make the correct option \
consistently the same letter.

7. Only include a true/false item when a crisp, unambiguous factual statement is available. \
Otherwise set true_false.enabled to false.

8. quality_flags: note anything that makes the photo a poor exam station (blurred, very dark, \
specimen mostly out of frame, marker ambiguous, paper obscures the specimen, duplicate view).

9. station_kind routes the photo to the right practice mode:
   - GROSS_ANATOMY: a cadaveric prosection, dissected region, or isolated dry bone.
   - HISTOLOGY: a microscope field, a histology slide, or a photograph of a screen or
     printout showing a stained microscopic section. These are common in this collection.
     For these, also fill histology_topic and identify the tissue or organ.
   - RADIOGRAPH: a plain film, CT or MRI image.
   - MODEL: a plastic or resin teaching model rather than real tissue.
   - OTHER: anything else, including photos that are not exam stations.
   For HISTOLOGY stations set region to UNKNOWN unless the tissue clearly belongs to one
   named body region, and set histology_topic to the best matching tissue class.

10. Write every field in English. Never emit words in any other language or script.
"""

RECORD_SHAPE = """{
  "is_station": bool,
  "station_kind": "GROSS_ANATOMY" | "HISTOLOGY" | "RADIOGRAPH" | "MODEL" | "OTHER",
  "histology_topic": one of EPITHELIUM, CONNECTIVE_TISSUE, MUSCLE, NERVOUS_TISSUE, BLOOD,
      CARTILAGE_BONE, LYMPHOID, CARDIOVASCULAR, RESPIRATORY, GASTROINTESTINAL,
      LIVER_PANCREAS, URINARY, MALE_REPRODUCTIVE, FEMALE_REPRODUCTIVE, ENDOCRINE, SKIN,
      SPECIAL_SENSES, UNKNOWN,
  "region": one of UPPER_LIMB, LOWER_LIMB, THORAX, ABDOMEN, PELVIS, PERINEUM, HEAD_NECK,
      NEUROANATOMY, UNKNOWN,
  "specimen_label": string | null,
  "specimen_bbox": {"x0": 0..1, "y0": 0..1, "x1": 0..1, "y1": 0..1},
  "question_paper_present": bool,
  "transcribed_question": string | null,
  "station_number": int | null,
  "marker": {"present": bool, "type": "pin"|"arrow"|"thread"|"tag"|"paint"|"probe"|"none",
             "x": 0..1 | null, "y": 0..1 | null, "description": string},
  "structure": string | null,
  "main_question": string | null,
  "main_answer": string | null,
  "main_explanation": string,
  "supporting_question": {"enabled": bool, "question": string,
                          "options": [4 strings], "correct_index": 0..3, "explanation": string},
  "true_false": {"enabled": bool, "statement": string, "answer": bool, "explanation": string},
  "confidence": 0..1,
  "needs_review": bool,
  "review_reason": string,
  "quality_flags": [string]
}"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_station", "station_kind", "histology_topic",
        "region", "specimen_label", "specimen_bbox",
        "question_paper_present", "transcribed_question", "station_number",
        "marker", "structure", "main_question", "main_answer", "main_explanation",
        "supporting_question", "true_false", "confidence", "needs_review",
        "review_reason", "quality_flags",
    ],
    "properties": {
        "is_station": {
            "type": "boolean",
            "description": "True only if this is a usable anatomy specimen photograph.",
        },
        "station_kind": {"type": "string", "enum": KINDS},
        "histology_topic": {
            "type": "string",
            "enum": HISTOLOGY_TOPICS,
            "description": "Tissue class when station_kind is HISTOLOGY, else UNKNOWN.",
        },
        "region": {"type": "string", "enum": REGIONS},
        "specimen_label": {
            "type": ["string", "null"],
            "description": "Short name of the specimen, e.g. 'articulated cervical vertebra'.",
        },
        "specimen_bbox": {
            "type": "object",
            "additionalProperties": False,
            "required": ["x0", "y0", "x1", "y1"],
            "properties": {
                "x0": {"type": "number"}, "y0": {"type": "number"},
                "x1": {"type": "number"}, "y1": {"type": "number"},
            },
        },
        "question_paper_present": {"type": "boolean"},
        "transcribed_question": {"type": ["string", "null"]},
        "station_number": {"type": ["integer", "null"]},
        "marker": {
            "type": "object",
            "additionalProperties": False,
            "required": ["present", "type", "x", "y", "description"],
            "properties": {
                "present": {"type": "boolean"},
                "type": {
                    "type": "string",
                    "enum": ["pin", "arrow", "thread", "tag", "paint", "probe", "none"],
                },
                "x": {"type": ["number", "null"]},
                "y": {"type": ["number", "null"]},
                "description": {"type": ["string", "null"]},
            },
        },
        "structure": {
            "type": ["string", "null"],
            "description": "The anatomical structure the marker indicates. Null if unsure.",
        },
        "main_question": {"type": ["string", "null"]},
        "main_answer": {"type": ["string", "null"]},
        "main_explanation": {"type": ["string", "null"]},
        "supporting_question": {
            "type": "object",
            "additionalProperties": False,
            "required": ["enabled", "question", "options", "correct_index", "explanation"],
            "properties": {
                "enabled": {"type": "boolean"},
                "question": {"type": ["string", "null"]},
                "options": {"type": "array", "items": {"type": "string"}},
                "correct_index": {"type": ["integer", "null"]},
                "explanation": {"type": ["string", "null"]},
            },
        },
        "true_false": {
            "type": "object",
            "additionalProperties": False,
            "required": ["enabled", "statement", "answer", "explanation"],
            "properties": {
                "enabled": {"type": "boolean"},
                "statement": {"type": ["string", "null"]},
                "answer": {"type": ["boolean", "null"]},
                "explanation": {"type": ["string", "null"]},
            },
        },
        "confidence": {
            "type": "number",
            "description": "0..1 confidence in the anatomical identification.",
        },
        "needs_review": {"type": "boolean"},
        "review_reason": {"type": ["string", "null"]},
        "quality_flags": {"type": "array", "items": {"type": "string"}},
    },
}

_print_lock = threading.Lock()

client = None
GEMINI_KEY = ""
GROQ_KEY = ""

if PROVIDER == "openai":
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=240.0, max_retries=0)
elif PROVIDER == "gemini":
    GEMINI_KEY = os.environ["GEMINI_API_KEY"]
else:
    GROQ_KEY = os.environ.get("LLM_API_KEY") or os.environ["GROQ_API_KEY"]


class RateLimiter:
    """Simple process-wide request-per-minute governor.

    The account this pipeline runs against is capped at 10 requests/minute, so the
    naive thread pool burned through its quota instantly. This spaces every call out
    to a fixed minimum interval regardless of how many workers are running.
    """

    def __init__(self, per_minute: int):
        self._interval = 60.0 / max(1, per_minute)
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_at = max(now, self._next_at) + self._interval


_limiter = RateLimiter(int(os.getenv("EMBY_VISION_RPM", "9")))

_RETRY_HINT = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


def _retry_delay(message: str, attempt: int) -> float:
    """How long to wait before retrying, preferring the provider's own hint."""
    match = _RETRY_HINT.search(message)
    if match:
        try:
            return min(float(match.group(1)) + 2.0, 120.0)
        except ValueError:
            pass
    return min(15.0 * (attempt + 1), 120.0)


def data_url(path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def analyse(rec: dict) -> tuple[str, str]:
    out_path = OUT_DIR / f"{rec['id']}.json"
    if out_path.exists():
        return rec["id"], "cached"

    img = RAW_DIR / rec["file"]
    for attempt in range(MAX_ATTEMPTS):
        _limiter.acquire()
        try:
            payload = _call_model(img)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            transient = any(
                marker in msg
                for marker in (
                    "rate_limit", "rate limit", "429", "timeout", "timed out",
                    "503", "500", "502", "504", "high demand", "overloaded",
                    "unavailable", "connection", "resource_exhausted", "quota",
                )
            )
            if transient and attempt < MAX_ATTEMPTS - 1:
                # Providers tell us exactly how long to wait; obey that when present,
                # since free-tier windows are per-minute and always recover.
                time.sleep(_retry_delay(str(e), attempt))
                continue
            with _print_lock:
                print(f"  FAILED {rec['id']}: {type(e).__name__}: {str(e)[:160]}", flush=True)
            return rec["id"], "error"

        payload["_source"] = {
            "id": rec["id"],
            "file": rec["file"],
            "width": rec["width"],
            "height": rec["height"],
            "source_pdf": rec["source_pdf"],
            "source_page": rec["source_page"],
            "model": MODEL,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return rec["id"], "ok"

    return rec["id"], "error"


MAX_ATTEMPTS = 12


def _gemini_schema(node):
    """Convert the OpenAI JSON Schema to the subset Gemini's responseSchema accepts.

    Gemini has no support for `"type": ["string", "null"]` unions or
    `additionalProperties`; it expresses optionality with a `nullable` flag instead.
    """
    if not isinstance(node, dict):
        return node

    out: dict = {}
    for key, value in node.items():
        if key == "additionalProperties":
            continue
        if key == "type" and isinstance(value, list):
            non_null = [t for t in value if t != "null"]
            out["type"] = non_null[0] if non_null else "string"
            if "null" in value:
                out["nullable"] = True
        elif key == "properties":
            out["properties"] = {k: _gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            out["items"] = _gemini_schema(value)
        else:
            out[key] = value
    return out


GEMINI_SCHEMA = _gemini_schema(SCHEMA)


def _call_gemini(img: pathlib.Path) -> dict:
    """One Gemini vision call returning the parsed station record."""
    mime = mimetypes.guess_type(img.name)[0] or "image/jpeg"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Analyse this anatomy steeplechase station photograph and "
                            "return the structured station record. Remember: null and "
                            "needs_review are the correct output whenever you are unsure."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(img.read_bytes()).decode(),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.2,
        },
    }
    resp = requests.post(
        GEMINI_ENDPOINT.format(model=MODEL),
        params={"key": GEMINI_KEY},
        json=body,
        timeout=240,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"unexpected Gemini response: {str(data)[:300]}") from exc
    return json.loads(text)


def _downscaled_jpeg_b64(img: pathlib.Path, max_edge: int = VISION_MAX_EDGE, quality: int = 78) -> str:
    """Shrink a station photo before sending it.

    Image size drives token cost, and that is the binding constraint: a 1024px photo
    costs roughly 9,400 tokens against Groq's 8,000 tokens-per-minute ceiling, so a
    single request is rejected outright with "Request too large". At 640px the same
    photo costs about 1,800 prompt tokens and the request comfortably fits.

    This is a genuine quality trade: fine handwriting on a question paper is harder to
    read at 640px, which is why the analyser is instructed to return null rather than
    guess, and why low-confidence records are held for review.
    """
    from PIL import Image, ImageOps

    with Image.open(img) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _call_groq(img: pathlib.Path) -> dict:
    """One vision call against an OpenAI-compatible multimodal endpoint.

    qwen3.6-27b on Groq is multimodal and supports strict structured output, so station
    analysis runs on the same provider and key as the rest of the platform.
    """
    b64 = _downscaled_jpeg_b64(img)
    resp = requests.post(
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyse this anatomy steeplechase station photograph and "
                                "reply with ONLY a JSON object using exactly these keys:\n"
                                + RECORD_SHAPE
                                + "\nRemember: null and needs_review:true are the correct "
                                "output whenever you are unsure."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                },
            ],
            # No response_format and no reasoning_format.
            #
            # This is a reasoning model. Strict-schema and json_object validation both
            # reject its <think> preamble with a 400 that discards the whole generation,
            # and reasoning_format "hidden"/"parsed" return an empty content field. Asking
            # for JSON in the prompt and parsing leniently is the only mode that yields a
            # usable answer, so _loads_lenient extracts the outermost JSON object.
            "temperature": 0.2,
            # max_completion_tokens counts toward the tokens-per-minute budget, not just
            # the response. With ~3,100 prompt tokens against an 8,000 TPM ceiling, asking
            # for 6,000 made every request exceed the limit before it was even served.
            "max_completion_tokens": 4000,
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    content = resp.json()["choices"][0]["message"]["content"]
    return normalise_record(_loads_lenient(content))


def _loads_lenient(text: str) -> dict:
    """Parse a model reply that may be fenced or wrapped in prose."""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def normalise_record(raw: dict) -> dict:
    """Coerce a model reply into the record the rest of the pipeline expects.

    Missing or malformed fields become safe defaults that route the station to human
    review rather than into practice, so a sloppy reply can never produce a confident-
    looking station.
    """
    def as_float(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def as_str(value):
        return value.strip() if isinstance(value, str) and value.strip() else None

    bbox = raw.get("specimen_bbox") or {}
    marker = raw.get("marker") or {}
    supporting = raw.get("supporting_question") or {}
    true_false = raw.get("true_false") or {}

    kind = str(raw.get("station_kind") or "OTHER").upper()
    region = str(raw.get("region") or "UNKNOWN").upper()
    topic = str(raw.get("histology_topic") or "UNKNOWN").upper()

    options = [str(o) for o in (supporting.get("options") or []) if str(o).strip()]
    correct = supporting.get("correct_index")
    supporting_ok = (
        bool(supporting.get("enabled"))
        and len(options) == 4
        and isinstance(correct, int)
        and 0 <= correct < 4
    )

    return {
        "is_station": bool(raw.get("is_station")),
        "station_kind": kind if kind in KINDS else "OTHER",
        "histology_topic": topic if topic in HISTOLOGY_TOPICS else "UNKNOWN",
        "region": region if region in REGIONS else "UNKNOWN",
        "specimen_label": as_str(raw.get("specimen_label")),
        "specimen_bbox": {
            "x0": as_float(bbox.get("x0"), 0.0) or 0.0,
            "y0": as_float(bbox.get("y0"), 0.0) or 0.0,
            "x1": as_float(bbox.get("x1"), 1.0) or 1.0,
            "y1": as_float(bbox.get("y1"), 1.0) or 1.0,
        },
        "question_paper_present": bool(raw.get("question_paper_present")),
        "transcribed_question": as_str(raw.get("transcribed_question")),
        "station_number": raw.get("station_number") if isinstance(raw.get("station_number"), int) else None,
        "marker": {
            "present": bool(marker.get("present")),
            "type": str(marker.get("type") or "none"),
            "x": as_float(marker.get("x")),
            "y": as_float(marker.get("y")),
            "description": as_str(marker.get("description")) or "",
        },
        "structure": as_str(raw.get("structure")),
        "main_question": as_str(raw.get("main_question")),
        "main_answer": as_str(raw.get("main_answer")),
        "main_explanation": as_str(raw.get("main_explanation")) or "",
        "supporting_question": (
            {
                "enabled": True,
                "question": as_str(supporting.get("question")) or "",
                "options": options,
                "correct_index": correct,
                "explanation": as_str(supporting.get("explanation")) or "",
            }
            if supporting_ok
            else {"enabled": False}
        ),
        "true_false": (
            {
                "enabled": True,
                "statement": as_str(true_false.get("statement")),
                "answer": bool(true_false.get("answer")),
                "explanation": as_str(true_false.get("explanation")) or "",
            }
            if true_false.get("enabled") and as_str(true_false.get("statement"))
            else {"enabled": False}
        ),
        "confidence": max(0.0, min(1.0, as_float(raw.get("confidence"), 0.0) or 0.0)),
        # A reply that omitted needs_review is itself a reason to review.
        "needs_review": bool(raw.get("needs_review", True)),
        "review_reason": as_str(raw.get("review_reason")) or "",
        "quality_flags": [str(f) for f in (raw.get("quality_flags") or [])],
    }


def _call_model(img: pathlib.Path) -> dict:
    """One vision call. Raises on any provider error so analyse() can retry."""
    if PROVIDER == "groq":
        return _call_groq(img)
    if PROVIDER == "gemini":
        return _call_gemini(img)

    resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Analyse this anatomy steeplechase station photograph and "
                            "return the structured station record. Remember: null and "
                            "needs_review are the correct output whenever you are unsure."
                        ),
                    },
                    {"type": "input_image", "image_url": data_url(img), "detail": "high"},
                ],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "steeplechase_station",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    )
    return json.loads(resp.output_text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", type=str, default="")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
        records = [r for r in records if r["id"] in wanted]
    if args.limit:
        records = records[: args.limit]

    print(f"analysing {len(records)} station photos with {MODEL}", flush=True)
    counts: dict[str, int] = {}
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for _id, status in ex.map(analyse, records):
            counts[status] = counts.get(status, 0) + 1
            done += 1
            if done % 25 == 0:
                with _print_lock:
                    print(f"  {done}/{len(records)} {counts}", flush=True)
    print(f"done: {counts}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
