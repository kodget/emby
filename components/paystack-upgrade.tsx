"use client";

import { useState } from "react";
import { loadScript } from "@paystack/inline-js";
import { Button } from "@/components/ui/button";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";

interface PaystackUpgradeProps {
  amount?: number;
  feature: string;
}

export function PaystackUpgrade({
  amount = 1499,
  feature,
}: PaystackUpgradeProps) {
  const [loading, setLoading] = useState(false);
  const user = useSelector((state: RootState) => state.user);

  const onPaymentSuccess = (reference: string) => {
    window.location.href = `/upgrade-success?reference=${reference}`;
  };

  const initializePayment = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/payments/checkout/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          email: user.email,
          amount: amount.toString(),
          user_id: user.id,
        }),
      });

      const data = await res.json();
      if (data.status === "success") {
        const handler = (window as any).PaystackPop.setup({
          key: "pk_live_90297962b58f43edd6d59f585b14323ae0d12a16",
          email: user.email,
          amount: amount * 100,
          ref: data.data.reference,
          callback: (response: any) => {
            window.location.href = `/upgrade-success?reference=${response.reference}`;
          },
          onClose: () => setLoading(false),
        });
        handler.openIframe();
      }
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <Button onClick={initializePayment} disabled={loading} className="w-full">
      {loading
        ? "Loading..."
        : `Monthly Premium - ₦1,499/mo`}
    </Button>
  );
}
