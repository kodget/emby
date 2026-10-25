"""
Slide Conversion Pipeline

FLOW:
  PDF            → PyMuPDF renders each page as JPG
  PPTX/PPT       → LibreOffice → PDF → PyMuPDF renders each page as JPG
  DOCX           → LibreOffice → PDF → PyMuPDF renders each page as JPG

Output: list of local JPG file paths (one per page), kept in temp_dir.
Caller (tasks.py) uploads them to Cloudinary then deletes temp_dir.
"""

import os
import re
import tempfile
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
        try:
            resp = requests.get(url, timeout=timeout)
        except requests.RequestException:
            raise IOError('File storage is temporarily unavailable.') from None
        if resp.status_code == 200:
            return resp.content
        return None

    # ── Attempt 1: plain URL ─────────────────────────────────────────────────
    data = _try_get(cloudinary_url)
    if data:
        return data

    from urllib.parse import urlsplit
    parsed = urlsplit(cloudinary_url)
    if parsed.path.endswith('/download') or '/authenticated/' in parsed.path:
        raise IOError('Private file download failed; obtain a fresh delivery link and retry.')

    logger.warning(f"Plain download failed — trying signed URL…")

    # ── Parse URL components ─────────────────────────────────────────────────
    # URL shape: https://res.cloudinary.com/<cloud>/<rtype>/upload/v<ver>/<public_id_with_ext>
    if "cloudinary.com" not in cloudinary_url:
        raise IOError('Cannot download from the configured storage URL.')

    m = re.search(
        r"cloudinary\.com/[^/]+/(image|raw|video|auto)/upload/(?:v\d+/)?(.+)",
        cloudinary_url,
    )
    if not m:
        raise IOError('Cannot parse the legacy storage URL.')

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
            logger.info('Trying legacy signed download (resource_type=%s)', rtype)
            data = _try_get(signed_url)
            if data:
                logger.info(f"✓ Signed URL worked with resource_type={rtype}")
                return data
        except Exception as exc:
            logger.debug('Download failed (resource_type=%s, %s)', rtype, type(exc).__name__)

    raise IOError(
        'Cannot download from storage after multiple attempts.'
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
        status_obj=None,
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

        temp_dir = tempfile.mkdtemp(prefix='emby-render-')
        result["temp_dir"] = temp_dir
        logger.info(f"=== PIPELINE START  slide={slide_id}  type={original_file_type} ===")
        logger.info(f"Temp dir: {temp_dir}")

        try:
            # ── 0. Download ──────────────────────────────────────────────────
            if status_obj:
                status_obj.status = 'downloading'
                status_obj.save(update_fields=['status'])
            logger.info('Downloading source file for slide %s', slide_id)
            from .document_extraction import source_bytes, content_text
            file_bytes = source_bytes(cloudinary_url)
            logger.info(f"Downloaded {len(file_bytes):,} bytes")

            ft = original_file_type.lower().lstrip(".")
            ext = f".{ft}"
            original_path = os.path.join(temp_dir, f"original{ext}")
            with open(original_path, "wb") as fh:
                fh.write(file_bytes)

            from .document_rendering import render_document
            if status_obj:
                status_obj.status = 'converting_to_jpg'
                status_obj.save(update_fields=['status'])
            # Publish the reader first; visual indexing runs as a separate durable job.
            rendered = render_document(original_path, ft, temp_dir, ocr=False)
            jpg_paths = rendered['image_paths']
            result['image_paths'] = jpg_paths
            result['page_count'] = rendered['page_count']
            result['text_content'] = content_text(rendered)
            result['pages'] = rendered['pages']
            result['text_extraction'] = rendered['text_extraction']

            result["success"] = True
            logger.info(f"=== PIPELINE COMPLETE: {len(jpg_paths)} pages ===")
            return result

        except Exception as exc:
            from .document_rendering import rendering_failure
            result['error_code'], result['error'] = rendering_failure(exc)
            logger.error('Pipeline error slide=%s type=%s code=%s exception=%s',
                         slide_id, original_file_type, result['error_code'], type(exc).__name__)
            # Clean up on failure — temp_dir is useless without images
            from .document_rendering import cleanup_render
            cleanup_render(result)
            result["temp_dir"] = None
            return result
