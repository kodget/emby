# Document extraction and OCR repair

Item 10 of `REPAIR_TRACKER.md`. Changes are local in `C:\Users\USER\emby`; no production migration, deployment, storage operation or AI provider call was performed.

## Behavior

- PDF, PPT, PPTX and DOCX use the same PDF page boundaries as the reader. Word tables and grouped PowerPoint shapes are included through LibreOffice conversion. Local paths, raw bytes and storage URLs are accepted; download failures and unsupported, corrupt or password-protected files fail explicitly.
- Every page has its text, page number, extraction method, status and safe error code. The document report records source SHA-256, total/processed pages, OCR pages, missing pages and character count. A successful attempt on every page is required for complete coverage; a true blank page is recorded as blank. Nonblank pages with no readable text are flagged for review.
- Native text has no 15,000-character cutoff. Explicit caller limits fail rather than returning a prefix. Scanned and mixed pages use local OCR on all pages, including pages after the third. Existing model providers and their keys are unchanged.
- Reading readiness and text readiness are separate. Missing OCR data or a recognition failure leaves rendered pages available. Course and standalone readers show which pages need attention. Authorized course uploaders/class heads can queue existing processing and refresh its result; students see guidance without a retry control. The existing standalone upload retry lifecycle remains part of item 8.
- Old unverified text caches are re-extracted from the original before question-bank generation or indexing. Cached page images and unrelated resources survive this upgrade. On-demand rendering preserves previously completed OCR for the same source. A blank page cannot inherit obsolete text blocks or a document prefix.
- Question banks cannot be generated from a partial extraction. An extraction failure persists a failed job rather than leaving it running or marking it complete. A skipped job does not claim completion. Other question-bank lifecycle, grounding, counts and durable retry requirements remain item 11.
- Search indexing uses all extracted pages in order. Embeddings must succeed for every chunk before an atomic replacement. Failures preserve previous rows without advertising them as a complete current index; old indexes without a matching text fingerprint are rebuilt.
- Standalone `SlideDeck` saves per-page text in the existing `SlidePage.extracted_text` field. Migration `0009_deck_text_extraction` adds a JSON coverage report to the deck. Existing decks default to an unchecked report, never a fabricated completion. Course reports use the existing `SlideContent.content_data` field.

## OCR installation

The existing PyMuPDF dependency supplies OCR integration and requires Tesseract language data. `render_build.sh` and CI install `tesseract-ocr-eng` alongside LibreOffice. The extractor checks explicit `TESSDATA_PREFIX` first, then common Linux/Windows directories. In Django debug mode only, it also checks the repository's ignored `.test-tessdata` directory so local Windows development can use the same English data as the extraction tests. Production does not use this test-data fallback. Missing data is an explicit page failure, and incomplete worker results log page-error codes without document text or storage URLs. `EMBY_OCR_LANGUAGES` defaults to `eng`; additional languages require their corresponding trained-data files. See the official [PyMuPDF installation documentation](https://pymupdf.readthedocs.io/en/latest/installation.html) and [OCR page API](https://pymupdf.readthedocs.io/en/latest/page.html).

Local tests used the official [Tesseract fast English data, tag 4.1.0](https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0), stored in ignored `.test-tessdata/eng.traineddata`. SHA-256: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. No trained-data binary is committed.

OCR is best effort. Complete coverage means every page was processed successfully, not that every recognized character is correct. Blurry scans, handwriting, mathematical notation and the meaning of diagrams need representative human acceptance. An unlabelled diagram may correctly produce an unreadable-text warning while its image remains viewable. Mixed pages retain native text while recognizing raster content.

## Local reproduction

Always use isolated settings. The repository's normal `.env` points at live Neon.

From `backend` in PowerShell, with LibreOffice and the English trained data available (debug mode discovers `.test-tessdata` automatically; this explicit setting also works):

```powershell
$env:TESSDATA_PREFIX='C:\Users\USER\emby\.test-tessdata'
..\.venv\Scripts\python.exe -m django test curriculum.tests.test_document_extraction curriculum.tests.test_extraction_integration --settings=tests.integration_settings --noinput
..\.venv\Scripts\python.exe -m django makemigrations --check --dry-run --settings=tests.integration_settings
```

Set `EMBY_TEST_POSTGRES=1` only with the disposable loopback PostgreSQL cluster on port 55432 running. These settings ignore production database variables. The focused PostgreSQL run includes the extraction integration suite and `curriculum.tests.test_private_media.PrivateMediaTests.test_text_extraction_failures_do_not_log_private_delivery_tokens`.

From the repository root, `npm.cmd run test:browser -- tests/browser/content.spec.ts --grep extraction` exercises the four new reader journeys with isolated API fixtures. The production build uses `NEXT_PUBLIC_API_URL=http://127.0.0.1:8600` for local validation.

## Acceptance boundary

Verified on 2026-10-17: **36 distinct checks passed** — 12 real-document extraction tests, 19 integration tests, one focused signed-URL error regression, and four browser journeys. The 19 integration tests plus the error regression passed against disposable PostgreSQL on localhost port 55432, including migration 0009; the test cluster was stopped afterward. Repeated SQLite/PostgreSQL runs are counted once. The production build passed strict TypeScript and generated all 47 static pages. Migration consistency, Python compilation and tracked diff whitespace checks passed. Remote CI has not run.

An initial OCR assertion was adjusted to normalize recognized whitespace; the words themselves were present. The initial sandboxed build failed on Google Font downloads and passed when rerun with approved network access. Browser checks passed before the Windows development servers were stopped to finish teardown. No earlier reader/approval repair is counted again in this batch.

The automated evidence covers real native PDF text beyond 15,000 characters; five-page fully scanned and mixed PDFs; native headers with scanned bodies; later-page preservation after an OCR failure; blank versus unreadable pages; encrypted/corrupt input and HTTP failure; real DOCX tables, PPTX grouped shapes/tables and binary PPT; stored coverage, generation guards, atomic indexing, cache preservation, retry permissions, standalone text and both reader notices.

Deployment still needs the normal reviewed migration/release procedure, confirmation that the Render worker has LibreOffice and language data, representative original files, real private-storage delivery and recognition review. Existing documents are upgraded lazily by generation/indexing or through authorized processing; this repair does not bulk-modify production content. Full-source use by every chat/resource feature remains items 15 and 16. Durable upload scheduling, refunds, source-grounded bank validation and production sign-off remain separate open work.

### 2026-10-21 local Windows follow-up

The reported 35-page upload rendered and stored all page images, but text extraction failed because the worker could not find English OCR data. Reproduction without `TESSDATA_PREFIX` returned `ocr_unavailable` for each scanned page; the local trained data in `.test-tessdata` completed the same OCR fixture. Django debug mode now discovers that ignored local data automatically, while an explicit `TESSDATA_PREFIX` remains authoritative and production does not use the development fallback. Incomplete worker results log per-page error-code counts without document text or signed storage URLs, and the reader displays the OCR-specific count so operators can distinguish missing language data from recognition failures.

Verified after the change: **32 document-extraction and worker integration tests passed** with isolated settings and explicit local OCR data; Python compilation and focused diff checks passed. A separate smoke test using the actual local Django settings, no `TESSDATA_PREFIX`, and a generated scanned PDF returned complete extraction and recognized the expected text. The previous failed slide is not automatically reprocessed by this code change; retry it through the existing authorized processing action after restarting Django.
