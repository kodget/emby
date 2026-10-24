# Emby repair progress and verification checklist

Audit date: 2026-10-13 (Africa/Lagos). Baseline commit: `ddf9f96` on `master`, tracking `origin/master`.

Latest checkpoint (2026-10-23): **18/20 locally verified, 2 in progress, 0 pending; 0 production sign-offs**. Items 8 and 19 have completed local acceptance; item 20's local frontend gate now passes all 75 browser tests, TypeScript, auth/state regressions, npm audit and production build. Remote CI and hosted acceptance remain outstanding; all current item statuses are recorded in [REPAIR_TRACKER.md](REPAIR_TRACKER.md). Earlier counts and open-work statements below are historical. The confirmed formal limits remain 50 MCQs/5 theories/150 minutes, chosen by the class head, with one attempt per student, and saved deck MCQ banks remain 15 (5 per difficulty).

This document tracks the twelve sections of `Emby_Coding_Master_Prompt.md`. The local delivery now includes persistence safeguards, legacy-credit transfer, class-head approvals, email verification and password-reset repairs. See ACCOUNT_REPAIR_RUNBOOK.md for current behavior and test evidence. A code inspection, a local test, and a production verification are different kinds of evidence; none substitutes for the others. Unchecked items remain outstanding. No production deployment, database migration, backup, restore, provider delivery test, or data-loss incident has been verified during this audit.

## Existing work preserved

At the start of the task, the working tree already contained these user changes:

- Modified: `backend/learning/admin.py`.
- Untracked: `README.md`, `PRD.md`, `PRD.html`, `PRD.pdf`, `TECHNICAL_ARCHITECTURE.md`, `TECHNICAL_ARCHITECTURE.html`, `TECHNICAL_ARCHITECTURE.pdf`, `convert.js`, `marked.min.js`, and `print.js`.

These files are existing work, not repair deliverables. No `AGENTS.md` was found in the workspace or at the directly readable ancestor paths.

## Architecture established from source and local configuration

| Area | Evidence and current implementation | Verification boundary |
| --- | --- | --- |
| Frontend | Next.js App Router; installed Next `16.2.0`, React `19.2.4`, TypeScript `5.7.3`; Tailwind `^4.2.4` declared in `package.json`; Radix UI, Redux Toolkit, Zustand, Axios, and Framer Motion. | Installed versions were read locally; routes have not all been exercised. |
| Frontend state | `store/store.ts` combines user, uploads, progress, schedule, flashcards, quiz attempts, and notifications. The slide reader also has a Zustand store. JWTs and the cached user are read from `sessionStorage` by `lib/api.ts` and authentication hooks. | Browser state is not the persistence source of record; reload and second-session behavior need feature tests. |
| API and authentication | Django REST Framework, Simple JWT, Django auth users and account profiles; `/auth/`, `/api/`, `/api/learning/`, `/api/pastquestions/`, `/api/payments/`, and `/api/credits/`. Django admin and a frontend admin interface coexist. | API routes and permission implementations are visible in source; production identities and authorization flows were not exercised. |
| Backend versions | `backend/requirements.txt` pins Django `6.0.4`, DRF `3.17.1`, Celery `5.4.0`, Channels `4.3.2`, Channels Redis `4.2.1`, Daphne `4.2.3`, Redis client `5.0.1`, and psycopg2-binary `2.9.12`. | Full application runtime remains unverified. The new isolated test environment installs Django `6.0.4`, dj-database-url `3.1.2`, Cloudinary `1.44.2` and PyYAML `6.0.3`. |
| Persistence | Django ORM; PostgreSQL configured through `DATABASE_URL` or `DB_*`; baseline settings also accept explicit SQLite and silently fall back to `backend/db.sqlite3` when DB configuration is absent. Local `.env` has a Neon PostgreSQL host and a configured `DB_NAME`. | No connection was made to that remote database. Production configuration, contents, backup policy, and restore ability are unverified. |
| Content hierarchy | `Subject > Block > SubBlock > Topic`; account `ClassGroup`; `Slide`, `SlideContent`, `Material`, `SlideDeck`, `SlidePage`, `SlideChunk`, `SlideChatMessage`, and `SlideProcessingStatus`. | Product terms Module/Submodule map to current Block/SubBlock terminology; actual class isolation and ancestor validation require route-by-route tests. |
| Assessments and activity | `QuizQuestion`, `Quiz`, `QuizAttempt`, `QuizAttemptResponse`, flashcards/progress/reviews, practical stations/sessions, `LearningEvent`, `WeakArea`, `QuestionExposure`, badges/achievements, and `BrainBattle`/participants/answers. | Model existence does not establish correct lifecycle, durable write behavior, or feature completeness. |
| Storage | Slide/material/deck/page fields use Cloudinary; inspected processing paths use temporary local files. Settings also define local `MEDIA_ROOT`; no ordinary model FileField/ImageField was found in the audited curriculum paths. | Original and derived bytes still need before/after deployment verification. Cloudinary credentials are configured locally; delivery was not called. |
| Background processing | Celery autodiscovers app tasks; broker defaults to Redis; result backend defaults to `django-db`. Slide conversion/question generation, grading, notifications, and credits use tasks. Local eager mode is enabled. | Task dispatch in source does not establish a running worker or successful job completion. Local eager mode can hide broker and worker problems. |
| Scheduling and realtime | `backend/backend/celery.py` defines hourly notifications, midnight daily credits, and hourly expiry cleanup. ASGI serves HTTP plus Channels WebSockets; Redis channel layer when configured, otherwise process-local memory. | Baseline `render.yaml` provisions web, worker, and Redis but no beat scheduler. The hosted dashboard could differ from this file. |
| AI | `backend/curriculum/llm.py` is the shared OpenAI-compatible HTTP provider layer. Local config selects Groq with `openai/gpt-oss-120b`, a Cerebras backup with `gpt-oss-120b`, and Groq vision configuration. Browser `lib/ai.ts` forwards to the authenticated backend. | Provider configuration was inspected without printing secrets. Requests, account limits, generation quality, billing, and failover were not tested. |
| Other integrations | Cloudinary media, Paystack payment endpoints, Google sign-in, SMTP email (Gmail default), YouTube API, and VAPID web push. | Credential presence is not proof of valid credentials, delivery, or provider setup. |
| Deployment | Root `render.yaml` specifies Daphne web, Celery worker, and Redis; both Python services use `backend/render_build.sh`. `vercel.json` is present for the frontend. | Files describe intended deployment, not confirmed live infrastructure. |

### Local environment alignment and tooling

- `.env.local` points the frontend at `http://localhost:8000`; backend `.env` uses `http://localhost:3000` as its frontend URL, allows localhost origins/hosts, has `DEBUG=True`, and enables eager Celery. Local HTTP endpoints align in configuration, but no live request has established connectivity.
- Backend `.env` sets `DB_NAME` and a Neon host, does not set `DATABASE_URL` or `USE_SQLITE`, and points its Celery broker at local Redis. `REDIS_URL` is absent, so the baseline channel layer is in memory. Do not run an unrestricted test, seed, or migration against the configured remote database.
- `.env.local` also contains backend-only credential names. They do not become browser-visible merely by lacking a `NEXT_PUBLIC_` prefix, but the frontend environment should be reduced to its needed values after checking server-side use. No secret values are recorded here.
- Installed tools: Node `22.18.0`, `npm.cmd` `10.9.3`, git `2.50.1.windows.1`. PowerShell blocks `npm.ps1`; use `npm.cmd`/`npx.cmd`.
- Initial sandbox tool discovery found LibreOffice's bundled Python `3.12.13` and an inaccessible Windows Python alias. An approved runtime check resolved the user's Python `3.14.4`; root `.venv` was created with that runtime and the minimal test dependencies. The sandbox cannot execute that underlying runtime without escalation. These local tests use Python `3.14.4`; the existing CI/Render configuration targets `3.12`, and CI is now configured to run the same isolated suite there. No CI run is claimed.
- `npm run lint` invokes ESLint, but ESLint is not a declared dependency and was not found in the installed modules. Playwright was initially absent; it is now a development dependency with isolated account browser tests. `scripts/run_checks.sh` expects the missing backend virtual environment, a running stack, and a demo account; it also resets that account's practice usage, so it was not run against the configured remote database.
- Baseline builds ignored TypeScript errors. The repair enables TypeScript build enforcement, adds `npm run typecheck`, `npm run test:auth` and `npm run test:browser`, and installs Playwright for isolated browser checks.

## Confirmed code findings, ranked by impact

These are source-level findings at the baseline, not claims that a specific hosted incident has occurred.

| Priority | Finding and evidence | Consequence / next action |
| --- | --- | --- |
| P0 | `backend/backend/settings.py` permits `USE_SQLITE` and a missing-DB SQLite fallback even with `DEBUG=False`. | An incomplete production environment can boot an unrelated local database. Reject SQLite and absent persistent DB configuration in production; verify rejection without connecting to a live DB. |
| P0 | `backend/render_build.sh` runs `migrate`, `create_admin`, and `seed_gamification`; both web and worker invoke this build script. | Builds mutate application data, and independent services may race migrations/seeds. Keep build artifact preparation separate; run migrations once in web predeploy; make admin/seeding deliberate maintenance actions. |
| P0 | `learning.0005` drops legacy credit tables; `credits.0001` creates different tables without transferring records. Reversing `learning.0004` deletes legacy lots/transactions. | The new preflight blocks automatic migration over populated legacy tables or accounts awaiting conversion. A conservative explicit transfer is implemented and locally tested (LEGACY_CREDIT_TRANSFER.md); hosted recovery is unverified; do not reverse these migrations as rollback. This hazard is separate from the unverified recurring deployment incident. |
| P1 | `backend/accounts/admin.py:approve_class_heads` adds heads directly without enforcing the three-head limit. `ClassGroup.add_class_head` and the API use count-then-add without a shared concurrency lock. | Approval paths can violate the three-head invariant. Centralize approval with a transaction/lock and cover concurrent, repeated, and rejected requests in phase 2. |
| P1 | `backend/curriculum/ai_views.py` reserves flashcard credits before checking required `slide_id`; its missing-ID response exits before the refund path. | Invalid requests can consume credits. Move validation before reservation and test every failure/refund path during the credit work. |
| P1 | The eager flashcard path launches a daemon `threading.Thread` and returns the constant task ID `local-eager-task`. | A process restart can lose this work and the returned identifier cannot distinguish jobs. Verify a durable job lifecycle in the AI/flashcard phases. |
| P1 | Celery beat schedules exist, but the baseline deployment blueprint starts no beat process. | The checked-in topology alone does not schedule daily grants/expiry/notifications. Audit actual hosting and add one scheduler only after shared DB, broker, and timezone settings are verified. |
| P2 | TypeScript errors are ignored by build, and declared lint/browser tooling does not provide a working local verification path. | Establish honest isolated checks; do not treat missing tools or skipped suites as passes. |

Upload loss, email nondelivery, production database loss, duplicate charges, and hosted scheduling failures remain hypotheses until runtime evidence establishes them. Source inspection is sufficient to justify the focused safeguards above, but not to assert historical data loss or successful recovery.

## Phase 1 delivery status

