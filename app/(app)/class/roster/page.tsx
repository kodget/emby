"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import { Users, Crown, Award, TrendingUp, ArrowLeft, Search } from "lucide-react";

type ClassMember = {
  id: number;
  user: {
    first_name: string;
    last_name: string;
    email: string;
  };
  profile_image: string | null;
  role: string;
  total_points: number;
  streak_days: number;
  rank: number | null;
};

export default function RosterPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [members, setMembers] = useState<ClassMember[]>([]);
  const [filteredMembers, setFilteredMembers] = useState<ClassMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (searchQuery) {
      const filtered = members.filter((member) => {
        const fullName = `${member.user.first_name} ${member.user.last_name}`.toLowerCase();
        return fullName.includes(searchQuery.toLowerCase());
      });
      setFilteredMembers(filtered);
    } else {
      setFilteredMembers(members);
    }
  }, [searchQuery, members]);

  const loadData = async () => {
    try {
      const profileData = await authApi.getProfile();
      setProfile(profileData);

      // TODO: Replace with actual API call when backend endpoint is ready
      // const membersData = await classApi.getClassMembers();
      // setMembers(membersData);

      // Mock data for now
      const mockMembers: ClassMember[] = [
        {
          id: 1,
          user: { first_name: "John", last_name: "Doe", email: "john@example.com" },
          profile_image: null,
          role: "student",
          total_points: 1250,
          streak_days: 15,
          rank: 1,
        },
        {
          id: 2,
          user: { first_name: "Jane", last_name: "Smith", email: "jane@example.com" },
          profile_image: null,
          role: "student",
          total_points: 980,
          streak_days: 12,
          rank: 2,
        },
      ];
      setMembers(mockMembers);
      setFilteredMembers(mockMembers);
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
            <p className="text-gray-600">Loading roster...</p>
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
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push("/class")}
                className="p-2 hover:bg-white rounded-lg transition-colors"
              >
                <ArrowLeft className="w-6 h-6 text-gray-600" />
              </button>
              <div>
                <h1 className="text-4xl font-bold text-gray-900">Class Roster</h1>
                <p className="text-gray-600">{profile?.set_name || "View class members"}</p>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="text-3xl font-bold text-purple-600 mb-1">{members.length}</div>
              <div className="text-sm text-gray-600">Total Members</div>
            </div>
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="text-3xl font-bold text-blue-600 mb-1">
                {members.filter((m) => m.role === "class_head").length}
              </div>
              <div className="text-sm text-gray-600">Class Heads</div>
            </div>
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="text-3xl font-bold text-green-600 mb-1">
                {Math.round(members.reduce((sum, m) => sum + m.total_points, 0) / members.length || 0)}
              </div>
              <div className="text-sm text-gray-600">Avg Points</div>
            </div>
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="text-3xl font-bold text-orange-600 mb-1">
                {Math.round(members.reduce((sum, m) => sum + m.streak_days, 0) / members.length || 0)}
              </div>
              <div className="text-sm text-gray-600">Avg Streak</div>
            </div>
          </div>

          {/* Search */}
          <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search members..."
                className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Members List */}
          {filteredMembers.length === 0 ? (
            <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
              <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">No Members Found</h2>
              <p className="text-gray-600">
                {searchQuery ? "Try a different search term" : "No members in this class yet"}
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Member</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Role</th>
                      <th className="px-6 py-4 text-center text-sm font-semibold text-gray-900">Rank</th>
                      <th className="px-6 py-4 text-center text-sm font-semibold text-gray-900">Points</th>
                      <th className="px-6 py-4 text-center text-sm font-semibold text-gray-900">Streak</th>
                      {isHead && (
                        <th className="px-6 py-4 text-center text-sm font-semibold text-gray-900">Actions</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {filteredMembers.map((member) => (
                      <tr key={member.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-blue-400 flex items-center justify-center text-white font-semibold">
                              {member.profile_image ? (
                                <img
                                  src={member.profile_image}
                                  alt=""
                                  className="w-full h-full rounded-full object-cover"
                                />
                              ) : (
                                `${member.user.first_name[0]}${member.user.last_name[0]}`
                              )}
                            </div>
                            <div>
                              <div className="font-semibold text-gray-900">
                                {member.user.first_name} {member.user.last_name}
                              </div>
                              <div className="text-sm text-gray-600">{member.user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          {member.role === "class_head" ? (
                            <span className="inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-yellow-500 to-orange-500 text-white text-sm font-semibold rounded-full">
                              <Crown className="w-3 h-3" />
                              Class Head
                            </span>
                          ) : (
                            <span className="text-gray-600 capitalize">{member.role}</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Award className="w-4 h-4 text-purple-600" />
                            <span className="font-semibold text-gray-900">#{member.rank || "N/A"}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="font-semibold text-blue-600">{member.total_points}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <TrendingUp className="w-4 h-4 text-orange-600" />
                            <span className="font-semibold text-gray-900">{member.streak_days}</span>
                          </div>
                        </td>
                        {isHead && (
                          <td className="px-6 py-4 text-center">
                            <button
                              onClick={() => router.push(`/profile/${member.id}`)}
                              className="text-purple-600 hover:text-purple-700 font-semibold text-sm"
                            >
                              View Profile
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </AuthGuard>
  );
}
