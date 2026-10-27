"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LandingNav, LandingHero, LandingFeatures, LandingReaderDemo, LandingSteeplechase, LandingPricing, LandingFooter } from "@/components/landing/landing-studio";
import { getRedirectPath, isAuthenticated } from "@/lib/guards";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated()) {
      router.push(getRedirectPath());
    }
  }, [router]);

  return (
    <main className="studio-landing min-h-screen text-foreground">
      <LandingNav />
      <LandingHero />
      <LandingFeatures />
      <LandingReaderDemo />
      <LandingSteeplechase />
      <LandingPricing />
      <LandingFooter />
    </main>
  )
}
