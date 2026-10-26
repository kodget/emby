# Upload and rendering reliability

## Evidence from the 26 October production log

Both failing PDFs reached storage and the worker downloaded them (3,915,803 and
1,825,426 bytes). The entire combined service restarted during rendering without
a conversion exception or completion event. This is consistent with memory
pressure, but the supplied log does not include an OOM event and cannot prove the
restart cause. There is no 1 MB application upload limit; validation allows 100 MB.
Repeated status requests also received 401 responses because that component used
raw fetch without the application's token-refresh handling.

## Changes

- Stream originals to temporary files in 256 KB chunks. Do not retain the whole
  download while rendering, or read an entire attachment to inspect its signature.
- Render each page at up to 150 DPI, a 1920-pixel long edge and approximately
  two million pixels. Save JPEGs at quality 85, release the bitmap and clear the
  MuPDF image cache after each page. Preserve every page, native text, page order
  and the private original. Hash the original incrementally.
- Run conversion in a disposable process without Django or eager AI imports.
  Both upload pipelines and the legacy reader use it. The parent enforces a
  420-second wall deadline independently of Celery's solo-pool time limits.
- On Linux, monitor converter-process-group RSS, including LibreOffice. Default
  budget is 192 MB, reduced to leave 48 MB of container headroom. Reject a new
  render if less than 64 MB is available for it. Stop rendering if free container
  headroom drops below 24 MB. Native rendering also has an address-space limit.
  The child watches its parent's pipe and kills its converter group if the parent
  disappears. Windows development has process isolation and deadlines; the Linux
  memory controls must also be exercised in Linux CI/staging.
- The combined deployment now starts one gevent web worker, one solo Celery
  worker and Beat. This lowers baseline memory use; it does not increase the
  hosting plan's CPU or memory allocation.
- Processing ownership lasts ten minutes and is renewed during downloading,
  rendering and page storage. Rendering reports progress every five seconds.
  Scheduled recovery replaces expired attempts. Both pipelines stop after four
  processing attempts; failed broker sends remain eligible for retry.
- Publish a new page set only after every image is stored. Failed/superseded
  attempts retain the original and existing published pages. Authorized uploaders
  can retry an exhausted standalone job from its reader.
- Show real transfer progress, rendering/storage page counts and scheduled
  retries on desktop and mobile. Status requests use token refresh, cancellation
  and sequential polling with network backoff. Readiness means pages are saved;
  AI indexing and question-bank generation have their own readiness states.

## Deployment and recovery

1. Deploy the backend and frontend from the same revision. Apply migrations
   through `curriculum.0031_processing_progress_and_recovery` using the existing
   deployment migration step. Migration 0031 caps legacy one/two-hour leases at
   ten minutes from migration time without deleting originals or page sets.
2. Keep the existing combined entry point and durable database/storage settings.
   No new external queue or storage service is introduced.
3. Inspect Render memory/restart metrics while uploading the two original failing
   PDFs. Look for `Render starting`, `Render complete`, or `Render stopped` logs,
   followed by saved pages and separate AI-index/question-bank readiness.
4. Scheduled recovery runs automatically when worker and Beat are available.
   Preview with `python manage.py recover_slide_processing` and
   `python manage.py recover_standalone_decks`. Add `--apply` to requeue eligible
   jobs; standalone legacy failures without a retry timestamp additionally need
   `--retry-failed`. These commands preserve originals and respect live leases.
5. If `render_memory` repeats, inspect the combined service's baseline usage and
   allocate more memory or separate the worker. `EMBY_RENDER_MEMORY_MB` can raise
   the renderer budget on a larger host (64–1024 MB); container-headroom checks
   still apply. Raising it does not create memory on a constrained host.

No code change can guarantee storage/network/provider uptime or prevent a host
from being terminated. These changes bound work, report failures, and make saved
uploads recoverable. Live Render/Cloudinary behavior and the user's original
problem files still require deployment validation; local tests use isolated
storage/provider fixtures.

## Validation

`test_large_document_rendering` exercises a real PDF over 3 MB with 16 image-heavy
pages, a 100,000 × 50,000 point page, streaming without a full response buffer,
deadline cancellation, low-memory admission, progress heartbeats, automatic
recovery and authorized manual retry. Existing format tests cover PDF, PPT,
PPTX and DOCX; processing tests cover atomic publication and obsolete workers.
The browser regression exercises a 2 MB upload, token refresh after a 401,
page counts, scheduled retry and reading readiness on a mobile viewport.

Reference: [PyMuPDF cache controls](https://pymupdf.readthedocs.io/en/latest/tools.html).
