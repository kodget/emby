# Render Production Setup Checklist

## Issue

Your deployment is failing with:

```
ImproperlyConfigured: Set DEBUG=False on Render. Set a strong, stable SECRET_KEY shared by web, worker and scheduler. Set CELERY_TASK_ALWAYS_EAGER=False and run the Celery worker.
```

## Root Cause

The `emby-production` environment group in Render is missing or has an invalid `SECRET_KEY`.

## Fix Instructions

### Step 1: Generate a Secure SECRET_KEY

Run this command from the backend directory:

```bash
cd backend
python generate_secret_key.py
```

This will output a secure key like:

```
django-v3w9k$2j#5h@9x7n&4m*8q!1p^6r...
```

**IMPORTANT:** Copy this key immediately and store it securely.

### Step 2: Configure Render Environment Group

1. Go to your Render Dashboard: https://dashboard.render.com
2. Navigate to **Environment Groups**
3. Find or create `emby-production`
4. Add/update these variables:

| Variable                | Value                                                          | Notes                                                                                            |
| ----------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `SECRET_KEY`            | (paste the generated key)                                      | Must be ≥32 bytes, same across all services                                                      |
| `DATABASE_URL`          | `postgresql://user:pass@host.neon.tech/dbname?sslmode=require` | **CRITICAL** Your existing Neon PostgreSQL URL - without this, you'll lose data on every deploy! |
| `CLOUDINARY_CLOUD_NAME` | Your Cloudinary cloud name                                     | For file storage                                                                                 |
| `CLOUDINARY_API_KEY`    | Your Cloudinary API key                                        | For file storage                                                                                 |
| `CLOUDINARY_API_SECRET` | Your Cloudinary API secret                                     | For file storage                                                                                 |
| `LLM_API_KEY`           | Your LLM API key (Groq/OpenAI)                                 | For AI features                                                                                  |
| `PAYSTACK_SECRET_KEY`   | Your Paystack secret key                                       | For payments                                                                                     |
| `PAYSTACK_PUBLIC_KEY`   | Your Paystack public key                                       | For payments                                                                                     |
| `EMAIL_HOST_USER`       | Your Gmail/SMTP username                                       | For sending emails                                                                               |
| `EMAIL_HOST_PASSWORD`   | Your Gmail app password                                        | For sending emails                                                                               |
| `REDIS_URL`             | (auto-set by redis service)                                    | Don't manually set this                                                                          |

**Do NOT set these** (they're in render.yaml):

- `DEBUG` - Already set to `False` in render.yaml
- `CELERY_TASK_ALWAYS_EAGER` - Already set to `False` in render.yaml
- `USE_SQLITE` - Already set to `False` in render.yaml

### Step 3: Verify Services

After updating the environment group, check that these services exist and are properly configured:

1. **emby-backend** (web service)
   - Uses the emby-production env group ✓
   - Has DEBUG=False in render.yaml ✓
   - Links to emby-redis ✓

2. **emby-celery-worker** (worker service)
   - Uses the emby-production env group ✓
   - Has CELERY_TASK_ALWAYS_EAGER=False ✓
   - Links to emby-redis ✓

3. **emby-scheduler** (worker service)
   - Uses the emby-production env group ✓
   - Has CELERY_TASK_ALWAYS_EAGER=False ✓
   - Links to emby-redis ✓

4. **emby-redis** (Redis service)
   - Plan: free
   - Should be running ✓

### Step 4: Trigger Redeployment

After updating the SECRET_KEY in the environment group:

1. Go to the **emby-backend** service
2. Click **Manual Deploy** → **Deploy latest commit**
3. Monitor the logs for successful deployment

All three services (web, worker, scheduler) will automatically use the updated environment variables.

## Verification

Once deployed, check:

```bash
# Health check should return 200 OK
curl https://your-app.onrender.com/health/

# Check logs for any startup errors
# In Render Dashboard: Services → emby-backend → Logs
```

## Common Issues

### "SECRET_KEY is too short"

- Generate a new key using the script above
- Django requires at least 32 bytes

### "SECRET_KEY starts with django-insecure"

- This is a development key
- Generate a production key using the script

### "REDIS_URL not set"

- Ensure emby-redis service is running
- Check that render.yaml correctly references it
- Redis URL is auto-injected, don't set manually

### Services using different SECRET_KEYs

- All services must use the SAME key from emby-production group
- Check that all services reference `fromGroup: emby-production`

## Security Notes

- **Never commit SECRET_KEY to git**
- Store it securely (password manager, Render only)
- Use the same key across all services (web, worker, scheduler)
- Rotate it periodically (requires redeployment of all services)

## Need More Help?

Check these files:

- `backend/backend/deployment_config.py` - Validation logic
- `render.yaml` - Service configuration
- `backend/render_release.sh` - Pre-deploy commands
- `backend/render_start.sh` - Service startup commands
