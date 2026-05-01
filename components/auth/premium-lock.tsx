"use client";

import { useRouter } from "next/navigation";
import { Lock, Crown } from "lucide-react";
import { isPremium } from "@/lib/guards";

type PremiumLockProps = {
  children: React.ReactNode;
  feature: string;
  showOverlay?: boolean;
};

export default function PremiumLock({ children, feature, showOverlay = true }: PremiumLockProps) {
  const router = useRouter();
  const hasPremium = isPremium();

  if (hasPremium) {
    return <>{children}</>;
  }

  if (!showOverlay) {
    return null;
  }

  return (
    <div className="relative">
      <div className="blur-sm pointer-events-none">{children}</div>
      <div className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm">
        <div className="text-center max-w-md p-8">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <Crown className="w-8 h-8 text-white" />
          </div>
          <h3 className="text-2xl font-bold text-gray-900 mb-2">Premium Feature</h3>
          <p className="text-gray-600 mb-6">
            Unlock {feature} and more with a Premium subscription
          </p>
          <button
            onClick={() => router.push("/payment")}
            className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all"
          >
            Upgrade to Premium
          </button>
        </div>
      </div>
    </div>
  );
}

export function PremiumBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-gradient-to-r from-purple-500 to-blue-500 text-white text-xs font-semibold rounded">
      <Crown className="w-3 h-3" />
      Premium
    </span>
  );
}

export function PremiumButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  const router = useRouter();
  const hasPremium = isPremium();

  if (!hasPremium) {
    return (
      <button
        onClick={() => router.push("/payment")}
        className="relative px-6 py-3 bg-gray-300 text-gray-500 rounded-lg font-semibold cursor-not-allowed"
      >
        <Lock className="w-4 h-4 inline-block mr-2" />
        {children}
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
    >
      {children}
    </button>
  );
}
