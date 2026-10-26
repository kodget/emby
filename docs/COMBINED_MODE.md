# Combined Mode: $0 Extra Cost Deployment

## Overview

**Combined mode** runs Django web (Gunicorn), Celery worker, and Celery Beat scheduler as three processes inside a single Render web service. This eliminates the need for separate worker and scheduler services, **saving $14/mo** on Render's free tier.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Render Free Web Service (0.5 CPU, 512MB RAM)  │
│                                                 │
│  ┌─────────────────────────────────────────┐  │
│  │  render_supervisor.py (process manager) │  │
│  │                                          │  │
│  │  ├─ Gunicorn (4 gevent workers)         │  │
│  │  │  └─ Django WSGI app                  │  │
│  │  │                                       │  │
│  │  ├─ Celery Worker (solo pool)           │  │
│  │  │  └─ Task execution                   │  │
│  │  │                                       │  │
│  │  └─ Celery Beat (singleton scheduler)   │  │
│  │     └─ Periodic task dispatch           │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │                    │
         ├──── HTTP ───────┐  │
         └──── Redis ──────┼──┘
                           │
                    ┌──────▼──────┐
                    │ Redis Free  │
                    └─────────────┘
```

## Cost Comparison

| Configuration | Monthly Cost | Services |
|--------------|--------------|----------|
| **Combined Mode** | **$0** | 1 web service (free tier) + Redis (free) |
| Separate Services | $14+ | Web (free) + Worker ($7) + Scheduler ($7) + Redis (free) |

## How It Works

1. **Process Supervisor** (`render_supervisor.py`)
   - Starts all three processes on service boot
   - Monitors for failures
   - Handles graceful shutdown (25s window)
   - Reaps orphaned child processes

2. **Singleton Beat Scheduler** (`backend.singleton_beat:SingletonScheduler`)
   - Uses Redis distributed lock
   - Only one Beat instance runs tasks (prevents duplicates)
   - 60-second lease, renewed every 5 seconds
   - Survives rolling deployments

3. **Preflight Validation** (`backend.combined_preflight`)
   - Verifies DEBUG=False and PostgreSQL
   - Checks migrations are applied
   - Validates Celery tasks and Beat schedule
   - Pings Redis broker

## Resource Constraints

### Free Tier Limitations

| Resource | Limit | Impact |
|----------|-------|--------|
| **CPU** | 0.5 shared CPU | All 3 processes compete for CPU time |
| **RAM** | 512MB total | ~200MB web + ~150MB worker + ~50MB beat + ~100MB OS |
| **Concurrency** | 4 Gunicorn workers | Limited parallel request handling |
| **Worker Pool** | Solo (single thread) | Tasks execute sequentially |
| **Cold Starts** | 30-60s after inactivity | First request after 15min idle is slow |

### Performance Characteristics

**Good for:**
- Low-traffic applications (< 100 req/min)
- Infrequent background tasks (< 10/min)
- Development/staging environments
- Periodic maintenance tasks (hourly/daily)
- Small team internal tools

**Not suitable for:**
- High-traffic production (> 500 req/min)
- CPU-intensive tasks (video processing, ML inference)
- Real-time task processing requirements
- High-frequency scheduled tasks (every minute)
- More than 5-10 concurrent long-running tasks

## Configuration

### render.yaml

```yaml
services:
  - type: web
    name: emby-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    preDeployCommand: bash render_release.sh
    dockerCommand: bash render_start.sh combined  # ← Combined mode
    healthCheckPath: /health/
    envVars:
      - fromGroup: emby-production
      - key: REDIS_URL
        fromService:
          type: redis
          name: emby-redis
          property: connectionString
      - key: DEBUG
        value: "False"
      - key: USE_SQLITE
        value: "False"
      - key: CELERY_TASK_ALWAYS_EAGER
        value: "False"

  - type: redis
    name: emby-redis
    plan: free
    maxmemoryPolicy: noeviction
```

### Required Environment Variables

Set these in the `emby-production` environment group:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | PostgreSQL connection string | Persistent Neon database |
| `SECRET_KEY` | 32+ byte random string | Stable across deployments |
| `DEBUG` | `False` | Required for combined mode |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | Required for combined mode |
| `REDIS_URL` | Auto-injected by Render | From redis service |

## Migration Guide

### From Separate Services to Combined Mode

**Step 1: Backup Current Configuration**

Save your current `render.yaml` and environment variables.

**Step 2: Update render.yaml**

```diff
   - type: web
     name: emby-backend
