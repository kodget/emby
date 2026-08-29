"use client";

/**
 * The list of battles you can see: ones you host, ones you have joined, and ones in your
 * class.
 *
 * Two things were wrong before: it fetched `/api/brain-battles/`, which is not a route
 * (the viewset is registered at `/api/battles/`), so the list silently 404'd and always
 * rendered empty; and it was styled for a dark page that no longer exists, so every
 * label was white-on-white.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Clock, Users } from "lucide-react";

import { AxoEmpty } from "@/components/brand/axo";
import { SurfaceSkeleton } from "@/components/ui/surface";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

type Battle = {
  id: number;
  title: string;
  code: string;
  topic: string;
  difficulty: string;
  status: "scheduled" | "active" | "completed";
  participants_count: number;
  time_per_question: number;
  created_at: string;
  host_name: string;
  host: number;
};

const STATUS: Record<Battle["status"], { label: string; className: string }> = {
  active: { label: "Live now", className: "bg-weakness/15 text-weakness" },
  scheduled: { label: "Waiting", className: "bg-review/15 text-review" },
  completed: { label: "Finished", className: "bg-secondary text-muted-foreground" },
};

export function BattlesDashboard() {
  const [battles, setBattles] = useState<Battle[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/api/battles/");
        if (!cancelled) setBattles(res.data.results ?? res.data ?? []);
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="space-y-3">
        <SurfaceSkeleton lines={2} />
        <SurfaceSkeleton lines={2} />
      </div>
    );
  }

  if (failed) {
    return (
      <AxoEmpty
        title="Couldn't load your battles"
        description="Check your connection and refresh."
        pose="oops"
      />
    );
  }

  if (battles.length === 0) {
    return (
      <AxoEmpty
        title="No battles yet"
        description="Host one and share the code, or enter a code a classmate sent you."
        pose="empty"
      />
    );
  }

  return (
    <section aria-labelledby="battles-heading" className="space-y-3">
      <h2
        id="battles-heading"
        className="px-1 text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
      >
        Your battles
      </h2>

      <ul className="space-y-2.5">
        {battles.map((battle) => {
          const status = STATUS[battle.status] ?? STATUS.scheduled;
          return (
            <li key={battle.id}>
              <Link
                href={`/battles/${battle.id}`}
                className="press card-3d card-3d-hover block p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="min-w-0 flex-1 truncate font-display text-[15px] font-semibold">
                    {battle.title}
                  </h3>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      status.className,
                    )}
                  >
                    {status.label}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {battle.code && (
                    <span className="font-mono font-semibold tracking-widest text-primary">
                      {battle.code}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 tabular">
                    <Users className="size-3" />
                    {battle.participants_count}
                  </span>
                  <span className="inline-flex items-center gap-1 tabular">
                    <Clock className="size-3" />
                    {battle.time_per_question}s
                  </span>
                  {battle.difficulty && (
                    <span className="capitalize">{battle.difficulty}</span>
                  )}
                  {battle.created_at && (
                    <span>
                      {formatDistanceToNow(new Date(battle.created_at), { addSuffix: true })}
                    </span>
                  )}
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
