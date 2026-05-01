import Link from "next/link"
import { Timer, ArrowUpRight } from "lucide-react"

export function LandingSteeplechase() {
  return (
    <section id="steeplechase" className="border-t border-border bg-primary text-primary-foreground">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-accent">
            Steeplechase — our obsession
          </p>
          <h2 className="mt-3 font-serif text-4xl leading-tight tracking-tight text-balance md:text-5xl">
            The exam that breaks medical students,
            <span className="italic"> finally practised properly.</span>
          </h2>
          <p className="mt-5 max-w-xl text-pretty text-primary-foreground/80">
            45 seconds. Move to the next station. Real cadaveric photographs and histology slides curated from your
            own department — not animated 3D models. Untimed for learning, timed for exam simulation.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/steeplechase"
              className="group inline-flex h-11 items-center gap-2 rounded-full bg-background px-5 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              Start a timed round
              <ArrowUpRight className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
            </Link>
            <Link
              href="/steeplechase"
              className="inline-flex h-11 items-center gap-2 rounded-full border border-primary-foreground/25 px-5 text-sm text-primary-foreground/90 hover:border-primary-foreground/50"
            >
              Practice untimed
            </Link>
          </div>

          <dl className="mt-12 grid max-w-md grid-cols-3 gap-6 border-t border-primary-foreground/15 pt-6 text-sm">
            <div>
              <dt className="text-primary-foreground/70">Stations</dt>
              <dd className="mt-1 font-serif text-2xl">320</dd>
            </div>
            <div>
              <dt className="text-primary-foreground/70">Real photos</dt>
              <dd className="mt-1 font-serif text-2xl">100%</dd>
            </div>
            <div>
              <dt className="text-primary-foreground/70">Per station</dt>
              <dd className="mt-1 font-serif text-2xl">45s</dd>
            </div>
          </dl>
        </div>

        {/* Mock station card */}
        <div className="relative">
          <div className="relative overflow-hidden rounded-3xl border border-primary-foreground/20 bg-background text-foreground shadow-2xl shadow-foreground/20">
            <div className="relative">
              <img
                src="/placeholder.svg?height=400&width=640"
                alt="Cadaveric dissection of the axilla with a numbered pin"
                className="h-64 w-full object-cover"
              />
              <div className="absolute right-4 top-4 flex items-center gap-1.5 rounded-full bg-background/90 px-3 py-1.5 text-xs font-medium text-foreground backdrop-blur">
                <Timer className="size-3.5 text-accent" aria-hidden="true" />
                <span>Station 2 / 20 · 00:38</span>
              </div>
              <div className="absolute bottom-4 left-4 rounded-full bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground shadow-md">
                Pin A
              </div>
            </div>
            <div className="p-5">
              <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                Upper limb · brachial plexus
              </p>
              <h3 className="mt-2 font-serif text-2xl">Identify the structure marked with pin A.</h3>
              <div className="mt-4 flex gap-2">
                <input
                  type="text"
                  placeholder="Type your answer…"
                  className="h-11 flex-1 rounded-full border border-border bg-card px-4 text-sm outline-none focus:border-primary"
                  readOnly
                />
                <button className="h-11 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground">
                  Submit
                </button>
              </div>
            </div>
          </div>

          {/* Floating timer progress */}
          <div className="absolute -bottom-5 left-6 right-6 rounded-full bg-background/95 p-1.5 shadow-lg backdrop-blur">
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full w-[22%] rounded-full bg-accent transition-all" aria-hidden="true" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