- [x] Inspect the existing repository and preserve the user's working changes.
- [x] Map the actual framework, ORM, storage, providers, task queue, and deployment files.
- [x] Identify the production SQLite fallback and shared build-time database mutations from code.
- [x] Record all twelve requirements and their verification criteria below.
- [x] Complete/review the production DB guard: production refuses SQLite and missing/incomplete PostgreSQL configuration; explicit local SQLite remains available for isolated development/tests.
- [x] Complete/review the build split: no migrate, admin creation, or application seeding in the artifact build; one web predeploy migration command. Paid Render hook requirement and manual release alternative are documented.
- [x] Add a read-only legacy-credit migration preflight; automatic releases also reject a target without migration history. Applied migration files are unchanged.
- [x] Add a redacted read-only inventory with database/Cloudinary fingerprints, row counts including membership join tables, and migration history. Missing SQLite files are not opened or created.
- [x] Complete `docs/PERSISTENCE_RUNBOOK.md` with staging persistence checks, backup/restore steps, rollback, and the exact operator evidence required.
- [x] Run 43 isolated regression tests: all passed. Backend compilation and `git diff --check` passed. Add the isolated suite to the existing CI workflow; remote CI has not run.
- [ ] Verify shared production web/worker database and media storage identities, obtain a backup, restore into an isolated target, and perform staging before/after redeploy checks.

Changes remain local until reviewed and deliberately deployed. The first phase does not complete the remaining product repairs.

Changed implementation files: `backend/backend/settings.py`, new `backend/backend/database_config.py`, `backend/render_build.sh`, new `backend/render_release.sh`, `render.yaml`, new `backend/accounts/persistence.py`, and new management commands `check_persistence_migrations.py` / `persistence_report.py`. Added four test modules and `requirements-persistence.txt` under `backend/tests`, wired them into `.github/workflows/ci.yml`, and ignored the local `.venv`. Documentation is this checklist plus `docs/PERSISTENCE_RUNBOOK.md`. That initial phase changed no application records or production settings. Subsequent additive account/archive migrations and the PostgreSQL battle-index migration repair are documented in ACCOUNT_REPAIR_RUNBOOK.md.

Current checkpoint: the user confirmed Render (backend) and Neon (PostgreSQL). 43 persistence tests, 36 account/email/password integration tests, 19 legacy-transfer integration tests and 16 frontend guard/session tests pass locally. The integration tests use isolated PostgreSQL 18.3, including concurrent approvals and reset-token consumption. TypeScript, Django system checks and migration consistency pass. No live provider/deployment evidence is claimed. Next: staging evidence from Render/Neon and provider email acceptance, followed by hierarchy/upload/read repairs. Eight isolated headless Edge browser journeys now pass.

## Progress accounting

Subsequent numbered reports use [REPAIR_TRACKER.md](REPAIR_TRACKER.md), a transparent new twenty-item breakdown rather than a claimed reconstruction of the missing conversational list. [CONTENT_REPAIR_RUNBOOK.md](CONTENT_REPAIR_RUNBOOK.md) records the current hierarchy/upload changes and their remaining boundaries.

Eight repair areas have implemented, locally tested changes: class-head approval/notifications, email verification, password reset, session recovery, legacy-credit transfer, course navigation/document reading, complete extraction/OCR, and durable source-grounded question banks. Deployment safeguards are implemented but hosted persistence acceptance is still open. This count uses REPAIR_TRACKER.md; this document organizes the supplied brief into its twelve sections. No production sign-off is claimed.

The next hierarchy phase has confirmed that current Subject/Block/SubBlock/Topic/Slide models do not consistently store class ownership, and legacy upload endpoints accept unvalidated ancestry. These need an explicit migration/backfill strategy and access tests before class isolation can be claimed.

The development dependency installation reported npm audit advisories (14 total); a dependency-specific review and safe upgrades are outstanding. No automatic force-upgrade was run.

## Requirement-to-verification checklist

### 2026-10-13 content repair checkpoint

Implemented and exercised the scoped repairs in CONTENT_REPAIR_RUNBOOK.md: server ancestry validation, immutable hierarchy identities/parent moves, protected content provenance/state, uploader/owner write permissions, validated multipart uploads, safe storage/queue failure behavior, recoverable upload form errors, topic/submodule filtering and actual parent navigation. Full class ownership, every upload/reader route and durable retry remain open; tracker rows 7–9 remain in progress.

Verification at this checkpoint:

- 79 tests passed on the isolated PostgreSQL cluster: 36 account, 19 legacy-credit, the initial 21 new content-integrity tests and 3 existing upload validators.
- The final 23 content-integrity tests passed on isolated in-memory SQLite after adding legacy-parent repair and nested-topic regression cases. The additional two cases were not run on PostgreSQL in this checkpoint.
- All 43 persistence regression tests and 16 frontend authentication/guard tests passed again.
- All 12 browser journeys passed (8 existing account journeys and 4 new upload/navigation journeys), using headless Edge and isolated API fixtures.
- This is **152 unique automated checks** across those suites, not 152 resolved issues. Python compilation, Django checks, migration consistency and `git diff --check` passed. The dedicated PostgreSQL cluster was stopped after testing.
- The final production build passed with TypeScript enforcement enabled and all 47 static pages generated. Run standalone TypeScript checks after the browser development server exits so Next's generated validator is stable. No provider request or production deployment was performed.

### 1. Deployment, persistence, and recovery

- [x] Production configuration resolution rejects missing DB configuration or SQLite; development/test behavior is explicit and covered without contacting the remote DB. Full hosted startup remains unverified.
- [ ] Web, worker, scheduler, and maintenance commands target the intended persistent database and consistent media storage; frontend points to the matching API environment.
- [x] Build/release shell behavior is tested using fake subprocess commands: builds contain no DB mutation commands, only web owns release, and failure stops later migration commands. Actual hosted rollout remains unverified.
- [ ] Record counts/identifiers for users, roles, classes, hierarchy nodes, decks, questions, attempts, analytics, achievements, and credit ledger survive staging redeploy.
- [ ] Original uploaded files and derived pages remain retrievable, with before/after byte hashes or equivalent integrity evidence; no necessary content relies only on an ephemeral path.
- [ ] Backup retention, restore target, recovery point/time objectives, restore procedure, and rollback owner are documented and exercised on an isolated restore.
- [ ] The app never presents a newly empty production DB as a successful deployment; prove the rejection/failure response and operator diagnosis.

### 2. Class-head requests and approvals

- [ ] Pending requests and their notifications persist across reload/redeploy and are visible only to authorized administrators.
- [x] Approve/reject actions record durable status and useful rejection feedback; repeat requests/actions are idempotent. Verified locally; hosted acceptance remains outstanding.
- [x] All approval entry points, including Django admin and the frontend API, share a concurrency-safe maximum of **three** approved class heads. Verified locally; hosted acceptance remains outstanding.
- [x] A concurrent fourth approval is rejected without partial membership or privilege changes; retrying an existing approval consumes no additional slot. Verified locally; hosted acceptance remains outstanding.
- [ ] Email verification and class-head approval are independent states, with permission tests for every combination.
- [x] Preserve the requested registration-time class-code email. Pending status is explicit and the code confers no approval. Tested locally; real inbox delivery remains open. Admin email notification is not configured as a separate channel and remains a product decision.

### 3. Email verification

- [ ] Trace signup through token creation, sender/provider configuration, message submission, and callback handling with redacted diagnostics.
- [x] Verification links expire, are single use, and are bound to the correct account and purpose; invalid/replayed/expired links fail safely. Verified locally; hosted acceptance remains outstanding.
- [x] Resend has a clear outcome and rate limit; old/new token behavior is defined and tested. Verified locally; hosted acceptance remains outstanding.
- [ ] Verify actual delivery and click-through using the intended provider/test inbox, including failure and retry behavior; API acceptance is not delivery proof.
- [ ] Unverified accounts have the intended restrictions without being confused with pending class-head approval.

### 4. Class, content hierarchy, uploads, and reading

- [ ] Verify `Class > Subject > Module > Submodule > Topic > Deck` throughout creation, listing, editing, upload, and reading; resolve Block/SubBlock naming consistently.
- [ ] Validate parent-child ancestry on the server so IDs from different branches/classes cannot be combined.
- [ ] Enforce membership and uploader/class-head permissions across every read/write endpoint, including direct ID access.
- [ ] Uploads preserve source bytes, provenance, class ownership, and metadata; processing state survives reload/retry.
- [ ] Course navigation, successful upload storage, and ordinary deck reading remain usable independently of AI provider availability.

### 5. Durable source-grounded question generation

- [x] Complete native/OCR document extraction with per-page references and explicit failures is locally verified under item 10; hosted recognition quality remains open.
- [ ] Persist a durable job ID, status, error, progress, content version, timestamps, and retry/recovery state; test worker restart and redelivery.
- [ ] Use idempotent versioned generation with a defined cost policy; retries or duplicate triggers must not duplicate banks or charges.
- [ ] Save a validated question bank with source grounding, answer/explanation, difficulty, scope, and validation outcomes before exposing it to practice.
- [x] User explicitly chose **15 MCQs: 5 easy, 5 medium, 5 hard** on 2026-10-18. Curriculum-slide generation and its tests enforce that target. The separate practice limit does not imply twenty questions are available at one difficulty.
- [ ] Confirm theory question counts and availability rules; report shortfalls instead of inventing fallback questions or quietly lowering requirements.
- [ ] Test malformed provider responses, partial extraction, timeouts, exhausted provider limits, and insufficient source content without losing successful work.

### 6. Practice, mock, formal assessments, and results

- [ ] Assemble assessments from saved validated banks, respecting scope/difficulty, availability, and repeat rules without new generation in the start path.
- [ ] Practice uses exactly **one selected deck**, with a maximum of **20 questions** and clear feedback when too few eligible questions exist.
- [ ] Confirm mock scope and formal assessment rules before implementing their differences.
- [ ] Persist attempt question selection, answers, lifecycle, and result; reload/reconnect resumes the same attempt instead of creating a new selection.
- [ ] Enforce timer boundaries and scoring on the server; answers/explanations remain hidden during an active scored attempt.
- [ ] Submission and retries are idempotent; simultaneous/replayed submissions cannot double-score, double-charge, or double-award progress.
- [ ] Test filters, empty/insufficient banks, timed expiry, mixed question types, scoring, and authorized access to attempt/results.

### 7. Evidence-based analytics and weak areas

- [ ] Derive counts, accuracy, time, topic coverage, and weaknesses deterministically from persisted attempts/events with clear denominators.
- [ ] Reconcile dashboard values to a small hand-checkable fixture including no-data, low-sample, and mixed-topic cases.
- [ ] Weakness explanations cite the student's actual evidence; any AI-generated suggestions are labeled hypotheses or guidance.
- [ ] Do not introduce unsupported exam predictions or invented performance facts; define unknown/insufficient-data states.

### 8. Deck assistant, flashcards, chat, and resources

