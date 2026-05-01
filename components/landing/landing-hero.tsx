import Link from "next/link"
import { ArrowRight, Flame, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"

export function LandingHero() {
  return (
    <section className="relative overflow-hidden">
      {/* Clinical blue glow + faint grid — focused, not warm */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 45% at 15% 10%, color-mix(in oklab, var(--learning) 22%, transparent), transparent 70%), radial-gradient(45% 40% at 88% 20%, color-mix(in oklab, var(--mastery) 14%, transparent), transparent 70%)",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 grid-surface opacity-40"
      />

      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[1.1fr_0.9fr] md:py-24 lg:py-28">
        <div className="flex flex-col justify-center">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-learning/30 bg-learning/10 px-3 py-1 text-xs text-learning">
            <span className="size-1.5 rounded-full bg-learning" />
            <span>Built for Basic Medical Science students</span>
          </div>

          <h1 className="mt-5 font-serif text-4xl font-semibold leading-[1.05] tracking-tight text-balance sm:text-5xl md:text-[56px]">
            Study medicine
            <br />
            <span className="text-learning">with direction.</span>
          </h1>

          <p className="mt-5 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
            Your slides, textbook, past questions, timed quizzes and steeplechase practice — in one focused dark app.
            Highlight any line and the AI tutor explains it, quizzes you, and shows the dissection video. No tab
            switching. No guessing what to study next.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Button asChild size="lg" className="h-11 rounded-full px-5 text-sm">
              <Link href="/signup">
                Get started free
                <ArrowRight className="ml-1 size-4" aria-hidden="true" />
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="lg"
              className="h-11 rounded-full border-border bg-card/60 px-5 text-sm"
            >
              <Link href="#reader">See the AI reader</Link>
            </Button>
          </div>

          <dl className="mt-10 grid max-w-md grid-cols-3 gap-6 border-t border-border pt-6 text-sm">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Students
              </dt>
              <dd className="mt-1 font-serif text-xl font-semibold">1,200+</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Past questions
              </dt>
              <dd className="mt-1 font-serif text-xl font-semibold">4,800</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Pass boost
              </dt>
              <dd className="mt-1 font-serif text-xl font-semibold text-mastery">+18%</dd>
            </div>
          </dl>
        </div>

        <HeroVisual />
      </div>
    </section>
  )
}

function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-md md:max-w-none">
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-2xl border border-border bg-card shadow-2xl shadow-learning/10 study-glow">
        {/* Mock browser chrome */}
        <div className="flex items-center gap-1.5 border-b border-border bg-background/60 px-4 py-3">
          <span className="size-2.5 rounded-full bg-weakness/70" />
          <span className="size-2.5 rounded-full bg-review/70" />
          <span className="size-2.5 rounded-full bg-mastery/70" />
          <span className="ml-3 truncate rounded-md bg-background/80 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
            studybuddy.app/read/axilla
          </span>
        </div>

        {/* Reader preview */}
        <div className="grid h-full grid-cols-[1fr_200px] gap-0">
          <article className="space-y-3 p-5 text-[13px] leading-relaxed">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-learning">
              ANAT 201 · Module 1
            </p>
            <h3 className="font-serif text-xl font-semibold leading-tight tracking-tight">
              The Axilla — Boundaries and Contents
            </h3>
            <p className="text-muted-foreground">
              The axilla is a pyramidal space between the upper part of the thoracic wall and the arm. It serves as a
              passageway for{" "}
              <mark className="ai-highlight">
                neurovascular structures travelling between the neck and the upper limb
              </mark>
              . Clinically it is examined in breast cancer staging and brachial plexus injury.
            </p>
            <div className="rounded-xl border border-review/30 bg-review/10 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-review">
                High yield
              </p>
              <p className="mt-1 text-[12px] text-foreground">
                Know the apex, base and four walls. The medial wall (serratus anterior + long thoracic nerve) is a
                favourite.
              </p>
            </div>
          </article>

          {/* AI sidebar */}
          <aside className="flex flex-col gap-3 border-l border-border bg-background/60 p-4 text-[12px]">
            <div className="flex items-center gap-2 text-learning">
              <Sparkles className="size-3.5" aria-hidden="true" />
              <span className="text-[11px] font-semibold uppercase tracking-wider">AI tutor</span>
            </div>
            <div className="rounded-lg border border-border bg-card p-3 leading-snug">
              <p className="text-[11px] text-muted-foreground">You highlighted</p>
              <p className="mt-1 text-foreground">
                &ldquo;neurovascular structures travelling between the neck and the upper limb&rdquo;
              </p>
            </div>
            <div className="rounded-lg border border-learning/30 bg-learning/10 p-3 leading-snug text-foreground">
              These are the axillary artery &amp; vein, cords of the brachial plexus, and lymphatics. Want me to quiz
              you on their spatial relationship?
            </div>
            <button className="mt-auto rounded-md bg-primary px-3 py-2 text-[12px] font-medium text-primary-foreground hover:opacity-90">
              Quiz me
            </button>
          </aside>
        </div>
      </div>

      {/* Floating streak card */}
      <div className="absolute -left-4 bottom-10 hidden items-center gap-3 rounded-xl border border-review/30 bg-card px-4 py-3 shadow-xl shadow-review/10 sm:flex">
        <span className="flex size-9 items-center justify-center rounded-full bg-review/15 text-review">
          <Flame className="size-4" aria-hidden="true" />
        </span>
        <div className="leading-tight">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Streak
          </p>
          <p className="font-serif text-base font-semibold">12 days in a row</p>
        </div>
      </div>
    </div>
  )
}
