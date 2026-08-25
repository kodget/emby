"""
Slide Conversion Pipeline

FLOW:
  PDF            → PyMuPDF renders each page as JPG
  PPTX/PPT       → LibreOffice → PDF → PyMuPDF renders each page as JPG
  DOCX/DOC       → LibreOffice → PDF → PyMuPDF renders each page as JPG

Output: list of local JPG file paths (one per page), kept in temp_dir.
Caller (tasks.py) uploads them to Cloudinary then deletes temp_dir.
"""

import io
import os
import re
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _libreoffice_path() -> str:
    """Return the soffice executable path, checking common locations."""
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    try:
        cmd = ["where", "soffice"] if os.name == "nt" else ["which", "soffice"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    for p in candidates:
        if os.path.exists(p):
            return p
    return "soffice"


def _convert_to_pdf_via_libreoffice(input_path: str, output_dir: str) -> str:
    """
    Use LibreOffice headless to convert input_path → PDF in output_dir.
    Returns the PDF path on success, raises RuntimeError on failure.
    """
    os.makedirs(output_dir, exist_ok=True)
    soffice = _libreoffice_path()
    logger.info(f"LibreOffice convert → PDF: {input_path}")
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", input_path, "--outdir", output_dir],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice failed: {result.stderr.strip()}")
    pdf_path = os.path.join(output_dir, Path(input_path).stem + ".pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF not produced at expected path: {pdf_path}")
    logger.info(f"✓ LibreOffice produced: {pdf_path}")
    return pdf_path


def _pdf_to_jpg_pages(pdf_path: str, output_dir: str, dpi: int = 150) -> List[str]:
    """
    Render every page of a PDF as a JPEG using PyMuPDF.
    Returns a list of absolute paths to the produced JPG files.
    """
    import fitz  # PyMuPDF

    os.makedirs(output_dir, exist_ok=True)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    doc = fitz.open(pdf_path)
    logger.info(f"PDF has {len(doc)} pages — rendering at {dpi} DPI")

    jpg_paths: List[str] = []
    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Save directly as JPEG (PyMuPDF supports jpg natively)
        jpg_filename = f"page_{i + 1:04d}.jpg"
        jpg_path = os.path.join(output_dir, jpg_filename)
        pix.save(jpg_path)  # extension determines format
        jpg_paths.append(jpg_path)
        logger.info(f"  ✓ page {i + 1}: {jpg_path}")

    doc.close()
    logger.info(f"✓ Rendered {len(jpg_paths)} pages")
    return jpg_paths


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract plain text from a PDF for RAG / search."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        parts = []
        for i in range(len(doc)):
            parts.append(doc[i].get_text())
            parts.append("\n---PAGE BREAK---\n")
        doc.close()
        text = "".join(parts)
        logger.info(f"Extracted {len(text)} chars from PDF")
        return text
    except Exception as e:
        logger.warning(f"Text extraction failed (non-fatal): {e}")
        return ""


