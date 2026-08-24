import { CreateBattle } from "@/components/battles/create-battle";

export const metadata = {
  title: "Create Brain Battle | Emby",
  description: "Configure and host a new Brain Battle",
};

export default function CreateBattlePage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] bg-[url('/grid.svg')] text-white p-6 md:p-12">
      <CreateBattle />
    </div>
  );
}
