# One existing free Render service: web, worker and Beat

Implementation prepared for review on 26 October 2026. No service was created,
deployed, resized or deleted. No production command, database migration or AI
request was run for this deployment task. Existing provider settings and secrets
are unchanged. This setup adds no hosting service or production dependency.

## Exact Render settings

Use the **existing native Python web service**, with its existing free plan,
database and Redis provider. Change its Start Command to:

```bash
python render_supervisor.py
```

The expected Root Directory is `backend`. That directory contains `manage.py`,
`requirements.txt`, `render_supervisor.py` and the nested `backend/` Django
package. The provided existing build and start commands resolve correctly there;
there is no root-level `manage.py` or `requirements.txt`. This is an inference
from repository layout and the supplied commands, **not a read of the live Render
dashboard**. Verify the current Root Directory before saving anything.

If the service deliberately starts at the repository root, the launcher also
supports `python backend/render_supervisor.py`: it gives every child the explicit
backend working directory. Do not change a working build/root configuration just
to use that alternative.

Keep the existing Build Command exactly as supplied:

```bash
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py create_admin
```

Keep `/health/` enabled as the HTTP health-check path. The launcher runs read-only
Django checks and `migrate --check` before starting services; it does not run
migrations, admin creation, seeding or static collection itself.

Do **not** apply the repository's current `render.yaml` to implement this free
setup. It describes a different Docker topology with separate workers and Redis.
Its declarations were left intact rather than removing potentially managed
resources. No Blueprint, paid pre-deploy hook or new service is needed here.

## What runs

| Component | Configuration |
| --- | --- |
| Gunicorn | Existing `backend.wsgi:application`; `0.0.0.0:$PORT`; one gthread worker, two threads; 120-second worker timeout, 20-second graceful timeout |
| Celery | Existing `-A backend` app; solo pool, concurrency 1, prefetch multiplier 1; no embedded Beat, gossip or mingle |
| Beat | Existing schedule/timezone; `backend.singleton_beat:SingletonScheduler`; transient per-process schedule file; shared Redis leadership lease |
| Supervisor | Standard-library Python; foreground children in separate process groups; local startup lock; monitors all children |

SIGTERM/SIGINT stops the masters first, allowing warm shutdown. After 25 seconds,
remaining process groups are killed, including converter/grandchild processes.
Linux subreaping collects orphaned descendants. Every unexpected child exit,
including exit code zero, stops the siblings and fails the service. The launcher
does not restart individual children silently; Render owns service restarts.
Partial startup failures follow the same cleanup path.

Only one supervisor can run on a given instance. During rolling deployments,
both instances may temporarily have workers, but only the Beat holding the
Redis lease publishes scheduled jobs. The new Beat stands by until ownership is
available; loss of ownership or a Redis error stops scheduling and fails the
supervised service. Every publish checks lease ownership. A crashed leader's
lease expires after 60 seconds. Do not manually delete its Redis key.

Any **other** Beat targeting this broker must be stopped before switching,
including local terminals and an old independent scheduler. The lease cannot
coordinate an external scheduler that does not use it. The legacy
`bash render_start.sh scheduler` entry point now uses the same guard.
`bash render_start.sh combined` is an optional alias for the new launcher.

The lease is not an exactly-once delivery guarantee: broker acknowledgements,
Redis loss, and resetting ephemeral Beat state can still repeat periodic work.
Existing task-level idempotency remains necessary.

## Environment: retain existing values

| Variable | Requirement |
| --- | --- |
| `PORT` | Supplied by Render; parsed as a valid TCP port. Local fallback is 8000. |
| `DEBUG` | `False` |
| `USE_SQLITE` | `False`; keep the existing PostgreSQL database |
| `CELERY_TASK_ALWAYS_EAGER` | `False`; combined startup refuses inline task execution |
| `REDIS_URL` | Existing remote Redis connection used by Channels and, by default, Celery |
| `CELERY_BROKER_URL` | Existing override, if configured; otherwise the app uses `REDIS_URL`. Must be remote `redis://` or `rediss://`, never localhost. |
| `CELERY_RESULT_BACKEND` | Preserve existing value; application default is `django-db` |
| `DATABASE_URL` / existing `DB_*` fields | Preserve the current database configuration and TLS options |
| `SECRET_KEY` | Preserve the existing stable key; Render validation requires at least 32 bytes and rejects the development default |
| `ALLOWED_HOSTS`, `FRONTEND_URL`, CORS/CSRF variables | Preserve valid domains for the existing app |
| Existing Cloudinary, AI, email, payments and push settings | Unchanged; still required by their respective features |
| `EMBY_BEAT_LOCK_KEY` | Optional; default `emby:celery:beat:leader:v1`. All schedulers for this broker/queue must use the same key. |

