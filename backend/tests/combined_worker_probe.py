"""Test-only entry point: the real app and worker, with an in-memory probe task."""
from celery.signals import worker_ready
from backend.celery import app


@app.task(name='tests.combined_worker_probe', ignore_result=True)
def probe():
    print('EMBY_ISOLATED_WORKER_PROBE_OK', flush=True)


@worker_ready.connect
def ready(**kwargs):
    probe.delay()
