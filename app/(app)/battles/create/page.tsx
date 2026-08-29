import { CreateBattle } from "@/components/battles/create-battle";

export const metadata = {
  title: "Create Brain Battle | Emby",
  description: "Configure and host a new Brain Battle",
};

export default function CreateBattlePage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <CreateBattle />
    </div>
  );
}
