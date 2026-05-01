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
      <div className="bg-white rounded-xl shadow-lg p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (!profile?.class_group) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <Users className="w-6 h-6 text-gray-400" />
          <h3 className="text-lg font-bold text-gray-900">My Class</h3>
        </div>
        <p className="text-gray-600 mb-4">
          {profile?.role === "class_head"
            ? "Your class will be created after verification"
            : "Join a class to connect with classmates"}
        </p>
        {profile?.role !== "class_head" && (
          <button
            onClick={() => router.push("/onboarding")}
            className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
          >
            Join Class
          </button>
        )}
      </div>
    );
  }

  const isHead = isClassHead();

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Users className="w-6 h-6 text-purple-600" />
          <h3 className="text-lg font-bold text-gray-900">My Class</h3>
        </div>
        {isHead && (
          <div className="flex items-center gap-1 px-2 py-1 bg-gradient-to-r from-yellow-500 to-orange-500 text-white text-xs font-semibold rounded">
            <Crown className="w-3 h-3" />
            Head
          </div>
        )}
      </div>

      <div className="space-y-3 mb-4">
        <div>
          <div className="text-xl font-bold text-gray-900">{profile.set_name}</div>
        </div>
        <div className="flex items-center gap-2 text-gray-600">
          <School className="w-4 h-4" />
          <span className="text-sm">{profile.school_name}</span>
        </div>
        <div className="flex items-center gap-2 text-gray-600">
          <Hash className="w-4 h-4" />
          <span className="text-sm font-mono font-semibold text-purple-600">{profile.class_code}</span>
        </div>
      </div>

      <div className="space-y-2">
        <button
          onClick={() => router.push("/class/announcements")}
          className="w-full flex items-center justify-between px-4 py-2 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors group"
        >
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-purple-600" />
            <span className="text-sm font-medium text-gray-900">Announcements</span>
          </div>
          <ArrowRight className="w-4 h-4 text-purple-600 group-hover:translate-x-1 transition-transform" />
        </button>
        <button
          onClick={() => router.push("/class/roster")}
          className="w-full flex items-center justify-between px-4 py-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors group"
        >
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-gray-900">Class Roster</span>
          </div>
          <ArrowRight className="w-4 h-4 text-blue-600 group-hover:translate-x-1 transition-transform" />
        </button>
        <button
          onClick={() => router.push("/class")}
          className="w-full px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-sm font-medium text-gray-900"
        >
          View All
        </button>
      </div>
    </div>
  );
}
