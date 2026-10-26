"use client";

import { useEffect } from 'react';
import Link from 'next/link';
import { CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { useAppSelector, useAppDispatch, useContentSessionKey } from '@/store/hooks';
import { updateProgress, type UploadStatus } from '@/store/uploads-slice';

export function UploadProgressStrip() {
  const dispatch = useAppDispatch();
  const items = useAppSelector(s => s.uploads.items);
  const sessionKey = useContentSessionKey();
  const activeKey = JSON.stringify(items.filter(u => u.slideId && !['uploading', 'done', 'error'].includes(u.status))
    .map(u => ({ id: u.id, slideId: u.slideId })));
  useEffect(() => {
    const active: { id: string; slideId: string }[] = JSON.parse(activeKey);
    if (!active.length) return;
    const controller = new AbortController();
    const owner = sessionStorage.getItem('user');
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    const current = () => !controller.signal.aborted && owner === sessionStorage.getItem('user');
    async function poll() {
      for (const upload of active) {
        try {
          // The shared client refreshes expired tokens. Sequential polling avoids
          // overlapping requests when the host is waking up or the network is slow.
          const { data } = await api.get(`/api/slides/${upload.slideId}/status/`, { signal: controller.signal, timeout: 30000 });
          if (!current()) return;
          failures = 0;
          let status: UploadStatus = 'processing', progress = 45, detail = 'Original saved. Waiting for processing…';
          const report = data.progress;
          if (data.reading_ready) {
            status = 'done'; progress = 100; detail = 'Ready to read. AI study tools prepare separately.';
          } else if (data.status === 'failed') {
            status = data.next_attempt_at ? 'retrying' : 'error';
            detail = data.next_attempt_at ? `Original saved. Automatic retry scheduled (attempt ${data.attempts || 1} of 4).` : '';
          } else if (report?.total > 0) {
            const storing = report.phase === 'storing_pages';
            const fraction = Math.max(0, Math.min(1, report.completed / report.total));
            progress = storing ? 75 + fraction * 23 : 50 + fraction * 25;
            detail = `${storing ? 'Saving' : 'Rendering'} pages ${report.completed} of ${report.total}`;
          } else if (data.status === 'downloading') {
            status = 'downloading'; detail = 'Loading your saved original…';
          } else if (data.status === 'converting_to_jpg') {
            status = 'converting_to_jpg'; progress = 50; detail = 'Preparing readable pages…';
          }
          dispatch(updateProgress({ id: upload.id, status, progress, detail,
            error: status === 'error' ? data.error_message || 'Processing stopped. Open the document to retry.' : undefined }));
        } catch (error: any) {
          if (!current()) return;
          const code = error.response?.status;
          if ([401, 403, 404].includes(code)) {
            dispatch(updateProgress({ id: upload.id, progress: 0, status: 'error', error:
              code === 401 ? 'Sign in again to check this upload.' : 'This document is no longer available to your account.' }));
          } else {
            failures += 1;
            dispatch(updateProgress({ id: upload.id, progress: 45, status: 'processing',
              detail: 'Connection interrupted. Your saved upload keeps processing; reconnecting…' }));
          }
        }
      }
      if (current()) timer = setTimeout(poll, Math.min(30000, 3000 * 2 ** Math.min(failures, 4)));
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [activeKey, dispatch, sessionKey]);

  const visible = [...items.filter(u => !['done', 'error'].includes(u.status)),
    ...items.filter(u => ['done', 'error'].includes(u.status)).slice(0, 1)].slice(0, 3);
  if (!visible.length) return null;
  return <section aria-label="Upload progress" className="space-y-2 border-b bg-card px-4 py-3">
    {visible.map(upload => <div key={upload.id} className="mx-auto max-w-5xl">
      <div className="flex items-center gap-2 text-sm">
        {upload.status === 'done' ? <CheckCircle2 className="size-4 shrink-0 text-primary" /> : upload.status === 'error'
          ? <AlertTriangle className="size-4 shrink-0 text-destructive" /> : <Loader2 className="size-4 shrink-0 animate-spin motion-reduce:animate-none" />}
        <span className="min-w-0 flex-1 truncate font-medium">{upload.title}</span>
        {upload.slideId && <Link className="shrink-0 px-2 py-2 text-sm font-medium text-primary underline" href={`/read/${upload.moduleId}/${upload.slideId}`}>Open document</Link>}
      </div>
      <p role={upload.status === 'error' ? 'alert' : 'status'} className="text-xs text-muted-foreground">{upload.error || upload.detail || 'Uploading…'}</p>
      {!['done', 'error'].includes(upload.status) && <div role="progressbar" aria-label={`Processing ${upload.title}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(upload.progress)} className="mt-2 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-[width] motion-reduce:transition-none" style={{ width: `${upload.progress}%` }} /></div>}
    </div>)}
  </section>;
}
