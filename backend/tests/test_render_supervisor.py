"""Pure-stdlib tests; real process/signal cases run on Linux, never production."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import render_supervisor as runtime


class CommandTests(unittest.TestCase):
    def test_three_foreground_children_keep_wsgi_and_single_worker(self):
        specs = dict(runtime.commands('10000', '/tmp/private/schedule'))
        self.assertEqual(set(specs), {'web', 'worker', 'beat'})
        self.assertIn('backend.wsgi:application', specs['web'])
        self.assertIn('0.0.0.0:10000', specs['web'])
        self.assertEqual(specs['web'][specs['web'].index('--workers') + 1], '4')
        self.assertEqual(specs['web'][specs['web'].index('--worker-class') + 1], 'gevent')
        self.assertIn('--pool=solo', specs['worker'])
        self.assertIn('--concurrency=1', specs['worker'])
        self.assertIn('--prefetch-multiplier=1', specs['worker'])
        self.assertIn('--scheduler=backend.singleton_beat:SingletonScheduler', specs['beat'])
        for argv in specs.values():
            self.assertEqual(argv[0], sys.executable)
            self.assertNotIn('--detach', argv)
            self.assertNotIn('--daemon', argv)
            self.assertNotIn('-B', argv)

    def test_invalid_port_is_rejected_without_echoing_input(self):
        for value in ('secret-value', '0', '65536', '8000; echo unsafe'):
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                runtime.commands(value, '/tmp/schedule')
            self.assertNotIn(value, str(error.exception))

    def test_spawn_uses_explicit_backend_cwd_separate_session_and_inherited_environment(self):
        runner = runtime.Supervisor([])
        with patch.object(runtime.subprocess, 'Popen') as popen:
            runner.launch('worker', ['python', '-m', 'celery'])
        self.assertEqual(popen.call_args.kwargs['cwd'], runtime.ROOT)
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertNotIn('shell', popen.call_args.kwargs)
        self.assertEqual(popen.call_args.kwargs['env']['PYTHONUNBUFFERED'], '1')
        self.assertEqual(len(runner.children), 1)

    def test_any_unexpected_exit_including_zero_is_failure(self):
        for code in (0, 1, -9):
            runner = runtime.Supervisor([])
            runner.children = [('worker', Mock(poll=Mock(return_value=code)))]
            self.assertTrue(runner.failed_child())

    def test_preflight_failure_starts_no_services_and_returns_nonzero(self):
        runner = runtime.Supervisor([('web', ['never-run'])], preflight=['check'])
        process = Mock(returncode=17, poll=Mock(return_value=17))
        with patch.object(runner, 'launch', return_value=process) as launch, patch.object(runner, 'shutdown'):
            self.assertEqual(runner.run(), 1)
        launch.assert_called_once_with('preflight', ['check'])

    def test_a_spawn_failure_cleans_already_started_children(self):
        runner = runtime.Supervisor([('web', ['ok']), ('worker', ['missing'])])
        with patch.object(runner, 'launch', side_effect=[Mock(), OSError('secret detail')]), patch.object(
                runner, 'shutdown') as cleanup, self.assertLogs('emby.supervisor', level='ERROR') as logs:
            self.assertEqual(runner.run(), 1)
        cleanup.assert_called_once()
        self.assertNotIn('secret detail', str(logs.output))


CHILD = r'''
import os, signal, subprocess, sys, time
from pathlib import Path
directory, name, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def stop(signum, frame):
    (directory / (name + '.stopped')).write_text(str(signum))
    raise SystemExit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN if mode == 'stubborn' else stop)
if mode == 'grandchild':
    subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)'])
(directory / (name + '.pid')).write_text(str(os.getpid()))
while True:
    if (directory / (name + '.exit')).exists():
        raise SystemExit(int((directory / (name + '.exit')).read_text()))
    time.sleep(0.02)
'''


@unittest.skipUnless(sys.platform.startswith('linux'), 'Real process-group/subreaper verification requires Linux')
class LinuxProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='emby-supervisor-test-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def start(self, modes=('normal', 'normal', 'normal'), preflight=None, cwd=None):
        child = self.directory / 'child.py'
        child.write_text(CHILD)
        specs = [(name, [sys.executable, str(child), str(self.directory), name, mode])
                 for name, mode in zip(('web', 'worker', 'beat'), modes)]
        harness = self.directory / 'supervisor.py'
        harness.write_text('import sys\nsys.path.insert(0, ' + repr(str(runtime.ROOT)) + ')\n'
            'from render_supervisor import Supervisor, enable_subreaper\n'
            'enable_subreaper()\n'
            f'sys.exit(Supervisor({specs!r}, preflight={preflight!r}, grace=0.4).run())\n')
        process = subprocess.Popen([sys.executable, str(harness)], cwd=cwd, start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.cleanup_process, process)
        return process

    def cleanup_process(self, process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=2)
        for path in self.directory.glob('*.pid'):
            try:
                os.killpg(int(path.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass

    def ready(self):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            paths = list(self.directory.glob('*.pid'))
            if len(paths) == 3:
                return [int(path.read_text()) for path in paths]
            time.sleep(0.02)
        self.fail('The supervisor did not start all three children.')

    def assert_groups_gone(self, pids):
        self.assertTrue(all(not runtime.group_alive(pid) for pid in pids))

    def test_sigterm_reaches_children_and_all_process_groups_exit(self):
        process = self.start(cwd=self.directory)  # Entry works outside backend/ too.
        pids = self.ready()
        process.terminate()
        self.assertEqual(process.wait(timeout=6), 0)
        self.assertEqual(len(list(self.directory.glob('*.stopped'))), 3)
        self.assert_groups_gone(pids)

    def test_worker_exit_zero_fails_service_and_stops_siblings(self):
        process = self.start()
        pids = self.ready()
        (self.directory / 'worker.exit').write_text('0')
        self.assertEqual(process.wait(timeout=6), 1)
        self.assert_groups_gone(pids)

    def test_killed_beat_fails_service_and_reaps_stubborn_orphan_grandchild(self):
        process = self.start(modes=('grandchild', 'stubborn', 'normal'))
        pids = self.ready()
        os.kill(int((self.directory / 'beat.pid').read_text()), signal.SIGKILL)
        self.assertEqual(process.wait(timeout=6), 1)
        self.assert_groups_gone(pids)

    def test_preflight_nonzero_does_not_start_children(self):
        process = self.start(preflight=[sys.executable, '-c', 'raise SystemExit(19)'])
        self.assertEqual(process.wait(timeout=6), 1)
        self.assertEqual(list(self.directory.glob('*.pid')), [])

    def test_local_startup_lock_rejects_second_supervisor(self):
        import fcntl
        with patch.object(runtime.tempfile, 'gettempdir', return_value=str(self.directory)):
            with runtime.startup_lock():
                with self.assertRaises(BlockingIOError):
                    with runtime.startup_lock():
                        self.fail('A second supervisor obtained the same startup lock.')
            with runtime.startup_lock():
                pass  # Reacquisition succeeds after the first owner exits.
