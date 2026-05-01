"use client";

import { useEffect, useState, lazy, Suspense } from "react";
import AuthGuard from "@/components/auth/auth-guard";
import { isEmailVerified } from "@/lib/guards";
import { Skeleton } from "@/components/ui/skeleton";

const DashboardHero = lazy(() => import("@/components/dashboard/dashboard-hero").then(m => ({ default: m.DashboardHero })));
const WeakTopics = lazy(() => import("@/components/dashboard/weak-topics").then(m => ({ default: m.WeakTopics })));
const UpcomingTests = lazy(() => import("@/components/dashboard/upcoming-tests").then(m => ({ default: m.UpcomingTests })));
const TodayPlan = lazy(() => import("@/components/dashboard/today-plan").then(m => ({ default: m.TodayPlan })));
const CoursesProgress = lazy(() => import("@/components/dashboard/courses-progress").then(m => ({ default: m.CoursesProgress })));
const WeeklyChart = lazy(() => import("@/components/dashboard/weekly-chart").then(m => ({ default: m.WeeklyChart })));
const Leaderboard = lazy(() => import("@/components/dashboard/leaderboard").then(m => ({ default: m.Leaderboard })));
const CommunityFeed = lazy(() => import("@/components/dashboard/community-feed").then(m => ({ default: m.CommunityFeed })));
const ScheduleModal = lazy(() => import("@/components/dashboard/schedule-modal").then(m => ({ default: m.ScheduleModal })));
const ClassInfoWidget = lazy(() => import("@/components/dashboard/class-info-widget").then(m => ({ default: m.ClassInfoWidget })));
const ExamCountdownWidget = lazy(() => import("@/components/dashboard/exam-countdown-widget").then(m => ({ default: m.ExamCountdownWidget })));
const PersonalizedGreeting = lazy(() => import("@/components/dashboard/personalized-greeting").then(m => ({ default: m.PersonalizedGreeting })));
const EmailVerificationBanner = lazy(() => import("@/components/auth/email-verification-banner"));

const WidgetSkeleton = () => <Skeleton className="h-40 w-full rounded-xl" />;

export default function DashboardPage() {
  const [showVerificationBanner, setShowVerificationBanner] = useState(false);

  useEffect(() => {
    setShowVerificationBanner(!isEmailVerified());
  }, []);

  return (
    <AuthGuard>
      <Suspense fallback={null}>
        {showVerificationBanner && <EmailVerificationBanner />}
      </Suspense>
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
        <Suspense fallback={<WidgetSkeleton />}>
          <PersonalizedGreeting />
        </Suspense>

        <Suspense fallback={<WidgetSkeleton />}>
          <DashboardHero />
        </Suspense>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Suspense fallback={<WidgetSkeleton />}><WeakTopics /></Suspense>
          <Suspense fallback={<WidgetSkeleton />}><UpcomingTests /></Suspense>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-6">
            <Suspense fallback={<WidgetSkeleton />}><TodayPlan /></Suspense>
            <Suspense fallback={<WidgetSkeleton />}><CoursesProgress /></Suspense>
            <Suspense fallback={<WidgetSkeleton />}><WeeklyChart /></Suspense>
          </div>
          <div className="space-y-6">
            <Suspense fallback={<WidgetSkeleton />}><ClassInfoWidget /></Suspense>
            <Suspense fallback={<WidgetSkeleton />}><ExamCountdownWidget /></Suspense>
            <Suspense fallback={<WidgetSkeleton />}><Leaderboard /></Suspense>
            <Suspense fallback={<WidgetSkeleton />}><CommunityFeed /></Suspense>
          </div>
        </div>

        <Suspense fallback={null}><ScheduleModal /></Suspense>
      </div>
    </AuthGuard>
  )
}
