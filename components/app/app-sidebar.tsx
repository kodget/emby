"use client";

/**
 * Desktop sidebar.
 *
 * Two things changed here beyond the visual pass:
 *
 *  1. It collapses to an icon rail and the choice persists across navigation and
 *     refreshes, read synchronously on first paint so the rail never flashes wide.
 *  2. Mobile no longer uses this at all — the bottom tab bar owns small screens — so the
 *     old hamburger and slide-over sheet are gone and the two behaviours no longer fight.
 */

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Icon3D } from "@/components/brand/icon-3d";
import { LOGO_MARK, type IconName } from "@/lib/brand";
import { cn } from "@/lib/utils";
import { useAppSelector } from "@/store/hooks";
import { UploadProgressStrip } from "./upload-progress-strip";

const STORAGE_KEY = "emby.sidebar.collapsed";

type NavItem = {
  label: string;
  href: string;
  icon: IconName;
  match?: RegExp;
};

const STUDY: NavItem[] = [
  { label: "Home", href: "/dashboard", icon: "dashboard", match: /^\/dashboard$/ },
  { label: "Learn", href: "/courses", icon: "read", match: /^\/(courses|read)/ },
  { label: "Practice", href: "/quiz", icon: "quiz", match: /^\/quiz/ },
  { label: "Steeplechase", href: "/steeplechase", icon: "steeplechase", match: /^\/steeplechase/ },
  { label: "Histology", href: "/histology", icon: "histology", match: /^\/histology/ },
  { label: "Review", href: "/flashcards", icon: "flashcards", match: /^\/(flashcards|decks)/ },
  { label: "Brain Battle", href: "/battles", icon: "battle", match: /^\/(battles|brainstorming)/ },
];

const TOOLS: NavItem[] = [
  { label: "Analytics", href: "/analytics", icon: "analytics", match: /^\/analytics/ },
  { label: "Study Plan", href: "/study-plan", icon: "planner", match: /^\/study-plan/ },
  { label: "Community", href: "/community", icon: "community", match: /^\/community/ },
  { label: "Profile", href: "/profile", icon: "profile", match: /^\/profile$/ },
  { label: "Premium", href: "/premium", icon: "premium", match: /^\/premium$/ },
];

const CLASS_ITEM: NavItem = {
  label: "Class Management",
  href: "/class/curriculum",
  icon: "community",
  match: /^\/class\//,
};

/** Read the stored preference before first paint to avoid a width flash. */
function readCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const isClassHead = useAppSelector((s) => s.user.isVerifiedClassHead);
  const streak = useAppSelector((s) => s.user.streak) || 0;
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => setHydrated(true), []);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* private mode — the preference simply won't persist */
      }
      return next;
    });
  }, []);

  const items = hydrated && isClassHead ? [...TOOLS, CLASS_ITEM] : TOOLS;

  return (
    <aside
      suppressHydrationWarning
      data-collapsed={collapsed}
      className={cn(
        "group sticky top-0 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex",
        "transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
        collapsed ? "w-[74px]" : "w-64",
      )}
    >
      {/* Brand + collapse control */}
      <div className="flex h-16 items-center gap-2.5 border-b border-sidebar-border px-4">
        <Link
          href="/dashboard"
          className="press flex min-w-0 items-center gap-2.5"
          aria-label="Emby home"
        >
          <Image
            src={LOGO_MARK}
            alt=""
            width={36}
            height={36}
            priority
            className="size-9 shrink-0 select-none"
            draggable={false}
          />
          <span className="flex min-w-0 flex-col leading-none group-data-[collapsed=true]:hidden">
            <span className="font-display text-lg font-semibold tracking-tight">Emby</span>
            <span className="truncate text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              BMS Edition
            </span>
          </span>
        </Link>

        <button
          type="button"
          onClick={toggle}
          aria-label="Collapse sidebar"
          className="press ml-auto flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-sidebar-accent hover:text-foreground group-data-[collapsed=true]:hidden"
        >
          <PanelLeftClose className="size-4" />
        </button>
      </div>

      <button
        type="button"
        onClick={toggle}
        aria-label="Expand sidebar"
        className="press mx-auto mt-3 flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-sidebar-accent hover:text-foreground group-data-[collapsed=false]:hidden"
      >
        <PanelLeftOpen className="size-4" />
      </button>

      <nav className="scroll-pane flex-1 overflow-y-auto px-3 py-4">
        <NavGroup title="Study" items={STUDY} pathname={pathname} collapsed={collapsed} />
        <div className="mx-2 my-3 border-t border-sidebar-border" />
        <NavGroup title="Tools" items={items} pathname={pathname} collapsed={collapsed} />
      </nav>

      <UploadProgressStrip />

      {/* Streak — a compact badge when collapsed, a card when open */}
      <div className="flex flex-col items-center gap-1 pb-4 group-data-[collapsed=false]:hidden" title={`${streak}-day streak`}>
        <Icon3D name="streak" size="sm" />
        <span className="tabular text-xs font-semibold">{streak}</span>
      </div>

      <div className="card-3d m-3 rounded-2xl p-3.5 group-data-[collapsed=true]:hidden">
        <div className="flex items-center gap-2.5">
          <Icon3D name="streak" size="md" />
          <div className="leading-tight">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Streak
            </p>
            <p className="font-display text-xl leading-none tabular">
              {streak} <span className="text-sm font-normal">{streak === 1 ? "day" : "days"}</span>
            </p>
          </div>
        </div>
        <p className="mt-2.5 text-[12px] leading-snug text-muted-foreground">
          {streak === 0
            ? "Study today to start your streak."
            : "Keep it going — study something today."}
        </p>
      </div>
    </aside>
  );
}

function NavGroup({
  title,
  items,
  pathname,
  collapsed,
}: {
  title: string;
  items: NavItem[];
  pathname: string;
  collapsed: boolean;
}) {
  return (
    <>
      <p className="px-3 pb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground group-data-[collapsed=true]:hidden">
        {title}
      </p>
      <ul className="space-y-0.5">
        {items.map((item) => {
          const active = item.match ? item.match.test(pathname) : pathname === item.href;
          return (
            <li key={item.href}>
              <NavLink item={item} active={active} collapsed={collapsed} />
            </li>
          );
        })}
      </ul>
    </>
  );
}

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <Link
      suppressHydrationWarning
      href={item.href}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "press relative flex items-center rounded-xl text-sm transition-colors",
        collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2",
        active
          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
      )}
    >
      {active && (
        <motion.span
          layoutId="sidebar-active"
          className="absolute inset-0 -z-10 rounded-xl bg-primary/10 ring-1 ring-inset ring-primary/15"
          transition={{ type: "spring", stiffness: 400, damping: 32 }}
        />
      )}
      <span className={cn("shrink-0 transition-opacity", !active && "opacity-70 saturate-[0.6] group-hover:opacity-100 group-hover:saturate-100")}>
        <Icon3D name={item.icon} size="sm" />
      </span>
      <span className="truncate group-data-[collapsed=true]:hidden">{item.label}</span>
    </Link>
  );
}
