import tempfile
import unittest
from unittest.mock import Mock, patch

from celery import Celery
from celery.beat import PersistentScheduler
from redis.exceptions import LockNotOwnedError

from backend.runtime_redis import validate_broker_url, broker_client
from backend.singleton_beat import SingletonScheduler


class BrokerTests(unittest.TestCase):
    def test_rejects_local_or_missing_broker_without_exposing_credentials(self):
        for url in ('', 'memory://', 'redis://localhost/0', 'redis://127.0.0.1/0',
                    'redis://[::1]/0', 'redis://0.0.0.0/0', 'redis://user:secret@localhost/0',
                    'redis://user:secret@remote.test:not-a-port'):
            with self.subTest(url=url), self.assertRaises(ValueError) as error:
                validate_broker_url(url)
            self.assertNotIn('secret', str(error.exception))

    def test_existing_remote_tls_broker_is_used_without_changing_its_url(self):
        url = 'rediss://user:placeholder@broker.example.test:6380/2?ssl_cert_reqs=required'
        app = Mock(conf=Mock(broker_url=url, broker_use_ssl={}))
        with patch('redis.Redis.from_url') as client:
            broker_client(app)
        client.assert_called_once_with(url, socket_connect_timeout=5, socket_timeout=5)

    def test_boolean_ssl_configuration_is_respected(self):
        from redis import SSLConnection
        app = Mock(conf=Mock(broker_url='redis://broker.example.test/0', broker_use_ssl=True))
        with patch('redis.Redis.from_url') as client:
            broker_client(app)
        self.assertIs(client.call_args.kwargs['connection_class'], SSLConnection)


class Lease:
    """Shared token state; redis-py's actual lease operations are not reimplemented."""
    def __init__(self, state):
        self.state = state
    def acquire(self, blocking=False):
        if self.state['owner'] is not None:
            return False
        self.state['owner'] = self
        return True
    def reacquire(self):
        if self.state['owner'] is not self:
            raise LockNotOwnedError('Lost lease')
        return True
    def release(self):
        if self.state['owner'] is not self:
            raise LockNotOwnedError('Lost lease')
        self.state['owner'] = None


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.state = {'owner': None}
        self.temp = tempfile.TemporaryDirectory(prefix='emby-scheduler-test-')
        self.addCleanup(self.temp.cleanup)
        self.app = Celery('isolated-beat', set_as_current=False, broker='memory://')
        self.app.conf.beat_schedule = {'probe': {'task': 'tests.probe', 'schedule': 60.0}}
        self.addCleanup(self.app.close)

    def scheduler(self, name):
        scheduler = SingletonScheduler(app=self.app, schedule_filename=self.temp.name + '/' + name)
        scheduler._lease = Lease(self.state)
        self.addCleanup(scheduler.close)
        return scheduler

    def test_two_schedulers_publish_only_from_lease_holder_then_transfer_ownership(self):
        first, second = self.scheduler('first'), self.scheduler('second')
        with patch.object(PersistentScheduler, 'tick', return_value=300) as tick:
            self.assertEqual(first.tick(), 5)
            self.assertEqual(second.tick(), 5)
            tick.assert_called_once()
            first.close()
            self.assertEqual(second.tick(), 5)
            self.assertEqual(tick.call_count, 2)
        self.assertIs(self.state['owner'], second._lease)

    def test_expired_lease_blocks_old_leader_before_publishing(self):
        first, second = self.scheduler('first'), self.scheduler('second')
        with patch.object(PersistentScheduler, 'tick', return_value=60):
            first.tick()
            self.state['owner'] = None  # Simulate TTL expiry after a suspended/dead instance.
            second.tick()
        with patch.object(PersistentScheduler, 'apply_async') as publish:
            with self.assertRaises(SystemExit):
                first.apply_async(Mock())
            publish.assert_not_called()
        first.close()
        self.assertIs(self.state['owner'], second._lease)

    def test_redis_failure_stops_scheduling_instead_of_running_unlocked(self):
        scheduler = self.scheduler('failure')
        scheduler._lease = Mock(acquire=Mock(side_effect=RuntimeError('redis://user:secret@host')))
        with self.assertLogs('backend.singleton_beat', level='ERROR') as logs, self.assertRaises(SystemExit):
            scheduler.tick()
        self.assertNotIn('secret', str(logs.output))

    def test_existing_schedule_and_timezone_are_preserved(self):
        self.app.conf.timezone = 'Africa/Lagos'
        scheduler = self.scheduler('config')
        self.assertEqual(scheduler.schedule['probe'].task, 'tests.probe')
        self.assertEqual(scheduler.app.conf.timezone, 'Africa/Lagos')