def _download_from_cloudinary(cloudinary_url: str, timeout: int = 60) -> bytes:
    """
    Download file bytes from Cloudinary.
    
    Strategy:
    1. Try plain GET (works for truly public assets)
    2. On 401, extract resource_type + public_id from the URL, 
       generate a proper signed download URL using the correct resource_type,
       and retry.
    3. If still failing, use cloudinary.api.resource() to get the secure_url 
       then sign that.
    """
    import requests
    import cloudinary.utils
    import cloudinary.api

    def _try_get(url: str) -> bytes | None:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.content
        return None

    # ── Attempt 1: plain URL ─────────────────────────────────────────────────
    data = _try_get(cloudinary_url)
    if data:
        return data

    logger.warning(f"Plain download failed — trying signed URL…")

    # ── Parse URL components ─────────────────────────────────────────────────
    # URL shape: https://res.cloudinary.com/<cloud>/<rtype>/upload/v<ver>/<public_id_with_ext>
    if "cloudinary.com" not in cloudinary_url:
        raise IOError(f"Cannot download from URL: {cloudinary_url}")

    m = re.search(
        r"cloudinary\.com/[^/]+/(image|raw|video|auto)/upload/(?:v\d+/)?(.+)",
        cloudinary_url,
    )
    if not m:
        raise IOError(f"Cannot parse Cloudinary URL: {cloudinary_url}")

    detected_rtype = m.group(1)  # what the URL says (may be wrong for PDFs)
    public_id_with_ext = m.group(2)

    # ── Attempt 2: sign with detected resource_type, keep extension ─────────
    # For PDFs stored under image/ we still need to include the extension
    # in the signed URL so Cloudinary knows what to serve.
    for rtype in [detected_rtype, "raw", "image", "auto"]:
        try:
            signed_url, _ = cloudinary.utils.cloudinary_url(
                public_id_with_ext,      # include extension
                resource_type=rtype,
                type="upload",
                sign_url=True,
                secure=True,
            )
            logger.info(f"Trying signed URL (resource_type={rtype}): {signed_url[:100]}…")
            data = _try_get(signed_url)
            if data:
                logger.info(f"✓ Signed URL worked with resource_type={rtype}")
                return data
        except Exception as exc:
            logger.debug(f"  resource_type={rtype} failed: {exc}")

    raise IOError(
        f"Cannot download from Cloudinary after multiple attempts. "
        f"URL: {cloudinary_url}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class SlideConversionPipeline:
    """
    Convert an uploaded slide file into per-page JPG images.

    process_slide() returns a dict:
      {
        'success': bool,
        'slide_id': str,
        'image_paths': ['/tmp/.../page_0001.jpg', ...],   # local paths
        'text_content': str,
        'page_count': int,
        'temp_dir': str,   # caller MUST delete after uploading images
        'error': str | None,
      }
    """

    @staticmethod
    def process_slide(
        cloudinary_url: str,
        slide_id: str,
        original_file_type: str,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "slide_id": slide_id,
            "file_type": original_file_type,
            "image_paths": [],
            "text_content": "",
            "page_count": 0,
            "temp_dir": None,
            "error": None,
        }

        temp_dir = tempfile.mkdtemp(prefix=f"slide_{slide_id}_")
        result["temp_dir"] = temp_dir
        logger.info(f"=== PIPELINE START  slide={slide_id}  type={original_file_type} ===")
        logger.info(f"Temp dir: {temp_dir}")

        try:
            # ── 0. Download ──────────────────────────────────────────────────
            logger.info(f"Downloading: {cloudinary_url}")
            file_bytes = _download_from_cloudinary(cloudinary_url)
            logger.info(f"Downloaded {len(file_bytes):,} bytes")

            ft = original_file_type.lower().lstrip(".")
            ext = f".{ft}"
            original_path = os.path.join(temp_dir, f"original{ext}")
            with open(original_path, "wb") as fh:
                fh.write(file_bytes)

            # ── 1. Get a PDF (or use the file directly if already PDF) ───────
            if ft == "pdf":
                logger.info("File is already PDF — skipping LibreOffice")
                pdf_path = original_path
            else:
                logger.info(f"Converting {ft.upper()} → PDF via LibreOffice…")
                pdf_dir = os.path.join(temp_dir, "pdf")
                pdf_path = _convert_to_pdf_via_libreoffice(original_path, pdf_dir)

            # ── 2. Extract text (for RAG) ────────────────────────────────────
            text_content = _extract_text_from_pdf(pdf_path)
            result["text_content"] = text_content

            # ── 3. Render each PDF page → JPG ────────────────────────────────
            logger.info("Rendering PDF pages → JPG…")
            jpg_dir = os.path.join(temp_dir, "pages")
            jpg_paths = _pdf_to_jpg_pages(pdf_path, jpg_dir, dpi=150)

            if not jpg_paths:
                raise RuntimeError("No pages were rendered from the PDF")

            result["image_paths"] = jpg_paths
            result["page_count"] = len(jpg_paths)
            result["success"] = True
            logger.info(f"=== PIPELINE COMPLETE: {len(jpg_paths)} pages ===")
            return result

        except Exception as exc:
            logger.error(f"Pipeline error: {exc}", exc_info=True)
            result["error"] = str(exc)
            # Clean up on failure — temp_dir is useless without images
            shutil.rmtree(temp_dir, ignore_errors=True)
            result["temp_dir"] = None
            return result