- [ ] Assistant context can cover the whole selected deck while preserving page/source references and class access checks.
- [ ] Conversations and useful responses persist with stable deck/session identity across page changes, refresh, and reconnect.
- [ ] Generated flashcards are stored with source/owner, deduplicated across retries, and available for subsequent review; reviews persist.
- [ ] Job status/progress/errors are durable and distinguishable; restart/retry tests cover the existing daemon-thread path replacement.
- [ ] Resource/video links correspond to real returned URLs with usable empty/failure states; no fabricated videos or false claims of lookup.
- [ ] Provider failures leave course reading usable and apply the agreed credit/refund policy.

### 9. Milestones and achievements

- [ ] Define and persist the milestone catalogue, qualifying criteria, progress, award identity, and earned date.
- [ ] Confirm intended thresholds/catalogue with product requirements; do not invent thresholds during repair.
- [ ] Awards are calculated from durable activity and are idempotent across retries/replay/redeploy.
- [ ] UI progress/earned dates match stored evidence; verify fresh, in-progress, earned, and repeated-event cases.

### 10. Credits, allowances, expiry, and refunds

- [x] Confirmed the existing free/premium and role-based daily allowances, configured timezone, daily expiry, and non-expiring purchased-credit treatment with the user; the user requested no policy changes for now.
- [ ] Specify any balance caps, action prices, inactivity handling, and plan-change rules not defined by the confirmed current policy.
- [ ] Confirm which background/shared question-bank costs belong to the platform versus an individual student's balance.
- [x] Use an auditable atomic ledger for grants, reservations, use, refunds, expiry, purchases, and adjustments with stable idempotency keys.
- [x] Daily grants and expiry run from one durable scheduler and produce the same result on replay or restart.
- [x] Invalid or failed actions are not charged; cover validation errors, provider timeout/partial response, queue failure, retries, and terminal job failure.
- [x] Concurrent requests cannot spend the same credits twice, create negative spendable balance, or duplicate refunds/purchase grants.
- [x] Verify boundary dates, timezone transitions, expiry ordering, plan upgrades/downgrades, and ledger-to-balance reconciliation.

### 11. Student competition / existing Brain Battles

- [x] Extend and verify the existing Battles implementation before adding another competition system.
- [x] Invitations, join codes, membership, ownership, and class permissions are enforced server-side, including cross-class access attempts.
- [x] Competitors receive the intended same questions/order and server-controlled start/end timing without exposed correct answers.
- [x] Answers, score, speed rules, participation, and results persist and are calculated on the server; duplicate answers/submissions are harmless.
- [x] Reconnect, host departure, delayed/disconnected clients, the user-selected no-late-join rule, and completed battle replay have explicit tested outcomes.

Local evidence (2026-10-23): item 18's credit-accounting, legacy-transfer, flashcard, chat, and class-access regressions ran as 88 tests on isolated SQLite (86 passed; 2 PostgreSQL-only concurrency tests skipped), with the credit row-lock concurrency checks separately passing on isolated PostgreSQL. Item 19's battle lifecycle, WebSocket authorization, and related class-access suites ran as 38 tests (37 passed; 1 PostgreSQL-only concurrency test skipped on SQLite); the answer-race test passed separately on isolated PostgreSQL. TypeScript, migration consistency, Django system checks, and diff checks passed. Shared AI-generation cost ownership, remaining policy details, hosted/provider behavior, and production acceptance are not established by these local checks.

### 12. Phased delivery and integrated verification

- [ ] Keep delivery in the brief's numbered order; complete the persistence foundation before broad feature rewrites.
- [ ] For each change record the reproduced issue, files changed, checks run/results, and remaining limitations; distinguish source inspection from runtime verification.
- [ ] Restore a repeatable local/staging test environment with isolated data and configured dependencies; missing tooling is a blocker, not a passing check.
- [ ] Run integrated signup/verification/approval, hierarchy/upload/read, bank generation/practice, results/analytics, chat/flashcards, milestones/credits, and battles regressions as their phases land.
- [ ] Re-run the staging redeploy persistence test after schema/storage/job changes; preserve backup and rollback evidence before production rollout.
- [ ] Keep this checklist and the persistence runbook current and give concise progress reports without claiming unverified whole-app completion.

## Decisions and external evidence still needed

These questions do not block the local phase 1 safeguards. They must be resolved before the affected feature or deployment is declared complete.

| Decision / evidence | Needed before |
| --- | --- |
| Render backend and Neon PostgreSQL confirmed by user; exact production/staging service, branch, database, frontend, media, Redis, worker and scheduler identities still required. | Live deployment verification and migration rollout. |
| Backup ownership, retention, restore target, and acceptable recovery point/time; successful isolated restore evidence. | Persistence completion and production rollout. |
| Class-code delivery timing and pending applicant visibility/privileges. | Final class-head registration/approval behavior. |
| Intended sender/domain/provider and accessible test inbox; actual message delivery evidence. | Email verification completion. |
| Theory question counts; mock scope; formal assessment rules; repeat policy when eligible banks are exhausted. | Question bank/assessment acceptance. |
| Approved milestone catalogue and thresholds. | Milestone implementation acceptance. |
| Credit allowances, action prices, timezone, rollover, expiry/cap, purchases, inactivity/plan change rules, and shared AI cost ownership. | Ledger/scheduler behavior acceptance. |
| Competition late-join/disconnect/host-departure rules if not already specified by the product. | Battle lifecycle acceptance. |

## Verification log

| Check | Result |
| --- | --- |
| Git baseline/status; framework and source configuration inspection. | Completed read-only; existing changes recorded above. |
| Local tool versions and installed JS package metadata. | Completed; isolated Python test environment added. Full backend runtime, ESLint, and Playwright remain unavailable/unverified. |
| Sanitized frontend/backend `.env` alignment. | Completed without connecting to providers or printing credentials. |
| Focused production DB guard, redacted report and migration-preflight checks. | Final isolated suite: **43 tests passed** on Python 3.14.4, Django 6.0.4. No project dotenv or remote services were loaded. Initial 9 mock-isolation errors were corrected before the final pass. |
| Shell release failure behavior and Blueprint ownership. | Passed using fake Python/package commands under Git Bash; no real migrations/install/build were executed by these tests. |
| `python -m compileall -q backend`; `git diff --check`. | Both passed. Compilation does not establish application startup or migration validity. |
| Existing CI workflow. | Updated with isolated integration dependencies, disposable PostgreSQL, TypeScript and frontend regressions under Python 3.12 / Node 20. Not executed remotely. |
| Account/recovery integration tests. | 36 account/email/password and 19 recovery tests passed on isolated PostgreSQL 18.3. Fresh migrations and concurrent approval/reset behavior exercised. |
| Frontend checks. | TypeScript, 16 permission/session tests, and 8 browser journeys passed. Browser tests use simulated localhost API responses; PostgreSQL integration tests separately verify real backend behavior. |
| Full backend suite. | Not run; remaining feature dependencies and phases are outstanding. |
| Production DB/storage inspection, email/provider checks, deploy/redeploy, backup/restore. | Not performed. |

## Previous local verification checkpoint

On 2026-10-13, the complete frontend production build passed with TypeScript errors enforced (47 static pages generated). The build used a loopback test API URL; deployment must build with the intended environment. Local checks total 122: 43 persistence, 36 account/email/password, 19 legacy-transfer, 16 frontend guard/session, and 8 browser journeys. Browser fixtures simulate the API, and the backend integration suite separately uses PostgreSQL 18.3. No remote CI, Render deployment, Neon mutation, inbox delivery or backup/restore is claimed.

## Previous checkpoint — 2026-10-15

The user confirmed that content must be visible only to its own class. Core class ownership and API restrictions are implemented in the working tree; see [CLASS_ISOLATION_RUNBOOK.md](CLASS_ISOLATION_RUNBOOK.md) for the exact coverage, adoption procedure and remaining privacy work. New ownership columns are additive. Existing ownership is never guessed; a validated manifest is required. The release preflight blocks unassigned historical content. No live migration, data assignment or deployment was performed.

This checkpoint also closes foreign references in quiz selection/history, flashcards, schedules and curriculum recommendations; restricts reprocessing to authorized owners/heads; repairs actual Topic versus legacy submodule selection; and removes the shared frontend curriculum cache. Missing slide IDs now fail before flashcard credit reservation. None of these changes constitutes full assessment, credit or AI lifecycle acceptance.

Executed checks on the final functional code:

| Check | Result |
| --- | --- |
| Disposable PostgreSQL account, recovery and content suite | **108 passed**: 36 accounts, 19 credits/recovery, 23 content integrity, 27 class access and 3 upload validators. Migration execution, adoption dry-run/apply/replay, class changes, foreign reads/writes, AI prechecks and existing concurrency regressions are included. |
| Pure persistence/configuration/preflight suite | **45 passed**, including release refusal before and after schema adoption when content is unassigned. |
| Frontend session/permission regressions | **16 passed**. |
| Headless browser journeys | **12 passed** with isolated localhost API fixtures. |
| Frontend production build | Passed with TypeScript checking; 47 static pages generated. |
| Migration/model consistency | `makemigrations --check --dry-run --settings=tests.integration_settings`: no changes detected. |
| Python compilation and diff whitespace check | Passed. |

Total: **181 distinct automated tests passed** in these suites. The 50 focused content tests also passed separately on SQLite and are not counted twice. CI was updated but not run remotely. Test PostgreSQL is dedicated to loopback port 55432; project dotenv was never loaded by Django checks. Provider delivery, actual file conversion, hosted deployment/redeployment and backup restoration remain unverified.

Next: finish private original/derived file delivery and the remaining class-access route audit, then rehearse explicit historical ownership adoption on a restored staging copy. Public Cloudinary URLs remain a blocker: filtering API responses does not protect an already-known URL. Tracker count stays **5/20 locally verified, 5 in progress, 10 pending; no production sign-offs**.

## Previous private-media checkpoint — 2026-10-16

Continued from the private-media work saved the previous day in `C:\Users\USER\emby`. Migration `0007_private_media_assets` adds a durable class-owned registry. New main/generic/standalone uploads and rendered pages request authenticated storage; API responses issue expiring links, and workers obtain fresh links when running. See [PRIVATE_MEDIA_RUNBOOK.md](PRIVATE_MEDIA_RUNBOOK.md) for exact coverage, migration/rollback requirements and the provider acceptance plan.

Community posts/replies/likes, past-question import/status, analytics labels/counts, dashboard caches and both battle HTTP routes now check class/source access. The alternate battle route has a direct regression test. These changes do not establish full competition, assessment or analytics correctness. Known outstanding routes include legacy steeplechase CRUD/spot-practice, administrative content access and asynchronous results.

Readers renew private URLs while preserving the selected page, clear displayed content on denied access, cancel stale loads/polling and remount after known account/class changes. Material opens recheck access. Saved-page reading no longer waits for the optional video-suggestion request. Standalone conversion can no longer report success after a page-storage failure; signed URLs are omitted from extraction/conversion failure messages. Durable jobs, automatic retry/idempotency and full browser-state isolation remain separate work.

Executed local tests:

