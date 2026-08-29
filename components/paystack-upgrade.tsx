"use client";

/**
 * Upgrade button.
 *
 * Three things were wrong here and are fixed:
 *   - the amount was sent from the browser, so the charge could be tampered with; the
 *     client now names a plan and the server resolves the price,
 *   - a live Paystack public key was committed in the source; it comes from the
 *     environment now,
 *   - it posted to /payments/checkout/, which is not a route — the API mounts payments
 *     under /api/payments/.
 */

import { useState } from "react";
import { useSelector } from "react-redux";

import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { DEFAULT_PLAN, PLANS, formatNaira, type PlanCode } from "@/lib/pricing";
import type { RootState } from "@/store/store";

interface PaystackUpgradeProps {
  plan?: PlanCode;
  feature?: string;
  className?: string;
}

export function PaystackUpgrade({
  plan = DEFAULT_PLAN.code,
  className,
}: PaystackUpgradeProps) {
  const [loading, setLoading] = useState(false);
  const user = useSelector((state: RootState) => state.user);
  const { toast } = useToast();

  const selected = PLANS[plan] ?? DEFAULT_PLAN;

  const initializePayment = async () => {
    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token =
        typeof window !== "undefined" ? sessionStorage.getItem("token") : null;

      const res = await fetch(`${baseUrl}/api/payments/checkout/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        // Only the plan code travels; the amount is the server's decision.
        body: JSON.stringify({ plan: selected.code }),
      });

      const data = await res.json();
      if (!res.ok || data.status !== "success") {
        throw new Error(data.error || "Could not start checkout");
      }

      const publicKey = process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY;
      const popup = (window as any).PaystackPop;

      // The inline popup is nicer, but it needs the script and a public key. When either
      // is missing, fall back to the hosted page Paystack already gave us.
      if (publicKey && popup) {
        popup
          .setup({
            key: publicKey,
            email: user.email,
            amount: data.data.plan.amount_kobo,
            ref: data.data.reference,
            callback: (response: any) => {
              window.location.href = `/upgrade-success?reference=${response.reference}`;
            },
            onClose: () => setLoading(false),
          })
          .openIframe();
        return;
      }

      window.location.href = data.data.authorization_url;
    } catch (err: any) {
      toast({
        title: "Payment could not start",
        description: err?.message || "Please try again in a moment.",
        variant: "destructive",
      });
      setLoading(false);
    }
  };

  return (
    <Button
      onClick={initializePayment}
      disabled={loading}
      className={className ?? "w-full"}
    >
      {loading
        ? "Starting checkout…"
        : `Go Premium — ${formatNaira(selected.amountNaira)}${
            selected.months === 1 ? "/mo" : "/yr"
          }`}
    </Button>
  );
}
