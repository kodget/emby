import { BattleArena } from "@/components/battles/battle-arena";

export const metadata = {
  title: "Battle Arena | Emby",
  description: "Live Brain Battle Arena",
};

export default function BattleArenaPage({ params }: { params: { id: string } }) {
  return (
    <div className="min-h-screen bg-[#0a0a0a] bg-[url('/grid.svg')] text-white p-6 md:p-12">
      <BattleArena battleId={params.id} />
    </div>
  );
}