| Check | Result |
| --- | --- |
| PostgreSQL account, recovery, content and class suite | **152 passed** in the combined run. This included the original 16 private-media tests. |
| Final focused private-media suite | **19 passed** after adding extraction-log redaction, safe deck-download failure and failed-page-storage tests. The first 16 overlap the combined run: **155 distinct backend tests**, not 171. Provider/converter calls use fixtures. |
| Backend breakdown | 36 accounts, 19 credits/recovery, 23 content integrity, 27 class access, 3 upload validators, 9 community, 19 related-class routes and 19 private media. |
| Persistence/configuration/release suite | **46 passed**, including release refusal while private-media adoption is incomplete. |
| Frontend session/permission regressions | **16 passed**. |
| Headless browser journeys | **17 distinct passed**. The expanded run passed 16; the final material test initially matched both the app alert and Next's route announcer, then passed with a specific locator. Earlier reader fixtures omitted required file_type and were corrected before their passing run. No application errors were concealed by these fixture fixes. |
| Migration/model consistency | No changes detected with isolated settings. |
| Python compilation and tracked diff whitespace | Passed after the final backend fixes. |
| Frontend production build | Passed with TypeScript checking and 47 static pages generated. The first attempt could not fetch the existing Google Fonts inside the network sandbox; the approved network-enabled retry passed. The API target was explicitly loopback. |

Total: **234 distinct automated tests passed**. Do not double-count focused reruns. Local browser-server shutdown required stopping only the test server processes after test completion. The dedicated PostgreSQL cluster was stopped after verification. CI now includes the community, related-class and private-media suites; remote CI was not run.

No live Neon data, Cloudinary assets or Render services were changed. Historical public URLs still need explicit private adoption and provider revocation; the release gate intentionally blocks unresolved storage. Existing source bytes are preserved. Actual file conversion, email inboxes, provider restrictions, deployment persistence and restore/redeploy acceptance remain unverified.

Next local work: finish the spot-practice/admin/asynchronous class-boundary audit, then repair durable upload/extraction dispatch and recovery. External acceptance still needs a restored staging database and verified storage identities. Tracker remains **5/20 locally verified, 5 in progress, 10 pending; 0 production sign-offs**. This checkpoint advances items 7–9 without marking their remaining requirements complete.

## Previous access-control checkpoint — 2026-10-16

The user confirmed that approved Steeplechase and Histology catalogue questions should be shared across classes. The implementation distinguishes explicitly published catalogue questions from private course-linked questions. Migration `0008_explicit_shared_practice_catalogue` adds a default-false publication flag, forbids shared entries with class sources and protects private source relationships against deletion. No existing records are automatically published. The runbook includes staged publication through `import_stations --publish-shared`, an inspectable dry run and protection against overwriting class questions or purging questions referenced by attempts or unanswered sessions.

Practice selection/counts, legacy station reads, answers, completion, results, history and practice analytics now enforce access to all session questions. Old sessions that contain foreign, missing or withdrawn questions are hidden without deleting their records. StudyProfile responses filter foreign course references while preserving saved preferences. Student catalogue writes are denied.

Administrator API routes, class-head review, notification recipients, frontend entry and Django's administrative site now use one platform-administrator policy. Staff alone does not grant global privileges. Active superusers and active accounts with the platform-admin role qualify; generic CRUD retains per-model permissions, and Django's site still requires staff status. This is an intentional privilege change and must be checked against the intended administrator accounts before rollout.

The live battle socket now requires current class/source access and host/participant membership. It rechecks account status, membership and token validity before actions and broadcasts. Tests cover foreign users, invalid/expired credentials, class changes, removed participants and malformed messages. The HTTP processing-status routes were inspected and already scope their queries by class. Battle scoring/timing/reconnect and notification-connection lifecycle still need their own acceptance work.

Private course-linked station images still use legacy URL fields and are outside the existing `check_private_media` inventory. Public file revocation, historical ownership/storage adoption and provider acceptance remain required. The new catalogue migration/publication has not been applied to Neon. No Render deployment or real provider calls were made.

Executed verification:

| Check | Result |
| --- | --- |
| Combined disposable PostgreSQL suite | **196 passed**: 47 account tests (including 11 new administrator tests), 19 credit/recovery, 23 content integrity, 27 class access, 3 upload validators, 9 community, 19 related-class, 19 private media, 22 practice access/import and 8 battle socket tests. |
| Persistence/configuration/release tests | **46 passed** without external services. |
| Frontend session/permission tests | **18 passed**, including the platform administrator guard. |
| Account/admin browser journeys | **10 passed** against isolated localhost fixtures, including staff denial and nonstaff platform-admin access. The 9 previously verified content/reader browser tests were unchanged and were not rerun in this batch. |
| TypeScript and production build | Both passed; build generated 47 static pages with a loopback API target. The sandbox initially blocked existing Google Font downloads; the approved network-enabled build passed. |
| Model/migration consistency | No changes detected under isolated settings. |
| Python compilation and tracked diff whitespace | Passed. |

This batch ran **270 distinct automated tests** across these suites. The retained checkpoint total is **279**, including the 9 unchanged content/reader browser tests from the previous checkpoint. Focused SQLite and PostgreSQL reruns overlap these tests and are not added again. CI now includes the practice and socket suites; remote CI was not run. Browser server shutdown required stopping the test server after all ten tests had passed.

The final **8-test socket PostgreSQL rerun passed** after adding explicit empty-token rejection. This is overlapping coverage, not eight additional tests.

All changes remain local in `C:\Users\USER\emby` and are visible in VS Code. Tracker status remains **5/20 locally verified, 5 in progress, 10 pending; 0 production sign-offs**. Next work is private station-image adoption, notification connection review and durable upload/extraction recovery; staging acceptance still requires verified database/storage targets and restored historical data.

## Latest reading checkpoint — 2026-10-17

Completed the scoped local acceptance for item 9. Both readers and the worker now use real PDF/PPT/PPTX/DOCX conversion. The standalone converter no longer deletes page images before upload, and on-demand rendering no longer reports skipped uploads or artificial text-only pages as a completed document. Originals are preserved and intermediate files are cleaned after use.

Course reading now has recoverable content failures, immediate ordered page-position saves, saved-page reopening, server-validated page bounds and expanded-image zoom. Page changes no longer resubmit accumulated study minutes. A failed saved-position lookup cannot let the background timer overwrite the old position; lookup and write failures each support retry. Optional video/breadcrumb services do not prevent reading. Standalone readers recover from list/load/status/image errors and report download failures, with reauthorization before downloads. Library entry pages reset on session/class changes and show request failures separately from empty libraries. Old chat/resource responses cannot write into another document's reader store.

Executed verification:

| Check | Result |
| --- | --- |
| Real-format rendering plus reading API suite | **14 passed** under isolated SQLite settings: 6 rendering tests (including three-page PDF, DOCX, PPTX and binary PPT fixtures) and 8 reading tests. Checks include ordered nonblank pages/text, unchanged source bytes, cleanup timing, invalid progress, cache reuse and failed-page storage. |
| Disposable PostgreSQL reading/access regression suite | **77 passed**: 8 reading, 19 private-media, 23 content-integrity and 27 class-access tests. Only localhost port 55432 was used; the cluster was stopped afterward. |
| Content/reader browser journeys | **24 distinct passed**: the clean 22-test run passed, then the final 2 library-entry tests passed after those entry-page repairs. APIs use isolated localhost fixtures; no real account or storage provider is exercised. |
| Production build and strict TypeScript | **Passed**, including 47 generated static pages. The API target was localhost. Existing Google Fonts were downloaded with approved network access. |
| Migration consistency | No changes detected with isolated settings. This reader batch adds no migration. |
| Python compilation and tracked diff whitespace | Passed. |

This batch verifies **107 distinct automated tests**: 83 backend plus 24 browser tests. The 8 reading tests run on both database engines are counted once; earlier partial/rerun results are not added again. Prior account, credit, persistence and guard totals are not presented as freshly rerun here.

Verification corrections are retained honestly: an initial chat test matched a title without its displayed prefix; the processing-failure fixture initially failed an extra development-mode load instead of the status poll. Those fixtures were corrected. An intermediate dev run produced a malformed generated route file and missing application routes; its cache was preserved at `.next/dev-reader-interrupted-20261017`, a clean run passed all 22 checks, and the final production build regenerated valid route types. The library navigation test was given an explicit destination wait for cold compilation and rerun with approved network access after blocked font requests; both final entry tests passed. Windows test-server processes were stopped only after completed checks where teardown waited; the interrupted invalid-cache run was stopped explicitly and is not counted as passing.

CI now installs LibreOffice for the real-format fixtures and includes reading tests in its PostgreSQL suite. Remote CI has not run. See [READING_REPAIR_RUNBOOK.md](READING_REPAIR_RUNBOOK.md) for exact scope, reproduction and hosted acceptance. Precise study-time analytics, offline/multi-device persistence, durable processing retries, OCR, full-deck chat persistence and resource generation remain separate unfinished items.

All changes are saved directly in `C:\Users\USER\emby` for VS Code. No production deployment, Neon migration, Cloudinary change or live AI operation was performed. At this checkpoint the tracker count was **6/20 locally verified, 4 in progress, 10 pending; 0 production sign-offs**. Historical ownership/storage adoption and Render/Neon staging acceptance remain open in parallel.

## 2026-10-17 checkpoint: item 10, complete extraction and OCR

Continued directly with item 10. A shared extractor now processes all native and scanned pages, using the reader's real Office-to-PDF page boundaries. Word tables, grouped PowerPoint shapes, native headers with scanned bodies and pages after the third are retained. The 15,000-character prefix limit and first-three-images vision fallback were removed. Every page carries a success, blank or failure result; a document report identifies missing pages and the original source hash. OCR uses local PyMuPDF/Tesseract language data, with no changes to AI providers or keys and no paid provider calls during verification.

Partial text no longer becomes a completed question-bank job or partially published search index. Legacy caches are rebuilt from their original source before these operations. Failed indexing preserves old rows without advertising an incomplete index as complete. Rendering preserves previously recovered OCR and saved resources. Main and standalone readers keep original page images visible while reporting text failures. Course uploaders/class heads have a retry action using the existing processing endpoint; student permissions remain enforced. Standalone decks now store per-page text and a coverage report through additive migration `0009_deck_text_extraction`.

Executed evidence:

| Check | Result |
| --- | --- |
| Real-document extraction | **12 passed**: native text beyond 15,000 characters, all five scanned pages, mixed documents, failed-page continuation, blank/unreadable distinction, real DOCX/PPTX/PPT contents, corrupt/encrypted/unsupported files and safe download failures. |
| Integration and URL-safety checks on disposable PostgreSQL | **20 passed**: 19 extraction integration tests plus one focused private-media error test, including the additive migration. Only localhost port 55432 was used; it was stopped afterward. |
| New browser journeys | **4 passed**: named missing pages, retry failure then queue/refresh recovery, authorization, unchecked legacy caches and standalone partial-extraction visibility. APIs were isolated fixtures. |
| Production build / strict TypeScript | **Passed**, with all 47 static pages generated and the API set to localhost. |
| Migration consistency / Python compilation / diff whitespace | **Passed**. |

This batch has **36 distinct automated checks**. Earlier partial/repeated runs and completed item 9 checks are not added again. An initial OCR assertion required whitespace normalization; actual words were retained. A sandboxed production build could not fetch the existing Google Fonts; the approved network rerun passed. Browser servers were stopped only after every assertion passed to finish Windows teardown. CI now installs English OCR data and includes the new extraction suites; remote CI has not run.

