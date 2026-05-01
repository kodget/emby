"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import { TrendingUp, Users, Award, BookOpen, Clock, Target, ArrowLeft } from "lucide-react";

export default function AnalyticsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const profileData = await authApi.getProfile();
      setProfile(profileData);

      if (profileData.role !== "class_head" || !profileData.class_head_verified) {
        router.push("/class");
        return;
      }

      // TODO: Load analytics data from backend
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
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

  // Mock data
  const analytics = {
    totalMembers: 25,
    activeToday: 18,
    avgPoints: 1250,
    avgStreak: 12,
    totalStudyTime: 450,
    completionRate: 78,
    topPerformers: [
      { name: "John Doe", points: 2500, rank: 1 },
      { name: "Jane Smith", points: 2300, rank: 2 },
      { name: "Bob Johnson", points: 2100, rank: 3 },
    ],
    weakTopics: [
      { name: "Biochemistry - Metabolism", struggles: 15 },
      { name: "Anatomy - Nervous System", struggles: 12 },
      { name: "Physiology - Cardiovascular", struggles: 10 },
    ],
    activityByDay: [
      { day: "Mon", active: 20 },
      { day: "Tue", active: 22 },
      { day: "Wed", active: 18 },
      { day: "Thu", active: 24 },
      { day: "Fri", active: 19 },
      { day: "Sat", active: 15 },
      { day: "Sun", active: 12 },
    ],
  };

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
                <span className="text-sm text-green-600 font-semibold">+3 this week</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.totalMembers}</div>
              <div className="text-sm text-gray-600">Total Members</div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-green-600" />
                </div>
                <span className="text-sm text-green-600 font-semibold">
                  {Math.round((analytics.activeToday / analytics.totalMembers) * 100)}%
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.activeToday}</div>
              <div className="text-sm text-gray-600">Active Today</div>
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

            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
                  <Clock className="w-6 h-6 text-indigo-600" />
                </div>
                <span className="text-sm text-indigo-600 font-semibold">This week</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.totalStudyTime}h</div>
              <div className="text-sm text-gray-600">Total Study Time</div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-pink-100 rounded-lg flex items-center justify-center">
                  <BookOpen className="w-6 h-6 text-pink-600" />
                </div>
                <span className="text-sm text-pink-600 font-semibold">{analytics.completionRate}%</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-1">{analytics.completionRate}%</div>
              <div className="text-sm text-gray-600">Completion Rate</div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid lg:grid-cols-2 gap-6 mb-8">
            {/* Activity Chart */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Weekly Activity</h3>
              <div className="space-y-3">
                {analytics.activityByDay.map((day) => (
                  <div key={day.day}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700">{day.day}</span>
                      <span className="text-sm font-semibold text-gray-900">{day.active} students</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full"
                        style={{ width: `${(day.active / analytics.totalMembers) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Performers */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Top Performers</h3>
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
            </div>
          </div>

          {/* Weak Topics */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-6">Topics Needing Attention</h3>
            <div className="space-y-4">
              {analytics.weakTopics.map((topic, index) => (
                <div key={index}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900">{topic.name}</span>
                    <span className="text-sm text-red-600 font-semibold">
                      {topic.struggles} students struggling
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-red-500 h-2 rounded-full"
                      style={{ width: `${(topic.struggles / analytics.totalMembers) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
