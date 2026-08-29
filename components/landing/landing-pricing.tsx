import { MONTHLY_PRICE_LABEL, YEARLY_PRICE_LABEL, formatNaira, yearlySavings } from "@/lib/pricing";
import Link from "next/link";
import { Check } from "lucide-react";

// Every line below maps to behaviour that is actually implemented and enforced
// server-side. Claims for features Emby does not have (an offline PDF reader, a free
// trial) were removed rather than left as aspirations.
const freePerks = [
  "Your class slides and materials",
  "Spaced-repetition flashcards",
  "10 MCQs per quiz",
  "5 Steeplechase and 5 Histology rounds a month",
  "A monthly allowance of AI credits",
  "Community Q&A (read-only)",
];

const proPerks = [
  "Everything in Free",
  "Unlimited Steeplechase and Histology rounds",
  "The full question bank, up to 100 per quiz",
  "Theory questions marked by AI, with feedback",
  "A far larger AI credit allowance",
  "Weak-area analysis and revision suggestions",
  "Post, like and comment in the community",
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
                {MONTHLY_PRICE_LABEL}{" "}
                <span className="text-base text-primary-foreground/80">
                  / month
                </span>
              </p>
              <p className="mt-2 text-sm text-primary-foreground/80">
                {`or ${YEARLY_PRICE_LABEL} / year · save ${formatNaira(yearlySavings())}`}
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
              Go Pro
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}