See [EXTRACTION_REPAIR_RUNBOOK.md](EXTRACTION_REPAIR_RUNBOOK.md) for setup, evidence and limits. Complete coverage means every page was processed, not guaranteed character accuracy. Representative scans, handwriting, diagram meaning and other recognition limits still need human acceptance. Render language-data availability, production migration 0009 and hosted original-file checks remain unverified. Durable upload retry, full-source chat/resources and complete question-bank quality remain their own open items.

Current tracker count: **7/20 locally verified, 4 in progress, 9 pending; 0 production sign-offs**. All changes are in the existing VS Code project at `C:\Users\USER\emby`. No production database or storage was modified and nothing was deployed. **Continue next at item 11: durable source-grounded question banks.**


## 2026-10-18 checkpoint: item 11, curriculum-slide question banks

Continued the unfinished generation repair and implemented the user's confirmed target of **15 MCQs: 5 easy, 5 medium, 5 hard**. Theory retains its existing additional pool of 10 (2/4/4); the user did not request a theory policy change. This checkpoint adds new work rather than repeating completed reader/OCR repairs.

Generation requests now persist before Celery dispatch. Expiring leases and source/job locking prevent duplicate workers and expired workers from publishing. Recovery retains broker-failed requests, resumes valid shortfalls, bounds retry cycles and reports exhausted jobs as failed. A forced request cannot steal an active lease. The old synchronous generation endpoint now queues a durable request, and the stuck-job repair command no longer declares completion from one question. No student credits are debited by this background path; shared generation-budget policy remains under item 18.

Each accepted generated question has a verified source-page quotation, valid answer/options or theory rubric, difficulty and current bank version. The fingerprint includes the original file hash, full extracted text, source/class/hierarchy identity and generation configuration. Source replacement preserves historical question rows while excluding stale rows from new selections. Invalid or ambiguous output does not fill a numeric quota. Page-labelled source windows span the document, and the UI reports pages actually cited rather than claiming every topic was assessed.

Review-flagged rows are held outside practice. A Django administrator can explicitly confirm a human review of the medical claims, answer and source evidence; the action validates current provenance/structure/quota and logs who performed it. Only reviewed generated document questions enter new formal selections. This does not certify medical correctness or complete the broader formal-assessment workflow.

The course reader shows separate bank progress, actual counts, review holds, source-page coverage and authorized retry controls. Status/queue failures do not prevent reading. Legacy unverified AI banks remain stored but are excluded from new selection; an authorized request starts a new verified bank with the 15 target. Existing manual and past-question paths remain available.

Executed evidence:

| Check | Result |
| --- | --- |
| Final bank suite on disposable PostgreSQL | **35 passed**, including two real row-lock races, late/stale workers, same-text original-file replacement, versioned retry, broker failure, rollback, preserved partial batches, exact 5/5/5 quotas, invalid quotations/answers/rubrics, review gating, source-window coverage, the 50-to-15 upgrade and permission checks. Providers and broker calls were mocked. |
| Affected class-access and extraction/worker regressions | **31 passed**: 27 class-access checks plus the four worker integrations changed by durable dispatch. Together with the final bank suite, this is 66 distinct backend tests. |
| New reader bank journeys | **2 passed**: 5/5/5 display, review/coverage reporting, failed retry then successful refresh, reading during failures, and absence of generation controls for students. Localhost API fixtures only. |
| Strict TypeScript / migration consistency / tracked diff whitespace | **Passed**. No production build was rerun for this checkpoint. |

Total: **68 distinct automated tests**, not 68 resolved issues. Overlapping intermediate runs are not added. The existing status test was then extended and passed on isolated in-memory SQLite to verify that withdrawing a question for review changes the displayed bank back to partial and recalculates progress; that focused rerun is not counted as an additional test. One regression run initially failed three class-isolation tests because their placeholder questions defaulted to unverified AI content; those access-only fixtures are now explicitly manual, and the final affected run passed. Browser assertions passed before Windows dev-server teardown waited; only the identified test-server processes were stopped, after which Playwright exited successfully. The local PostgreSQL cluster was stopped after verification.

New additive migrations are `learning/0007_question_generation_leases`, `learning/0008_bank_source_references` and `curriculum/0010_bank_source_references`. CI includes the bank tests on disposable PostgreSQL; remote CI has not run. No production database, storage, AI provider, deployed service or user credit balance was changed. Files are saved in `C:\Users\USER\emby` for VS Code.

**Item 11 is still in progress**, so the completed count remains **7/20**. The next local step is an explicit source association and generation/reader integration for the separate standalone `SlideDeck` upload model, which currently lacks curriculum hierarchy fields. Do not connect models by coincidentally equal IDs. The course-slide bank implementation above is tested and should not be restarted. Hosted Render/Neon acceptance also needs the additive migrations, an approved recovery scheduler, a real worker/broker restart exercise and representative provider outputs. The existing Render blueprint has no Beat service; enabling its other scheduled credit jobs also needs the item 18 review.


## 2026-10-19 checkpoint: item 11 standalone integration completed locally

Continued the standalone work already started, without redoing the completed course-bank implementation. Standalone decks now have a stored one-to-one curriculum source association. The reader lets the authorized uploader or class head select a course and module, validates ownership/ancestry on the server, reuses existing assets/pages/text and queues the same durable bank. The target remains the user's **15 MCQs, 5/5/5**. No subject or class is guessed from a matching ID. Completed processing is required before assignment; ordinary reading remains available during setup or provider failures.

New endpoints expose setup/status and accept explicit assignment/retry requests. Repeated or racing requests reuse one source and one job. Students may inspect their class's bank, but cannot assign or retry. Foreign classes, foreign assets, mismatched parents, arbitrary association IDs and reassignment are rejected. Source fingerprints include the standalone source/manifest/page text; changed documents reject stale workers and refresh their canonical cache on authorized retry. The reader filters modules by course, handles request failures, restores the saved association after refresh and shares the existing bank progress/review UI.

Deleting a deck removes its linked source/job while preserving question rows used by history; those detached generated rows are excluded from new sessions. The unrelated same-ID curriculum slide is retained. Legacy provider-prefix deletion was removed from the deck deletion action; private assets remain in the registry pending the separate orphan-reconciliation work under item 8.

Executed verification:

| Check | Result |
| --- | --- |
| Standalone integration and affected bank regressions on disposable PostgreSQL | **47 distinct tests passed**: the combined 46-test run passed, followed by the final additional cross-class asset/rollback test. This comprises 12 standalone tests and 35 bank regressions. Three concurrency tests use real PostgreSQL row locks across these suites. Broker/provider operations use mocks. |
| Browser journeys | **4 distinct passed**: two existing bank journeys affected by the shared component change, plus standalone assignment/failure recovery/refresh and student read-only setup. |
| Strict TypeScript | Passed. |
| Migration consistency / Django system checks / tracked diff whitespace | Passed. Migration `curriculum/0011_standalone_bank_source` adds the association only. |

One initial browser run passed three tests but timed out selecting the course dropdown in the fourth. The control was present in its accessibility snapshot. The test now selects the combobox by accessible role/name, and that journey passed on rerun. The failed run is not reported as a fully passing suite. Windows browser-server teardown again required stopping only the identified test-server processes after assertions finished; the successful rerun then exited zero. The disposable PostgreSQL cluster was stopped. No production build was rerun because the scoped TypeScript and browser checks covered this change; no production or paid provider operation was performed.

Item 11 is now **locally verified**. Tracker total: **8/20 locally verified, 4 in progress, 8 pending; 0 production sign-offs**. CI includes the standalone tests, but remote CI has not run. Hosted acceptance still requires the additive migrations, an approved recovery scheduler, a real worker/broker interruption exercise and representative provider/medical-review samples. Standalone upload conversion itself is still synchronous and is part of item 8's outstanding durable upload lifecycle, not a claim made by this bank repair.

All edits are in `C:\Users\USER\emby` for VS Code. **Continue next with item 12: single-deck practice.** Check all ordinary quiz entry points against the saved eligible bank, exact requested difficulty, available-count feedback, the 20-question attempt ceiling and server answer/scoring behavior. Do not silently borrow another difficulty to make five available medium questions look like twenty.


## 2026-10-19 — single-deck practice verified locally (item 12)

New practice attempts require one authorized deck and 1–20 MCQs at the exact selected difficulty. Availability is displayed before starting; a shortage returns its actual count and offers a smaller quiz explicitly. No AI generation or credit spending occurs during selection. Missed-question review is constrained to the same deck/difficulty. The bank target remains 15 MCQs (5/5/5).

Private snapshots preserve each attempt's question versions and answer key. Nested responses do not reveal answers while active. Browser refresh restores selections; failed saves are visible, pending saves block submission, and stale attempt responses are ignored. Flags can be saved/removed idempotently. The server rejects late/invalid/foreign answers and marks against the original saved key. A single transaction records the score and completion effects; concurrent/repeated submissions return the same result. Completion failures roll back before retry. Results show right/wrong/unanswered and correct answers without claiming nonexistent flashcard creation.

Both reader entry points and study sessions now use saved single-deck practice. The reader Quiz tab does not generate temporary MCQs or put the saved-practice link behind the premium resource screen. The unused legacy unscoped creator returns 410 with a link to the current flow; existing history remains available. Migration 0012 adds private snapshots and preserves attempts when a source slide is deleted. This does not claim arbitrary hierarchy/user/question deletion has been repaired.

Verification: **90 distinct backend tests passed** across isolated PostgreSQL runs: 16 practice tests, 27 class-access regressions, and 47 bank/standalone regressions. The first combined run passed 86; subsequent tests added same-class deck exclusion, attempt ownership, atomic rollback and flag removal. One new rollback test initially lacked a stats fixture; the fixture was corrected and that test passed. The final added active-result guard also passed its focused rerun. Three distinct browser journeys passed: shortages/current availability; failed save, reload and correct-result review; reader/session entry without question generation. Strict TypeScript, migration consistency, system checks and diff whitespace checks passed. CI includes the new practice suite; remote CI has not run.

The browser results journey initially timed out during cold local route compilation and passed unchanged on rerun. The entry-point test caught and led to fixing the reader's premium gate; a later local Next run returned an intermittent 404 for the existing reader route, and restarting the test server made the same assertions pass. Failed runs are not counted as successful suites. Windows teardown required stopping the identified owned Next server processes after tests ended. No production build, provider call, deployment or production migration was performed.

Tracker: **9/20 locally verified, 4 in progress, 7 pending; 0 production sign-offs**. Changes are saved in `C:\Users\USER\emby` for VS Code. Next is **item 13**, retaining broader mock/formal policy questions rather than silently inventing rules. Hosted acceptance for item 12 still requires migration 0012 and real student/class/reconnect/deadline journeys, as detailed in PRACTICE_REPAIR_RUNBOOK.md.


## 2026-10-19 — assessment answers and timing, first item 13 checkpoint

