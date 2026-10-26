# Production recovery — 24 October 2026

These changes are in `C:\Users\USER\emby`. They have not been deployed by this repair session. Local tests do not establish that the running Render service is healthy or that missing production accounts have been recovered.

## Confirmed deployment mismatch

The live settings supplied by the owner were:

- Build: `pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py create_admin`
- Start: `gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT` (a trailing `|` was also included in the pasted value; remove it if present in Render).
- `DEBUG=True`.

The pasted log shows successful PPTX storage/download followed by conversion failure, HTTP 404 for notification WebSockets, rejected old tokens, a newly created Google account after login, and an empty subjects response. It does **not** prove that a deployment deleted a Neon database.

The WSGI process cannot serve the Channels WebSocket routes. The build does not install LibreOffice/OCR. The former database guard also allowed a temporary SQLite fallback with `DEBUG=True`. The revised guard requires PostgreSQL on Render regardless of DEBUG and rejects DEBUG, weak/default secrets, missing shared Redis, and inline Celery execution on Render.

## Preserve and identify the existing data first

1. In the currently running backend's Render Shell, run `python manage.py persistence_report`. Save the output privately. It reports hashed database/storage targets, model counts and migration history without connection strings. Capture the same report from the worker and scheduler when available.
2. Confirm Render uses the **existing** Neon project, branch, database and role. `DATABASE_URL` takes precedence over `DB_*`. Do not create a fresh database to make the deployment start. Check the report's engine: a SQLite report means the service was not using Neon.
3. Compare expected account/profile/subject counts and the target hashes. Check the original Neon target and its recovery history if those records are missing. Obtain a verified backup before migrations. A rotated JWT secret logs people out; it does not delete accounts.
4. Use [PERSISTENCE_RUNBOOK.md](PERSISTENCE_RUNBOOK.md) for the existing read-only inventory, backup/restore rehearsal, ownership adoption and credit-transfer guards. Do not bypass a migration guard or seed replacement accounts/content over a missing database.

After the new settings validation is deployed, the command requires the corrected production environment described below. It deliberately fails closed with incomplete settings.

## Deploy the supplied runtime

`backend/Dockerfile` installs LibreOffice, English OCR data, Poppler, fonts and Python requirements in the **running image**. The revised `render.yaml` defines a single web service running all three processes (web, worker, scheduler) in **combined mode** plus Redis. Docker is appropriate for OS dependencies that Render's native Python runtime does not provide ([Render documentation](https://render.com/docs/docker)).

**Combined mode eliminates the need for separate worker and scheduler services**, saving $14/mo on Render's free tier. See [COMBINED_MODE.md](COMBINED_MODE.md) for detailed documentation on resource constraints, monitoring, and migration instructions.

Review service plans before applying the Blueprint. This session has not provisioned services or changed billing. Docker itself was not available in this workstation's PATH, so the container build still needs verification in staging/Render.

Create one Render environment group named `emby-production` containing the existing integration configuration, then link all three app services to it:

| Setting                                        | Required value                                                                          |
| ---------------------------------------------- | --------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                 | Existing Neon connection URL, with its SSL options, entered privately in Render         |
| `SECRET_KEY`                                   | One stable secret of at least 32 bytes, shared by web, worker and scheduler             |
| `DEBUG`                                        | `False`                                                                                 |
| `USE_SQLITE`                                   | `False`                                                                                 |
| `CELERY_TASK_ALWAYS_EAGER`                     | `False`                                                                                 |
| `REDIS_URL`                                    | Same Redis connection on all three services; Blueprint supplies it                      |
| `ALLOWED_HOSTS`                                | Actual backend hostname, without scheme                                                 |
| `FRONTEND_URL`                                 | Actual Vercel frontend origin                                                           |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Actual frontend HTTPS origin                                                            |
| Cloudinary and LLM settings                    | Existing credentials and model configuration used by both web and worker                |
| Google, payment and email settings             | Preserve the existing integration values                                                |
| VAPID settings                                 | Backend private key/contact and matching frontend public key if browser push is enabled |

Remove conflicting per-service overrides after comparing them with the shared group. Preserve any deliberate dedicated broker configuration, but confirm it points at the same reachable queue the worker consumes. Do not generate a different secret on each deploy. The logged 13-byte secret needs replacement once; that replacement invalidates existing login tokens, so users will need to sign in again without recreating accounts.

For the Docker configuration in combined mode, paths are relative to the repository root:

| Service        | Dockerfile             | Context     | Docker command                  |
| -------------- | ---------------------- | ----------- | ------------------------------- |
| Web (combined) | `./backend/Dockerfile` | `./backend` | `bash render_start.sh combined` |

The web service runs Django (Gunicorn), Celery worker, and Celery Beat scheduler in a single process managed by `render_supervisor.py`. Only the web service owns the release hook: `bash render_release.sh`. It checks the existing database and legacy migration safety, applies migrations, checks migration state, and verifies private media adoption. Render's pre-deploy hook requires a supported paid service; if the current service does not support it, follow the manual release procedure in the persistence runbook. Builds do not migrate, create admins, seed data, or reset profiles. Startup refuses unapplied migrations.

The web command starts a process supervisor that manages Gunicorn (with 4 gevent workers), Celery worker, and Celery Beat. See [COMBINED_MODE.md](COMBINED_MODE.md) for resource constraints, monitoring, troubleshooting, and migration from separate services. If moving to a new backend URL, update the frontend's `NEXT_PUBLIC_API_URL`, backend host/CORS settings and integration callbacks deliberately. Check that the Vercel deployment uses the same repaired commit.

