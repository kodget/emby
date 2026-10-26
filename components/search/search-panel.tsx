"use client";

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, BookOpen, CalendarDays, Clock, FileText, Layers, ListChecks, Megaphone, Search, X } from 'lucide-react';
import { Command, CommandInput, CommandList, CommandGroup, CommandItem } from '@/components/ui/command';
import { Button } from '@/components/ui/button';
import { searchLibrary, searchTypes, searchUrl, type SearchResponse, type SearchType } from '@/lib/search';
import { useContentSessionKey } from '@/store/hooks';

const icons = { course: BookOpen, topic: BookOpen, slide: FileText, deck: FileText,
  flashcard: Layers, question: ListChecks, material: BookOpen, announcement: Megaphone, exam: CalendarDays, page: ArrowRight };
const shortcuts = [
  { title: 'Browse class materials', url: '/courses', icon: BookOpen },
  { title: 'Review flashcards', url: '/flashcards', icon: Layers },
  { title: 'Practice questions', url: '/quiz', icon: ListChecks },
  { title: 'Class announcements', url: '/class/announcements', icon: Megaphone },
];

function Highlight({ text, query }: { text: string; query: string }) {
  const terms = query.match(/[\p{L}\p{N}]+/gu)?.slice(0, 8) ?? [];
  if (!terms.length) return <>{text}</>;
  const regex = new RegExp(`(${terms.join('|')})`, 'giu');
  return <>{text.split(regex).map((part, index) => index % 2
    ? <mark key={index} className="rounded-sm bg-primary/10 text-inherit">{part}</mark> : part)}</>;
}

