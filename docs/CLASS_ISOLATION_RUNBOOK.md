# Class ownership repair — updated 2026-10-16

Confirmed product rule: only students in the owning class should see its content. The user separately confirmed that the approved Steeplechase/Histology catalogue should be shared across classes. Course-linked questions remain private. Approved heads and authorized uploaders manage their class; platform administrators retain administrative access. This checkpoint implements the core API boundary. It is **not ready for a production privacy sign-off**.

## Implemented

- Migration `curriculum.0006_class_content_ownership` adds nullable, protected ownership to Subject, Slide, Material and SlideDeck. New API records take the actor's active class. Client payloads cannot choose ownership. Changing an uploader's membership does not move files.
- Unassigned historical records remain stored but hidden from ordinary users. Classless users, inactive classes and unapproved heads do not receive a library. No owner is guessed from an uploader's current membership.
- Curriculum, slide/material/deck records, extracted pages, processing status and slide AI entry points are filtered by class. Foreign references fail before storage, AI or credit work. Writable serializer relations use the same scope.
- Quiz selection, attempts, legacy history, class-linked flashcards, schedules, upcoming tests and curriculum study recommendations restrict their references. Historical attempts with foreign questions/parents are hidden. Questions outside an attempt/quiz cannot be answered through that session.
- Attempt creation supports the historical submodule `topic` alias and actual Topic IDs; real topics select their source decks/materials. Upcoming tests serialize the actual submodule relationship and require head privileges for writes.
- Uploaders cannot edit or reprocess a peer's files. Approved heads manage their class's files. Arbitrary raw storage deletion is restricted to administrators; ordinary users delete an authorized content record.
- The frontend curriculum loader no longer reuses a module-level library cache across sessions.
- The read-only release preflight stops automatic releases while historical ownership is incomplete.
- Community posts, replies and likes use persistent class ownership and validate linked sources. Past-question imports/status, weak-area labels, question-bank counts, dashboard messages and both battle HTTP routes now restrict foreign sources. Dashboard caches recheck their class and source before reuse.
- New originals and rendered pages use a private asset registry with expiring delivery links. Readers renew links, stop stale polling after denial/unmount, and obtain a fresh authorized link when a material is opened. See [PRIVATE_MEDIA_RUNBOOK.md](PRIVATE_MEDIA_RUNBOOK.md) for storage migration and provider acceptance requirements.
- Spot-practice counts, sections, station selection, answers, completion, history and analytics use the visible, approved catalogue. Sessions containing a missing, withdrawn or foreign station are hidden without deleting their history. Legacy steeplechase CRUD permits student reads only; catalogue writes require platform administrator access. StudyProfile responses filter old foreign subject references without deleting preferences.
- Migration `0008_explicit_shared_practice_catalogue` adds an explicit `is_shared` flag, default false. Shared stations cannot have a class course/block source. Private source relationships are protected against deletion. Unassigned records are not automatically public; see publication procedure below.
- Platform administrator means an active superuser or an active account with `profile.platform_role=admin`. Staff status alone no longer grants global API access or approval rights. The frontend consumes the server's `is_platform_admin` capability; generic administrator CRUD still requires the appropriate Django model permissions. Django's administrative site additionally requires its normal staff flag. Approval notifications use the same administrator definition.
- The battle WebSocket checks current class/source access and requires a host or joined participant. It rechecks access before incoming actions and outgoing broadcasts, including account deactivation, membership changes, participant removal and access-token expiry. This does not certify battle scoring or lifecycle behavior.

## Shared catalogue publication

Rehearse on the restored staging database with writes and imports paused. Migration `0008` preserves station records and attempt history, but existing unlinked stations stay hidden until explicitly published. Plan publication together with the migration so the catalogue does not unexpectedly disappear at rollout.

1. Review the intended shared catalogue JSON and its existing station IDs. Confirm those records are approved for platform-wide use and contain no private class material. Approval, complete question data and `needs_review=False` are still required for student practice.
2. Run `python manage.py import_stations --path reviewed-stations.json --publish-shared --dry-run`, then inspect the report and ownership. The import refuses to replace course/block-linked stations.
3. Apply that reviewed import without `--dry-run`, only to the approved staging target first. Confirm that two active classes can see shared questions while each class sees only its own linked questions. Verify session/history continuity. The flag publishes only the supplied IDs; it does not publish the whole database.
4. Ordinary reimports preserve publication status and human approval/answer decisions. Avoid `--purge`: it deletes unused shared records and refuses stations referenced by attempts or session question lists. It preserves private stations. Run imports while practice writes are paused; concurrent purge/start is not a supported maintenance operation.

