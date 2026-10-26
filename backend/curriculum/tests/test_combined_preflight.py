from unittest.mock import Mock, patch, call
import os
from pathlib import Path
import subprocess
import tempfile
import time

from django.test import SimpleTestCase, override_settings

from backend import combined_preflight
from backend.celery import app
import render_supervisor


class CombinedPreflightTests(SimpleTestCase):
    @override_settings(DEBUG=False, CELERY_TASK_ALWAYS_EAGER=False)
    def test_wsgi_discovery_and_checks_are_read_only_and_use_existing_schedule(self):
        client = Mock()
        with patch('django.conf.settings.DATABASES', {'default': {'ENGINE': 'django.db.backends.postgresql'}}), patch(
                'django.core.management.call_command') as command, patch(
                'backend.runtime_redis.broker_client', return_value=client), patch('shutil.which', return_value='/usr/bin/tool'):
            combined_preflight.check()
        self.assertEqual(command.call_args_list, [call('check', fail_level='ERROR'),
                         call('migrate', check=True, interactive=False, verbosity=0)])
        client.ping.assert_called_once(); client.close.assert_called_once()
        from backend.wsgi import application
        self.assertTrue(callable(application))
        for entry in app.conf.beat_schedule.values():
            self.assertIn(entry['task'], app.tasks)

    @override_settings(DEBUG=False, CELERY_TASK_ALWAYS_EAGER=True)
    def test_eager_mode_is_rejected_before_database_or_broker_checks(self):
        with patch('django.core.management.call_command') as command, self.assertRaises(ValueError):
            combined_preflight.check()
        command.assert_not_called()

    @override_settings(DEBUG=False, CELERY_TASK_ALWAYS_EAGER=False)
    def test_pending_migrations_stop_startup_without_running_migrations(self):
        from django.core.management.base import CommandError
        with patch('django.conf.settings.DATABASES', {'default': {'ENGINE': 'django.db.backends.postgresql'}}), patch(
                'django.core.management.call_command', side_effect=[None, CommandError('Unapplied migrations')]), patch(
                'backend.runtime_redis.broker_client') as client, self.assertRaises(CommandError):
            combined_preflight.check()
        client.assert_not_called()

    @override_settings(DEBUG=False, CELERY_TASK_ALWAYS_EAGER=False)
    def test_broker_failure_fails_startup_and_closes_connection(self):
        client = Mock(ping=Mock(side_effect=ConnectionError('unavailable')))
        with patch('django.conf.settings.DATABASES', {'default': {'ENGINE': 'django.db.backends.postgresql'}}), patch(
                'django.core.management.call_command'), patch('backend.runtime_redis.broker_client', return_value=client), self.assertRaises(ConnectionError):
            combined_preflight.check()
        client.close.assert_called_once()

    def test_real_worker_boots_discovers_tasks_and_consumes_an_isolated_probe(self):
        argv = dict(render_supervisor.commands('8000', '/unused/schedule'))['worker']
        # Same backend.celery app; this test-only module adds one harmless probe.
        argv[argv.index('-A') + 1] = 'tests.combined_worker_probe'
        environment = os.environ.copy()
        environment.update(DJANGO_SETTINGS_MODULE='tests.integration_settings',
            CELERY_BROKER_URL='memory://', CELERY_BROKER_READ_URL='memory://',
            CELERY_BROKER_WRITE_URL='memory://', CELERY_RESULT_BACKEND='cache+memory://',
            PYTHONUNBUFFERED='1')
        with tempfile.TemporaryDirectory(prefix='emby-worker-smoke-') as directory:
            log = Path(directory) / 'worker.log'
            with log.open('w', encoding='utf-8') as output:
                process = subprocess.Popen(argv, cwd=render_supervisor.ROOT, env=environment,
                    stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                try:
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline and process.poll() is None:
                        if 'EMBY_ISOLATED_WORKER_PROBE_OK' in log.read_text(encoding='utf-8', errors='replace'):
                            break
                        time.sleep(0.1)
                    text = log.read_text(encoding='utf-8', errors='replace')
                    self.assertIn('EMBY_ISOLATED_WORKER_PROBE_OK', text, text[-4000:])
                    for task in ('curriculum.tasks.process_slide_task', 'curriculum.tasks.generate_question_bank_task',
                                 'learning.tasks.recover_question_generation_task'):
                        self.assertIn(task, text)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(timeout=5)
