"use client";

import { useRouter } from "next/navigation";
import { isPremium } from "@/lib/guards";
import { Lock, Crown } from "lucide-react";

const MAX_FREE_PLANNER_ITEMS = 3;

export function StudyPlannerLimitChecker({ 
  currentItemCount, 
  children 
}: { 
  currentItemCount: number;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const hasPremium = isPremium();

  if (hasPremium) {
    return <>{children}</>;
  }

  if (currentItemCount >= MAX_FREE_PLANNER_ITEMS) {
    return (
      <div className="relative">
        <div className="blur-sm pointer-events-none">{children}</div>
        <div className="absolute inset-0 flex items-center justify-center bg-white/90 backdrop-blur-sm">
          <div className="text-center max-w-md p-8">
            <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
              <Lock className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">Free Tier Limit Reached</h3>
            <p className="text-gray-600 mb-6">
              You've reached the maximum of {MAX_FREE_PLANNER_ITEMS} study plan items for free users.
              Upgrade to Premium for unlimited planning!
            </p>
            <button
              onClick={() => router.push("/payment")}
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all inline-flex items-center gap-2"
            >
              <Crown className="w-5 h-5" />
              Upgrade to Premium
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {currentItemCount >= MAX_FREE_PLANNER_ITEMS - 1 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
          <div className="flex items-start gap-3">
            <Crown className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-yellow-800">
                <strong>Free Tier:</strong> {MAX_FREE_PLANNER_ITEMS - currentItemCount} study plan item{MAX_FREE_PLANNER_ITEMS - currentItemCount !== 1 ? "s" : ""} remaining.{" "}
                <button
                  onClick={() => router.push("/payment")}
                  className="underline font-semibold hover:text-yellow-900"
                >
                  Upgrade for unlimited
                </button>
              </p>
            </div>
          </div>
        </div>
      )}
      {children}
    </>
  );
}
