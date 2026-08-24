import { BattlesDashboard } from "@/components/battles/battles-dashboard";

export const metadata = {
  title: "Brain Battles | Emby",
  description: "Compete with your classmates in real-time quiz challenges!",
};

export default function BattlesPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] bg-[url('/grid.svg')] text-white p-6 md:p-12">
      <BattlesDashboard />
    </div>
  );
}