Redis lease operations reuse the effective Celery broker, including its database
number, TLS URL and configured SSL options. No credentials are embedded in argv
or logged by the new code. It uses the existing `redis==5.0.1` dependency.
Separate staging/prod stacks need separate brokers/queues; merely changing a
lock key does not isolate a shared Celery queue.

## Inspected compatibility and recovery

Inspected `backend/backend/{settings,celery,__init__,wsgi,asgi,urls}.py`,
`backend/requirements.txt`, `backend/Dockerfile`, all three existing
`render_{start,build,release}.sh` scripts, `render.yaml`, `README.md`,
`DEPLOYMENT.md`, `RENDER_SETUP.md`, and `create_admin.py`. There is no existing
Supervisor/Procfile process manager. The Dockerfile selects Python 3.12; this
machine uses Python 3.14. The native Render Python version is not verified.
Pinned Django is 6.0.4, Celery 5.4.0, Gunicorn 26.2.0 and redis-py 5.0.1.
Use Python 3.12 or later supported by these pinned packages; dependency versions
were not changed for production.

The app's `backend.__init__` imports its Celery app. That app loads `CELERY_*`
from Django, discovers application tasks, and owns the one existing Beat schedule.
Startup imports WSGI, checks Django/migrations, verifies scheduled task discovery,
and pings the existing broker. Existing health routes remain unchanged.

| Reviewed behavior | Result / remaining issue |
| --- | --- |
| AI HTTP 429 | Existing bounded HTTP retries/backoff remain. Numeric `Retry-After` is capped at 20 seconds; HTTP-date values are not handled. A separate follow-up should honor longer provider cooldowns using durable `next_attempt_at`, not block the only worker indefinitely. |
| Task acknowledgement | Existing early acknowledgements remain unchanged. No blanket late-ack/reject-on-worker-loss change was made: not every side effect is replay-safe. A hard-killed task is not guaranteed automatic broker redelivery. |
| Slide/index recovery | Original/private assets and database jobs survive process restarts. Token/lease checks fence stale workers. Existing five-minute recovery schedules requeue eligible work after lease expiry. |
| Question banks | Existing saved batches, source identity and leases remain. Retries fill shortages and preserve valid questions. Retry delay is five minutes with bounded attempts. |
| Assessment drafts/grading | Existing persisted jobs, bounded retries and expired-lease recovery remain. |
| Standalone decks | Recovery sweeps pending/processing rows after the two-hour lease/staleness threshold. Failed conversions require the existing explicit `--retry-failed` recovery option; Beat does not enable that option. |
| Flashcards | Existing database job, credit settlement and request-triggered stale-job handling remain. There is no dedicated periodic flashcard-recovery entry in Beat. |
| Notifications | Database dedupe keys and dispatch locking limit duplicates. External push delivery can still duplicate or be lost around process death/acknowledgement; a per-device durable delivery outbox is a separate improvement. |
| Daily credits / expiry | Per-user row locks, existing daily-allocation checks and transactional expiry updates make repeats safe at the database level. |
| Files | New uploads/page images use existing private Cloudinary assets; conversion/OCR uses temporary files. Temp render/schedule files can disappear; originals must remain in provider storage. Legacy local media would still be ephemeral. |

No task retry, acknowledgement, rate-limit, AI-provider or database schema
configuration was changed by this deployment task.

## Limits that this configuration cannot remove