No catalogue publication or migration has been run against Neon. Keep the additive schema on rollback; older code would restore global catalogue visibility.

## Historical adoption: rehearse on an isolated restored database first

No production database was inspected or changed. This is an operator procedure, not work already performed. The repository's normal environment points at Neon; do not use it for casual local checks.

1. Verify the exact Render service, Neon branch/database, workers and storage account. Take and verify a restorable backup. Reconcile legacy credits first with the recovery runbook.
2. Restore a separate staging database with separate storage/provider settings. Inspect the migration plan before applying the additive ownership migration. Do not bypass unresolved credit gates with a blanket `migrate`.
3. Apply `curriculum.0006_class_content_ownership` in isolation. Pause content writes and workers during review and adoption.
4. Run `python manage.py assign_content_classes` to inventory unassigned IDs without changing rows. This requires the new columns. Review the actual records to establish their school/class; IDs alone do not prove ownership.
5. Prepare a JSON manifest mapping IDs to actual ClassGroup primary keys, not class codes. Example placeholders:

   ```json
   {
     "subjects": {"reviewed-course-id": 123},
     "slides": {"reviewed-slide-id": 123},
     "materials": {},
     "decks": {}
   }
   ```

6. Run `python manage.py assign_content_classes --manifest reviewed-ownership.json` for validation only. Missing/inactive classes, unknown IDs, owner reassignment and contradictory ancestry fail. Historically shared trees need a separately reviewed split; this tool does not clone them.
7. With writes actually paused, add `--apply --confirm-writes-paused`. The flag asserts operator action; it does not pause writers. Changes are atomic and replay is safe. Omitted rows remain hidden and continue to block automatic release.
8. Repeat the inventory and `check_persistence_migrations --require-existing-database`. Verify records/files with two different classes, a head, an uploader and an administrator. Reconcile counts and rehearse a restart. Preserve the manifest and evidence.
9. Complete storage privacy and route review below before proposing production rollout. Passing the migration gate does not certify private storage or authorization.

Rollback: preserve the additive schema, assignments and manifest. Reverting to old code restores its global visibility and is not a privacy-safe rollback. Keep maintenance enabled and repair forward, or use the verified restoration procedure after reconciling writes. Do not casually drop ownership columns.

## Remaining acceptance

- **Historical public Cloudinary URLs have not been revoked.** New storage code requests authenticated delivery, but old originals, conversions and cached pages need a reviewed migration. Verify old public URLs fail without destroying the only file copy. Provider upload/download behavior is untested.
- Generic uploads now have a class-owned asset registry. The dry-run-first `recover_slide_processing` command can explicitly reclaim stale pending/processing slide jobs; run it only after checking the processing SLA, because it may duplicate work that is still active. Automatic scheduler/worker acceptance, orphan reconciliation, consistent validation across all formats and durable/idempotent conversion jobs remain.
- Spot-practice/admin routes and battle WebSocket access now have regression coverage; slide-processing status/overview were also inspected for class filtering. Continue notification connection lifecycle and other feature-specific audits. Battle class checks do not establish safe battle mutation, scoring, timing or reconnect behavior. Not every route is certified class-safe.
- **Private course-linked SpotStation image URLs still need storage adoption.** They do not yet have `MediaAsset` references. The private-media release gate now fails read-only while these stations retain legacy image fields; this blocks release but does not revoke an already-known public image URL. Shared catalogue images are intentionally available across classes.
- Practice timing, duplicate-answer handling, concurrent free-round limits and full scoring rules remain unverified and belong to the assessment lifecycle work.
- Personal copies whose source relationships were previously deleted need explicit historical review; their origin cannot be inferred automatically.
- Continue the app-wide audit of in-flight requests and persisted frontend stores during logout/class changes. Reader loads and media refreshes now discard stale responses; reader remounts follow known account/class changes. This does not certify every store or automatically detect an administrator changing membership while a tab is idle.
- Attempt-history filtering inspects stored question-ID lists. Measure and replace with normalized/indexed membership if necessary; do not remove authorization for performance.

## Verification

Use only `--settings=tests.integration_settings` for local Django tests; it never reads dotenv. `EMBY_TEST_POSTGRES=1` selects the dedicated loopback PostgreSQL cluster on port 55432. CI includes `curriculum.tests.test_class_access` with existing account/credit/content tests. Browser fixtures do not establish provider behavior.

Executed results are recorded in [EMBY_REPAIR_PROGRESS.md](EMBY_REPAIR_PROGRESS.md). Local class-access and privacy-gate code paths are regression-verified. Tracker item 7 is locally verified; staging ownership adoption, provider URL revocation and hosted privacy acceptance remain unperformed.
