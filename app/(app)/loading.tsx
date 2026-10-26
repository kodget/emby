export default function Loading() {
  return <div className="mx-auto max-w-6xl space-y-5 px-4 py-8 sm:px-8" role="status" aria-label="Loading page">
    <div className="h-8 w-48 animate-pulse rounded-lg bg-muted" />
    <div className="h-4 w-64 max-w-full animate-pulse rounded bg-muted" />
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map(i => <div key={i} className="h-44 animate-pulse rounded-2xl border border-border bg-card" />)}</div>
    <span className="sr-only">Loading your workspace…</span>
  </div>;
}