-    dockerCommand: bash render_start.sh web
+    dockerCommand: bash render_start.sh combined

-  - type: worker
-    name: emby-celery-worker
-    ...
-
-  - type: worker
-    name: emby-scheduler
-    ...
```

**Step 3: Apply Blueprint**

1. In Render dashboard: Settings → Blueprint → Update
2. Upload modified `render.yaml`
3. Review changes (worker/scheduler will be deleted)
4. Confirm and deploy

**Step 4: Verify Deployment**

Check logs for:
```
[supervisor] INFO Started web (pid=72)
[supervisor] INFO Started worker (pid=85)
[supervisor] INFO Started beat (pid=91)
[preflight] INFO WSGI, migration state, Celery tasks, Beat schedule and Redis checks passed.
```

**Step 5: Test Functionality**

- Dashboard loads without timeouts
- Background tasks execute (upload processing)
- Scheduled tasks run (check Beat logs for `build-notifications-hourly`)
- WebSocket connections work (notifications, battles)

### From Combined Mode to Separate Services

If you need to scale back to separate services:

**Step 1: Update render.yaml**

```diff
   - type: web
     name: emby-backend
-    dockerCommand: bash render_start.sh combined
+    dockerCommand: bash render_start.sh web

+  - type: worker
+    name: emby-celery-worker
+    dockerCommand: bash render_start.sh worker
+    ...
+
+  - type: worker
+    name: emby-scheduler
+    dockerCommand: bash render_start.sh scheduler
+    numInstances: 1
+    ...
```

**Step 2: Deploy**

Apply the blueprint. Render will create the worker and scheduler services.

**Cost:** Worker ($7/mo) + Scheduler ($7/mo) = **$14/mo extra**

## Monitoring

### Health Checks

**Web health endpoint:** `GET /health/`
- Should return 200 OK
- Verifies Django is running
- Does NOT verify worker/beat (they don't expose HTTP)

**Worker verification:**
```bash
# In Render Shell
python -m celery -A backend inspect active
```

**Beat verification:**
```bash
# Check logs for periodic task dispatch
[beat: INFO/MainProcess] Scheduler: Sending due task ...
```

### Log Patterns

**Successful startup:**
```
[preflight] INFO Loading Django and the existing WSGI application.
[preflight] INFO Checking applied database migrations (read-only).
[preflight] INFO Checking the existing remote Celery broker.
[preflight] INFO WSGI, migration state, Celery tasks, Beat schedule and Redis checks passed.
[supervisor] INFO Started web (pid=72)
[supervisor] INFO Started worker (pid=85)
[supervisor] INFO Started beat (pid=91)
[beat: INFO/MainProcess] Beat acquired the scheduler lease.
```

**Failed child process:**
```
[supervisor] ERROR worker exited unexpectedly (exit=1); stopping the service.
[supervisor] INFO Stopping web, worker and Beat; allowing up to 25s for graceful exit.
```

**Redis connection issue:**
```
[preflight] ERROR Startup check failed (ConnectionError). Check Django, migration and existing Redis configuration.
```

## Troubleshooting

### Service Fails to Start

**Symptom:** Deployment succeeds but service crashes immediately

**Check:**
1. Preflight logs for configuration errors
2. `DEBUG=False` in environment
3. `DATABASE_URL` points to PostgreSQL (not SQLite)
4. `REDIS_URL` is accessible
5. All migrations applied (`python manage.py migrate --check`)

### Worker Not Processing Tasks

**Symptom:** Tasks queue but don't execute

**Check:**
1. Worker process is running: `ps aux | grep celery`
2. Redis connection: `python -m celery -A backend inspect ping`
3. Task registered: `python -m celery -A backend inspect registered`
4. Queue not blocked: `python -m celery -A backend inspect active`

### Beat Not Scheduling Tasks

**Symptom:** Periodic tasks don't run

**Check:**
1. Beat acquired lease: Look for "Beat acquired the scheduler lease" in logs
2. Redis lock exists: `redis-cli GET emby:celery:beat:leader:v1`
3. Schedule file exists: Beat creates temporary schedule in `/tmp/emby-beat-*/`
4. Tasks in schedule: Check `backend/celery.py` beat_schedule

### Timeout Issues Persist

**Symptom:** Dashboard still times out after migration

**Check:**
1. Gevent workers running: `ps aux | grep gunicorn` (should show `gevent`)
2. Worker count: Should be 4 (not 1)
3. Redis connection pool: May need to increase `REDIS_URL` max connections
4. Database query performance: Check slow query logs

### Memory Pressure

**Symptom:** Out of memory errors, service restarts

**Solutions:**
1. Reduce Gunicorn workers: 4 → 2 in `render_supervisor.py`
2. Optimize task memory usage: Limit batch sizes
3. Clear Beat schedule cache: Restart service
4. Upgrade to paid tier: 512MB → 2GB+ RAM

## When to Upgrade

Consider separate services ($14/mo) when:

1. **Traffic exceeds 100 req/min** - Need more web workers
2. **Tasks take > 30s** - Worker blocks other tasks
3. **> 50 tasks/day** - Need dedicated worker resources
4. **Memory errors** - 512MB not enough for all 3 processes
5. **Cold starts unacceptable** - Free tier spins down after 15min
6. **Real-time requirements** - Need instant task processing

Consider paid tier ($25/mo single service) when:

- Traffic > 500 req/min
- Need 2+ CPU cores
- Need 2+ GB RAM
- 24/7 availability required (no spin-down)

## Technical Details

### Process Management

**Supervisor Features:**
- POSIX process groups (Linux only)
- Subreaper mode (adopts grandchildren)
- SIGTERM → 25s grace → SIGKILL
- Orphan process reaping
- Startup lock (prevents duplicate supervisors)

**Worker Configuration:**
- Solo pool (single-threaded)
- Concurrency=1 (sequential task execution)
- No gossip/mingle (reduces overhead)
- Prefetch multiplier=1 (one task at a time)

**Beat Configuration:**
- Singleton scheduler (Redis lease)
- 60s lease, renewed every 5s
- Temporary schedule file per deployment
- Leadership lost → exits immediately

### Redis Usage

- **Broker:** Celery task queue
- **Channel Layer:** Django Channels (WebSockets)
- **Beat Lock:** `emby:celery:beat:leader:v1`
- **Connection Pool:** Shared across all processes

### Security

- No secrets in logs (exception messages sanitized)
- Startup lock prevents privilege escalation
- Process groups prevent orphaned services
- Preflight validates secure configuration (DEBUG=False, strong SECRET_KEY)

## FAQ

**Q: Can I run this locally?**

A: No. Combined mode requires Linux/POSIX. Use separate processes locally:
```bash
python manage.py runserver  # Terminal 1
celery -A backend worker    # Terminal 2
celery -A backend beat      # Terminal 3
```

**Q: Does this work on Windows/macOS in development?**

A: No. The supervisor uses Linux-specific process groups. Set `CELERY_TASK_ALWAYS_EAGER=True` locally to run tasks inline without a worker.

**Q: What happens during deployment?**

A: Render uses rolling deployments. The old instance keeps running until the new one passes health checks. Beat's Redis lease ensures only one scheduler runs at a time.

**Q: Can I scale horizontally?**

A: No. Combined mode runs on a single instance. For horizontal scaling, use separate services and scale the worker service to multiple instances.

**Q: How do I debug worker issues?**

A: Check Render logs filtered by process name:
```
[supervisor] INFO Started worker (pid=85)
[celery.worker] INFO ...
```

**Q: What's the maximum task execution time?**

A: Default 120s (Gunicorn timeout). Tasks that take longer should use `task.update_state()` to signal progress and prevent timeout.

## Support

- **Code:** `backend/render_supervisor.py`, `backend/combined_preflight.py`
- **Tests:** `backend/curriculum/tests/test_combined_preflight.py`
- **Logs:** Check Render dashboard → Logs → Filter by service name

## References

- [Render Docker Deployment](https://render.com/docs/docker)
- [Celery Workers](https://docs.celeryq.dev/en/stable/userguide/workers.html)
- [Celery Beat](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)
- [Gunicorn Gevent Workers](https://docs.gunicorn.org/en/stable/design.html#async-workers)
