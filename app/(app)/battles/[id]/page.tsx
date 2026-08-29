import { BattleArena } from "@/components/battles/battle-arena";

export const metadata = {
  title: "Battle Arena | Emby",
  description: "Live Brain Battle Arena",
};

export default function BattleArenaPage({ params }: { params: { id: string } }) {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <BattleArena battleId={params.id} />
    </div>
  );
}