The user confirmed mock scopes of course/module/submodule. Formal assessments are created by class heads using manual questions or AI assistance. Heads choose counts and duration up to 50 MCQs, 5 theory questions and 150 minutes; only one attempt is allowed per student. These decisions are recorded in ASSESSMENT_REPAIR_RUNBOOK.md and must not be asked again. Formal authoring/publication and one-attempt enforcement are still to be implemented; the old student-created formal path is not certified by this checkpoint.

Repaired the shared answer path: theory text now reaches the backend, saves with a server timestamp, reloads, and can be cleared explicitly. MCQ/theory payloads are validated separately, client scores are ignored, and writes at or beyond the deadline or after submission are rejected. Private snapshots are respected when present. The browser debounces and serializes written saves, exposes failures/retry, flushes before manual submission and protects newer drafts from stale save responses. Cleared answers are not counted as answered. The Submit confirmation can open during the blur-triggered save, while final submission waits for it.

Timers now calculate elapsed wall-clock time rather than assuming one callback per elapsed second. Visibility changes refresh the display. Automatic submission fires once per mounted timer and exposes request failures rather than falsely reporting success.

Verification: **22 backend tests passed on isolated PostgreSQL**, comprising 6 new assessment-answer tests and 16 affected practice regressions, including the concurrent-submit test. The earlier SQLite run passed 21 and skipped that PostgreSQL-only test; the later PostgreSQL run exercised all 22. **3 state tests passed** for background timer catch-up, stale written-save protection/empty answers, and failed automatic submission. **2 distinct browser journeys passed**: the existing MCQ save/reload/results journey and the new written-save failure/retry/reload/clear/submit-order journey. The written journey initially caught the blur/Submit interaction and passed after the UI fix. Strict TypeScript passed after regenerating a damaged Next-generated validator; the invalid generated file was retained under an ignored backup filename and source validation was not relaxed. Diff whitespace checks passed. CI includes the added tests; remote CI has not run.

No production build, deployment, provider grading/generation call or Neon operation occurred. The isolated PostgreSQL cluster and the identified test server processes were stopped after verification. Windows browser teardown required that targeted server cleanup as in earlier checkpoints.

Count remains **9/20 locally verified; 5 in progress; 6 pending**. Item 13 is in progress, not completed. Next: implement the confirmed mock scope/selection rules, class-head formal drafts/publication and protected answer keys, database-enforced single attempts, saved rubric grading, idempotent mock/formal submission and truthful results. Do not redo the completed answer-saving batch unless a regression warrants it.

## 2026-10-19 — private formal papers, manual authoring and single attempts

Continued item 13 without repeating the completed answer-saving repair. Approved current class heads now have a `/quiz/assessments` interface for private manual drafts, MCQs with keys/explanations, theory questions with model answers/rubrics, reopening saved drafts, choosing counts/duration and publishing. Server validation enforces at most 50 MCQs, 5 theory questions and 150 minutes, exact published counts, valid options and rubric totals. Revision checks reject stale saves/publishing. Published content/settings cannot be changed through this API. The practice landing and old formal selector link to the new class-paper flow; students cannot submit their own formal configuration and no premium/certificate claim blocks or misrepresents it.

Papers keep questions outside the general bank. Migration 0013 adds private papers, protected attempt references, one `(user, assessment)` constraint and snapshot-only response identifiers. The original response relation remains for practice/history. A locked paper provides start/resume with the same deadline and a permanent single attempt. Cross-class reads/writes, unapproved heads, edited timing, duplicate starts and student deletion are rejected. Removing source courses/decks cannot erase or reset these new independent papers/attempts. No historical formal attempts were assigned invented paper identities.

Submission scores MCQs from saved versions and records the result, stats and completion event in one transaction. Repeat/concurrent requests return the same outcome; a completion-storage failure rolls back for retry. Heads can close new entries and release answers once all remaining active deadlines have passed or students have submitted. Existing attempts retain their time. Draft questions/keys never enter student paper listings, and active attempts never receive answer keys. Submitted students see their written responses, pending theory grading and controlled answer release. The legacy live-question grader/analysis is explicitly excluded from these snapshot papers so it cannot falsely mark them complete.

Verification: **65 distinct backend tests passed on isolated PostgreSQL**: the final combined run passed 64 (15 formal, 6 answer, 16 practice, 27 class access), and one added formal rollback/retry test passed separately. Concurrent start/submission and database uniqueness were exercised on real PostgreSQL. **3 state tests and 3 browser journeys passed**: existing practice save-failure/reload/results; head draft/save/reload/publish; student resume/submission/pending result/reopen. The initial new backend run exposed form-encoded revision strings in the test fixture; the fixture now uses the JSON numbers sent by the UI. Failed runs are not counted as passing suites. Strict TypeScript passed after normal Next route-type regeneration, migration consistency and diff whitespace checks passed. CI includes the formal suite; remote CI has not run.

Only local isolated services and browser API fixtures were used. No production migration, deployment, provider generation/grading call or Neon operation occurred. Browser assertions passed and their identified Next processes were stopped to finish Windows teardown. The test PostgreSQL cluster was stopped after checks. All source changes are saved in `C:\Users\USER\emby` for VS Code.

**Count remains 9/20 locally verified, 5 in progress, 6 pending; 0 production sign-offs.** Item 13 is still in progress because durable AI-assisted drafts, course/module/submodule mock assembly, saved-rubric grading/recovery and final combined results are unfinished. Continue with those gaps; do not rebuild the verified manual formal publishing/single-attempt workflow. See ASSESSMENT_REPAIR_RUNBOOK.md for the exact API behaviour and migration notes.

## 2026-10-20 — durable formal written grading and combined results

Continued item 13 from the saved manual formal papers. Submission now persists a grading job before dispatch. The grader uses each attempt's immutable question/model answer/rubric and stored student answer, validates every criterion and total, and preserves fractional marks. Invalid provider output remains a failed/retryable grade instead of becoming zero. Unanswered written questions receive zero without a provider call and remain in the final marks denominator. Combined percentages use correct MCQs plus written marks over all available marks, with provisional results clearly identified until completion.

Each worker must hold a current lease; duplicate or expired workers cannot overwrite results. Validated answers are checkpointed individually so retries retain completed marks. The durable job survives queue failure, missing acknowledgements and worker interruption. Automatic retries are bounded to three worker attempts per cycle; the owner can retry an exhausted job after a cooldown. A five-minute scheduled recovery sweep and explicit recovery command restore due jobs and earlier pending versioned formal submissions. Legacy mocks are not assigned fabricated historical rubrics. Provider calls do not hold database transactions open.

Migration 0014 adds grading jobs/private evidence and two-decimal score storage while retaining the old integer field's range. Finalization updates the existing completion event without another points/XP award. The result page now shows progress, retry failures, refreshed final marks and per-answer scores. Feedback/rubric details remain private until the head releases answers. Fingerprints and raw provider errors remain private throughout.

Verification: **79 affected backend tests passed on disposable PostgreSQL** (14 grading, 16 formal, 6 answer, 16 practice and 27 class-access tests). The 14 grading tests passed again after the final decimal-field range adjustment, including duplicate-worker concurrency, stale leases, checkpoint recovery, invalid grading, blank answers, fractional totals and release privacy. **Three distinct browser journeys passed across runs**: formal resume/submission, grading failure/retry/final result/released feedback, and practice save-failure/reload/results. The initial combined browser run passed two tests but timed out on practice results navigation; its trace showed a successful submit response with the local results-route request still unfinished. The practice test passed unchanged on its focused rerun. Failed runs are not counted as fully passing suites.

Strict TypeScript, migration consistency and diff whitespace checks passed. CI includes the grading suite; remote CI has not run. Browser assertions completed and only the identified owned Next processes were stopped to finish Windows teardown. The isolated PostgreSQL cluster was stopped. No production migration, deployment, Neon access or real grading-provider request occurred; local tests used mocked provider/broker calls. Real marking quality and hosted worker/scheduler recovery still require acceptance.

**Count remains 9/20 locally verified, 5 in progress, 6 pending; 0 production sign-offs.** The formal written-grading portion is now locally verified; the remaining item-13 work is AI-assisted private drafts and course/module/submodule mock assembly, submission and grading. All edits are saved in `C:\Users\USER\emby` for VS Code. Continue with those remaining gaps, not the completed manual publication, answer-saving or formal grading implementations.

## 2026-10-20 — course/module/submodule mock exams verified locally

New mocks now require an explicit authorized course, module or submodule. They use eligible saved questions at the exact difficulty and requested MCQ/written counts, with no fallback to another difficulty or scope. Availability is shown before starting and checked again at creation; shortages create no attempt and offer a smaller exam explicitly. Review holds, stale generated banks, structurally invalid questions, duplicate stems and contradictory source ancestry are excluded. Selection rotates topics and source files so one large deck cannot accidentally dominate an available smaller source. The existing configurator's 100-MCQ/10-written upper bounds and 1–180-minute timed/untimed options are retained for mocks, separate from formal-paper limits.

Migration 0015 records the original class for new mock snapshots and changes optional attempt curriculum references to SET_NULL. Ordered question/key/rubric and topic-label snapshots, plus snapshot-only answers, survive removal of the original course/questions. The original class and owner remain authoritative for access. Submission reuses durable saved-rubric grading and atomic completion, retains the existing mock points multiplier, includes unanswered questions, preserves fractional marks, and cannot award completion twice. Topic MCQ totals are calculated from persisted question/answer evidence. Results show explanations, topic totals, written answers and fractional grading after reload.

The new `/quiz/mock` page connects from the practice landing and old mock selector. It preserves the existing Premium presentation, supports catalogue pagination, rejects stale availability after scope changes, exposes request failures and lets students explicitly reduce a request after a bank change. Subscription/payment policy was not redesigned. No generation or debit occurs during selection.

Verification: **93 distinct backend tests passed across isolated PostgreSQL runs**: 79 existing grading/formal/answer/practice/class tests passed in the combined 92-test run; eight new mock cases initially failed on PostgreSQL's prohibition on locking nullable outer joins. Restricting the source lock to the source table fixed that issue. All 13 mock tests then passed; a final added ancestry/invalid-scope check brought the focused suite to **14 passing tests**, including concurrent submission and source-removal persistence. An earlier SQLite run exposed a fixture trying to reclaim an active generation lease; the fixture setup was corrected before these successful runs. No failed whole-suite run is reported as a complete pass.

**Four distinct browser journeys passed across runs**: new mock scope/availability/shortage/start; new mock explanation/topic/fractional-result/reload; existing practice save/reload/results; existing formal grading retry/release. The result journey caught a missing explanation render, which was fixed. The start journey twice reached a successful API response while local route compilation exceeded the navigation assertion window. Test setup now warms the attempt route without relaxing navigation/content assertions. A later local Next run returned an intermittent 404 for the existing mock page; after moving the generated `.next/dev` cache to the ignored `.next/dev-mock-check-backup-20261020` folder and regenerating route types, that journey passed. The final clean run used fallback fonts when Google Fonts requests were unavailable; visual font fidelity is not claimed by these functional checks.

Three assessment-state tests, strict TypeScript, migration consistency and diff whitespace checks passed. CI includes the mock suite; remote CI has not run. Only identified test-server processes were stopped to finish Windows teardown, and the isolated PostgreSQL server was stopped. No production migration, deployment, Neon operation or real AI grading request occurred. All edits are saved in `C:\Users\USER\emby` for VS Code.

