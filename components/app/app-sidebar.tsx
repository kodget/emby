"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faGaugeHigh,
  faBookOpen,
  faBookOpenReader,
  faListCheck,
  faTrophy,
  faLayerGroup,
  faComments,
  faFire,
  faStethoscope,
  faUser,
  faLightbulb,
  faBars,
  faXmark,
  faChartLine,
} from "@fortawesome/free-solid-svg-icons";
import { cn } from "@/lib/utils";
import { UploadProgressStrip } from "./upload-progress-strip";
import { useAppSelector } from "@/store/hooks";
import { useEffect, useState } from "react";

type NavItem = {
  label: string;
  href: string;
  icon: typeof faGaugeHigh;
  match?: RegExp;
};

const primary: NavItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: faGaugeHigh,
    match: /^\/dashboard$/,
  },
  {
    label: "Analytics",
    href: "/analytics",
    icon: faChartLine,
    match: /^\/analytics/,
  },
  {
    label: "Premium",
    href: "/premium",
    icon: faFire,
    match: /^\/premium$/,
  },
  {
    label: "Study Plan",
    href: "/study-plan",
    icon: faBookOpen,
    match: /^\/study-plan/,
  },
  {
    label: "My Courses",
    href: "/courses",
    icon: faBookOpenReader,
    match: /^\/courses/,
  },
  {
    label: "Materials",
    href: "/materials",
    icon: faLayerGroup,
    match: /^\/materials/,
  },
  {
    label: "Quizzes",
    href: "/quiz",
    icon: faListCheck,
    match: /^\/quiz/,
  },
  {
    label: "Flashcards",
    href: "/flashcards",
    icon: faLayerGroup,
    match: /^\/flashcards/,
  },
  {
    label: "Community",
    href: "/community",
    icon: faComments,
    match: /^\/community/,
  },
  {
    label: "My Class",
    href: "/class",
    icon: faUser,
    match: /^\/class/,
  },
  {
    label: "Profile",
    href: "/profile",
    icon: faUser,
    match: /^\/profile$/,
  },
];

function SidebarContent({ onNav }: { onNav?: () => void }) {
  const pathname = usePathname();
  const isClassRep = useAppSelector((s) => s.user.isClassRep);
  const isUploader = useAppSelector((s) => s.user.role === "uploader");
  const canBrainstorm = useAppSelector(
    (s) => s.user.role === "class-rep" || s.user.role === "brainstormer",
  );
  const userProfile = useAppSelector((s) => s.user.profile);
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  const visibleNavItems = hasHydrated
    ? primary.filter((item) => item.href !== "/brainstorming" || canBrainstorm)
    : primary.filter((item) => item.href !== "/brainstorming");
  const badge =
    hasHydrated && (isClassRep ? "Class Rep" : isUploader ? "Uploader" : null);
  
  const streak = userProfile?.streak || 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-5">
        <Link
          href="/"
          className="group flex items-center gap-2.5"
          aria-label="Emby home"
          onClick={onNav}
        >
          <span
            className="relative flex size-9 items-center justify-center rounded-xl text-primary-foreground transition-transform duration-200 group-hover:scale-105"
            style={{
              background:
                "linear-gradient(140deg, color-mix(in oklab, var(--primary) 100%, white 12%), color-mix(in oklab, var(--primary) 78%, black 8%))",
              boxShadow:
                "inset 0 1px 0 0 color-mix(in oklab, white 30%, transparent), 0 6px 18px -6px color-mix(in oklab, var(--primary) 70%, transparent)",
            }}
          >
            <FontAwesomeIcon icon={faStethoscope} className="size-4" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-serif text-lg font-semibold tracking-tight">Emby</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              BMS Edition
            </span>
          </span>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 pb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          Study
        </p>
        <ul className="space-y-0.5">
          {visibleNavItems.map((item) => {
            const active = item.match
              ? item.match.test(pathname)
              : pathname === item.href;
            return (
              <li key={item.label}>
                <Link
                  href={item.href}
                  onClick={onNav}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                    active
                      ? "nav-active-bar bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground hover:translate-x-0.5",
                  )}
                >
                  <FontAwesomeIcon
                    icon={item.icon}
                    className={cn(
                      "size-4 transition-colors",
                      active ? "text-primary" : "group-hover:text-foreground",
                    )}
                    aria-hidden="true"
                  />
                  <span>{item.label}</span>
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="ml-auto h-1.5 w-1.5 rounded-full bg-primary"
                      style={{
                        boxShadow:
                          "0 0 6px 2px color-mix(in oklab, var(--primary) 70%, transparent)",
                      }}
                      transition={{
                        type: "spring",
                        stiffness: 400,
                        damping: 30,
                      }}
                    />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Upload progress */}
      <UploadProgressStrip />

      {/* Streak + role */}
      <div className="glass m-3 rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-review/15 text-review">
              <FontAwesomeIcon
                icon={faFire}
                className="size-4"
                aria-hidden="true"
              />
            </span>
            <div className="leading-tight">
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                Streak
              </p>
              <p className="font-serif text-lg leading-none">{streak} {streak === 1 ? 'day' : 'days'}</p>
            </div>
          </div>
          {badge && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-3 text-[12px] text-muted-foreground">
          {streak === 0 
            ? "Start studying today to begin your streak!"
            : "Keep studying daily to maintain your streak!"}
        </p>
      </div>
    </div>
  );
}

export function AppSidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile hamburger */}
      <button
        type="button"
        className="fixed top-4 left-4 z-40 flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-sm md:hidden"
        aria-label="Open menu"
        onClick={() => setMobileOpen(true)}
      >
        <FontAwesomeIcon icon={faBars} className="size-4" />
      </button>

      {/* Mobile sheet */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <motion.div
            className="absolute inset-0 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onClick={() => setMobileOpen(false)}
          />
          <motion.div
            className="absolute left-0 top-0 h-full w-full max-w-[85vw] border-r border-sidebar-border bg-sidebar text-sidebar-foreground sm:max-w-xs"
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
          >
            <button
              type="button"
              className="absolute top-4 right-4 flex size-8 items-center justify-center rounded-full border border-border text-muted-foreground"
              aria-label="Close menu"
              onClick={() => setMobileOpen(false)}
            >
              <FontAwesomeIcon icon={faXmark} className="size-4" />
            </button>
            <SidebarContent onNav={() => setMobileOpen(false)} />
          </motion.div>
        </div>
      )}
    </>
  );
}
