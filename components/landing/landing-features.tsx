import { BookOpen, Bot, CalendarDays, Layers, ListChecks, Search } from 'lucide-react';
const features = [
  { icon: Search, title: 'Find the exact concept', body: 'Search document titles and saved slide text alongside your topics, flashcards and class updates.' },
  { icon: BookOpen, title: 'One home for class materials', body: 'Follow your subjects and modules to the slides and resources shared with your class.' },
  { icon: Bot, title: 'Ask as you read', body: 'Discuss uploaded slides with your AI tutor and explore suggested videos and textbooks.' },
  { icon: Layers, title: 'Revise a little, often', body: 'Create flashcards from your study material and revisit cards with spaced repetition.' },
  { icon: ListChecks, title: 'Put understanding to the test', body: 'Practice MCQs and written questions, review your results and prepare for class assessments.' },
  { icon: CalendarDays, title: 'Know what comes next', body: 'Keep your study plan, class announcements and exam countdowns close at hand.' },
];
export function LandingFeatures() {
  return <section id="features" className="bg-background"><div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-20">
    <p className="text-xs font-semibold uppercase tracking-widest text-primary">A place for every part of studying</p>
    <h2 className="mt-3 max-w-2xl text-3xl font-semibold leading-tight text-balance sm:text-4xl">From “where is that slide?”<br />to “I understand this.”</h2>
    <p className="mt-4 max-w-xl text-muted-foreground">Keep the material, the explanation and the practice together. Spend your energy on learning.</p>
    <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{features.map(({ icon: Icon, title, body }) => <li key={title} className="rounded-2xl border border-border bg-card p-6"><span className="flex size-11 items-center justify-center rounded-xl bg-primary/7 text-primary"><Icon className="size-5" aria-hidden="true" /></span><h3 className="mt-4 text-base font-semibold">{title}</h3><p className="mt-3 text-sm leading-relaxed text-muted-foreground">{body}</p></li>)}</ul>
  </div></section>;
}
