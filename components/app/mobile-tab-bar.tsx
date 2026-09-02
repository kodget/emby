"use client";

/**
 * The mobile bottom tab bar.
 *
 * Emby is a web app that people use like a phone app, and nothing signals "app" more
 * than thumb-reachable primary navigation. This replaces the hamburger-only mobile nav:
 * the five things students do most are always one tap away, the active tab is marked
 * with a shared-layout pill that springs between tabs, and everything else moves behind
 * a "More" sheet.
 *
 * Rendered only below `md`; desktop keeps the collapsible sidebar.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  BarChart3,
  CalendarDays,
  Crown,
  GraduationCap,
  Microscope,
  Settings,
  Sparkles,
  Trophy,
  Users,
  X,
} from "lucide-react";

import { Icon3D } from "@/components/brand/icon-3d";
import type { IconName } from "@/lib/brand";
import { cn } from "@/lib/utils";
import { useAppSelector } from "@/store/hooks";

type Tab = {
  label: string;
  href: string;
  icon: IconName;
  match: RegExp;
};

const TABS: Tab[] = [
  { label: "Home", href: "/dashboard", icon: "dashboard", match: /^\/dashboard/ },
  { label: "Learn", href: "/courses", icon: "read", match: /^\/(courses|read)/ },
  { label: "Practice", href: "/quiz", icon: "quiz", match: /^\/(quiz|steeplechase|histology)/ },
  { label: "Review", href: "/flashcards", icon: "flashcards", match: /^\/(flashcards|decks)/ },
];

const MORE_LINKS = [
  { label: "Analytics", href: "/analytics", Icon: BarChart3 },
  { label: "Study plan", href: "/study-plan", Icon: CalendarDays },
  { label: "Achievements", href: "/achievements", Icon: Trophy },
  { label: "Brain Battle", href: "/battles", Icon: Sparkles },
  { label: "Histology", href: "/histology", Icon: Microscope },
  { label: "Community", href: "/community", Icon: Users },
  { label: "Profile", href: "/profile", Icon: GraduationCap },
  { label: "Premium", href: "/premium", Icon: Crown },
  { label: "Settings", href: "/settings", Icon: Settings },
];

export function MobileTabBar() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  // A route change should always dismiss the sheet, including back/forward.
  useEffect(() => {
    setMoreOpen(false);
  }, [pathname]);

  const moreActive = MORE_LINKS.some((l) => pathname.startsWith(l.href));

  return (
    <>
      <nav
        // Nearly opaque on purpose: at lower alpha, page content scrolling underneath
        // stayed legible through the blur and collided with the tab labels.
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/97 backdrop-blur-xl supports-[backdrop-filter]:bg-card/95 md:hidden pb-safe"
        aria-label="Primary"
      >
        <ul className="flex items-stretch">
          {TABS.map((tab) => {
            const active = tab.match.test(pathname);
            return (
              <li key={tab.href} className="flex-1">
                <Link
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className="press relative flex h-16 flex-col items-center justify-center gap-1"
                >
                  {active && (
                    <motion.span
                      layoutId="tab-pill"
                      className="absolute inset-x-3 inset-y-1.5 -z-10 rounded-2xl bg-primary/10"
                      transition={{ type: "spring", stiffness: 420, damping: 32 }}
                    />
                  )}
                  <motion.span
                    animate={{ scale: active ? 1.08 : 1, y: active ? -1 : 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 24 }}
                    className={cn(!active && "opacity-55 saturate-50")}
                  >
                    <Icon3D name={tab.icon} size="sm" />
                  </motion.span>
                  <span
                    className={cn(
                      "text-[10px] font-medium leading-none tracking-tight",
                      active ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    {tab.label}
                  </span>
                </Link>
              </li>
            );
          })}

          <li className="flex-1">
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-expanded={moreOpen}
              aria-haspopup="dialog"
              className="press relative flex h-16 w-full flex-col items-center justify-center gap-1"
            >
              <span
                className={cn(
                  "flex flex-col gap-[3px]",
                  moreActive ? "opacity-100" : "opacity-55",
                )}
                aria-hidden="true"
              >
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className={cn(
                      "block h-[3px] w-[18px] rounded-full",
                      moreActive ? "bg-primary" : "bg-foreground/60",
                    )}
                  />
                ))}
              </span>
              <span
                className={cn(
                  "text-[10px] font-medium leading-none tracking-tight",
                  moreActive ? "text-primary" : "text-muted-foreground",
                )}
              >
                More
              </span>
            </button>
          </li>
        </ul>
      </nav>

      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
    </>
  );
}

function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const isClassHead = useAppSelector((s) => s.user.isVerifiedClassHead);

  // Lock the page behind the sheet so only the sheet scrolls.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const links = isClassHead
    ? [...MORE_LINKS, { label: "Class management", href: "/class/curriculum", Icon: GraduationCap }]
    : MORE_LINKS;

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="More">
          <motion.button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-foreground/35 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.div
            className="absolute inset-x-0 bottom-0 rounded-t-3xl border-t border-border bg-card pb-safe depth-4"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.5 }}
            onDragEnd={(_, info) => {
              // A deliberate downward flick dismisses, matching native sheets.
              if (info.offset.y > 90 || info.velocity.y > 550) onClose();
            }}
          >
            <div className="flex justify-center pt-3 pb-1">
              <span className="sheet-grabber" aria-hidden="true" />
            </div>

            <div className="flex items-center justify-between px-5 pb-2">
              <h2 className="font-display text-lg font-semibold tracking-tight">More</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="press flex size-8 items-center justify-center rounded-full bg-secondary text-muted-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2 px-4 pb-6 pt-2">
              {links.map(({ label, href, Icon }) => {
                const active = pathname.startsWith(href);
                return (
                  <button
                    key={href}
                    type="button"
                    onClick={() => {
                      onClose();
                      router.push(href);
                    }}
                    className={cn(
                      "press flex flex-col items-center gap-2 rounded-2xl border px-2 py-4 text-center",
                      active
                        ? "border-primary/30 bg-primary/10"
                        : "border-border/70 bg-secondary/40",
                    )}
                  >
                    <Icon
                      className={cn(
                        "size-5",
                        active ? "text-primary" : "text-muted-foreground",
                      )}
                    />
                    <span className="text-[11px] font-medium leading-tight">{label}</span>
                  </button>
                );
              })}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
