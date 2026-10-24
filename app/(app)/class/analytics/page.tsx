"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, classApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import { TrendingUp, Users, Award, BookOpen, Clock, Target, ArrowLeft } from "lucide-react";

type ClassMember = {
  id: number;
  user: { id: number; first_name: string; last_name: string; username: string };
  total_points: number;
  streak_days: number;
};

type ClassAnalytics = {
  totalMembers: number;
  avgPoints: number;
  avgStreak: number;
  topPerformers: { name: string; points: number; rank: number }[];
};

export default function AnalyticsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [analytics, setAnalytics] = useState<ClassAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const loadingRef = useRef(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setAnalytics(null);
    try {
      const profileData = await authApi.getProfile();
      setProfile(profileData);

      if (!profileData || profileData.class_role !== "class_head" || !profileData.class_head_verified) {
        router.push("/class");
        return;
      }

      // Fetch real class members data
      const members: ClassMember[] = await classApi.getClassMembers();

      const totalMembers = members.length;
      const totalPoints = members.reduce((sum, m) => sum + (m.total_points || 0), 0);
      const totalStreak = members.reduce((sum, m) => sum + (m.streak_days || 0), 0);
      const avgPoints = totalMembers > 0 ? Math.round(totalPoints / totalMembers) : 0;
      const avgStreak = totalMembers > 0 ? Math.round(totalStreak / totalMembers) : 0;

      // Sort members by points for top performers
      const sorted = [...members].sort((a, b) => (b.total_points || 0) - (a.total_points || 0) || a.user.id - b.user.id);
      const topPerformers = sorted.slice(0, 5).map((m, i) => ({
        name: `${m.user.first_name} ${m.user.last_name}`.trim() || m.user.username,
        points: m.total_points || 0,
        rank: i + 1,
      }));

      setAnalytics({
        totalMembers,
        avgPoints,
        avgStreak,
        topPerformers,
      });
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading analytics...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!analytics) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
          <div className="text-center">
            <p className="text-gray-600">Could not load class analytics. Please try again.</p>
            <button
              onClick={loadData}
              className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <button
              onClick={() => router.push("/class")}
              className="p-2 hover:bg-white rounded-lg transition-colors"
            >
              <ArrowLeft className="w-6 h-6 text-gray-600" />
            </button>
            <div>
              <h1 className="text-4xl font-bold text-gray-900">Class Analytics</h1>
              <p className="text-gray-600">{profile?.set_name || "Performance insights"}</p>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                  <Users className="w-6 h-6 text-purple-600" />
                </div>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.totalMembers}</div>
              <div className="text-sm text-gray-600">Total Members</div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Award className="w-6 h-6 text-blue-600" />
                </div>
                <span className="text-sm text-blue-600 font-semibold">Avg</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.avgPoints}</div>
              <div className="text-sm text-gray-600">Average Points</div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                  <Target className="w-6 h-6 text-orange-600" />
                </div>
                <span className="text-sm text-orange-600 font-semibold">Avg</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.avgStreak} days</div>
              <div className="text-sm text-gray-600">Average Streak</div>
            </div>
          </div>

          {/* Top Performers */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-6">Top members by points</h3>
            {analytics.topPerformers.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No member data available yet.</p>
            ) : (
              <div className="space-y-4">
                {analytics.topPerformers.map((performer, index) => (
                  <div key={index} className="flex items-center gap-4">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white ${
                        index === 0
                          ? "bg-yellow-500"
                          : index === 1
                          ? "bg-gray-400"
                          : "bg-orange-600"
                      }`}
                    >
                      {performer.rank}
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900">{performer.name}</div>
                      <div className="text-sm text-gray-600">{performer.points} points</div>
                    </div>
                    <Award className="w-5 h-5 text-purple-600" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
