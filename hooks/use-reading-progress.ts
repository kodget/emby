"use client";
import { useEffect, useRef, useState } from 'react';
import { ReadingRecorder, type ReadingCheckpoint } from '@/lib/reading-recorder';

function identity() {
  try {
    const user = JSON.parse(sessionStorage.getItem('user') ?? 'null');
    const id = user?.user_id ?? user?.id;
    return (typeof id === 'number' || (typeof id === 'string' && id.length > 0))
      ? JSON.stringify([id, user.class_group, user.class_role]) : null;
  } catch { return null; }
}

export function useReadingProgress({ sourceId, namespace, load, save, ready, page, maxPage, loaded, setPage, denied, authorized, initialPage }: {
  sourceId: string; namespace: 'course-reading' | 'deck-reading'; load: () => Promise<{ current_page: number }>;
  save: (data: ReadingCheckpoint) => Promise<unknown>; ready: boolean; page: number; maxPage: number; loaded: boolean;
  setPage: (page: number) => void; denied: () => void;
  authorized: () => boolean;
  initialPage?: number;
}) {
  const recorder = useRef<ReadingRecorder | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [unavailableSave, setUnavailableSave] = useState<ReadingCheckpoint>();
  const [attempt, setAttempt] = useState(0);
  const latest = useRef({ page, loaded, setPage, denied, authorized, load, save });
  latest.current = { page, loaded, setPage, denied, authorized, load, save };
  const navigated = useRef(false);
  const changePage = (value: number) => {
    navigated.current = true;
    if (recorder.current && value !== recorder.current.page) recorder.current.visible(false);
    recorder.current?.turn(value);
    setPage(value);
  };

  useEffect(() => {
    if (!ready) { navigated.current = false; return; }
    const saveCheckpoint = latest.current.save;
    const owner = identity();
    if (!owner) return;
    const key = `emby:${namespace}:${owner}:${sourceId}`;
    let mounted = true;
    let tracker: ReadingRecorder | null = null;
    let interval: ReturnType<typeof setInterval> | undefined;
    const active = () => identity() === owner && latest.current.authorized();
    const visible = () => document.visibilityState === 'visible' && latest.current.loaded;
    const onVisibility = () => { tracker?.visible(visible()); };
    const onExit = () => { tracker?.visible(false); };
    const onOnline = () => { tracker?.retry(); };
    setLoadError(false);
    setSaveError(false);
    setUnavailableSave(undefined);
    void latest.current.load().then(saved => {
      if (!mounted || !active()) return;
      let pending: ReadingCheckpoint[] = [];
      try {
        const stored = JSON.parse(sessionStorage.getItem(key) ?? '[]');
        if (Array.isArray(stored)) pending = stored.filter(row => row && Number.isInteger(row.current_page)
          && row.current_page > 0 && Number.isInteger(row.seconds) && row.seconds >= 0 && row.seconds <= 300
          && typeof row.request_id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(row.request_id));
      } catch { /* A fresh checkpoint can still be saved if browser storage is unavailable. */ }
      const owned = new Set(pending.map(row => row.request_id));
      tracker = new ReadingRecorder({ page: saved.current_page || 1, maxPage, pending,
        now: () => performance.now(), id: () => crypto.randomUUID(), active,
        send: async data => {
          try { return await saveCheckpoint(data); }
          catch (error: any) {
            if (mounted && active() && [401, 403, 404].includes(error?.response?.status)) latest.current.denied();
            throw error;
          }
        },
        persist: queue => {
          try {
            const stored = JSON.parse(sessionStorage.getItem(key) ?? '[]');
            const other = Array.isArray(stored) ? stored.filter(row => !owned.has(row.request_id)
              && !queue.some(queued => queued.request_id === row.request_id)) : [];
            sessionStorage.setItem(key, JSON.stringify([...other, ...queue]));
            queue.forEach(row => owned.add(row.request_id));
          } catch { if (mounted) setSaveError(true); }
        },
        unavailable: (error: any) => error?.response?.status === 400
          && error?.response?.data?.code === 'reading_page_unavailable',
        status: (error, rejected) => { if (mounted && active()) {
          setSaveError(error); setUnavailableSave(rejected);
        } },
      });
      recorder.current = tracker;
      if (navigated.current) tracker.turn(latest.current.page);
      else {
        if (initialPage && Number.isInteger(initialPage) && initialPage > 0) tracker.turn(Math.min(initialPage, maxPage));
        latest.current.setPage(tracker.page);
      }
      tracker.visible(tracker.page === latest.current.page && visible());
      tracker.retry();
      let ticks = 0;
      interval = setInterval(() => {
        tracker?.visible(visible());
        if (++ticks % 15 === 0) tracker?.checkpoint();
      }, 1000);
    }).catch((error: any) => {
      if (!mounted || !active()) return;
      if ([401, 403, 404].includes(error?.response?.status)) latest.current.denied();
      else setLoadError(true);
    });
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onExit);
    window.addEventListener('online', onOnline);
    return () => {
      mounted = false;
      tracker?.visible(false); // Persist unsent checkpoints even if navigation cancels the request.
      recorder.current = null;
      if (interval) clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onExit);
      window.removeEventListener('online', onOnline);
    };
  }, [sourceId, namespace, ready, maxPage, attempt, initialPage]);

  useEffect(() => { recorder.current?.visible(document.visibilityState === 'visible' && loaded); }, [loaded]);
  return { changePage, loadError, saveError, unavailableSave,
    discardUnavailable: () => recorder.current?.discardUnavailable(),
    retry: () => { if (loadError) setAttempt(value => value + 1); else recorder.current?.retry(); } };
}
