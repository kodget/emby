"""Contain native converter crashes, memory spikes and hangs outside Celery."""
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .document_rendering import DocumentRenderingError

MIB = 1024 ** 2
logger = logging.getLogger(__name__)


def available_container_memory():
    """Return cgroup headroom on Render/Linux, or None when unavailable."""
    for root, limit_name, usage_name in (
        ('/sys/fs/cgroup', 'memory.max', 'memory.current'),
        ('/sys/fs/cgroup/memory', 'memory.limit_in_bytes', 'memory.usage_in_bytes'),
    ):
        try:
            limit = int((Path(root) / limit_name).read_text())
            usage = int((Path(root) / usage_name).read_text())
            if limit < 1 << 60:
                return max(0, limit - usage)
        except (OSError, ValueError):
            pass
    return None


def group_memory(pid):
    """RSS for the isolated group, including LibreOffice (Linux only)."""
    if not sys.platform.startswith('linux'):
        return 0
    total = 0
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == pid:  # pgrp; rss is field 24 in /proc/PID/stat.
                total += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError, IndexError):
            pass
    return total


def stop(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        # /T includes Office children. The PID belongs to this Popen only.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    process.wait(timeout=10)


def render_document_isolated(source, kind, output, *, progress=None, timeout=420):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    budget = max(64, min(1024, int(os.environ.get('EMBY_RENDER_MEMORY_MB', '192'))))
    available = available_container_memory()
    if available is not None:
        budget = min(budget, (available - 48 * MIB) // MIB)
    if budget < 64:
        raise DocumentRenderingError('render_memory')
    logger.info('Render starting: format=%s memory_budget_mb=%s', kind, budget)
    # Use a fresh result path per attempt; callers already create a fresh workspace.
    process = subprocess.Popen([sys.executable, '-m', 'curriculum.services.render_worker',
        str(Path(source).resolve()), kind, str(output), str(budget)],
        cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=os.name == 'posix',
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    started, heartbeat = time.monotonic(), 0
    latest = {'phase': 'rendering' if kind == 'pdf' else 'converting', 'completed': 0, 'total': 0}
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now - started > timeout:
                raise DocumentRenderingError('render_timeout')
            available = available_container_memory()
            if group_memory(process.pid) > budget * MIB or (available is not None and available < 24 * MIB):
                raise DocumentRenderingError('render_memory')
            if progress and now - heartbeat >= 5:
                try:
                    latest = json.loads((output / 'progress.json').read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    pass
                progress(**latest)
                heartbeat = now
            time.sleep(0.2)
        try:
            envelope = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise DocumentRenderingError('render_failed') from None
        if not envelope.get('success') or process.returncode:
            raise DocumentRenderingError(envelope.get('error_code', 'render_failed'))
        result = envelope['result']
        if progress:
            progress('rendering', result['page_count'], result['page_count'])
        logger.info('Render complete: pages=%s seconds=%.1f', result['page_count'], time.monotonic()-started)
        return result
    except DocumentRenderingError as exc:
        logger.warning('Render stopped: code=%s seconds=%.1f', exc.code, time.monotonic()-started)
        raise
    finally:
        stop(process)
        process.stdin.close()
