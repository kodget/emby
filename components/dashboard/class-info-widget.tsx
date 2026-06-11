"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import { Users, School, Hash, Crown, Calendar, ArrowRight } from "lucide-react";
import { isClassHead } from "@/lib/guards";

export function ClassInfoWidget() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await authApi.getProfile();
      setProfile(data);
    } catch (error) {
      console.error("Failed to load profile:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 animate-pulse">
        <div className="mb-4 h-6 w-1/2 rounded bg-muted"></div>
        <div className="space-y-3">
          <div className="h-4 rounded bg-muted"></div>
          <div className="h-4 w-3/4 rounded bg-muted"></div>
        </div>
      </div>
    );
  }

  if (!profile?.class_group) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-learning/12 text-learning">
            <Users className="size-4" />
          </span>
          <h3 className="font-serif text-base font-semibold tracking-tight">My Class</h3>
        </div>
        <p className="mb-4 text-sm text-muted-foreground">
          {profile?.role === "class_head"
            ? "Your class will be created after verification"
            : "Join a class to connect with classmates"}
        </p>
        {profile?.role !== "class_head" && (
          <button
            onClick={() => router.push("/onboarding")}
            className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_8px_20px_-8px_color-mix(in_oklab,var(--primary)_60%,transparent)] transition-colors hover:bg-primary/90"
          >
            Join Class
          </button>
        )}
      </div>
    );
  }

  const isHead = isClassHead();

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-learning/12 text-learning">
            <Users className="size-4" />
          </span>
          <h3 className="font-serif text-base font-semibold tracking-tight">My Class</h3>
        </div>
        {isHead && (
          <div className="flex items-center gap-1 rounded-full bg-review/15 px-2.5 py-1 text-xs font-semibold text-review">
            <Crown className="size-3" />
            Head
          </div>
        )}
      </div>

      <div className="mb-4 space-y-2.5">
        <div className="font-serif text-xl font-semibold tracking-tight text-foreground">
          {profile.set_name}
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <School className="size-4" />
          <span className="text-sm">{profile.school_name}</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Hash className="size-4" />
          <span className="font-mono text-sm font-semibold text-learning">{profile.class_code}</span>
        </div>
      </div>

      <div className="space-y-2">
        <button
          onClick={() => router.push("/class/announcements")}
          className="group flex w-full items-center justify-between rounded-xl border border-border bg-background/50 px-4 py-2.5 transition-colors hover:border-learning/40 hover:bg-learning/5"
        >
          <div className="flex items-center gap-2">
            <Calendar className="size-4 text-learning" />
            <span className="text-sm font-medium text-foreground">Announcements</span>
          </div>
          <ArrowRight className="size-4 text-learning transition-transform group-hover:translate-x-0.5" />
        </button>
        <button
          onClick={() => router.push("/class/roster")}
          className="group flex w-full items-center justify-between rounded-xl border border-border bg-background/50 px-4 py-2.5 transition-colors hover:border-mastery/40 hover:bg-mastery/5"
        >
          <div className="flex items-center gap-2">
            <Users className="size-4 text-mastery" />
            <span className="text-sm font-medium text-foreground">Class Roster</span>
          </div>
          <ArrowRight className="size-4 text-mastery transition-transform group-hover:translate-x-0.5" />
        </button>
        <button
          onClick={() => router.push("/class")}
          className="w-full rounded-xl bg-secondary px-4 py-2.5 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
        >
          View All
        </button>
      </div>
    </div>
  );
}
