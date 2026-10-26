import Link from 'next/link';
import { ArrowRight, BookOpen, Check, FileText, Layers, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function LandingHero() {
  return <section className="relative overflow-hidden">
    <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-14 sm:px-6 md:grid-cols-[1.1fr_1fr] md:py-24">
      <div>
        <p className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/5 px-3 py-2 text-xs font-medium text-primary"><BookOpen className="size-4" />Made for medical students</p>
        <h1 className="mt-6 text-4xl font-semibold leading-[1.12] tracking-tight text-balance sm:text-5xl lg:text-6xl">Your next<br />study breakthrough<br /><span className="text-primary">starts here.</span></h1>
        <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">Bring your class slides, revision and practice into one place. Find the concept you need, ask your AI tutor, and turn understanding into progress.</p>
        <div className="mt-8 flex flex-wrap gap-3"><Button asChild size="lg" className="rounded-xl"><Link href="/signup">Start studying free <ArrowRight className="size-4" /></Link></Button><Button asChild size="lg" variant="outline" className="rounded-xl"><Link href="#how-it-works">See how it works</Link></Button></div>
        <p className="mt-4 text-sm text-muted-foreground">Already part of a class? <Link href="/signin" className="font-medium text-primary underline underline-offset-4">Sign in</Link></p>
        <div className="mt-9 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">{['Class-organised materials', 'Study at your pace', 'Start with a free account'].map(text => <span key={text} className="inline-flex items-center gap-1.5"><Check className="size-3.5 text-mastery" />{text}</span>)}</div>
      </div>
      <div className="rounded-3xl border border-primary/15 bg-secondary/60 p-4 sm:p-6" aria-label="Illustrative preview of the Emby study workspace">
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
          <div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Your study space</p><span className="rounded-full bg-muted px-2 py-1 text-[10px] text-muted-foreground">Example</span></div>
          <h2 className="mt-4 text-2xl">A little clearer.<br />A little closer.</h2>
          <div className="mt-5 flex items-center gap-2 rounded-xl border border-input bg-background px-3 py-3 text-sm text-muted-foreground"><Search className="size-4" />Search “brachial plexus”</div>
          <div className="mt-4 rounded-xl border border-border p-4"><div className="flex gap-3"><FileText className="mt-1 size-5 text-primary" /><div><p className="text-xs text-muted-foreground">Anatomy · Upper limb</p><h3 className="mt-1 text-sm font-semibold">Brachial plexus</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">Roots, trunks, divisions, cords and terminal branches.</p></div></div><div className="mt-4 border-t border-border pt-3 text-xs font-medium text-primary">Find it in your class slides <ArrowRight className="ml-1 inline size-3" /></div></div>
          <div className="mt-3 grid grid-cols-2 gap-3"><div className="rounded-xl bg-primary/5 p-4"><Sparkles className="mb-2 size-5 text-primary" /><p className="text-sm font-semibold">Understand it</p><p className="mt-1 text-xs text-muted-foreground">Ask your AI tutor</p></div><div className="rounded-xl bg-mastery/5 p-4"><Layers className="mb-2 size-5 text-mastery" /><p className="text-sm font-semibold">Remember it</p><p className="mt-1 text-xs text-muted-foreground">Review with flashcards</p></div></div>
        </div>
      </div>
    </div>
    <div id="how-it-works" className="border-y border-border bg-card/60"><ol className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:grid-cols-3 sm:px-6">{[
      ['Join your class', 'Use your class code to find the materials your class shares.'],
      ['Find your focus', 'Search a topic or open a slide and ask questions as you read.'],
      ['Make it stick', 'Revise with flashcards, practice questions and a study plan.'],
    ].map(([title, body], index) => <li key={title} className="flex gap-3"><span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/8 text-sm font-semibold text-primary">{index + 1}</span><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p></div></li>)}</ol></div>
  </section>;
}
