# Course navigation and document reading — 2026-10-17

Scope: tracker item 9, covering course navigation, rendering supported files, opening both reader routes, page controls, saved course-reader position, recovery and document/session isolation. **Locally verified** after 83 distinct backend tests, 24 browser journeys and a production build with strict TypeScript checks. Hosted acceptance remains outstanding.

## Confirmed defects and repairs

- The main conversion pipeline accepted only PDF despite advertising Office support. The standalone converter called nonexistent Office conversion methods and deleted the rendered images before its caller could upload them. Both now use the same renderer: PDF directly, and PPT/PPTX/DOCX through LibreOffice to PDF. It renders every page in order, retains the original bytes and keeps intermediate files until storage finishes. Each Office job has its own profile to avoid competing with an existing Office process.
- On-demand rendering previously skipped failed page uploads and substituted text-only images when Office rendering failed. It now reports failure and publishes a reader cache only when every page is stored. Conversion failure, corrupt documents and missing Office support are explicit failures. No artificial replacement slides are returned.
- The course reader previously swallowed content errors, could discard a readable document when optional breadcrumb requests failed, and waited for optional video suggestions. It now separates those requests, shows retryable document errors, and opens saved pages independently of AI availability.
- Reading home and the standalone document list distinguish failed requests from an empty library and offer retry. Their requests and displayed data reset after account/class changes; obsolete responses are discarded.
- Page navigation now saves the current position immediately, serializes its requests, and resumes the stored page on reopening. The server checks page bounds against the document's own page count. Moving between pages sends zero additional study minutes, avoiding repeated accumulated-time submissions. Saved-position lookup and save failures each have recovery controls; background saving waits until the saved position is loaded or the student navigates deliberately.
- Readers clamp page controls, clear content after renewed access denial, refresh private delivery links and ignore obsolete asynchronous responses after document/account changes. Late chat/resource responses cannot populate a different document's global reader store. This does not implement persistent whole-deck chat or complete resource generation.
- The course reader supports expanded images with zoom and fit controls. The standalone reader wraps its controls on mobile, reports broken images and download failures, reauthorizes before downloading, and has retry controls for load/status failures. A failed processing job still needs the separate durable retry work in item 8.

## Verification

All Django commands must use `--settings=tests.integration_settings`; ordinary settings load the configured Neon environment. The test settings never read project dotenv. `EMBY_TEST_POSTGRES=1` selects only the disposable PostgreSQL cluster at `127.0.0.1:55432`.

```powershell
# From backend; local Office installation required for the real-format fixtures.
..\.venv\Scripts\python.exe -m django test curriculum.tests.test_document_rendering curriculum.tests.test_reading --settings=tests.integration_settings --noinput

# With the isolated local PostgreSQL cluster running:
$env:EMBY_TEST_POSTGRES='1'
..\.venv\Scripts\python.exe -m django test curriculum.tests.test_reading curriculum.tests.test_private_media curriculum.tests.test_content_integrity curriculum.tests.test_class_access --settings=tests.integration_settings --noinput
```

From the repository root, `npm run test:browser -- tests/browser/content.spec.ts` exercises browser journeys against localhost API fixtures. Browser fixtures do not contact Cloudinary, Neon, AI providers or Render. Real conversion fixtures use three-page PDF, DOCX, PPTX and binary PPT files, preserving order/text and confirming nonblank rendered images and unchanged original bytes. Storage calls in API tests remain mocked. CI installs LibreOffice and runs both the real-format suite and PostgreSQL reading tests; no remote CI run is claimed.

Executed results and final totals are recorded in [EMBY_REPAIR_PROGRESS.md](EMBY_REPAIR_PROGRESS.md).

## Deployment and remaining acceptance

The existing backend build declares LibreOffice, its Writer/Impress components, fonts and PyMuPDF. Confirm those dependencies are present in the actual Render runtime. No new database migration is required for this reader batch; earlier ownership/private-storage migrations and their release gates still apply.

Hosted acceptance must use representative real course files, especially diagrams and institution-specific fonts. Verify the original and every rendered page, Cloudinary authenticated delivery/CORS, downloads, expiry/renewal, two-class access denial, phone usability and reopening from persisted progress. These local fixtures are not a guarantee of fidelity for every Office file, font, animation or embedded object.

Items 1, 7, 8 and 20 retain provider, historical-data/storage, durable-job and release acceptance. OCR and explicit extraction coverage (10), validated question banks (11), precise activity analytics (14), persistent whole-deck chat (15) and full learning resources (16) remain separate unfinished work. This batch neither changes nor deploys production data. Reading-position repair does not certify study-time accuracy, multi-device conflict handling or offline persistence.

### 2026-10-21 course materials and extraction retry follow-up

The course card paths have two valid three-segment forms: a module with a direct topic, or a submodule. The materials page previously treated every third segment as a topic, so opening a submodule such as `/courses/<subject>/<block>/<sub-block>` requested that ID from `/api/topics/<id>/` and failed before rendering the reader. It now resolves the segment against the selected block, applies the corresponding topic/submodule filters, and re-runs the data request from the Try again button without reloading the document. The four-segment submodule/topic path is unchanged.

The extraction retry remains in the slide reader because it needs the slide's extraction report and server-provided `can_reprocess` permission. Fixing the submodule route restores the path to that reader and its authorized Retry text processing action. Browser regressions cover the submodule-to-reader retry journey, direct-topic paths and retry without full-page navigation. Current Django URL resolution maps `/api/slides/` and `/api/materials/` to their list views; if those exact list URLs still return 404 after restarting the backend, verify the running server uses `backend.settings` and that the frontend points to that same backend.
