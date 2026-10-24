# Private files and reader repair — 2026-10-16

Reader follow-up (2026-10-17): real-format conversion and reader/library recovery, saved position, mobile controls and stale-response handling are locally verified in [READING_REPAIR_RUNBOOK.md](READING_REPAIR_RUNBOOK.md). Provider delivery, historical adoption/revocation and the storage requirements below remain outstanding.

This is a local implementation checkpoint for tracker items 7–9. It is not a production privacy sign-off. No Cloudinary upload, Neon migration, Render deployment or legacy-file deletion was performed.

## Confirmed defects and changes

Previously, uploads and rendered pages stored public Cloudinary URLs. Class filtering on an API cannot protect an already-known public URL. The generic attachment route also accepted an arbitrary client folder, and content creation accepted an unregistered URL without durable storage ownership.

- Additive migration `curriculum.0007_private_media_assets` creates `MediaAsset`, storing provider identity, owning class, uploader, resource/delivery type, format and size. Slide, Material, SlideDeck and SlidePage gain nullable protected asset references. Existing records and bytes are preserved; no owner is guessed.
- New original, generic-attachment, main-worker and standalone-renderer uploads request `type=authenticated`, a random identity and no overwrite. A response must confirm authenticated storage before registration. Content serializers accept `asset_id`, restrict it to the owning class and disallow source replacement through an ordinary edit.
- Original and page responses generate a fresh 15-minute download URL from the asset identity. Raw public IDs retain their extension. Persistent page JSON stores asset IDs instead of delivery URLs. Content responses carrying these URLs use `Cache-Control: private, no-store`.
- Workers obtain source URLs when executing, not when queuing. A failed authenticated download cannot fall back to an unsigned public URL. Download/extraction failure messages avoid signed URLs. New-file registration/record failures attempt compensation; cleanup failures still require reconciliation.
- Both readers renew links every ten minutes and on tab return/image failure. Renewal preserves the selected page. Access denial clears displayed content, cancels loading/poll publication, and stale responses after navigation/account changes are discarded. Material opens and page downloads request fresh authorization. The image cache is bounded, expires and changes with the session token.
- Reading already-extracted pages no longer waits for suggested videos. Standalone deck conversion marks page-storage failure as a failure instead of claiming a complete deck. Initial conversion still runs synchronously, but a dry-run-first recovery command and five-minute Beat task requeue stale in-progress conversions after an interrupted request; failed conversions require an explicit `--retry-failed` recovery.
- `check_private_media` inventories unresolved legacy file fields, public cached page URLs, private course-linked SpotStation image fields, invalid registry delivery types and ownership mismatches. `render_release.sh` fails when this check fails, after the existing persistence preflight and additive migrations. The check does not delete files or certify provider-side URL revocation.

The 15-minute link is a bearer credential: a person who receives a copy may use it until expiry. It does not recheck class membership for each byte request. An authenticated streaming proxy would be needed for stronger immediate revocation. Do not describe expiring links as preventing downloads or copies by an authorized student.

## Staging adoption and acceptance still required

Use an explicitly isolated database and storage account. Normal repository settings load the configured Neon environment and must not be used for casual local tests.

1. Identify the exact Render services, Neon branch/database and Cloudinary account. Verify a restorable database backup and an inventory of original/page bytes. Resolve legacy-credit and class-ownership gates first using the existing runbooks.
2. Rehearse the additive migrations against the restored staging copy, with content writes and workers paused. Review every historical owner through the explicit class-assignment manifest. Keep before/after counts and checksums where available.
3. Inventory every legacy original, conversion, SlidePage and cached page reference. Plan its private replacement or provider delivery-type migration using the actual stored resource identity. Do not infer identity by blindly parsing a URL or delete the only readable original.
4. Verify a private copy is readable and complete before linking its `MediaAsset`. Clear legacy fields only after their migration has been verified. Replace cached image URLs with same-class asset IDs. A general legacy-provider migration command has not been implemented; this step needs a reviewed manifest and reconciliation procedure.
5. Revoke the previous public original and derivative URLs at the provider, including CDN invalidation where needed. Verify those URLs actually fail. The database gate alone cannot prove this, and clearing a database URL does not revoke it.
6. Exercise PDF, PPT/PPTX, DOCX, image and any supported video assets against the configured provider. Verify authenticated original/page access, raw ID/format handling, expiry, post-expiry renewal, worker downloads, browser CORS/download behavior and account-plan restrictions. The download API bypasses normal CDN caching; measure bandwidth and latency.
7. Run `python manage.py check_private_media` on the prepared staging copy. Test two classes, an uploader, an approved head and an administrator. Reopen a reader after more than 15 minutes; verify the selected page is retained and denied membership no longer obtains fresh URLs.
8. Rehearse a restart/redeploy, worker interruption and failed page upload. Compare the same records and original bytes afterward. Record actual provider evidence before proposing production rollout. Do not bypass a failing release gate to get a green deploy.

