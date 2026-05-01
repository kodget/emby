import Link from "next/link";
import { Check } from "lucide-react";

const freePerks = [
  "Your class materials",
  "Daily study plan (30 min)",
  "1 quiz + 1 flashcard deck / day",
  "Community Q&A (read-only)",
];

const proPerks = [
  "Everything in Free",
  "Unlimited AI tutor explanations",
  "All past questions + steeplechase",
  "Spaced-repetition flashcards",
  "Post & answer in community",
  "Weekly analytics report",
  "Offline PDF reader",
];

export function LandingPricing() {
  return (
    <section id="pricing" className="border-t border-border">
      <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
            Pricing
          </p>
          <h2 className="mt-3 font-serif text-4xl leading-tight tracking-tight text-balance md:text-5xl">
            Cheaper than <span className="italic">your data subscription.</span>
          </h2>
          <p className="mt-4 text-pretty text-muted-foreground">
            We priced Emby for Nigerian medical students, not for Silicon
            Valley. Pay monthly, or save with yearly.
          </p>
        </div>

        <div className="mx-auto mt-12 grid max-w-4xl gap-6 md:grid-cols-2">
          <article className="flex flex-col rounded-3xl border border-border bg-card p-6">
            <header>
              <p className="text-sm font-medium text-muted-foreground">
                Free · Starter
              </p>
              <p className="mt-2 font-serif text-4xl">
                ₦0{" "}
                <span className="text-base text-muted-foreground">/ month</span>
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Enough to decide you can&apos;t live without Pro.
              </p>
            </header>
            <ul className="mt-6 space-y-2.5 text-sm">
              {freePerks.map((p) => (
                <li key={p} className="flex items-start gap-2">
                  <Check
                    className="mt-0.5 size-4 text-primary"
                    aria-hidden="true"
                  />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/signup"
              className="mt-auto inline-flex h-11 items-center justify-center rounded-full border border-border bg-background px-5 text-sm font-medium hover:bg-muted/60"
            >
              Start free
            </Link>
          </article>

          <article className="relative flex flex-col rounded-3xl border-2 border-primary bg-primary text-primary-foreground p-6">
            <span className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground shadow">
              Most BMS students
            </span>
            <header>
              <p className="text-sm font-medium text-primary-foreground/80">
                Pro · Exam Ready
              </p>
              <p className="mt-2 font-serif text-4xl">
                ₦1,499{" "}
                <span className="text-base text-primary-foreground/80">
                  / month
                </span>
              </p>
              <p className="mt-2 text-sm text-primary-foreground/80">
                or ₦15,000 / year · save 17%
              </p>
            </header>
            <ul className="mt-6 space-y-2.5 text-sm">
              {proPerks.map((p) => (
                <li key={p} className="flex items-start gap-2">
                  <Check
                    className="mt-0.5 size-4 text-accent"
                    aria-hidden="true"
                  />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/signup"
              className="mt-auto inline-flex h-11 items-center justify-center rounded-full bg-background text-foreground px-5 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
            >
              Go Pro · 7-day free trial
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}
