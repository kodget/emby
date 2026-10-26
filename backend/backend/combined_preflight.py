"""Read-only startup validation for the single-service deployment."""
import logging
import os
import shutil
import sys
from backend.runtime_redis import RuntimeConfigurationError

log = logging.getLogger('emby.preflight')


def check():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    log.info('Loading Django and the existing WSGI application.')
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from backend.celery import app
    from backend.runtime_redis import broker_client
    from backend.wsgi import application
    if settings.DEBUG or app.conf.task_always_eager:
        raise RuntimeConfigurationError('Combined startup requires DEBUG=False and CELERY_TASK_ALWAYS_EAGER=False.')
    if not settings.DATABASES['default']['ENGINE'].endswith('postgresql'):
        raise RuntimeConfigurationError('Combined startup requires the existing PostgreSQL database.')
    if not callable(application):
        raise RuntimeError('The WSGI application could not be loaded.')
    call_command('check', fail_level='ERROR')
    log.info('Applying database migrations.')
    call_command('migrate', interactive=False, verbosity=0)
    app.autodiscover_tasks(force=True)
    if any(entry['task'] not in app.tasks for entry in app.conf.beat_schedule.values()):
        raise RuntimeError('A scheduled task is missing from Celery discovery.')
    log.info('Checking the existing remote Celery broker.')
    client = broker_client(app)
    try:
        client.ping()
    finally:
        client.close()
    for binary, feature in (('soffice', 'PPT/PPTX/DOCX rendering'), ('tesseract', 'local OCR fallback')):
        if not shutil.which(binary):
            log.warning('%s is unavailable; %s needs a separate runtime dependency fix.', binary, feature)
    log.info('WSGI, migration state, Celery tasks, Beat schedule and Redis checks passed.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[preflight] %(levelname)s %(message)s')
    try:
        check()
    except RuntimeConfigurationError as exc:
        log.error('%s', exc)
        sys.exit(1)
    except Exception as exc:
        # Connection exceptions can contain credentials. Never echo raw config.
        log.error('Startup check failed (%s). Check Django, migration and existing Redis configuration.', type(exc).__name__)
        sys.exit(1)
