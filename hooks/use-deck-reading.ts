"use client";
import { deckApi } from '@/lib/api';
import { useReadingProgress } from './use-reading-progress';

export function useDeckReading({ deckId, ...options }: {
  deckId: string; ready: boolean; page: number; maxPage: number; loaded: boolean;
  initialPage?: number;
  setPage: (page: number) => void; denied: () => void; authorized: () => boolean;
}) {
  return useReadingProgress({ ...options, sourceId: deckId, namespace: 'deck-reading',
    load: () => deckApi.getReadingProgress(deckId),
    save: data => deckApi.saveReadingProgress(deckId, data) });
}
