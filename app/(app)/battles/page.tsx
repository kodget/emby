import Link from "next/link";

import { BattlesDashboard } from "@/components/battles/battles-dashboard";
import { JoinBattle } from "@/components/battles/join-battle";
import { Axo } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";

export const metadata = {
  title: "Brain Battles | Emby",
  description: "Compete with your classmates in real-time quiz challenges.",
};

/**
 * Brain Battles.
 *
 * This page used to force its own dark theme (`bg-[#0a0a0a] text-white`), which fought
 * the rest of the app and broke in the viewer's light theme. It now uses the shared
 * design system like every other screen.
 *
 * Joining by code is the primary action, so it leads rather than sitting below the list.
 */
export default function BattlesPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <header className="flex items-start gap-4">
        <Icon3D name="battle" size="lg" />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
            Brain Battles
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Race your classmates through a set of questions. Faster correct answers score
            more.
          </p>
        </div>
        <Axo pose="trophy" size="md" float className="hidden sm:block" />
      </header>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.3fr]">
        <div className="space-y-4">
          <JoinBattle />
          <Link
            href="/battles/create"
            className="press card-3d card-3d-hover flex items-center gap-3 p-4"
          >
            <Icon3D name="brain" size="md" />
            <span className="min-w-0 flex-1">
              <span className="block font-display text-[15px] font-semibold">
                Host a battle
              </span>
              <span className="block text-xs text-muted-foreground">
                Pick a topic and get a code to share
              </span>
            </span>
          </Link>
        </div>

        <BattlesDashboard />
      </div>
    </div>
  );
}
