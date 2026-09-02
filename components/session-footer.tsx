"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";

export function SessionFooter({ 
  currentStep, 
  onNext, 
  onPrev,
  isEmbedded = false
}: { 
  currentStep: number, 
  onNext?: () => void,
  onPrev?: () => void,
  isEmbedded?: boolean
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isSession = searchParams.get("session") === "true" || isEmbedded;

  if (!isSession || currentStep >= 6) {
    return null;
  }

  const handlePrev = () => {
    if (onPrev) {
      onPrev();
      return;
    }
    const prevStep = Math.max(1, currentStep - 1);
    router.push(`/session?step=${prevStep}`);
  };

  const handleNext = () => {
    if (onNext) {
      onNext();
      return;
    }
    const nextStep = Math.min(6, currentStep + 1);
    router.push(`/session?step=${nextStep}`);
  };

  return (
    <footer className="border-t border-border bg-card px-6 py-4 flex items-center justify-between sticky bottom-0 z-50 shadow-xs mt-auto">
      <Button 
        onClick={handlePrev} 
        variant="outline" 
        disabled={currentStep === 1}
        className="w-24"
      >
        Previous
      </Button>
      <div className="flex items-center gap-4">
        <span className="text-xs font-semibold text-zinc-400 hidden sm:inline-block">
          Daily Session (Step {currentStep} of 5)
        </span>
        <Button 
          onClick={handleNext} 
          variant="default"
          className="w-24 bg-primary text-primary-foreground shadow-lg"
        >
          {currentStep === 5 ? "Finish" : "Next"}
        </Button>
      </div>
    </footer>
  );
}