**Overall count remains 9/20 locally verified, 5 in progress, 6 pending.** Within item 13, new scoped mocks and their results are now locally verified. Continue with durable AI-assisted private drafts, deeper evidence-based formal feedback and handling of historical attempts that lack original snapshots. Do not retrofit invented historical rubric versions or repeat the completed mock implementation.

## 2026-10-20 — private AI assessment drafting verified locally

Continued the remaining AI-authoring portion of item 13. Approved heads can select extracted documents from their own class, choose difficulty and generate only the missing slots in a saved formal paper. Each selected document contributes; page excerpts span the selected source where multiple slots are available. Existing manual questions are preserved. Suggestions include visible source titles, page numbers and verified quotations, and never enter the shared question bank.

Generation persists one validated suggestion at a time, with worker leases, bounded retries, queue redelivery, interruption recovery and a head retry after cooldown. A failed later question retains earlier suggestions. Duplicate requests/jobs, simultaneous workers and simultaneous apply requests cannot duplicate questions. Stale manual edits cancel outstanding work, late workers cannot overwrite the paper, and changed/missing source versions block apply. Generation never publishes a paper.

The editor supports source pagination, progress polling, reload/resume, retry, discard, source/answer/rubric review and explicit apply. Unsaved edits disable apply/retry and survive discard. Publishing a paper with generated questions requires explicit head review; editing clears the browser confirmation, and the backend records the final reviewer/time. Migration 0016 contains the job and review fields; no production migrations were run.

Verification: **45 distinct backend checks passed across isolated PostgreSQL runs**: the first combined 42-test run covered drafting, formal papers and grading; the final 15-test drafting run passed after adding three cases, bringing distinct coverage to 15 drafting + 16 formal + 14 grading. These include real row-lock concurrency for request/apply and competing workers. **Two browser journeys passed across runs**: existing manual drafting/publication and new AI generation/reload/retry/source review/unsaved-edit protection/apply/review reset/publication. The first AI journey failed on an exact label selector, while its captured page showed the correct existing field/value. A role/name selector corrected the test, and the complete AI journey passed on rerun. Failed whole-suite runs are not counted as passes.

TypeScript, route type generation, migration consistency and diff checks passed. CI now includes the drafting suite; remote CI has not run. AI and broker calls were mocked, so this verifies workflow and validation rather than real medical question quality. Browser checks used fallback fonts after remote font downloads failed. The identified owned test-server processes were stopped to finish Windows teardown, and the isolated PostgreSQL cluster was stopped. No Neon operation, production migration or deployment occurred. Changes are saved in `C:\Users\USER\emby` for VS Code.

**Overall remains 9/20 locally verified, 5 in progress, 6 pending; 0 production sign-offs.** AI-assisted private drafting is now locally verified within item 13. Next: deeper formal feedback and safe handling of historical assessments without original snapshots. Do not redo the completed new mock, manual formal, saved grading or AI drafting implementations.

## 2026-10-20 — assessment repair completed locally; pending analytics repair started

Closed the remaining item-13 implementation gaps. Released formal results now provide deterministic, question-linked guidance from saved keys, explanations, selected answers and rubric evidence. The report separates wrong from unanswered MCQs, identifies difficulty groups with too few questions, and lists exact written criteria requiring revision. Pending grades remain pending, and guidance is withheld until the class head releases answers. No extra AI analysis call or speculative diagnosis/prediction is introduced.

Older attempts without original question snapshots now have an explicit read-only history policy. Existing answers and stored marks remain available where they still exist, with marks labelled unverified. Today's edited question text/keys and old AI narratives are not misrepresented as original evidence. Write, submit, flag, delete and grading-retry endpoints reject these historical records; legacy grading/analysis tasks stop before provider work. Missing source rows do not hide an otherwise authorized historical record, while foreign-class source/parent checks remain. Already-deleted responses are not reconstructed.

Added `/quiz/history` with pagination, retry, ordinary resume/results links and separate historical-record links. Direct navigation to an old active attempt redirects to its historical record. A never-submitted record is clearly distinguished from a completed result.

Started pending item 14 with a repaired main analytics report. A single local-calendar evidence window includes today, excludes future rows, aggregates seconds before rounding and supports study-only activity. Versioned submitted attempts contribute directly from saved responses, independent of missing/duplicate events or corrupt cached scores. Historical assessments, pending written marks and self-rated flashcards cannot inflate objective accuracy. Known one-time completion events are deduplicated for reporting. Streaks use local evidence dates, trends use weighted counts and minimum sample sizes, and topic detail reflects the selected period rather than the lifetime cache. Switching report periods ignores late responses from the old selection.

Verification: **165 backend tests passed together on isolated PostgreSQL**, including 6 new feedback/history and 10 analytics tests, existing authoring/drafting/grading/mock/practice regressions, answer saving and class boundaries. The earlier SQLite run passed 62 tests and failed one new history fixture because its comparison statistics row did not exist; the fixture was corrected before the successful PostgreSQL run. **Three browser journeys passed in one run**: formal grading/release/guidance, history/direct legacy-resume redirection, and analytics study-only display/stale-period protection. Three assessment-state tests, strict TypeScript, route type generation, migration consistency and diff checks passed. CI includes both new backend suites; remote CI has not run.

No production migration, deployment, Neon access or live AI request occurred. Browser checks used fallback fonts after remote font downloads failed; identified owned test-server processes were stopped after assertions to complete Windows teardown. Source changes are saved in `C:\Users\USER\emby` for VS Code.

**Current count: 10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs.** Item 13 is now locally verified. Item 14 remains in progress because upstream event/counter concurrency, dashboard/header reconciliation, bank coverage and other feature producers still require work. Continue with those gaps, then the pending chat, resources/flashcards, achievements, economy and battles; do not reopen completed assessment implementation without a new defect. See ANALYTICS_REPAIR_RUNBOOK.md and ASSESSMENT_REPAIR_RUNBOOK.md.


## 2026-10-20 — activity delivery, study logs and dashboard consistency

Continued item 14 without repeating assessment implementation. Known one-time completions now use durable keys and a shared statistics-row lock, including detection of pre-migration completion rows. Replays do not repeat study, weak-area, achievement or XP effects. XP decisions persist zero awards as well as positive ones; local-day caps and concurrent requests preserve ledger totals and independently earned quiz points. Separate savepoints isolate failed reward/achievement writes from the completed student action. Invalid counts, times and metadata fail before event creation. Migration learning 0009 adds the request-key constraint and XP decision field without deleting historical records.

Reading and manual study now feed the evidence ledger atomically with their progress updates. The client provides stable IDs for authentication retries and accepts explicit IDs for manual retry. Manual logs are validated and retain their original implicit date when retried after midnight; reading/manual logs retain their non-XP policy. Short event durations carry forward before whole-minute cache increments. Streaks rebuild from accepted local-date evidence, including out-of-order records, and the refresh endpoint no longer counts an app visit as study. Self-rated flashcards no longer update objective weak areas.

Dashboard greeting figures/suggestions, the dashboard streak stat and weekly study data now use the same evidence as analytics. Changed or newly unauthorized cached greeting facts trigger a local replacement during the existing cache window without another provider call or credit charge. Historical daily minute totals are retained for a later controlled reconciliation; cache-only activity is not invented as evidence. Remaining profile/class statistics, lifetime weak-area caches, bank coverage and some feature producers still need work.

Verification: **119 distinct backend tests passed across PostgreSQL runs**, with 117 in the combined run and 36 in the final writer/reading run (including two additional cases). Tests cover simultaneous duplicate and distinct activity, concurrent reward/manual-log retries, caps, local dates, out-of-order streaks, stale counters, transaction rollback, reading logs and class boundaries. Ten Node client/session checks passed, including real Axios 401 replay preserving the request UUID. Strict TypeScript, migration consistency and diff checks passed. CI was extended but has not run remotely. No new browser run was needed for the request-metadata change; no browser pass is claimed for this batch.

Changes are saved in `C:\Users\USER\emby` and appear in VS Code. No Neon access, production migration, deployment or live AI call occurred. The isolated local PostgreSQL server was stopped after tests. **Overall remains 10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs.** Next: remaining profile/header/class and weak-area summaries, bank readiness/coverage, and a read-only historical reconciliation report before any reviewed cache repair. Do not redo the completed writer/dashboard work unless new evidence warrants it.


## 2026-10-21 — remaining progress surfaces, usable-bank coverage and historical audit

Continued item 14. Profile, roster, statistics and gamification streaks now use the accepted evidence set; serializer fields share a request-local read. Stats expose observed minutes, completed versioned assessments and authorized completed documents rather than stale totals. Header/sidebar refresh on navigation, return and activity, aborting superseded requests and guarding account identity. Weak-area APIs and recommendations use period-specific saved objective results with authorized ancestor rollup and minimum evidence; historical AI narratives are not recycled as advice.

Fixed the class analytics page reading the wrong roster response fields, which caused blank names and zero points/streaks. Added load retry and consistent local ranks. Counter serializer fields are read-only, and the client-callable arbitrary points endpoint now returns 403 while normal server awards remain. This is a targeted integrity fix, not a completion claim for the economy or achievements items.

Unified mock/deck selection and coverage validation for current source versions, review holds, question structure and source ancestry. Current MCQ bank coverage deduplicates stems within a source/difficulty while preserving exposure, and the analytics page shows coverage for both tiers even before activity or topic tracking. No generation/debit occurs for coverage reads.

Added the read-only audit_activity command for explicitly selected account IDs. It compares evidence and caches and reports duplicate/invalid/future records, missing completion events and historical assessments without snapshots. There is no apply mode. It neither recreates historical evidence nor adjusts points/rewards.

Verification: **137 distinct PostgreSQL backend checks passed across runs** (134 affected regressions together and three audit tests). Four browser journeys passed for free/Premium coverage, class analytics retry/schema and stale header-response isolation. Ten client/session checks passed. TypeScript, route type generation and diff checks passed; CI was extended but not run remotely. An initial SQLite run failed two fixtures that still expected cache-only weaknesses and malformed questions to count; valid persisted fixture evidence was added before the final passing run. Browser assertions passed before a long Windows teardown; only identified local test-server processes were stopped. Google font failures used fallbacks. No live providers, production migration/deployment or Neon access occurred.

Changes remain saved in C:\Users\USER\emby for VS Code. **Overall: 10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs.** Continue with image-practice summaries, remaining activity producers (planner/standalone reader), controlled historical reconciliation and production-size query acceptance. Do not repeat the completed profile/class/coverage repairs. See ANALYTICS_REPAIR_RUNBOOK.md.

## 2026-10-21 — Image-practice evidence and planner completion

Continued item 14 with saved image-round question versions, all-presented-item scoring, weighted per-mode accuracy, and report reconstruction independent of cached scores or completion-event duplication. Submission/completion locks preserve the first answer and completion time under retries and concurrency. Monthly allowance locking prevents spending the last free round twice. Historical image rounds without verifiable versions are labelled and excluded from accuracy while retaining authorized activity. No historical questions or rewards were rewritten.

