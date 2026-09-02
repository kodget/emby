"use client";

/**
 * Dashboard.
 *
 * Previously ten widgets of identical visual weight stacked down the page, which gave a
 * student nowhere to look first. This version has a deliberate reading order:
 *
 *   1. Who you are and how you're doing        (header band + stat rail)
 *   2. What to do right now                    (today's session)
 *   3. Where to go                             (quick action tiles)
 *   4. What needs attention                    (weak topics, tests, progress)
 *   5. Context and social                      (class, leaderboard, feed)
 *
 * Everything below the fold stays lazy so the first paint is just the band and tiles.
 */

import { Suspense, lazy, useEffect, useState } from "react";

import AuthGuard from "@/components/auth/auth-guard";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { Momentum } from "@/components/dashboard/momentum";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { SurfaceSkeleton } from "@/components/ui/surface";
import { isEmailVerified } from "@/lib/guards";
import { flashcardApi, statsApi, learningApi } from "@/lib/api";

const TodaySessionCard = lazy(() =>
  import("@/components/dashboard/today-session-card").then((m) => ({
    default: m.TodaySessionCard,
  })),
);
const WeakTopics = lazy(() =>
  import("@/components/dashboard/weak-topics").then((m) => ({
    default: m.WeakTopics,
  })),
);
const UpcomingTests = lazy(() =>
  import("@/components/dashboard/upcoming-tests").then((m) => ({
    default: m.UpcomingTests,
  })),
);
const CoursesProgress = lazy(() =>
  import("@/components/dashboard/courses-progress").then((m) => ({
    default: m.CoursesProgress,
  })),
);
const Leaderboard = lazy(() =>
  import("@/components/dashboard/leaderboard").then((m) => ({
    default: m.Leaderboard,
  })),
);
const CommunityFeed = lazy(() =>
  import("@/components/dashboard/community-feed").then((m) => ({
    default: m.CommunityFeed,
  })),
);
const ClassInfoWidget = lazy(() =>
  import("@/components/dashboard/class-info-widget").then((m) => ({
    default: m.ClassInfoWidget,
  })),
);
const ExamCountdownWidget = lazy(() =>
  import("@/components/dashboard/exam-countdown-widget").then((m) => ({
    default: m.ExamCountdownWidget,
  })),
);
const ScheduleModal = lazy(() =>
  import("@/components/dashboard/schedule-modal").then((m) => ({
    default: m.ScheduleModal,
  })),
);
const EmailVerificationBanner = lazy(
  () => import("@/components/auth/email-verification-banner"),
);

type Snapshot = {
  streak: number;
  xp: number;
  creditsRemaining: number | null;
  cardsDue: number | null;
};

export default function DashboardPage() {
  const [showBanner, setShowBanner] = useState(false);
  const [snapshot, setSnapshot] = useState<Partial<Snapshot>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setShowBanner(!isEmailVerified());
  }, []);

  useEffect(() => {
    let cancelled = false;

    // Each source is independent: one failing endpoint must not blank the whole rail,
    // so unresolved values stay undefined and render as an em dash.
    (async () => {
      try {
        const snap = await learningApi.getDashboardSnapshot();
        if (cancelled) return;

        setSnapshot({
          streak: snap.streak,
          xp: snap.xp,
          cardsDue: snap.cards_due,
          creditsRemaining: snap.credits?.remaining ?? snap.credits,
        });
      } catch (err) {
        console.error("Failed to load dashboard snapshot", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AuthGuard>
      <Suspense fallback={null}>
        {showBanner && <EmailVerificationBanner />}
      </Suspense>

      <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-5 sm:px-6 lg:py-8">
        <DashboardHeader snapshot={snapshot} loading={loading} />

        {/* The daily tracker sits directly under the greeting: it is the thing that
            makes a return visit feel like continuing something. */}
        <Momentum />

        <Suspense fallback={<SurfaceSkeleton lines={2} />}>
          <TodaySessionCard />
        </Suspense>

        <QuickActions />

        <div className="grid gap-4 md:grid-cols-2">
          <Suspense fallback={<SurfaceSkeleton />}>
            <WeakTopics />
          </Suspense>
          <Suspense fallback={<SurfaceSkeleton />}>
            <UpcomingTests />
          </Suspense>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-5">
            <Suspense fallback={<SurfaceSkeleton />}>
              <CoursesProgress />
            </Suspense>
            <Suspense fallback={<SurfaceSkeleton />}>
              <CommunityFeed />
            </Suspense>
          </div>
          <div className="space-y-5">
            <Suspense fallback={<SurfaceSkeleton lines={2} />}>
              <ClassInfoWidget />
            </Suspense>
            <Suspense fallback={<SurfaceSkeleton lines={2} />}>
              <ExamCountdownWidget />
            </Suspense>
            <Suspense fallback={<SurfaceSkeleton />}>
              <Leaderboard />
            </Suspense>
          </div>
        </div>

        <Suspense fallback={null}>
          <ScheduleModal />
        </Suspense>
      </div>
    </AuthGuard>
  );
}
