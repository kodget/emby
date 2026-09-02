"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, Bell, User, LogOut, Trash2 } from "lucide-react";
import AuthGuard from "@/components/auth/auth-guard";
import { usePushNotifications } from "@/hooks/use-push-notifications";

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<
    "account" | "password" | "notifications"
  >("account");
  const { isSupported, isSubscribed, subscribe, unsubscribe } = usePushNotifications();
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [notifications, setNotifications] = useState({
    academic_enabled: true,
    community_enabled: true,
    system_enabled: true,
    flashcards_enabled: true,
    planner_enabled: true,
    study_goal_enabled: true,
    streak_enabled: true,
    weak_area_enabled: true,
    browser_push_enabled: false,
  });
  const [loading, setLoading] = useState(false);
  const [prefsLoading, setPrefsLoading] = useState(true);

  useEffect(() => {
    const fetchPrefs = async () => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${baseUrl}/api/notifications/preferences/`, {
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem("token")}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setNotifications({
            academic_enabled: data.academic_enabled,
            community_enabled: data.community_enabled,
            system_enabled: data.system_enabled,
            flashcards_enabled: data.flashcards_enabled,
            planner_enabled: data.planner_enabled,
            study_goal_enabled: data.study_goal_enabled,
            streak_enabled: data.streak_enabled,
            weak_area_enabled: data.weak_area_enabled,
            browser_push_enabled: data.browser_push_enabled,
          });
        }
      } catch (err) {
        console.error("Failed to fetch preferences", err);
      } finally {
        setPrefsLoading(false);
      }
    };
    fetchPrefs();
  }, []);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(
        `${baseUrl}/api/accounts/change-password/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${sessionStorage.getItem("token")}`,
          },
          body: JSON.stringify({
            old_password: passwordForm.current_password,
            new_password: passwordForm.new_password,
          }),
        },
      );
      if (response.ok) {
        alert("Password changed successfully");
        setPasswordForm({
          current_password: "",
          new_password: "",
          confirm_password: "",
        });
      } else {
        const data = await response.json();
        alert(data.error || "Failed to change password");
      }
    } catch (error) {
      console.error("Failed to change password:", error);
      alert("Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("refreshToken");
    sessionStorage.removeItem("user");
    router.push("/signin");
  };

  const handleDeleteAccount = async () => {
    if (
      !confirm(
        "Are you sure you want to delete your account? This action cannot be undone.",
      )
    ) {
      return;
    }
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(
        `${baseUrl}/api/accounts/profile/`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem("token")}`,
          },
        },
      );
      if (response.ok) {
        alert("Account deleted successfully");
        handleLogout();
      } else {
        alert("Failed to delete account");
      }
    } catch (error) {
      console.error("Failed to delete account:", error);
      alert("Failed to delete account");
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen px-4 py-6 sm:px-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-gray-900 mb-8">Settings</h1>

          {/* Tabs */}
          <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
            <div className="flex border-b">
              <button
                onClick={() => setActiveTab("account")}
                className={`flex-1 px-6 py-4 font-semibold transition-colors ${
                  activeTab === "account"
                    ? "bg-primary/8 text-primary border-b-2 border-primary"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <User className="w-5 h-5 inline-block mr-2" />
                Account
              </button>
              <button
                onClick={() => setActiveTab("password")}
                className={`flex-1 px-6 py-4 font-semibold transition-colors ${
                  activeTab === "password"
                    ? "bg-primary/8 text-primary border-b-2 border-primary"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <Lock className="w-5 h-5 inline-block mr-2" />
                Password
              </button>
              <button
                onClick={() => setActiveTab("notifications")}
                className={`flex-1 px-6 py-4 font-semibold transition-colors ${
                  activeTab === "notifications"
                    ? "bg-primary/8 text-primary border-b-2 border-primary"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <Bell className="w-5 h-5 inline-block mr-2" />
                Notifications
              </button>
            </div>

            <div className="p-8">
              {/* Account Tab */}
              {activeTab === "account" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-4">
                      Account Management
                    </h2>
                    <p className="text-gray-600 mb-6">
                      Manage your account settings and preferences
                    </p>
                  </div>

                  <div className="space-y-4">
                    <button
                      onClick={() => router.push("/profile")}
                      className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium press transition-colors text-left"
                    >
                      Edit Profile
                    </button>

                    <button
                      onClick={handleLogout}
                      className="w-full px-6 py-3 bg-gray-600 text-white rounded-lg font-semibold hover:bg-gray-700 transition-colors flex items-center justify-center gap-2"
                    >
                      <LogOut className="w-5 h-5" />
                      Logout
                    </button>

                    <div className="pt-6 border-t">
                      <h3 className="text-lg font-medium text-destructive mb-2">
                        Danger Zone
                      </h3>
                      <p className="text-gray-600 mb-4 text-sm">
                        Once you delete your account, there is no going back.
                        Please be certain.
                      </p>
                      <button
                        onClick={handleDeleteAccount}
                        className="px-6 py-3 bg-destructive text-white rounded-xl font-medium press transition-colors flex items-center gap-2"
                      >
                        <Trash2 className="w-5 h-5" />
                        Delete Account
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Password Tab */}
              {activeTab === "password" && (
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">
                    Change Password
                  </h2>
                  <p className="text-gray-600 mb-6">
                    Update your password to keep your account secure
                  </p>

                  <form onSubmit={handlePasswordChange} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Current Password
                      </label>
                      <input
                        type="password"
                        value={passwordForm.current_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            current_password: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 border border-border bg-card rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        New Password
                      </label>
                      <input
                        type="password"
                        value={passwordForm.new_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            new_password: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 border border-border bg-card rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent"
                        required
                        minLength={8}
                      />
                      <p className="text-sm text-gray-500 mt-1">
                        Must be at least 8 characters
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Confirm New Password
                      </label>
                      <input
                        type="password"
                        value={passwordForm.confirm_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            confirm_password: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 border border-border bg-card rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent"
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium press transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loading ? "Updating..." : "Update Password"}
                    </button>
                  </form>
                </div>
              )}

              {/* Notifications Tab */}
              {activeTab === "notifications" && (
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">
                    Notification Preferences
                  </h2>
                  <p className="text-gray-600 mb-6">
                    Choose what notifications you want to receive
                  </p>

                  <div className="space-y-4">
                    {[
                      {
                        key: "academic_enabled",
                        label: "Academic Notifications",
                        desc: "Get notified about quizzes, steeplechases, and academic activities",
                      },
                      {
                        key: "community_enabled",
                        label: "Community Activity",
                        desc: "Get notified about likes, replies, and comments",
                      },
                      {
                        key: "system_enabled",
                        label: "System Updates",
                        desc: "Important platform announcements and account alerts",
                      },
                      {
                        key: "flashcards_enabled",
                        label: "Flashcards Due",
                        desc: "Reminders when your flashcards are due for review",
                      },
                      {
                        key: "planner_enabled",
                        label: "Study Planner",
                        desc: "Get notified about upcoming tasks in your study plan",
                      },
                      {
                        key: "study_goal_enabled",
                        label: "Study Goals",
                        desc: "Updates on your personal study goals",
                      },
                      {
                        key: "streak_enabled",
                        label: "Streak Reminders",
                        desc: "Daily reminders to keep your streak going",
                      },
                      {
                        key: "weak_area_enabled",
                        label: "Weak Area Focus",
                        desc: "Recommendations based on your weak areas",
                      },
                      {
                        key: "browser_push_enabled",
                        label: "Browser Push Notifications",
                        desc: "Receive real-time popups even when you are on other tabs",
                      },
                    ].map((item) => (
                      <div
                        key={item.key}
                        className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                      >
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            {item.label}
                          </h3>
                          <p className="text-sm text-gray-600">{item.desc}</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={
                              notifications[
                                item.key as keyof typeof notifications
                              ]
                            }
                            onChange={async (e) => {
                              const checked = e.target.checked;
                              if (item.key === "browser_push_enabled") {
                                if (checked) {
                                  if (isSupported) {
                                    const success = await subscribe();
                                    if (success) {
                                      setNotifications({ ...notifications, browser_push_enabled: true });
                                    } else {
                                      alert("Failed to enable push notifications. Please check your browser permissions.");
                                    }
                                  } else {
                                    alert("Push notifications are not supported in your browser.");
                                  }
                                } else {
                                  if (isSupported) {
                                    await unsubscribe();
                                  }
                                  setNotifications({ ...notifications, browser_push_enabled: false });
                                }
                              } else {
                                setNotifications({
                                  ...notifications,
                                  [item.key]: checked,
                                });
                              }
                            }}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-muted peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                        </label>
                      </div>
                    ))}

                    <button
                      onClick={async () => {
                        try {
                          const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
                          const res = await fetch(`${baseUrl}/api/notifications/preferences/`, {
                            method: "PATCH",
                            headers: {
                              "Content-Type": "application/json",
                              Authorization: `Bearer ${sessionStorage.getItem("token")}`,
                            },
                            body: JSON.stringify(notifications),
                          });
                          if (res.ok) {
                            alert("Notification preferences saved successfully");
                          } else {
                            alert("Failed to save notification preferences");
                          }
                        } catch (err) {
                          console.error(err);
                          alert("Failed to save notification preferences");
                        }
                      }}
                      className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium press transition-colors mt-6"
                    >
                      Save Preferences
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
