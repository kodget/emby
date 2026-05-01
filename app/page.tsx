"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LandingNav } from "@/components/landing/landing-nav"
import { LandingHero } from "@/components/landing/landing-hero"
import { LandingFeatures } from "@/components/landing/landing-features"
import { LandingReaderDemo } from "@/components/landing/landing-reader-demo"
import { LandingSteeplechase } from "@/components/landing/landing-steeplechase"
import { LandingPricing } from "@/components/landing/landing-pricing"
import { LandingFooter } from "@/components/landing/landing-footer"
import { getRedirectPath, isAuthenticated } from "@/lib/guards";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated()) {
      router.push(getRedirectPath());
    }
  }, [router]);

  return (
    <main className="min-h-screen bg-background text-foreground">
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
