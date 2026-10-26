"""Celery's existing schedule with one Redis lease holder during rolling deploys."""
import logging
import os

from celery.beat import PersistentScheduler

from .runtime_redis import broker_client

log = logging.getLogger(__name__)


class SingletonScheduler(PersistentScheduler):
    LEASE_SECONDS = 60
    CHECK_SECONDS = 5

    def __init__(self, *args, **kwargs):
        self._lease = None
        self._client = None
        self._leader = False
        self._waiting_logged = False
        self._closed = False
        super().__init__(*args, **kwargs)

    def lease(self):
        if self._lease is None:
            self._client = broker_client(self.app)
            self._lease = self._client.lock(os.environ.get('EMBY_BEAT_LOCK_KEY', 'emby:celery:beat:leader:v1'),
                timeout=self.LEASE_SECONDS, blocking=False, thread_local=False)
        return self._lease

    def renew(self):
        try:
            if not self._leader or not self.lease().reacquire():
                raise RuntimeError('Leadership lost.')
        except Exception as exc:
            log.error('Beat leadership lost (%s); refusing further schedule publication.', type(exc).__name__)
            # Celery catches Exception from apply_entry. SystemExit stops its
            # service loop; the supervisor treats ANY Beat exit as a failure.
            raise SystemExit(1) from None

    def tick(self, *args, **kwargs):
        if not self._leader:
            try:
                self._leader = self.lease().acquire(blocking=False)
            except Exception as exc:
                log.error('Beat lease unavailable (%s).', type(exc).__name__)
                raise SystemExit(1) from None
            if not self._leader:
                if not self._waiting_logged:
                    log.info('Beat is standing by while another deployment owns the scheduler lease.')
                    self._waiting_logged = True
                return self.CHECK_SECONDS
            log.info('Beat acquired the scheduler lease.')
        self.renew()
        return min(super().tick(*args, **kwargs), self.CHECK_SECONDS)

    def apply_async(self, *args, **kwargs):
        self.renew()  # Check ownership immediately before every publication.
        return super().apply_async(*args, **kwargs)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            super().close()
        finally:
            if self._leader and self._lease:
                try:
                    self._lease.release()  # Token checked: never delete another leader's lease.
                except Exception as exc:
                    log.warning('Beat lease release was not confirmed (%s).', type(exc).__name__)
                self._leader = False
            if self._client:
                self._client.close()