## Repairs in this changeset

| Reported problem                     | Implemented repair                                                                                                                                                                                                               | Remaining live verification                                                                             |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Blank class page                     | Restored class hub, loading/error/empty states and working navigation                                                                                                                                                            | Sign in as a real class member/head                                                                     |
| Announcements/countdowns fail saving | Server assigns class; head-only create/update/delete; announcement notifications persist before delivery                                                                                                                         | Publish and edit a test notice in the intended class                                                    |
| Brain Battles inactive               | Next route fix, manual/AI authoring, validated answers/timers, correct host identity, join code, participant updates, question preview, connection error feedback and expired-session recovery                                   | Two authenticated browsers through ASGI/Redis; AI requires a working provider                           |
| PPTX upload/processing               | Docker conversion dependencies; meaningful conversion failures; existing retry pipeline retained                                                                                                                                 | Upload an actual production file, read every page and verify extracted text                             |
| Duplicate topic/title inputs         | One title creates/reuses the Learn topic inside the selected module/submodule, transactionally                                                                                                                                   | Uploaded topic appears under the correct course                                                         |
| Free users and purchased credits     | Removed reader/resource subscription gates for credit-funded AI; AI battles now charge the same purchased/daily wallet; backend reservation/refund remains authoritative                                                         | Real free allocation and a credited purchase fund generation                                            |
| Tutor shortcut                       | Dialog searches processed class slides/decks, uses bounded relevant excerpts, cites sources and saves class-scoped history                                                                                                       | Confirm source accuracy with actual slides and configured LLM                                           |
| Notifications                        | Single scheduler, delayed delivery/retry outbox, local quiet hours, exam countdowns, owner-scoped due/unreviewed flashcard prompts, reconnect/inbox catch-up; push retries only failed devices and removes expired subscriptions | Worker/Redis/scheduler running; browser push also needs consent and VAPID                               |
| Profile privacy                      | Persistent public/private and ranking controls; class-scoped public profile endpoint                                                                                                                                             | Private profile inaccessible to another student                                                         |
| Subjects missing                     | Fixed class link and course loading/error feedback; class isolation retained                                                                                                                                                     | Resolve original database/class ownership if the actual response is empty                               |
| Profiles seem reset                  | Hosted SQLite fallback closed; shared stable deployment settings; case-insensitive Google account reuse                                                                                                                          | Compare actual DB fingerprints/counts across a deployment; recover missing data separately if necessary |

The tutor does not put every document into one model request. It searches the accessible extracted library and sends a bounded set of relevant excerpts. Unprocessed or unreadable text cannot support a grounded answer. Purchasing credits enables credit-funded AI; it does not confer class-management privileges or every subscription benefit.

## Release acceptance

1. Save persistence reports before and after deployment. Existing account IDs, class memberships, announcements and materials must still be present.
2. Confirm HTTP health, successful login refresh, and WebSocket 101 handshakes for notifications and battles.
3. Upload a real PDF and PPTX. Check pages, extracted text, Learn topic, tutor citations, flashcards and the 15-MCQ bank (5 easy/5 medium/5 hard).
4. As a head, save/edit an announcement and an exam countdown. As a student, read them but verify that write attempts are rejected.
5. Host a manual battle and an AI battle with two users. Verify lobby join code, participants, timed answers, results and reconnect.
6. Check free AI credit consumption, provider-failure refunds and exhaustion; confirm cached resources remain readable.
7. Toggle privacy, reload, and test another classmate's access. Verify unrelated classes cannot read private class content.
8. Run one scheduled notification sweep and confirm deduplication and quiet hours. Check browser push only after granting browser permission.

Do not mark the incident resolved until these checks pass on the actual deployment. In particular, no local test in this session establishes that missing historical production accounts have been recovered.

## Local verification — 24 October 2026

- Combined backend acceptance: **195 tests run, 190 passed, five skipped** on an isolated in-memory SQLite database. Includes class notices and authorization, purchased-credit exhaustion/refunds for AI battles, tutor history/retrieval, flashcards, upload receipts, processing recovery, real local PDF/Word/PowerPoint rendering, privacy, push retry/preferences, account login and deployment guards. The skipped cases require PostgreSQL concurrency; this run makes no PostgreSQL concurrency claim.
- **Three browser journeys passed** through `npx playwright test tests/browser/content.spec.ts --config=playwright.repairs.config.ts`: class hub/library tutor with a failed request and successful retry, manual battle creation/lobby with distinct user/profile IDs, and privacy persistence across reload. These use intercepted API/WebSocket fixtures. Earlier runs exposed a missing battle-state fixture and asynchronous checkbox feedback; both were corrected. A cold webpack build also exceeded the initial heading wait; the isolated preview was warmed before the successful run. Google Fonts used local fallbacks.
- Strict TypeScript, **19 Node authentication/guard checks**, model/migration consistency and `git diff --check` passed. There are no new model changes beyond the supplied additive migrations.
- The Docker image was not built locally. No live LLM/storage calls, production database access, deployment, or historical account recovery was performed. Existing unrelated workspace changes were preserved.

Test logs are local ignored artifacts: `.test-production-combined.log` and `.test-production-browser-verified.log`. Use the release acceptance steps above against the actual deployed services before recording a production sign-off.
