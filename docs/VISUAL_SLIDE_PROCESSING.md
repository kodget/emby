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

## Upload timeout follow-up — 26 October 2026

The supplied log showed a successful 15-page render followed by cancellation of
the upload HTTP request. Local `CELERY_TASK_ALWAYS_EAGER=True` made `.delay()`
run the remaining pipeline inline, including question generation. Standalone
uploads also invoked conversion directly before responding.

Course and standalone uploads now dispatch after the original and upload receipt
commit. Production still uses Celery; local eager mode uses two background
threads with a bounded queue and separate database connections. Indexing and bank
generation use the same dispatcher, so chained eager tasks cannot hold the HTTP
response. Local recovery commands wait for their queued work before exiting.
These threads are for local development; the database records and recovery
commands remain necessary if that server stops during processing.

Opening an upload before its pages are published returns a preparation response
instead of starting a second conversion inside the reader request. The reader
polls and opens the saved pages automatically. Upload retries reuse the original
receipt and document rather than creating another original.

Verification: 230 backend tests ran, with 217 passing and 13 database-specific
concurrency tests skipped. Five browser journeys passed, including automatic
opening after preparation and current-page chat before indexing. TypeScript
passed. The eight dispatch regression tests were rerun successfully on 26 October.
Provider and storage failures are simulated in these tests; they do not establish
that every external service or production deployment is healthy.

Question-generation retries now include existing stems and validation feedback.
When a batch makes no progress because of an invalid citation, duplicate stem or
invalid answer structure, it gets one corrective request for that difficulty.
The exact source-quotation checks still apply. Repeatedly unsupported questions
stay rejected, and questions awaiting review are not automatically approved.
An empty response or provider outage does not trigger this extra correction.

The obsolete `test_generate_questions_task.py` module still imports the removed
`generate_questions_task` symbol and cannot run. It was not changed or silently
skipped; verification targets the supported durable question-bank workflow.

### Live recovery

On 26 October, the specific slide from the supplied logs
(`slide_49232b2de5b542e890915a3eb5f09cac`) was checked and its partial question bank
retried. The final saved bank is complete: 15 MCQs and 10 theory questions.
The private original, all 15 rendered pages, and every previously saved question
were verified preserved. The document's text index was already complete.
One diagnostic retry identified an unsupported source quotation; strict evidence
validation remained enabled throughout recovery.

This live check covers that saved document and its question-bank recovery.
It does not verify live flashcard, chat, textbook or video services. No application
deployment was performed in this follow-up; the new retry logic needs the usual
backend restart or deployment to serve subsequent requests.