- The free service sleeps after 15 idle minutes; all its processes stop.
  Beat cannot run reminders while asleep or guarantee catch-up of every missed
  cron occurrence. Redis/database queues recover only after the service wakes.
  Local files disappear on sleep/restart/redeploy. Existing provider usage limits
  still apply; this change does not add a paid resource or change a billing plan.
  [Render free-instance documentation](https://render.com/docs/free).
- Web, worker and Beat share the same small memory/CPU budget. Large PDFs,
  LibreOffice and embedding models can exhaust it. A single long task delays
  other work. Solo avoids an extra worker pool process, but Celery soft/hard time
  limits and child recycling are unavailable in that pool. Existing HTTP and
  converter timeouts still apply. [Celery 5.4 concurrency](https://docs.celeryq.dev/en/v5.4.0/userguide/concurrency/index.html).
- The supplied native build installs Python packages only. LibreOffice is needed
  for Office documents; Tesseract is needed for local OCR fallback. Startup logs
  their absence rather than pretending those features work. The existing Docker
  image supplies them, but switching runtime/build is a separate reviewed change.
- WSGI is preserved as requested. It does not serve the app's Channels WebSocket
  routes for battles/notifications. Restoring those requires a separate ASGI
  deployment decision; this task does not silently change the entry point.
- `create_admin` can promote a matching username/email and optionally overwrite
  its password when `DJANGO_SUPERUSER_OVERWRITE_PASSWORD=True`. Migrations run in
  the existing build while an older instance might still be live. These behaviors
  were inspected and left unchanged; future migration changes must be compatible
  with that overlap. No admin operation was run here.

## Review, deploy and roll back

1. Review the launcher, scheduler guard, startup checks, tests and this document.
   Run the Linux process tests in CI before deploying. Check the actual existing
   service Root Directory/runtime and save its previous Start Command.
2. Confirm its existing remote Redis URL, persistent database and stable secrets;
   keep eager mode off. Stop any other Beat using this broker. Do not create a
   worker, cron, Redis or database service, and do not apply the multi-service
   Blueprint for this procedure.
3. After review, deploy the reviewed commit to the **same** native Python web
   service with Start Command `python render_supervisor.py`. Keep the quoted
   existing Build Command. No additional migration is introduced here.
4. Check logs for successful preflight, `Started web`, `Started worker`,
   `Started beat`, Celery's ready message, and Beat acquiring the scheduler lease
   (temporary standby during a rolling deployment is expected). Check `/health/`
   returns HTTP 200 and then test one small upload and one due scheduled task.
   HTTP health alone proves neither task progress nor successful AI generation.
5. For rollback, restore the previous Start Command exactly:
   `gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT`, then redeploy the same
   existing service (or its last good commit). Do not reverse migrations, rotate
   secrets, delete queues or recreate resources. A normal stop releases leadership;
   a killed instance's lease expires. Background processing pauses after this
   rollback until a worker/scheduler is running again; saved originals and jobs
   remain in their existing stores.

Render sends SIGTERM and normally allows 30 seconds before SIGKILL; the launcher
uses a 25-second grace period plus bounded cleanup to fit that window.
[Render shutdown documentation](https://render.com/docs/deploys#graceful-shutdown).

## Changed files and verification

- Added `backend/render_supervisor.py`, `backend/backend/combined_preflight.py`,
  `backend/backend/runtime_redis.py`, `backend/backend/singleton_beat.py`.
- Updated `backend/render_start.sh` with the optional combined entry and guarded
  legacy scheduler; `.gitignore` and `backend/.dockerignore` ignore runtime Beat
  state without deleting the existing local files.
- Added supervisor tests and isolated preflight/scheduler tests; added the already
  pinned Redis client to test dependencies. Updated the existing Linux CI job
  to run isolated Django settings and the new checks, without adding CI services.
- Added this deployment/reliability report. Other pre-existing workspace edits,
  the Render build/release scripts, manifest and production dependencies are
  preserved.

Linux test command, from `backend/`:

```bash
python -m django test tests curriculum.tests.test_combined_preflight curriculum.tests.test_singleton_beat --top-level-directory . --settings=tests.integration_settings --noinput
```

The five Linux-only process tests exercise termination, unexpected clean exit,
killed Beat, stubborn descendants, failed preflight and duplicate startup locks.
They are skipped on this Windows host: WSL discovery found no installed Linux
distribution, and Docker is unavailable. Their execution in Linux CI and actual
Gunicorn/Celery startup against the existing production broker remain deployment
verification requirements. Local checks do not establish production success.
