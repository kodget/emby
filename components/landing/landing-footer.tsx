import { Stethoscope } from "lucide-react"

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-card/40">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope className="size-4" aria-hidden="true" />
          </span>
          <div className="leading-tight">
            <p className="font-serif">Emby</p>
            <p className="text-[11px] uppercase tracking-widest text-muted-foreground">BMS Edition · Made in Lagos</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} Emby. Built by medical students, for medical students.
        </p>
      </div>
    </footer>
  )
}
