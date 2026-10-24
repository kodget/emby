"use client";
import type { ReadingCheckpoint } from '@/lib/reading-recorder';

export function UnavailableReadingSave({ checkpoint, retry, discard }: {
  checkpoint: ReadingCheckpoint; retry: () => void; discard: () => void;
}) {
  return <div role="alert" className="bg-amber-950 p-3 text-sm text-amber-100">
    Page {checkpoint.current_page} is no longer available. Its unsaved {checkpoint.seconds} seconds
    are holding up later saves. Retry if the page has been restored, or discard this save to continue
    syncing. Discarding will lose these {checkpoint.seconds} seconds of unsaved reading time.{' '}
    <button className="mr-3 underline" onClick={retry}>Retry unavailable page</button>
    <button className="underline" onClick={discard}>Discard this save</button>
  </div>;
}
