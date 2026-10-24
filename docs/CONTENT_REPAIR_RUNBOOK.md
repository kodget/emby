# Curriculum and upload repair checkpoint

Reader follow-up (2026-10-17): [READING_REPAIR_RUNBOOK.md](READING_REPAIR_RUNBOOK.md) now verifies real PDF/PPT/PPTX/DOCX conversion and both reader/library workflows locally. Its results supersede the unverified-conversion statements in this historical checkpoint. Hosted storage, extraction/OCR and durable processing still require separate acceptance.

Historical checkpoint: the class-ownership restrictions described below were superseded on 2026-10-15 by [CLASS_ISOLATION_RUNBOOK.md](CLASS_ISOLATION_RUNBOOK.md), and URL-based upload storage by [PRIVATE_MEDIA_RUNBOOK.md](PRIVATE_MEDIA_RUNBOOK.md) on 2026-10-16. Current code includes additive ownership/private-asset migrations, explicit ownership adoption tooling and class-filtered APIs. Historical storage adoption, provider verification and full route coverage still require work. The sections below describe the earlier checkpoint, not the current storage implementation.

Scope: the existing Subject/Block/SubBlock/Topic serializers, Slide and Material CRUD endpoints, main slide multipart upload, upload modal and course navigation. These changes do not modify existing records or add a migration.

## Implemented behavior

- A slide's topic, submodule, module and subject must agree. Missing ancestors can be inferred from the selected child; explicitly contradictory or null parents fail with field errors. Material ancestry uses the same checks. Partial updates check the stored values too.
- Topics require a module or submodule. A submodule supplies its actual module. Conflicting legacy `topic`/`sub_block` aliases fail. Existing direct-module topics remain supported until the complete hierarchy migration is ready.
- Ordinary node edits cannot move existing modules/submodules/topics or change primary keys and leave dependent records inconsistent. Moving a populated hierarchy needs a dedicated migration operation.
- Slide and Material CRUD writes require an active authorized uploader with an active class, or a platform administrator. Because historical content has no reliable class owner, editing/deletion is temporarily restricted to its uploader or platform administrator. A class head cannot infer ownership of historical content from the uploader's current class. Class-wide management will require the explicit ownership migration.
- Client payloads cannot forge uploader identity or slide page/generation state. Slide filtering supports a real `sub_block` ID separately from `topic`.
- Main multipart slide upload validates ancestry and file before storage: nonempty, maximum 100 MB, PDF/PPT/PPTX/DOCX, matching signatures and Office container entries. These are format checks, not a malware scan or a guarantee that every parser accepts a damaged document.
- A successful upload saves the original Cloudinary URL/resource metadata and processing-status row atomically. Dispatch happens after database commit. Broker failure preserves the original and records a safe processing error; storage failure makes no slide; database failure rolls back the slide and attempts cleanup of only the newly uploaded asset. Cleanup failure is logged and still needs an operator reconciliation process.
- The upload modal uses authenticated API refresh, sends an actual multipart body, supports the backend formats and size limit, preserves the form/file on failure and prevents repeated submission while a request is pending. The progress strip displays processing errors without a forever-spinning failure icon.
- Course queries keep submodule and topic IDs separate. Topic pages no longer merge every sibling module upload into the selected topic. Parent navigation uses returned foreign keys, not guessed slug fragments. Material API outages show a retryable error rather than an empty-course message.

## Explicitly outstanding

This does **not** establish class isolation. Subject, Slide, Material and SlideDeck historical ownership still needs a reviewed mapping; do not derive it by guessing from today's uploader membership. Public Cloudinary delivery, raw upload/delete endpoints, standalone SlideDeck uploads, extraction, question banks, direct file/page/content routes and Django/universal admin access need the same ownership review. Source URLs are not yet protected by class membership.

The main upload now records failed dispatch durably, but there is not yet a durable outbox, task identity, safe automatic retry or recovery after a process crash between commit and dispatch. Network ambiguity can still create duplicate uploads on a later retry; end-to-end idempotency is outstanding. All conversion formats, OCR and AI-independent reader behavior remain to be tested with real documents. Existing malformed or orphan hierarchy rows are preserved and need a read-only inventory followed by explicit repair.

Do not deploy this checkpoint as “all upload/class isolation issues solved.” The restrictive edit rule above is a deliberate interim behavior and should be communicated during rollout. See [REPAIR_TRACKER.md](REPAIR_TRACKER.md), rows 7–11.

## Local verification

Use the isolated settings, which never load the production `.env`:

```powershell
# Run from backend. EMBY_TEST_POSTGRES=1 selects only the disposable localhost:55432 cluster.
$env:EMBY_TEST_POSTGRES='1'
..\.venv\Scripts\python.exe -m django test accounts.tests credits.tests curriculum.tests.test_content_integrity curriculum.tests.test_upload_validation --settings=tests.integration_settings --noinput
```

`npm run test:browser -- tests/browser/content.spec.ts` exercises the main browser paths with isolated API fixtures. Browser mocks do not verify Cloudinary, Celery, conversion, Neon or Render. Final results are recorded in EMBY_REPAIR_PROGRESS.md after execution.

Final checkpoint: 23 content-integrity tests passed (the initial 21 also passed on PostgreSQL; the final two additions were checked on SQLite), 3 existing upload-validator tests passed on PostgreSQL, all 12 browser journeys passed, and the production build passed with TypeScript checks enabled. The wider account/credit/persistence/guard suites also passed. No production changes were made.
