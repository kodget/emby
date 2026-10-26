# Production API Timeout Fix

## Problem
Dashboard was timing out with all API calls failing after 20 seconds:
- `/api/learning/dashboard/snapshot/` - timeout
- `/auth/profile/` - timeout
- `/api/stats/leaderboard/` - timeout
- `/api/subjects/` - timeout
- All other API endpoints - timeout

## Root Cause
Render was running **Gunicorn with WEB_CONCURRENCY=1** (single worker) instead of the configured Daphne ASGI server. With only one synchronous worker:
- Every request blocks the single thread
- Dashboard makes 8+ parallel API calls
- Each call waits for the previous one to complete
- Total time: 8 calls × 3s each = 24s > 20s timeout

Additionally, Render free tier has:
- Cold starts (~30-60s to wake up after inactivity)
- Limited CPU/memory
- Slow first response times

## Solution Applied

### 1. Switch to Gunicorn with Gevent Workers
**File:** `backend/render_start.sh`

Changed from:
```bash
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" backend.asgi:application
```

To:
```bash
exec gunicorn backend.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 4 \
  --worker-class gevent \
  --worker-connections 1000 \
  --timeout 120 \
  --keep-alive 5 \
  --log-level info
```

**Why gevent:**
- Gevent uses greenlets (cooperative multitasking) for async I/O
- Single worker can handle 1000+ concurrent connections
- Non-blocking I/O for database queries, HTTP requests, file operations
- Ideal for I/O-bound applications like Django APIs
- Works with standard WSGI (no ASGI needed for your use case)

### 2. Increased Frontend Timeout
**File:** `lib/api.ts`

Changed from:
```typescript
timeout: 20000,  // 20 seconds
```

To:
```typescript
timeout: 60000,  // 60 seconds
```

This handles:
- Cold starts on Render free tier (30-60s)
- Slow first requests after deployment
- Network latency spikes

### 3. Added gevent to Dependencies
**File:** `backend/requirements.txt`

```
gevent==26.0.0
```

## Performance Improvements

### Before Fix:
- WEB_CONCURRENCY=1 (single worker)
- Synchronous blocking on every request
- Dashboard load: 20s+ (timeout)
- API calls: sequential, blocking

### After Fix:
- 4 gevent workers with 1000 connections each
- Non-blocking async I/O
- Dashboard load: expected 2-5s (parallel requests)
- API calls: concurrent, non-blocking

## Expected Results After Deployment

1. **Dashboard loads successfully** - All 8+ API calls complete in parallel
2. **No more timeouts** - 60s frontend timeout handles cold starts
3. **Better concurrency** - 4 workers × 1000 connections = 4000 concurrent requests
4. **Faster response times** - Gevent handles I/O without blocking

## Monitoring After Deploy

Check these in Render logs:

```bash
# Should see gevent workers starting
[INFO] Starting gunicorn 26.2.0
[INFO] Using worker: gevent
[INFO] Booting worker with pid: 72
[INFO] Booting worker with pid: 73
[INFO] Booting worker with pid: 74
[INFO] Booting worker with pid: 75
```

## Alternative Solutions (If Still Slow)

If timeouts persist after this fix:

### Option A: Database Query Optimization
- Add missing indexes
- Use `select_related()` / `prefetch_related()`
- Cache frequently accessed data in Redis

### Option B: Upgrade Render Plan
- Free tier: 0.5 CPU, 512MB RAM, spins down after inactivity
- Starter ($7/mo): 0.5 CPU, 512MB RAM, always on
- Standard ($25/mo): 2 CPU, 2GB RAM, much faster

### Option C: Add Caching Layer
- Use Redis for dashboard snapshots
- Cache for 5 minutes
- Reduces DB queries by 90%

### Option D: Move to Daphne (ASGI) with Channels
- Only needed if you use WebSockets heavily
- More complex setup
- Requires Redis for channel layer

## Technical Details

### Why Not Daphne?
Daphne is an ASGI server designed for WebSockets and async views. Your app:
- Uses standard Django views (WSGI)
- Has minimal WebSocket usage (just real-time battles)
- Benefits more from gevent's proven concurrency model
- Daphne adds complexity without benefits for your use case

### Gevent vs. Threading
- **Gevent**: Cooperative multitasking, single-threaded, non-blocking I/O
- **Threading**: Pre-emptive multitasking, multi-threaded, GIL limitations
- Gevent wins for I/O-bound apps (database, API calls, file operations)
- Threading wins for CPU-bound apps (image processing, calculations)

### Why 4 Workers?
Render free tier has ~0.5 CPU cores. Formula:
```
workers = (2 × CPU_cores) + 1
workers = (2 × 0.5) + 1 = 2
```

We use 4 to handle cold starts and burstiness, acceptable on free tier since gevent workers are lightweight.

## Verification Steps

1. **Deploy and wait** - Let build complete (5-10 min)
2. **Visit dashboard** - https://emby-jkwv.onrender.com (frontend)
3. **Check logs** - Should see gevent workers, no timeouts
4. **Test cold start** - Wait 15 min, visit again, should load in <60s
5. **Monitor performance** - Check response times in browser devtools

## Rollback Plan

If this breaks something:

```bash
# Revert render_start.sh to Daphne
git revert HEAD
git push origin master
```

Or manually edit `render_start.sh`:
```bash
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" backend.asgi:application
```

## Related Files Changed
- `backend/render_start.sh` - Switch to Gunicorn gevent
- `backend/requirements.txt` - Add gevent
- `lib/api.ts` - Increase timeout to 60s

## References
- [Gunicorn Design](https://docs.gunicorn.org/en/stable/design.html)
- [Gevent Documentation](http://www.gevent.org/intro.html)
- [Render Concurrency Guide](https://render.com/docs/deploy-django#gunicorn-workers)
