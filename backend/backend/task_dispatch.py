"""Keep document work off HTTP requests, including brokerless local development.

Production uses Celery. Eager mode uses two bounded, daemon worker threads; the
database job/lease remains the recovery record if the development server stops.
Call after committing the source/job, never from inside its transaction.
"""
import logging
from queue import Queue
from threading import Lock, Thread, current_thread
from types import SimpleNamespace
from uuid import uuid4

from django.conf import settings
from django.db import close_old_connections, connections

logger = logging.getLogger(__name__)
_queue = Queue(maxsize=64)
_lock = Lock()
_workers = []


def _work():
    while True:
        task, args, kwargs, task_id = _queue.get()
        try:
            close_old_connections()
            # apply is deliberately explicit: no broker and no recursive .delay
            # execution on the requesting thread when eager mode is enabled.
            task.apply(args=args, kwargs=kwargs, task_id=task_id, throw=True)
        except Exception as exc:
            # Tasks retain failure/retry state in their own persisted job rows.
            # Provider exceptions may contain signed URLs or credentials.
            logger.warning('Local background task %s failed (%s)', task_id, type(exc).__name__)
        finally:
            try:
                connections.close_all()
            finally:
                _queue.task_done()


def dispatch_task(task, *args, **kwargs):
    if not settings.CELERY_TASK_ALWAYS_EAGER:
        return task.delay(*args, **kwargs)

    task_id = uuid4().hex
    with _lock:
        _workers[:] = [worker for worker in _workers if worker.is_alive()]
        while len(_workers) < 2:
            worker = Thread(target=_work, name='emby-document-worker', daemon=True)
            worker.start()
            _workers.append(worker)
        # Fail promptly if overloaded. Callers retain the saved upload/job for
        # recovery instead of creating unlimited threads or blocking the request.
        _queue.put_nowait((task, args, kwargs, task_id))
    return SimpleNamespace(id=task_id)


def wait_for_local_tasks():
    """CLI recovery must finish eager work before its process exits.

    HTTP handlers never call this. A recovery command invoked from an existing
    worker must not wait on itself (or other workers waiting on the same queue).
    """
    if settings.CELERY_TASK_ALWAYS_EAGER and current_thread() not in _workers:
        _queue.join()
