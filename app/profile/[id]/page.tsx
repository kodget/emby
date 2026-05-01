"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { authApi, statsApi, communityApi } from "@/lib/api";
import { UserProfile, UserStats, CommunityPost } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  Trophy,
  Flame,
  BookOpen,
  Clock,
  Award,
  MessageCircle,
  Calendar,
  School,
  Users,
} from "lucide-react";

export default function UserProfilePage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.id as string;
  
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOwnProfile, setIsOwnProfile] = useState(false);

  useEffect(() => {
    loadUserData();
  }, [userId]);

  const loadUserData = async () => {
    try {
      // Get current user to check if viewing own profile
      const currentUser = await authApi.getProfile();
      setIsOwnProfile(currentUser.id === parseInt(userId));

      // For now, we'll show current user's data
      // TODO: Add backend endpoint to get other users' public profiles
      if (currentUser.id === parseInt(userId)) {
        setProfile(currentUser);
        
        const [userStats, userPosts] = await Promise.all([
          statsApi.getMyStats(),
          communityApi.getPosts(),
        ]);
        
        setStats(userStats);
        // Filter posts by this user
        setPosts(userPosts.filter(p => p.user === currentUser.id));
      } else {
        // For other users, show limited info
        // This would need a backend endpoint
        setProfile(null);
        setStats(null);
        setPosts([]);
      }
    } catch (error) {
      console.error("Failed to load user data:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading profile...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!profile) {
    return (
      <AuthGuard>
        <div className="min-h-screen flex items-center justify-center p-4">
          <Card className="max-w-md w-full p-8 text-center">
            <h2 className="text-2xl font-bold mb-2">Profile Not Found</h2>
            <p className="text-muted-foreground mb-6">
              This user's profile is not available or set to private.
            </p>
            <Button onClick={() => router.back()}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Go Back
            </Button>
          </Card>
        </div>
      </AuthGuard>
    );
  }

  const firstName = profile.full_name.split(" ")[0];
  const roleLabels: Record<string, string> = {
    student: "Student",
    brainstormer: "Brainstormer",
    class_head: "Class Head",
    material_uploader: "Material Uploader",
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 py-8 px-4">
        <div className="max-w-5xl mx-auto">
          {/* Back Button */}
          <Button
            variant="ghost"
            onClick={() => router.back()}
            className="mb-6"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>

          {/* Profile Header */}
          <Card className="p-8 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-start">
              <Avatar className="w-24 h-24">
                <AvatarImage src={profile.photo_url || "/placeholder.svg"} alt={profile.full_name} />
                <AvatarFallback className="text-2xl">{firstName[0]}</AvatarFallback>
              </Avatar>

              <div className="flex-1">
                <div className="flex items-start justify-between flex-wrap gap-4">
                  <div>
                    <h1 className="text-3xl font-bold mb-2">{profile.full_name}</h1>
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <Badge variant="secondary">
                        {roleLabels[profile.role] || profile.role}
                      </Badge>
                      {profile.is_premium && (
                        <Badge className="bg-gradient-to-r from-purple-600 to-blue-600 text-white">
                          Premium
                        </Badge>
                      )}
                      {profile.role === "class_head" && profile.class_head_verified && (
                        <Badge className="bg-green-600 text-white">
                          Verified Class Head
                        </Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      {profile.school_name && (
                        <div className="flex items-center gap-2">
                          <School className="w-4 h-4" />
                          {profile.school_name}
                        </div>
                      )}
                      {profile.set_name && (
                        <div className="flex items-center gap-2">
                          <Users className="w-4 h-4" />
                          {profile.set_name}
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4" />
                        Joined {new Date(profile.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>

                  {isOwnProfile && (
                    <Button onClick={() => router.push("/profile")}>
                      Edit Profile
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Stats Grid */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <Card className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
                    <Trophy className="w-5 h-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.points}</p>
                    <p className="text-xs text-muted-foreground">Points</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                    <Award className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">#{stats.rank}</p>
                    <p className="text-xs text-muted-foreground">Rank</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                    <Flame className="w-5 h-5 text-orange-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.current_streak}</p>
                    <p className="text-xs text-muted-foreground">Day Streak</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                    <BookOpen className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.slides_completed}</p>
                    <p className="text-xs text-muted-foreground">Slides Done</p>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Activity Stats */}
          {stats && (
            <Card className="p-6 mb-6">
              <h2 className="text-xl font-bold mb-4">Activity</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{stats.total_study_minutes}</p>
                    <p className="text-sm text-muted-foreground">Minutes Studied</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <BookOpen className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{stats.quizzes_taken}</p>
                    <p className="text-sm text-muted-foreground">Quizzes Taken</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Flame className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{stats.longest_streak}</p>
                    <p className="text-sm text-muted-foreground">Longest Streak</p>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Recent Posts */}
          <Card className="p-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <MessageCircle className="w-5 h-5" />
              Recent Posts ({posts.length})
            </h2>
            {posts.length === 0 ? (
              <div className="text-center py-12">
                <MessageCircle className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">No posts yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {posts.slice(0, 5).map((post) => (
                  <div key={post.id} className="border-b pb-4 last:border-0">
                    <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
                      <Badge variant="secondary" className="text-xs">
                        {post.post_type}
                      </Badge>
                      <span>·</span>
                      <span>{new Date(post.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-sm line-clamp-3">{post.content}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span>{post.likes_count} likes</span>
                      <span>{post.comments_count} comments</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </AuthGuard>
  );
}
