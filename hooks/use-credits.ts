import { useState, useEffect } from "react";
import { creditsApi } from "@/lib/api";

export function useCredits() {
  const [balance, setBalance] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchBalance = async () => {
    try {
      setIsLoading(true);
      const data = await creditsApi.getBalance();
      setBalance(data.balance);
      setError(null);
    } catch (err: any) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchBalance();
  }, []);

  return {
    balance,
    isLoading,
    error,
    refetch: fetchBalance,
    // Add logic to quickly verify affordability
    canAfford: (estimatedCost: number) => {
      return balance >= estimatedCost;
    },
  };
}
