import { api } from './api';
export const searchTypes = {
  all: 'Everything', course: 'Subjects & modules', topic: 'Topics', slide: 'Slides',
  deck: 'Documents', flashcard: 'Flashcards', question: 'Questions', material: 'Resources',
  announcement: 'Announcements', exam: 'Exams', page: 'Pages & tools',
} as const;
export type SearchType = keyof typeof searchTypes;
export type SearchResult = {
  id: string; type: Exclude<SearchType, 'all'>; title: string; excerpt: string;
  url: string; label: string; page: number | null; created_at: string | null;
};
export type SearchResponse = {
  query: string; results: SearchResult[]; total: number; next_offset: number | null;
  counts: Record<string, number>; subjects: { id: string; name: string }[];
  suggestions?: string[];
};
export async function searchLibrary(params: {
  q: string; type: SearchType; subject: string; sort: string; offset: number; limit: number;
}, signal: AbortSignal): Promise<SearchResponse> {
  return (await api.get('/api/search/', { params, signal })).data;
}
export function searchUrl(query: string, type: SearchType = 'all', subject = '', sort = 'relevance') {
  const params = new URLSearchParams({ q: query });
  if (type !== 'all') params.set('type', type);
  if (subject) params.set('subject', subject);
  if (sort !== 'relevance') params.set('sort', sort);
  return `/search?${params}`;
}
