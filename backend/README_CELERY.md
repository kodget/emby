# Celery Setup for Emby Backend

## Prerequisites

### 1. Install Redis (Windows)

Download and install Redis for Windows:

- **Option 1**: Use WSL2 and install Redis in Linux
- **Option 2**: Use Memurai (Redis-compatible for Windows): https://www.memurai.com/
- **Option 3**: Use Docker: `docker run -d -p 6379:6379 redis`

### 2. Start Redis

```bash
# If using WSL2
wsl
sudo service redis-server start

# If using Docker
docker run -d -p 6379:6379 redis

# If using Memurai
# Start from Windows Services or Memurai app
```

## Running Celery

### Start Celery Worker

```bash
# Windows
cd backend
start_celery.bat

# Or manually
celery -A backend worker --loglevel=info --pool=solo
```

### Start Celery Beat (for periodic tasks)

```bash
celery -A backend beat --loglevel=info
```

## Monitoring

### Check Task Status

```bash
# In Django shell
python manage.py shell

from django_celery_results.models import TaskResult
TaskResult.objects.all()
```

### Flower (Web-based monitoring)

```bash
pip install flower
celery -A backend flower
# Open http://localhost:5555
```

## Testing

```python
# In Django shell
from curriculum.tasks import process_slide_task

# Queue a task
task = process_slide_task.delay('slide_id_here')

# Check status
task.status  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'
task.result  # Task result
```

## Troubleshooting

### Redis Connection Error

- Make sure Redis is running on localhost:6379
- Check firewall settings
- Verify CELERY_BROKER_URL in settings.py

### Tasks Not Processing

- Make sure Celery worker is running
- Check worker logs for errors
- Verify task is registered: `celery -A backend inspect registered`

### Import Errors

- Make sure all dependencies are installed
- Check Python path includes backend directory
- Restart Celery worker after code changes
