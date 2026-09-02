"use client";

import { creditsApi } from "@/lib/api";
import { Coins, History, CreditCard, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useCredits } from "@/hooks/use-credits";
import type { CreditPackage, CreditHistoryItem } from "@/lib/api";

export default function CreditsPage() {
  const { balance, refetch: refetchBalance } = useCredits();
  const [isPurchasing, setIsPurchasing] = useState<number | null>(null);

  const [packagesData, setPackagesData] = useState<{ packages: CreditPackage[] } | null>(null);
  const [isLoadingPackages, setIsLoadingPackages] = useState(true);

  const [historyData, setHistoryData] = useState<{ history: CreditHistoryItem[] } | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  useEffect(() => {
    creditsApi.getPackages().then(setPackagesData).finally(() => setIsLoadingPackages(false));
    creditsApi.getHistory(20).then(setHistoryData).finally(() => setIsLoadingHistory(false));
  }, []);

  const handlePurchase = async (packageId: number) => {
    try {
      setIsPurchasing(packageId);
      // Init purchase
      const { authorization_url, reference } = await creditsApi.initPurchase(packageId);
      
      // Normally, we redirect to authorization_url.
      // But in this implementation, we will simulate the redirect for now 
      // or open it in a popup if it's Paystack. 
      // We will just navigate to authorization_url
      window.location.href = authorization_url;
      
    } catch (err: any) {
      toast.error(err.response?.data?.error || "Failed to initialize purchase");
      setIsPurchasing(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6 lg:p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">AI Credits</h1>
        <p className="text-muted-foreground mt-2">
          Manage your AI credits. Credits are dynamically consumed based on the exact amount of AI compute used across Emby features.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Balance Card */}
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-6 opacity-10">
            <Coins className="w-32 h-32 text-amber-500" />
          </div>
          <div className="relative z-10">
            <h3 className="text-lg font-medium">Available Balance</h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-5xl font-bold text-foreground">
                {balance.toLocaleString()}
              </span>
              <span className="text-lg font-medium text-muted-foreground">
                credits
              </span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground max-w-xs">
              Credits reset daily based on your subscription tier. Purchased credits never expire.
            </p>
          </div>
        </div>

        {/* Packages */}
        <div className="space-y-4">
          <h3 className="text-xl font-semibold flex items-center gap-2">
            <CreditCard className="size-5" /> Buy Credits
          </h3>
          {isLoadingPackages ? (
            <div className="flex justify-center p-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : packagesData?.packages.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
              No credit packages available at the moment.
            </div>
          ) : (
            <div className="grid gap-4">
              {packagesData?.packages.map((pkg) => (
                <div
                  key={pkg.id}
                  className="flex items-center justify-between rounded-xl border border-border bg-card p-4 shadow-sm"
                >
                  <div>
                    <div className="font-semibold text-lg flex items-center gap-1.5">
                      <Sparkles className="size-4 text-amber-500" />
                      {pkg.credits.toLocaleString()} Credits
                    </div>
                  </div>
                  <button
                    onClick={() => handlePurchase(pkg.id)}
                    disabled={isPurchasing !== null}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    {isPurchasing === pkg.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      `Buy ₦${pkg.total_price.toLocaleString()}`
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* History */}
      <div className="space-y-4 pt-8 border-t border-border">
        <h3 className="text-xl font-semibold flex items-center gap-2">
          <History className="size-5" /> Transaction History
        </h3>
        
        {isLoadingHistory ? (
          <div className="flex justify-center p-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : historyData?.history.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
            No transactions yet.
          </div>
        ) : (
          <div className="rounded-xl border border-border overflow-hidden bg-card">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Description</th>
                  <th className="px-4 py-3 font-medium text-right">Amount</th>
                  <th className="px-4 py-3 font-medium text-right">Balance</th>
                  <th className="px-4 py-3 font-medium text-right">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {historyData?.history.map((tx) => (
                  <tr key={tx.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">{tx.action}</td>
                    <td className="px-4 py-3 text-muted-foreground">{tx.description}</td>
                    <td className={`px-4 py-3 text-right font-medium ${tx.amount > 0 ? 'text-green-500' : 'text-foreground'}`}>
                      {tx.amount > 0 ? '+' : ''}{tx.amount.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">{tx.balance_after.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {new Date(tx.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
