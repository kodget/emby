"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, statsApi } from "@/lib/api";
import { UserProfile, UserStats } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { updateUserProfile } from "@/store/user-slice";
import {
  Upload,
  Mail,
  Calendar,
  Award,
  Edit2,
  Check,
  X,
  Loader2,
  Crown,
  Shield,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";

export default function ProfilePage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const { toast } = useToast();
  const user = useAppSelector((s) => s.user);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
  });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const [profileData, statsData] = await Promise.all([
        authApi.getProfile(),
        statsApi.getMyStats().catch(() => null),
      ]);
      setProfile(profileData);
      setStats(statsData);

      // Update Redux store
      dispatch(
        updateUserProfile({
          name: profileData.full_name,
          email: profileData.email,
          photoUrl: profileData.photo_url,
          school: profileData.school_name,
          setName: profileData.set_name,
          streak: profileData.streak,
          points: statsData?.points || 0,
          rank: statsData?.rank || 0,
        }),
      );

      // Initialize edit form
      const nameParts = profileData.full_name.split(" ");
      setEditForm({
        first_name: nameParts[0] || "",
        last_name: nameParts.slice(1).join(" ") || "",
      });

      // Update sessionStorage
      sessionStorage.setItem("user", JSON.stringify(profileData));
    } catch (error) {
      console.error("Failed to load profile:", error);
      toast({
        title: "Error",
        description: "Failed to load profile data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "File too large",
        description: "Please select an image smaller than 5MB",
        variant: "destructive",
      });
      return;
    }

    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast({
        title: "Invalid file type",
        description: "Please select an image file",
        variant: "destructive",
      });
      return;
    }

    setUploading(true);
    try {
      // Upload to Cloudinary
      const formData = new FormData();
      formData.append("file", file);
      formData.append(
        "upload_preset",
        process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET || "emby_uploads",
      );
      formData.append("folder", "profile_images");

      const cloudinaryResponse = await fetch(
        `https://api.cloudinary.com/v1_1/${process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME}/image/upload`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!cloudinaryResponse.ok) {
        throw new Error("Failed to upload image");
      }

      const cloudinaryData = await cloudinaryResponse.json();

      // Update profile with new photo URL
      const response = await authApi.updateProfile({
        photo_url: cloudinaryData.secure_url,
      });

      toast({
        title: "Success",
        description: response.message,
      });

      await loadProfile();
    } catch (error) {
      console.error("Failed to upload image:", error);
      toast({
        title: "Upload failed",
        description: "Failed to upload profile photo. Please try again.",
        variant: "destructive",
      });
    } finally {
      setUploading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!editForm.first_name.trim()) {
      toast({
        title: "Validation error",
        description: "First name is required",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.updateProfile({
        first_name: editForm.first_name,
        last_name: editForm.last_name,
      });

      toast({
        title: "Success",
        description: response.message,
      });

      setEditing(false);
      await loadProfile();
    } catch (error) {
      console.error("Failed to update profile:", error);
      toast({
        title: "Update failed",
        description: "Failed to update profile. Please try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading profile...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!profile) return null;

  const subscriptionBadge = {
    free: { label: "Free", color: "bg-gray-100 text-gray-700", icon: null },
    premium: {
      label: "Premium",
      color: "bg-gradient-to-r from-purple-500 to-blue-500 text-white",
      icon: Crown,
    },
    class_head: {
      label: "Class Head",
      color: "bg-gradient-to-r from-yellow-500 to-orange-500 text-white",
      icon: Shield,
    },
  }[profile.subscription_tier];

  const roleBadge = {
    student: { label: "Student", icon: Users },
    class_head: { label: "Class Head", icon: Shield },
    brainstormer: { label: "Brainstormer", icon: Award },
    material_uploader: { label: "Material Uploader", icon: Upload },
  }[profile.role];

  const getInitials = (name: string) => {
    const parts = name.split(" ");
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <AuthGuard>
      <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Header Card */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-start gap-6">
                {/* Profile Image */}
                <div className="relative">
                  <Avatar className="h-32 w-32">
                    <AvatarImage
                      src={profile.photo_url || undefined}
                      alt={profile.full_name}
                    />
                    <AvatarFallback className="text-3xl bg-gradient-to-br from-purple-400 to-blue-400 text-white">
                      {getInitials(profile.full_name)}
                    </AvatarFallback>
                  </Avatar>
                  <label className="absolute bottom-0 right-0 bg-primary text-primary-foreground p-2 rounded-full cursor-pointer hover:bg-primary/90 transition-colors shadow-lg">
                    {uploading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Upload className="w-5 h-5" />
                    )}
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageUpload}
                      className="hidden"
                      disabled={uploading}
                    />
                  </label>
                </div>

                {/* Profile Info */}
                <div className="flex-1 space-y-4">
                  {editing ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label htmlFor="first_name">First Name</Label>
                          <Input
                            id="first_name"
                            value={editForm.first_name}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                first_name: e.target.value,
                              })
                            }
                          />
                        </div>
                        <div>
                          <Label htmlFor="last_name">Last Name</Label>
                          <Input
                            id="last_name"
                            value={editForm.last_name}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                last_name: e.target.value,
                              })
                            }
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={handleSaveProfile}>
                          <Check className="w-4 h-4 mr-1" />
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditing(false)}
                        >
                          <X className="w-4 h-4 mr-1" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-3 flex-wrap">
                        <h1 className="text-3xl font-bold">
                          {profile.full_name}
                        </h1>
                        <Badge className={subscriptionBadge.color}>
                          {subscriptionBadge.icon && (
                            <subscriptionBadge.icon className="w-3 h-3 mr-1" />
                          )}
                          {subscriptionBadge.label}
                        </Badge>
                        <Badge variant="outline">
                          {roleBadge.icon && (
                            <roleBadge.icon className="w-3 h-3 mr-1" />
                          )}
                          {roleBadge.label}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Mail className="w-4 h-4" />
                        <span>{profile.email}</span>
                        {profile.email_verified ? (
                          <Badge
                            variant="outline"
                            className="text-green-600 border-green-600"
                          >
                            Verified
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="text-yellow-600 border-yellow-600"
                          >
                            Unverified
                          </Badge>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditing(true)}
                      >
                        <Edit2 className="w-4 h-4 mr-1" />
                        Edit Profile
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-4xl font-bold text-orange-600 mb-2">
                  {profile.streak}
                </div>
                <div className="text-sm text-muted-foreground">
                  Day Streak 🔥
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-4xl font-bold text-blue-600 mb-2">
                  {stats?.points || 0}
                </div>
                <div className="text-sm text-muted-foreground">
                  Total Points
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-4xl font-bold text-green-600 mb-2">
                  #{stats?.rank || "N/A"}
                </div>
                <div className="text-sm text-muted-foreground">Class Rank</div>
              </CardContent>
            </Card>
          </div>

          {/* Class Info */}
          {profile.class_group && (
            <Card>
              <CardHeader>
                <CardTitle>Class Information</CardTitle>
                <CardDescription>Your class and school details</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Class Name</span>
                  <span className="font-semibold">{profile.set_name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">School</span>
                  <span className="font-semibold">{profile.school_name}</span>
                </div>
                {profile.class_code && profile.role !== "class_head" && (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Class Code</span>
                    <code className="font-mono font-semibold text-primary bg-primary/10 px-2 py-1 rounded">
                      {profile.class_code}
                    </code>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Subscription Info */}
          <Card>
            <CardHeader>
              <CardTitle>Subscription</CardTitle>
              <CardDescription>Manage your subscription plan</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Current Plan</span>
                <Badge className={subscriptionBadge.color}>
                  {subscriptionBadge.icon && (
                    <subscriptionBadge.icon className="w-3 h-3 mr-1" />
                  )}
                  {subscriptionBadge.label}
                </Badge>
              </div>
              {profile.subscription_expires_at && (
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Valid Until</span>
                  <span className="font-semibold">
                    {new Date(
                      profile.subscription_expires_at,
                    ).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                </div>
              )}
              {profile.subscription_tier === "free" && (
                <Button
                  onClick={() => router.push("/premium")}
                  className="w-full"
                >
                  <Crown className="w-4 h-4 mr-2" />
                  Upgrade to Premium
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Activity Stats */}
          {stats && (
            <Card>
              <CardHeader>
                <CardTitle>Activity Stats</CardTitle>
                <CardDescription>Your learning progress</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Study Time</span>
                  <span className="font-semibold">
                    {Math.floor((stats.total_study_minutes || 0) / 60)}h{" "}
                    {(stats.total_study_minutes || 0) % 60}m
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">
                    Slides Completed
                  </span>
                  <span className="font-semibold">
                    {stats.slides_completed || 0}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Quizzes Taken</span>
                  <span className="font-semibold">
                    {stats.quizzes_taken || 0}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </AuthGuard>
  );
}
