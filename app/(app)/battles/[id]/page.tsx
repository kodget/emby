import { BattleArena } from "@/components/battles/battle-arena";

export const metadata = {
  title: "Battle Arena | Emby",
  description: "Live Brain Battle Arena",
};

export default async function BattleArenaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <BattleArena battleId={id} />
    </div>
  );
}
