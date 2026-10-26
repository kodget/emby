import Image from "next/image";
import { LOGO_MARK } from "@/lib/brand";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function LandingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/70 bg-background/80 backdrop-blur-md">
      <nav aria-label="Main navigation" className="mx-auto flex h-18 w-full max-w-6xl items-center justify-between gap-2 px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2"
          aria-label="Emby home"
        >
          <Image
            src={LOGO_MARK}
            alt=""
            width={32}
            height={32}
            priority
            className="size-8 select-none"
            draggable={false}
          />
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
            className="inline-flex"
          >
            <Link href="/signin">Sign in</Link>
          </Button>
          <Button size="sm" asChild className="rounded-full">
            <Link href="/signup">Get started</Link>
          </Button>
        </div>
      </nav>
      <nav aria-label="Explore Emby" className="flex gap-5 overflow-x-auto border-t border-border px-4 text-xs text-muted-foreground md:hidden">
        <a href="#how-it-works" className="flex min-h-11 shrink-0 items-center">How it works</a>
        <a href="#features" className="flex min-h-11 shrink-0 items-center">Features</a>
        <a href="#reader" className="flex min-h-11 shrink-0 items-center">AI reader</a>
        <a href="#pricing" className="flex min-h-11 shrink-0 items-center">Pricing</a>
      </nav>
    </header>
  );
}
