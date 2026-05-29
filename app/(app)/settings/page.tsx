"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Bell, User, LogOut, Trash2 } from "lucide-react";
import AuthGuard from "@/components/auth/auth-guard";

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<
    "account" | "password" | "notifications"
  >("account");
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [notifications, setNotifications] = useState({
    email_updates: true,
    community_activity: true,
    study_reminders: false,
    weekly_report: true,
  });
  const [loading, setLoading] = useState(false);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(
        "http://localhost:8000/api/accounts/change-password/",
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
      const response = await fetch(
        "http://localhost:8000/api/accounts/profile/",
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
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-gray-900 mb-8">Settings</h1>

          {/* Tabs */}
          <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
            <div className="flex border-b">
              <button
                onClick={() => setActiveTab("account")}
                className={`flex-1 px-6 py-4 font-semibold transition-colors ${
                  activeTab === "account"
                    ? "bg-purple-50 text-purple-600 border-b-2 border-purple-600"
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
                    ? "bg-purple-50 text-purple-600 border-b-2 border-purple-600"
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
                    ? "bg-purple-50 text-purple-600 border-b-2 border-purple-600"
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
                      className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors text-left"
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
                      <h3 className="text-lg font-semibold text-red-600 mb-2">
                        Danger Zone
                      </h3>
                      <p className="text-gray-600 mb-4 text-sm">
                        Once you delete your account, there is no going back.
                        Please be certain.
                      </p>
                      <button
                        onClick={handleDeleteAccount}
                        className="px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center gap-2"
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
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
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
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
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
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                        key: "email_updates",
                        label: "Email Updates",
                        desc: "Receive updates about new features and content",
                      },
                      {
                        key: "community_activity",
                        label: "Community Activity",
                        desc: "Get notified about likes and comments on your posts",
                      },
                      {
                        key: "study_reminders",
                        label: "Study Reminders",
                        desc: "Daily reminders to keep your streak going",
                      },
                      {
                        key: "weekly_report",
                        label: "Weekly Report",
                        desc: "Weekly summary of your learning progress",
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
                            onChange={(e) =>
                              setNotifications({
                                ...notifications,
                                [item.key]: e.target.checked,
                              })
                            }
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                        </label>
                      </div>
                    ))}

                    <button
                      onClick={() => alert("Notification preferences saved")}
                      className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors mt-6"
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
