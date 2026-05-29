@echo off
echo Starting Celery Worker for Emby Backend...
echo.
echo Make sure Redis is running on localhost:6379
echo.
celery -A backend worker --loglevel=info --pool=solo
