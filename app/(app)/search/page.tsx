"use client";
import { WorkspaceHeader, WorkspaceEmpty } from "@/components/ui/workspace-header";
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import AuthGuard from '@/components/auth/auth-guard';
import { SearchPanel } from '@/components/search/search-panel';
import { searchTypes, type SearchType } from '@/lib/search';
import { useContentSessionKey } from '@/store/hooks';
function SearchPageContent() {
  const params = useSearchParams();
  const identity = useContentSessionKey();
  const type = params.get('type') ?? 'all';
  return <AuthGuard><div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
    <WorkspaceHeader className="mb-6" eyebrow="Follow a thought" title="Less searching. More studying." description="Find a concept inside your slides, pick up a flashcard, or check what your class has planned." />
    <SearchPanel key={identity} initialQuery={params.get('q') ?? ''} initialType={type in searchTypes ? type as SearchType : 'all'}
      initialSubject={params.get('subject') ?? ''} initialSort={params.get('sort') === 'recent' ? 'recent' : 'relevance'} />
  </div></AuthGuard>;
}
export default function SearchPage() { return <Suspense fallback={<p role="status" className="p-8">Opening search…</p>}><SearchPageContent /></Suspense>; }
