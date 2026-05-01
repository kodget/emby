import Link from "next/link";
import { Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LandingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/70 bg-background/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2"
          aria-label="Emby home"
        >
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope className="size-4" aria-hidden="true" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-serif text-lg">Emby</span>
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
              BMS Edition
            </span>
          </span>
        </Link>

        <ul className="hidden items-center gap-8 text-sm text-muted-foreground md:flex">
          <li>
            <a
              href="#features"
              className="transition-colors hover:text-foreground"
            >
              Features
            </a>
          </li>
          <li>
            <a
              href="#reader"
              className="transition-colors hover:text-foreground"
            >
              AI reader
            </a>
          </li>
          <li>
            <a
              href="#steeplechase"
              className="transition-colors hover:text-foreground"
            >
              Steeplechase
            </a>
          </li>
          <li>
            <a
              href="#pricing"
              className="transition-colors hover:text-foreground"
            >
              Pricing
            </a>
          </li>
        </ul>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="hidden sm:inline-flex"
          >
            <Link href="/signin">Sign in</Link>
          </Button>
          <Button size="sm" asChild className="rounded-full">
            <Link href="/signup">Get started</Link>
          </Button>
        </div>
      </nav>
    </header>
  );
}