Rollback: retain the additive schema, manifests and verified private assets. Old code cannot safely read the new asset references and may restore global/public access. Use maintenance mode and repair forward or a reviewed, reconciled restore; do not drop registry rows or private copies as a routine rollback.

Provider design references: [Cloudinary time-limited download access](https://cloudinary.com/documentation/control_access_to_media#providing_time_limited_access_to_private_media_assets) and [delivery types](https://cloudinary.com/documentation/upload_parameters#delivery_types). These describe the intended integration; they are not evidence that this account has passed provider acceptance.

## Local verification and remaining scope

Django tests use only `--settings=tests.integration_settings`, inert signing credentials and mocked storage/AI calls. `EMBY_TEST_POSTGRES=1` selects the dedicated loopback test cluster on port 55432. The private-media suite covers ownership, signing, cache rewriting, upload registration/cleanup, download failures, release refusal and safe conversion failure states. Browser tests use localhost API fixtures. Exact executed totals are in [EMBY_REPAIR_PROGRESS.md](EMBY_REPAIR_PROGRESS.md).

Outstanding: historical migration/revocation; provider file-byte acceptance; provider-side orphan inventory/reconciliation; storage cleanup policy; full-format extraction/OCR; further notification/feature lifecycle checks; and browser-state isolation beyond these readers. The dry-run-first `recover_slide_processing` and `recover_standalone_decks` commands run from five-minute Beat tasks when the scheduler is configured; this is recovery for stale local records, not provider-side orphan discovery or a replacement for monitoring the worker/broker. Administrator, spot-practice and battle WebSocket class access now have regression coverage. Course-linked SpotStation images still use legacy URL fields and have no private asset references; the release gate now blocks private course stations with those fields, but their bytes still require separate storage adoption and provider revocation. Shared catalogue images are intentionally available across classes. Existing public fallbacks are retained for deliberate migration. A passing database gate alone must not be treated as a finished private-storage rollout.

## Item 8 follow-up: recoverable standalone publication and storage inventory, 2026-10-23

Standalone conversions now claim a unique processing token and a two-hour renewable lease. Recovery reserves a new token after stale pending/processing work (or explicitly selected failed work), then dispatches that exact token after commit. Duplicate messages cannot claim the same conversion twice, and a late superseded worker cannot publish pages or mark the newer generation failed. A broker acknowledgement failure cannot overwrite a worker that has already claimed its reservation. Recovery excludes active leases, inactive classes and mismatched source ownership.

Page uploads are staged before publication. The complete page set, page count, extraction metadata and completed status publish atomically under the deck lock. A partial failure preserves the previous page rows, so retry does not collide with their page numbers. Unpublished uploads are compensated where possible; failed compensation retains the registry entry for reconciliation. Previous published assets are retained for review rather than deleted during replacement. The original source is never removed by recovery. This also covers a request interrupted after creating a pending deck but before starting conversion. Initial upload conversion remains synchronous.

Additive migration `curriculum.0020_standalone_processing_leases` must precede this API/worker code. Drain/restart older workers during deployment: old binaries do not honor the token. Recovery uses the new token in queued messages. No production migration or provider operation was performed here.

The new `reconcile_media_inventory --inventory <export.json>` command reads an explicit local provider inventory and compares it with the selected database. It does not call the provider, modify the database or delete anything. It accounts for original/deck/material/page foreign keys **and** asset IDs in SlideContent page JSON. Malformed cached page references prevent confident unused classification. Its report separates referenced assets, old registered-but-unreferenced assets, provider-only files, recent uploads, missing identities, non-authenticated delivery, and incomplete-export uncertainty. Resource and delivery types are part of the identity; equal public IDs alone do not match. Signed URLs or other extra export fields are not copied into the report. The report fingerprint identifies the reviewed output, not permission to delete.

Use a selected staging/copy database and an export from its matching provider account. Normalize the inventory to this schema, merging every page of the provider listing before claiming `complete: true`:

```json
{
  "version": 1,
  "prefix": "emby/",
  "complete": false,
  "exported_at": "2026-10-23T03:00:00Z",
  "resources": [
    {
      "public_id": "emby/deck_pages/example/1/random-identity",
      "resource_type": "image",
      "delivery_type": "authenticated",
      "created_at": "2026-10-20T03:00:00Z"
    }
  ]
}
```

The prefix must be `emby/` or a slash-terminated descendant, and every supplied resource must be in scope. Default age grace is 24 hours (`--older-than-hours`); inventory capture time also bounds eligibility. Partial exports never prove absence, and registrations newer than the export are listed separately. A candidate can still be used by a legacy URL, external reference or an interrupted upload: preserve it until reviewed against those sources and a verified backup. There is deliberately no apply/delete mode. Actual provider export, legacy adoption/revocation and byte-integrity acceptance remain outstanding.

At this checkpoint, main curriculum conversion ownership/atomic publication, ambiguous repeated uploads and connected acceptance were still outstanding. The subsequent course/upload work is recorded below. Items 7 and 14 remain locally verified as recorded in REPAIR_TRACKER.md.

Verification: **139 tests passed together on isolated PostgreSQL**, including two new real row-lock races, standalone recovery, inventory classification, private media, upload validation/integrity, real PDF/DOCX/PPTX/PPT rendering, extraction, reading, banks and deck chat. The new coverage adds nine processing tests, five recovery cases and eight inventory tests. Migration consistency and diff checks passed; CI includes the new/recovery modules but has not run remotely. Initial failures were an incorrect test-server port, mocks still targeting the old conversion location, and Celery task proxies resolving differently in test threads. These were corrected before the full passing run and are not counted as passes. No frontend behavior was changed or new browser pass claimed in this batch. No production migration, storage deletion, Render/Neon write or deployment occurred.

## Course conversion and upload receipts, 2026-10-23

Course conversion now owns a UUID token and renewable one-hour lease. It stages every rendered page, then publishes the whole page set, extraction summary, page count and generation request in one transaction. Failed staging/publication preserves the old readable content. Late or duplicate workers cannot claim, publish or fail a replacement attempt. Recovery excludes live leases and inactive/mismatched ownership, dispatches the exact reserved token and permits four worker attempts before requiring an explicit uploader retry. Broker failure preserves the original and exposes a safe retry message. Finishing an older question-generation job cannot overwrite an active conversion's processing phase. Asset compensation also checks cached page references before deleting an unpublished upload.

Course and standalone upload APIs accept a UUID `request_id`, scoped to the authenticated user. A receipt binds it to the uploaded bytes, type, title, class and course placement. Concurrent matching requests serialize and return the saved document; changed content with the same ID returns 409, and a removed/inaccessible saved document returns 410. Every replay still passes current permission and class checks. The receipt and content record commit together, before conversion dispatch. Standalone conversion remains synchronous after that commit; interruption leaves a recoverable pending record instead of requiring another original upload.

Both upload forms retain the request ID across a failed response; changing the file, title, placement or account/class creates a new intent. Authentication refresh reuses the same multipart body. Closing/resetting the form or reloading and reselecting a file starts a new intent; this is request replay protection, not global file-content deduplication. Older clients without an ID retain their existing behavior. The standalone form uses the actual 100 MB limit, rejects empty selections, respects the 200-character title field and hides upload controls from students.

Additive migration `curriculum.0021_upload_receipts_and_course_processing_leases` must precede the updated API/worker code. Drain older workers before restarting with this version. No production migration has been applied. External provider storage cannot participate in the database transaction: an abrupt crash or failed compensation may leave provider-only bytes. Review those using the inventory command and the staging procedure above; no automatic cleanup policy or deletion permission is implied by a receipt.


Final local acceptance: **208 tests passed together on isolated PostgreSQL**, including the new worker/receipt races, connected upload/conversion/replay, source versioning, bank recovery, private media, real-format rendering/extraction and reading. **Three browser journeys and 12 client/session checks passed**, as did TypeScript, migration consistency and targeted diff checks. Item 8 is now locally verified in the numbered tracker; this does not certify hosted provider delivery or a production rollout. Earlier failed/interrupted runs are not counted as passes.

Run the isolated upload browser acceptance with `node node_modules/@playwright/test/cli.js test tests/browser/content.spec.ts --config playwright.upload.config.ts --grep "upload validation|standalone upload"`. It uses port 3118, `.next/upload-browser-tests`, `.test-results-uploads`, Webpack and disabled trace recording to avoid shared preview/cache conflicts and Windows trace-teardown delays. The normal test configuration remains available for the complete browser suite. The current migration graph joins the upload branch and separately completed flashcard work at `curriculum.0025_merge_item8_and_flashcard_migrations`; preserve that merge during release preparation.
