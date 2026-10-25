# Readable slides before AI preparation

Uploading and rendering no longer waits for OCR or AI. PDF, PPT/PPTX and DOCX
still need to be uploaded to private storage and rendered into page images.
The renderer keeps native selectable text because that operation is inexpensive.
Image pages no longer make an otherwise successful render fail.

After the pages are published, a durable `DocumentIndexJob` reads pages needing
visual interpretation with the configured vision model. Each successful reading
is saved against its original page. Deliveries handle three pages at a time;
retries reuse completed pages. An expiring lease and source identity prevent a
stale worker from publishing into a replacement document. The scheduler recovers
lost queue deliveries and interrupted workers, with four consecutive failures
before a manual retry is needed. Rendered pages remain available throughout.

The resulting page index is shared by the class library tutor, slide chat,
resources, flashcards, MCQs and theory question banks. Standalone documents also
receive an index; their existing course assignment step connects them to a
question bank. AI Brain Battles search the host's class slides (restricted to the
selected curriculum when provided) before reserving credits; an empty library
cannot produce an ungrounded battle. Assessment workflows can reuse saved banks. The index
is derived AI content, not a guarantee of perfect transcription or answers.
Page references remain available for checking the original slide.

The reader sends a page number to chat. After checking class access, the server
loads that page's private image and gives it to the vision model. This can work
before indexing finishes. Whole-library search still needs the background page
index; repeatedly sending every image in a large library on each question would
be expensive, slow and exceed model input limits.

## Deployment

Apply migration `curriculum.0029_documentindexjob` and run web, Celery worker and
one Celery beat scheduler from the same revision. The existing `recover-document-indexes`
schedule runs every five minutes. No new storage service or Python dependency is
required. LibreOffice is still required for Office documents; storage permissions,
file limits and a functioning worker remain prerequisites for rendering.

Set `LLM_VISION_MODEL` to an image-capable model offered by `LLM_BASE_URL`. The
default Groq endpoint uses `qwen/qwen3.8-27b`. Other providers require an explicit
vision model. Set `LLM_BACKUP_1_VISION_MODEL` (and slots 2/3) for image-capable
backups; text-only providers are skipped for image calls. An explicit empty
`LLM_VISION_MODEL` disables primary vision. With no vision provider, background
indexing uses the existing local OCR fallback, requiring Tesseract language data.
See the provider's [vision documentation](https://console.groq.com/docs/vision)
for current image input limits and supported models.

Background visual indexing uses the application's provider quota. It does not
deduct student wallet credits. Interactive chat/resource/flashcard requests keep
their existing reservations, usage settlement and error refunds. Confirm provider
model availability, quotas and costs before enabling this in production. No
production request or deployment is performed by the local tests.

`ai_index.status` reports `pending`, `running`, `complete` or `failed` separately
from rendering. Existing incomplete course documents can retry with
`POST /api/slides/<id>/reprocess/` and `{"index_only": true}` without another
upload. Existing original files and page assets are retained.
Standalone document uploaders can use the reader's Retry AI preparation button
(`POST /api/decks/<id>/prepare-ai/`).

## Local verification — 25 October 2026

- Backend: 123 tests run, 118 passed and five PostgreSQL-only concurrency tests
  skipped using isolated SQLite settings. Includes real PDF, DOCX, PPTX and PPT
  rendering, scanned pages without synchronous OCR, visual-index recovery,
  source replacement, class isolation, flashcards, deck banks and credit refunds.
- Browser: all four selected journeys passed, covering readable scanned pages,
  current-page chat before indexing, preparation retry, and persisted deck chat.
  One local JavaScript chunk-load timeout passed on a targeted rerun.
- TypeScript, migration consistency and diff whitespace checks passed.
- AI provider responses and private storage were mocked. Live provider access,
  rate limits, production workers and production uploads still need validation
  after deployment. No existing production data was changed by this work.
