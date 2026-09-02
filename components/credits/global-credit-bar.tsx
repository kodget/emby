"use client";

import { useCredits } from "@/hooks/use-credits";
import Link from "next/link";
import { Coins, Loader2 } from "lucide-react";

export function GlobalCreditBar() {
  const { balance, isLoading } = useCredits();

  return (
    <Link
      href="/credits"
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:border-primary/50 transition-colors"
      title="AI Credits"
    >
      <Coins className="size-3.5 text-amber-500" />
      {isLoading ? (
        <Loader2 className="size-3 animate-spin text-muted-foreground" />
      ) : (
        <span className="font-semibold">{balance.toLocaleString()}</span>
      )}
    </Link>
  );
}
