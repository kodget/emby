"""Run the existing web/worker/scheduler stack on one Linux Render instance.

No shell background jobs, daemonized children, migrations, or secret output.
Run `python render_supervisor.py` from backend/ (or pass its path from repo root).
"""
import ctypes
from contextlib import contextmanager
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
log = logging.getLogger('emby.supervisor')
SHUTDOWN_SECONDS = 25  # Leave time for cleanup before Render's default 30s kill.


@contextmanager
def startup_lock():
    """Reject a second supervisor on the same instance without touching its children."""
    import fcntl
    path = Path(tempfile.gettempdir()) / 'emby-combined.lock'
    with path.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    # Keep the inode: unlinking a lock file allows two different locks for one path.


def commands(port, schedule_file):
    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('PORT must be an integer between 1 and 65535.') from None
    return [
        ('web', [sys.executable, '-m', 'gunicorn', 'backend.wsgi:application',
                 '--bind', f'0.0.0.0:{port}', '--workers', '1', '--worker-class', 'gevent',
                 '--worker-connections', '1000', '--timeout', '120', '--graceful-timeout', '20',
                 '--keep-alive', '5', '--error-logfile', '-', '--log-level', 'info',
                 '--access-logfile', '-', '--access-logformat', '%(m)s %(U)s %(s)s %(L)s']),
        ('worker', [sys.executable, '-m', 'celery', '-A', 'backend', 'worker',
                    '--loglevel=info', '--pool=solo', '--concurrency=1',
                    '--prefetch-multiplier=1', '--without-gossip', '--without-mingle',
                    '--hostname=emby-combined@%h']),
        ('beat', [sys.executable, '-m', 'celery', '-A', 'backend', 'beat',
                  '--loglevel=info', '--scheduler=backend.singleton_beat:SingletonScheduler',
                  f'--schedule={schedule_file}', '--pidfile=']),
    ]


def enable_subreaper():
    """Adopt/reap grandchildren if a master exits before its own children."""
    if sys.platform.startswith('linux'):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError('Could not enable child-process reaping.')


def group_alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Supervisor:
    def __init__(self, services, *, preflight=None, cwd=ROOT, grace=SHUTDOWN_SECONDS):
        self.services, self.preflight = services, preflight
        self.cwd, self.grace = cwd, grace
        self.children = []
        self.stopping = False

    def request_stop(self, signum, _frame):
        # Only set state in the handler. A signal during Popen cannot strand a
        # child between spawning and registration in self.children.
        self.stopping = True

    def launch(self, name, argv):
        environment = os.environ.copy()
        environment['PYTHONUNBUFFERED'] = '1'
        for setting in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
            environment.setdefault(setting, '1')
        process = subprocess.Popen(argv, cwd=self.cwd, env=environment, start_new_session=True)
        self.children.append((name, process))
        log.info('Started %s (pid=%s)', name, process.pid)
        return process

    def failed_child(self):
        for name, process in self.children:
            code = process.poll()
            if code is not None:
                log.error('%s exited unexpectedly (exit=%s); stopping the service.', name, code)
                return True
        return False

    @staticmethod
    def signal_group(process, sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    def reap_orphans(self):
        # Popen must reap its own direct children first, preserving their codes.
        if all(process.poll() is not None for _, process in self.children):
            while True:
                try:
                    if os.waitpid(-1, os.WNOHANG)[0] == 0:
                        break
                except ChildProcessError:
                    break

    def shutdown(self):
        if not self.children:
            return
        log.info('Stopping web, worker and Beat; allowing up to %ss for graceful exit.', self.grace)
        for _, process in reversed(self.children):
            if process.poll() is None:
                # Celery/Gunicorn masters handle warm shutdown of their workers.
                process.send_signal(signal.SIGTERM)
            else:
                self.signal_group(process, signal.SIGTERM)
        deadline = time.monotonic() + self.grace
        while time.monotonic() < deadline:
            self.reap_orphans()
            if not any(group_alive(p.pid) for _, p in self.children):
                break
            time.sleep(0.1)
        for name, process in self.children:
            # Check the group even if its leader exited: converters/grandchildren
            # must not survive a failed worker or Gunicorn master.
            if group_alive(process.pid):
                log.warning('Force-stopping remaining %s process group.', name)
                self.signal_group(process, signal.SIGKILL)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.reap_orphans()
            if not any(group_alive(p.pid) for _, p in self.children):
                break
            time.sleep(0.05)
        self.reap_orphans()
        if any(group_alive(p.pid) for _, p in self.children):
            raise RuntimeError('A child process group did not stop.')

    def run(self):
        previous = {sig: signal.signal(sig, self.request_stop) for sig in (signal.SIGTERM, signal.SIGINT)}
        result = 1
        try:
            if self.preflight:
                check = self.launch('preflight', self.preflight)
                deadline = time.monotonic() + 120
                while check.poll() is None and not self.stopping:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Startup checks exceeded 120 seconds.')
                    time.sleep(0.1)
                if self.stopping:
                    return 0
                if check.returncode != 0:
                    log.error('Startup checks failed (exit=%s); no services started.', check.returncode)
                    return 1
                self.children.remove(('preflight', check))
            for name, argv in self.services:
                if self.stopping:
                    return 0
                if self.failed_child():
                    return 1
                self.launch(name, argv)
            while not self.stopping:
                if self.failed_child():
                    return 1  # Even an unexpected clean exit is a service failure.
                time.sleep(0.2)
            result = 0
        except Exception as exc:
            log.error('Supervisor failed (%s).', type(exc).__name__)
        finally:
            try:
                self.shutdown()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        return result


def main():
    logging.basicConfig(level=logging.INFO, format='[supervisor] %(levelname)s %(message)s')
    if os.name != 'posix':
        log.error('Combined startup requires Linux/POSIX process groups.')
        return 1
    
    # Ensure backend module is importable (native runtime has different PYTHONPATH)
    import sys
    backend_dir = ROOT.parent if (ROOT.parent / 'backend').exists() else ROOT
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    try:
        enable_subreaper()
        # Each deployment has its own transient schedule file. The Redis lease,
        # not this file or a local pidfile, coordinates overlapping deployments.
        with startup_lock(), tempfile.TemporaryDirectory(prefix='emby-beat-') as directory:
            return Supervisor(commands(os.environ.get('PORT', '8000'), str(Path(directory) / 'schedule')),
                preflight=[sys.executable, '-m', 'backend.combined_preflight']).run()
    except Exception as exc:
        log.error('Combined startup failed (%s).', type(exc).__name__)
        return 1


if __name__ == '__main__':
    sys.exit(main())
