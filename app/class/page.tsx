"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { classApi, authApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import { Users, School, Hash, Crown, Calendar, Plus, FileText } from "lucide-react";

export default function ClassPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [classData, setClassData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const profileData = await authApi.getProfile();
      setProfile(profileData);
      
      if (profileData.class_group) {
        const classInfo = await classApi.getMyClass();
        setClassData(classInfo);
      }
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
            <p className="text-gray-600">Loading class...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!profile?.class_group) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
          <div className="max-w-4xl mx-auto">
            <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
              <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">No Class Yet</h2>
              <p className="text-gray-600 mb-6">
                {profile?.role === "class_head"
                  ? "Your class will be created after verification"
                  : "Join a class to connect with your classmates"}
              </p>
              {profile?.role !== "class_head" && (
                <button
                  onClick={() => router.push("/onboarding")}
                  className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
                >
                  Join Class
                </button>
              )}
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  const isHead = isClassHead();

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h1 className="text-4xl font-bold text-gray-900 mb-2">{profile.set_name}</h1>
                <div className="flex items-center gap-4 text-gray-900">
                  <div className="flex items-center gap-2">
                    <School className="w-5 h-5" />
                    <span>{profile.school_name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Hash className="w-5 h-5" />
                    <span className="font-mono font-semibold text-purple-600">{profile.class_code}</span>
                  </div>
                </div>
              </div>
              {isHead && (
                <div className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-yellow-500 to-orange-500 text-white rounded-lg">
                  <Crown className="w-5 h-5" />
                  <span className="font-semibold">Class Head</span>
                </div>
              )}
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-4 pt-6 border-t">
              <div className="text-center">
                <div className="text-3xl font-bold text-purple-600">{classData?.member_count || 0}</div>
                <div className="text-sm text-gray-900">Members</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600">0</div>
                <div className="text-sm text-gray-900">Announcements</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">0</div>
                <div className="text-sm text-gray-900">Active Today</div>
              </div>
            </div>
          </div>

          {/* Navigation Cards */}
          <div className="grid md:grid-cols-3 gap-6">
            <button
              onClick={() => router.push("/materials")}
              className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow text-left"
            >
              <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center mb-4">
                <FileText className="w-6 h-6 text-indigo-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Extra Materials</h3>
              <p className="text-gray-900 text-sm">
                Access notes, videos, links, and past questions
              </p>
            </button>

            <button
              onClick={() => router.push("/class/announcements")}
              className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow text-left"
            >
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
                <Calendar className="w-6 h-6 text-purple-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Announcements</h3>
              <p className="text-gray-900 text-sm">
                {isHead ? "Create and manage class announcements" : "View class announcements and updates"}
              </p>
              {isHead && (
                <div className="mt-4 flex items-center gap-2 text-purple-600 font-semibold">
                  <Plus className="w-4 h-4" />
                  <span>Create New</span>
                </div>
              )}
            </button>

            <button
              onClick={() => router.push("/class/roster")}
              className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow text-left"
            >
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                <Users className="w-6 h-6 text-blue-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Class Roster</h3>
              <p className="text-gray-900 text-sm">
                {isHead ? "View and manage class members" : "See your classmates"}
              </p>
            </button>

            {isHead && (
              <button
                onClick={() => router.push("/class/analytics")}
                className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow text-left"
              >
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
                  <School className="w-6 h-6 text-green-600" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Class Analytics</h3>
                <p className="text-gray-900 text-sm">View class performance and engagement stats</p>
              </button>
            )}

            {isHead && (
              <button
                onClick={() => router.push("/class/exams")}
                className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow text-left"
              >
                <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
                  <Calendar className="w-6 h-6 text-orange-600" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Exam Countdowns</h3>
                <p className="text-gray-900 text-sm">Manage exam dates and countdowns for your class</p>
              </button>
            )}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
