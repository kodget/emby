import Link from "next/link";
import {
  ArrowUpRight,
  BookOpenText,
  Highlighter,
  Play,
  Sparkles,
} from "lucide-react";

export function LandingReaderDemo() {
  return (
    <section id="reader" className="border-t border-border">
      <div className="mx-auto grid w-full max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="flex flex-col justify-center gap-5">
          <p className="text-[11px] font-medium uppercase tracking-widest text-accent">
            The hero feature
          </p>
          <h2 className="font-serif text-4xl leading-tight tracking-tight text-balance md:text-5xl">
            Highlight anything.
            <br />
            <span className="italic">Understand it in seconds.</span>
          </h2>
          <p className="text-pretty text-muted-foreground">
            Open a slide. Highlight the sentence you don&apos;t understand. The
            AI tutor explains it using your recommended textbook and suggests a
            real dissection video — without you leaving the page.
          </p>

          <ul className="mt-2 space-y-4 text-sm">
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Highlighter className="size-3.5" aria-hidden="true" />
              </span>
              <span>
                <strong className="font-medium">Select to explain.</strong>{" "}
                <span className="text-muted-foreground">
                  Works on any paragraph, figure caption, or past question.
                </span>
              </span>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <BookOpenText className="size-3.5" aria-hidden="true" />
              </span>
              <span>
                <strong className="font-medium">Textbook, attached.</strong>{" "}
                <span className="text-muted-foreground">
                  Every class ships with its recommended textbook side-by-side.
                </span>
              </span>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Play className="size-3.5" aria-hidden="true" />
              </span>
              <span>
                <strong className="font-medium">Real dissection videos.</strong>{" "}
                <span className="text-muted-foreground">
                  We find the actual human-cadaver video, not a 3D animation.
                </span>
              </span>
            </li>
          </ul>

          <Link
            href="/read"
            className="group mt-2 inline-flex w-fit items-center gap-2 text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Try the reader with real content
            <ArrowUpRight
              className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        </div>

        {/* Larger reader mock */}
        <div className="relative overflow-hidden rounded-3xl border border-border bg-card shadow-2xl shadow-foreground/10">
          <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2.5">
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <BookOpenText className="size-3.5" aria-hidden="true" />
              <span>
                ANAT 201 · Axilla — Boundaries and Contents · page 4 / 34
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-primary">
              <Sparkles className="size-3.5" aria-hidden="true" />
              <span className="text-[11px]">AI tutor online</span>
            </div>
          </div>

          <div className="grid grid-cols-[1fr_260px]">
            <article className="space-y-4 p-6 text-[13.5px] leading-relaxed">
              <h3 className="font-serif text-2xl leading-tight">
                Contents of the Axilla
              </h3>
              <p className="text-muted-foreground">
                The axilla contains the axillary artery and its branches, the
                axillary vein and its tributaries, cords and branches of the
                brachial plexus, axillary lymph nodes, and fat.
              </p>
              <p className="text-muted-foreground">
                The{" "}
                <mark className="ai-highlight text-foreground">
                  long thoracic nerve runs on the surface of serratus anterior
                </mark>{" "}
                and is vulnerable during mastectomy — injury causes winging of
                the scapula.
              </p>
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <p className="text-[11px] font-medium uppercase tracking-wider text-destructive">
                  Clinical
                </p>
                <p className="mt-1 text-[12px]">
                  A patient with winged scapula post-mastectomy has damaged the
                  long thoracic nerve (C5–C7).
                </p>
              </div>
            </article>

            <aside className="flex flex-col gap-3 border-l border-border bg-muted/30 p-4">
              <div className="flex items-center gap-2 text-primary">
                <Sparkles className="size-3.5" aria-hidden="true" />
                <span className="text-[11px] font-medium uppercase tracking-wider">
                  Explain selection
                </span>
              </div>
              <div className="rounded-lg border border-border bg-card p-3 text-[12px] leading-snug">
                <p className="text-[11px] text-muted-foreground">Selected</p>
                <p className="mt-1">
                  “long thoracic nerve runs on the surface of serratus anterior”
                </p>
              </div>
              <div className="rounded-lg bg-primary/10 p-3 text-[12.5px] leading-snug">
                It emerges from the roots of C5, C6, and C7, descends on the
                medial wall of the axilla, and innervates serratus anterior.
                Because it lies superficially on the muscle, it&apos;s at risk
                in axillary surgery.
              </div>
              <div className="rounded-lg border border-border bg-card p-3 text-[12px]">
                <p className="flex items-center gap-1.5 text-[11px] font-medium text-foreground">
                  <Play className="size-3" aria-hidden="true" />
                  Suggested video
                </p>
                <p className="mt-1 text-muted-foreground">
                  “Long thoracic nerve — cadaver dissection” · Acland&apos;s,
                  4:12
                </p>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </section>
  );
}