export function SearchPanel({ compact = false, initialQuery = '', initialType = 'all', initialSubject = '', initialSort = 'relevance', onNavigate }: {
  compact?: boolean; initialQuery?: string; initialType?: SearchType; initialSubject?: string;
  initialSort?: string; onNavigate?: () => void;
}) {
  const router = useRouter();
  const sessionKey = useContentSessionKey();
  const historyKey = `emby:search:${sessionKey}`;
  const [query, setQuery] = useState(initialQuery);
  const [type, setType] = useState<SearchType>(initialType);
  const [subject, setSubject] = useState(initialSubject);
  const [sort, setSort] = useState(initialSort);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [subjects, setSubjects] = useState<SearchResponse['subjects']>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const sequence = useRef(0);
  const lastWrittenUrl = useRef('');
  const completedRequest = useRef('');
  const normalized = query.trim().replace(/\s+/g, ' ');
  const words = normalized.match(/[\p{L}\p{N}]+/gu) ?? [];
  const valid = normalized.length >= 2 && normalized.length <= 160 && words.length > 0 && words.length <= 8;
  const requestKey = JSON.stringify([normalized, type, subject, sort, offset]);

  useEffect(() => {
    if (lastWrittenUrl.current === searchUrl(initialQuery, initialType, initialSubject, initialSort)) return;
    setQuery(initialQuery); setType(initialType); setSubject(initialSubject); setSort(initialSort); setOffset(0);
  }, [initialQuery, initialType, initialSubject, initialSort]);
  useEffect(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem(historyKey) || '[]');
      setRecent(Array.isArray(stored) ? stored.filter(q => typeof q === 'string').slice(0, 6) : []);
    } catch { setRecent([]); }
  }, [historyKey]);
  function remember(value: string) {
    if (value.trim().length < 2) return;
    const values = [value.trim(), ...recent.filter(item => item !== value.trim())].slice(0, 6);
    setRecent(values);
    try { sessionStorage.setItem(historyKey, JSON.stringify(values)); } catch { /* Search works without storage. */ }
  }
  function navigate(url: string) { remember(normalized); onNavigate?.(); router.push(url); }
  function changeQuery(value: string) { setQuery(value); setOffset(0); }
  useEffect(() => {
    const current = ++sequence.current;
    const controller = new AbortController();
    const owner = sessionStorage.getItem('user');
    const active = () => current === sequence.current && !controller.signal.aborted && owner === sessionStorage.getItem('user');
    setData(null); setError(''); setLoading(valid);
    if (!valid) return () => controller.abort();
    const timer = setTimeout(() => {
      void searchLibrary({ q: normalized, type, subject, sort, offset, limit: compact ? 8 : 20 }, controller.signal)
        .then(response => { if (active()) { completedRequest.current = requestKey; setData(response); setSubjects(response.subjects); } })
        .catch(reason => { if (active()) setError(reason?.response?.status === 429
          ? 'You’re searching quickly. Wait a moment, then try again.'
          : 'Could not search your library. Check your connection and try again.'); })
        .finally(() => { if (active()) setLoading(false); });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [normalized, type, subject, sort, offset, compact, retry, sessionKey, valid, requestKey]);

  useEffect(() => {
    if (compact || (normalized && (!data || loading || completedRequest.current !== requestKey))) return;
    const url = searchUrl(normalized, type, subject, sort);
    lastWrittenUrl.current = url;
    window.history.replaceState(null, '', url);
  }, [compact, data, loading, normalized, type, subject, sort, requestKey]);

  return <Command shouldFilter={false} className={compact ? 'rounded-none' : 'rounded-2xl border border-border bg-card shadow-sm'} loop>
    <div className="flex items-center pr-3">
      <div className="min-w-0 flex-1">
        <CommandInput value={query} onValueChange={changeQuery} maxLength={160} aria-label="Search your library"
          placeholder="Try a topic, phrase or document…" className="h-14 text-base"
          onKeyDown={event => { if (event.key === 'Enter') remember(normalized); }} />
      </div>
      {query && <button type="button" aria-label="Clear search" onClick={() => changeQuery('')} className="flex size-11 shrink-0 items-center justify-center rounded-lg hover:bg-muted"><X className="size-4" /></button>}
    </div>
    <div className="flex flex-wrap items-center gap-2 border-b border-border p-3">
      <label className="sr-only" htmlFor={compact ? 'quick-type' : 'search-type'}>Content type</label>
      <select id={compact ? 'quick-type' : 'search-type'} value={type} onChange={e => { setType(e.target.value as SearchType); setOffset(0); }}
        className="h-11 max-w-full rounded-lg border border-input bg-background px-3 text-sm">
        {Object.entries(searchTypes).map(([key, label]) => <option key={key} value={key}>{label}{data && key !== 'all' ? ` (${data.counts[key] ?? 0})` : ''}</option>)}
      </select>
      <label className="sr-only" htmlFor={compact ? 'quick-subject' : 'search-subject'}>Subject</label>
      <select id={compact ? 'quick-subject' : 'search-subject'} value={subject} onChange={e => { setSubject(e.target.value); setOffset(0); }}
        className="h-11 min-w-0 max-w-[200px] rounded-lg border border-input bg-background px-3 text-sm">
        <option value="">All subjects</option>
        {subject && !subjects.some(s => s.id === subject) && <option value={subject}>Selected subject</option>}
        {subjects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      {!compact && <><label className="sr-only" htmlFor="search-sort">Sort results</label><select id="search-sort" value={sort} onChange={e => { setSort(e.target.value); setOffset(0); }} className="h-11 rounded-lg border border-input bg-background px-3 text-sm sm:ml-auto">
        <option value="relevance">Most relevant</option><option value="recent">Newest first</option>
      </select></>}
    </div>
    <CommandList aria-label="Search results" className={compact ? 'max-h-[min(45dvh,400px)]' : 'max-h-none'} aria-busy={loading}>
      {!normalized && <>
        <div className="px-5 pt-5 pb-2 text-sm text-muted-foreground">Search titles and the text inside processed slides. Your results follow your class access.</div>
        {recent.length > 0 && <CommandGroup heading="Recent searches">
          {recent.map(value => <CommandItem key={value} value={`recent:${value}`} onSelect={() => changeQuery(value)} className="min-h-11 gap-3 px-4"><Clock className="size-4" />{value}</CommandItem>)}
          <button type="button" className="min-h-11 px-4 text-xs text-muted-foreground underline" onClick={() => { setRecent([]); try { sessionStorage.removeItem(historyKey); } catch {} }}>Clear recent searches</button>
        </CommandGroup>}
        <CommandGroup heading="Go straight to">
          {shortcuts.map(item => <CommandItem key={item.url} value={item.url} onSelect={() => navigate(item.url)} className="min-h-12 gap-3 px-4"><item.icon className="size-4 text-primary" />{item.title}<ArrowRight className="ml-auto size-4" /></CommandItem>)}
        </CommandGroup>
      </>}
      {normalized && !valid && <p role="status" className="p-6 text-sm text-muted-foreground">Use at least two characters and no more than eight search words.</p>}
      {loading && <div role="status" className="p-5"><p className="mb-4 text-sm text-muted-foreground">Searching your library…</p>{[1, 2, 3].map(i => <div key={i} className="mb-3 h-16 animate-pulse rounded-xl bg-muted" />)}</div>}
      {error && <div role="alert" className="p-6"><p className="text-sm">{error}</p><Button variant="outline" className="mt-4" onClick={() => setRetry(n => n + 1)}>Try again</Button></div>}
      {data && data.total === 0 && <div className="px-5 py-10 text-center">
        <Search className="mx-auto mb-4 size-7 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-lg">No matches for “{normalized}”</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">Try fewer words, check the spelling, or search the document title. Text becomes searchable after processing.</p>
        {data.suggestions?.map(suggestion => <Button key={suggestion} variant="outline" className="mt-4" onClick={() => changeQuery(suggestion)}>Search “{suggestion}” instead</Button>)}
        {(type !== 'all' || subject) && <Button variant="outline" className="mt-4" onClick={() => { setType('all'); setSubject(''); setOffset(0); }}>Clear filters</Button>}
        <Link href="/courses" onClick={onNavigate} className="mt-4 block text-sm text-primary underline">Browse class materials</Link>
      </div>}
      {data && data.total > 0 && <CommandGroup heading={`${data.total} result${data.total === 1 ? '' : 's'}${offset ? ` · From ${offset + 1}` : ''}`}>
        {data.results.map(result => { const Icon = icons[result.type]; return <CommandItem key={result.id} value={result.id} onSelect={() => navigate(result.url)} className="items-start gap-3 rounded-xl px-4 py-4">
          <span className="mt-1 flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 text-primary"><Icon className="size-4" aria-hidden="true" /></span>
          <span className="min-w-0 flex-1">
            <span className="mb-1 block text-xs text-muted-foreground">{result.label}{result.page ? ` · Page ${result.page}` : ''}</span>
            <span className="block break-words text-sm font-semibold leading-relaxed"><Highlight text={result.title} query={normalized} /></span>
            {result.excerpt && <span className="mt-1 line-clamp-2 break-words text-sm leading-relaxed text-muted-foreground"><Highlight text={result.excerpt} query={normalized} /></span>}
          </span><ArrowRight className="mt-3 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </CommandItem>; })}
      </CommandGroup>}
    </CommandList>
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-xs text-muted-foreground">
      {compact ? <><span>↑ ↓ to choose · Enter to open</span><Button variant="ghost" size="sm" onClick={() => navigate(searchUrl(normalized, type, subject, sort))}>All results <ArrowRight className="size-4" /></Button></>
        : <><span role="status" aria-live="polite">{data ? `${data.total} matching results` : 'Search your study library'}</span><div className="flex gap-2">
          {offset > 0 && <Button variant="outline" disabled={loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</Button>}
          {data?.next_offset != null && <Button variant="outline" onClick={() => setOffset(data.next_offset!)}>Next results</Button>}
        </div></>}
    </div>
  </Command>;
}