Planner completion no longer turns an estimate into actual study minutes. Completion/activity writes are atomic, retries preserve timestamps, undo/redo cannot repeat rewards, direct edits cannot bypass the writer, and local calendar dates match analytics. Both feature completions trigger header progress refresh. Migration learning.0010 is additive and remains local only.

Image verification: 149 PostgreSQL checks passed after repairing two pre-existing frozen-clock fixture defects. Twelve client/session checks passed. The separate planner/class-access/analytics/audit run passed 48 PostgreSQL checks: 184 distinct backend checks across the two runs, including 23 new image/planner tests. TypeScript, migration consistency and diff checks passed; see ANALYTICS_REPAIR_RUNBOOK.md. No new browser run, remote CI, provider call, deployment or production migration occurred.

Overall remains 10/20 locally verified. Remaining item 14 work: standalone-reader/remaining producer acceptance, controlled historical reconciliation (including nullable WeakArea duplicates/legacy selectors), large-history and roster query-cost checks, and cross-feature browser acceptance. Continue there instead of redoing image-practice or planner repairs.

## 2026-10-21 — Standalone-reader resume and reading-time evidence

Added authorized per-student standalone-deck progress and durable checkpoint receipts, atomic time/activity writes, same-request retry protection, stale-replay position protection and short-session seconds. Ordinary students can save their own progress without upload permissions. No XP is awarded for reading. A new reader clock pauses while hidden/loading, caps suspension gaps, serializes saves and keeps unsent checkpoints in tab session storage. Saved positions never override navigation made during a delayed resume lookup; load/save failures expose retry. Account/class changes prevent writes under another identity.

Profile and analytics totals include authorized standalone reading, exclude inaccessible deck activity, recheck completion after page-count/processing changes, and count curriculum-linked documents only once. Migration curriculum.0017 remains local only. Sources are saved directly in C:\Users\USER\emby for VS Code.

Verification: 106 distinct PostgreSQL checks across 104- and 32-test runs, 18 client/session checks and three browser journeys across runs passed. The timed browser fixture was corrected to return pages for the visibility-triggered media refresh; this resolved its initial failure. TypeScript, route type generation, migration consistency and diff checks passed. Test servers/database are stopped. No live providers, remote CI, production changes or deployment.

Next: fix the course reader's older minute timer and failed-time-save handling; then controlled historical cache reconciliation (including duplicate nullable WeakArea rows/legacy selectors), history/roster query-cost checks and remaining cross-feature acceptance. Do not repeat standalone-reader work. Overall remains 10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs.


## 2026-10-21 — Course-reader seconds and failed-save recovery

Continued item 14. Course reading now counts visible, loaded-image time in seconds through the shared recorder, retains failed checkpoints for retry/reload, preserves manual navigation during a resume lookup and stops when access is revoked. Outdated saved positions are clamped before new time is recorded. The backend retains minute-client compatibility and historical whole minutes, carries new sub-minute remainders, atomically stores receipts/progress/activity, and prevents duplicate time or backward page movement from late retries. Reading awards no XP. Migration curriculum.0018 remains local only.


Verification: **98 PostgreSQL backend checks passed together**, including 11 new course-reader checks (two concurrency cases), existing reading/standalone-reader tests, activity writers, analytics, progress surfaces and related class isolation. **19 client/session checks and eight distinct browser journeys passed across runs.** The new browser coverage includes timed-save recovery after reload, hidden/loading-time exclusion, revoked-access cleanup and an outdated saved page after a document shrinks. Existing course position/retry and standalone timing/recovery journeys also passed. The first timed browser assertion incorrectly expected the whole initial checkpoint interval to count before the image loaded; it was corrected to verify the observed positive interval and exact payload replay. One rerun hit another development server's build lock, and the first isolated cold start exceeded its startup timeout; separate test build output and a longer startup allowance resolved those setup failures. These failed runs are not counted as passes. Google fonts used fallbacks, so no remote-font fidelity claim is made. Strict TypeScript, route type generation, migration consistency and diff checks passed. CI includes the new backend suite but has not run remotely.

The isolated PostgreSQL database and owned browser-test server were stopped. The user's separate Emby development server was left running. Changes are saved in `C:\Users\USER\emby` for VS Code. No Neon/Render changes or production migration/deployment occurred. Overall remains **10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs**.

Next: controlled historical cache reconciliation, nullable WeakArea duplicates/legacy selector review, production-size history/roster query costs and remaining cross-feature acceptance. Also define explicit handling for pending checkpoints whose source pages were removed before acceptance. Do not repeat the course/standalone reader timing work. See ANALYTICS_REPAIR_RUNBOOK.md.

## 2026-10-21 — Controlled historical reconciliation and legacy weak-area recovery

Continued item 14. New weak-area updates adopt one matching legacy row under the account lock and use a database-unique canonical node key. Other historical duplicates remain intact rather than being added together. Failed writes roll back adoption and activity; retries and backfilled timestamps cannot duplicate counts or regress last practice. Legacy practice selection, strongest/weakest helpers and revision reminders now use current-class saved-answer evidence, with specific child evidence taking precedence over a broader weak ancestor. Held, malformed and stale questions cannot enter legacy selection. Topic rollup now indexes node identities instead of repeatedly scanning the complete node list.

Added a separate time/streak reconciliation command that defaults to a read-only preview for one explicit account. Applying requires the exact reviewed fingerprint, recomputes under the activity lock and stores before/after values in an atomic receipt. Changed evidence, caches, membership or date reject an outdated plan. Replays return their prior receipt without overwriting new activity. Historical events, answers, rewards, points, rank and credits remain untouched; cache-only daily rows are retained and their previous counters preserved in the receipt. Reconciled accounts subsequently derive time/session caches from accepted evidence, including cross-day fractional time and zero-duration planner completions. The existing audit remains read-only and now distinguishes canonical from unkeyed legacy weak-area rows.

Verification: **217 distinct PostgreSQL backend checks passed across a 172-test regression run and a final 72-test run, with 27 overlaps.** Coverage includes duplicate and concurrent weak writes, valid weak-only selection, local-period thresholds, class boundaries, reminder evidence, read-only previews, exact-plan invalidation, concurrent repair/new activity, rollback, repeated cache drift and real quiz/image/planner completion after repair. An initial SQLite failure came from an old class-access fixture with unusable question fields; the fixture was corrected before the successful PostgreSQL runs. Migration consistency and diff checks passed. CI includes both new test modules; remote CI and a new browser run were not performed.

Additive migrations learning.0011 and learning.0012 remain local only. No live provider, Render/Neon access, production repair or deployment occurred. Changes are saved in C:\Users\USER\emby for VS Code. Overall remains **10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs**.

Next: large-history/roster query performance, remaining cross-feature acceptance and explicit recovery for pending reading checkpoints whose pages were removed before their first save. Staging/copy reconciliation review and hosted acceptance remain separate. Continue from these gaps without repeating the completed reader, weak-area or reconciliation implementation.

## 2026-10-23 — Verified current status and continued item 8

The current tracker supersedes the historical entries above: **items 7 and 14 are locally verified**, with the recorded class/private-media, 10,000-event roster, connected PostgreSQL and removed-page reader acceptance. Overall is **12/20 locally verified, 4 in progress, 4 pending; 0 production sign-offs**. Item 15 also has standalone whole-deck chat work already implemented. Do not restart those completed slices.

Continued item 8 from stale-job recovery. Previously, a standalone conversion that had saved a partial page set could fail every retry on duplicate page numbers. It now stages uploaded pages and atomically publishes the entire replacement with its metadata and completed status. Failure preserves the previous pages and original; newly uploaded unpublished files receive compensation, with failed cleanup retained in the registry for review. Unique generation tokens and renewable leases prevent duplicate claims and superseded workers from publishing or failing a newer result. Recovery covers stale pending records, excludes live leases/inactive classes/mismatched sources, and reserves the dispatch token before commit. Broker ambiguity cannot mark an already running worker failed. Migration curriculum.0020 is additive and local only.

Added read-only provider-export reconciliation for explicit Emby prefixes. It distinguishes referenced, registered unused, provider-only, recent and absent assets, and handles partial exports without claiming files are missing. Both model foreign keys and SlideContent JSON asset IDs are checked; malformed page references prevent confident unused classification. No provider calls, database updates or deletion occur in this command. It is a review report, not a cleanup authorization; actual provider export/adoption/revocation and legacy external references still require review.

Verification: **139 backend tests passed together on isolated PostgreSQL**, including real concurrent claims/recovery and PDF, Word and PowerPoint rendering, plus extraction, reading, private media, banks and deck chat regressions. This includes 22 added cases: nine processing, five recovery and eight inventory checks. Migration consistency and diff checks passed. Earlier attempts exposed a wrong test port, stale upload mock locations and thread-local Celery proxy mocks; they were corrected before the successful full run. CI includes the new modules but has not run remotely. No frontend change or new browser pass is claimed for this batch. No production migration, deployment or Render/Neon change occurred. Changes remain in C:\Users\USER\emby for VS Code.

Next local item-8 gaps: main curriculum conversion worker ownership/atomic publication, ambiguous repeated upload requests, then connected upload/retry acceptance. Preserve the completed standalone recovery and inventory tooling. Actual storage migration/provider review and hosted acceptance remain separate; item 8 is not yet counted as complete.


## Item 8 local acceptance completed — 2026-10-23

- Course conversions now claim a unique worker token, renew a lease, stage page assets and publish the full readable page set atomically. Failures preserve previous readable content; superseded workers and duplicate messages cannot publish or fail a replacement. Recovery allows four worker attempts before explicit uploader retry. Question-bank completion cannot overwrite an active conversion, and re-rendering an unchanged finished bank does not leave a permanent generating state.
- Course and standalone originals use user-scoped upload receipts. Identical concurrent/replayed requests return the saved authorized document. Changed bytes/metadata with a reused ID are rejected, and deletion leaves a receipt tombstone. Permission/class checks still apply to every retry. A lost standalone conversion response can return the already-saved original without another upload.
- Both forms preserve the request ID for an unchanged retry and authentication replay. Standalone uploads enforce the actual 100 MB and 200-character limits, reject empty/invalid replacements, show useful errors and hide upload controls from students. Explicit new selections/form resets remain new upload intents; older clients without an ID are not deduplicated.
- Verification: **208 PostgreSQL tests passed together** (`.test-item8-acceptance.log`), **3 browser journeys passed** (`.test-item8-browser-isolated.log`), **12 client/session tests passed** (`.test-item8-client-final.log`), and TypeScript/model-migration/diff checks passed. The earlier 72-test focused run and final 11-test worker-status check overlap this final backend run and are not added to its count. Initial fixture, response-contract, stale preview/font and browser teardown failures were repaired or isolated before the final passes; interrupted runs are not passes.
- Browser acceptance uses `playwright.upload.config.ts` on port 3118 with a separate generated cache and output folder so it can coexist with other work. The normal browser suite retains its existing configuration. Shared migration work is preserved, including the independent upload migration and its existing merge with the flashcard branch.
- All changes are in the local Emby checkout. Production migrations, worker rollout, provider inventory review, historical storage migration/revocation and hosted file-byte acceptance remain outstanding. Storage and AI calls in backend checks were mocked; no real storage upload/deletion, Render deployment or Neon change was performed.
