"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, statsApi, progressApi } from "@/lib/api";
import { UserProfile, UserStats, UserProgress } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UpgradePrompt } from "@/components/premium/upgrade-prompt";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Award,
  BookOpen,
  Clock,
  Target,
  BarChart3,
  Activity,
  Lock,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444"];

export default function AnalyticsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [progress, setProgress] = useState<UserProgress[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [profileData, statsData, progressData] = await Promise.all([
        authApi.getProfile(),
        statsApi.getMyStats(),
        progressApi.getProgress(),
      ]);
      setProfile(profileData);
      setStats(statsData);
      setProgress(progressData);
    } catch (error) {
      console.error("Failed to load analytics:", error);
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
            <p className="text-muted-foreground">Loading analytics...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  // Prepare chart data
  const studyTimeData = [
    { day: "Mon", minutes: 45 },
    { day: "Tue", minutes: 60 },
    { day: "Wed", minutes: 30 },
    { day: "Thu", minutes: 75 },
    { day: "Fri", minutes: 50 },
    { day: "Sat", minutes: 90 },
    { day: "Sun", minutes: 40 },
  ];

  const progressBySubject = [
    { subject: "Anatomy", completed: 12, total: 20 },
    { subject: "Physiology", completed: 8, total: 15 },
    { subject: "Biochemistry", completed: 15, total: 18 },
  ];

  const completionData = progressBySubject.map((item) => ({
    name: item.subject,
    value: Math.round((item.completed / item.total) * 100),
  }));

  const streakData = [
    { week: "Week 1", streak: 3 },
    { week: "Week 2", streak: 5 },
    { week: "Week 3", streak: 7 },
    { week: "Week 4", streak: stats?.current_streak || 0 },
  ];

  const totalStudyHours = Math.floor((stats?.total_study_minutes || 0) / 60);
  const avgDailyMinutes = Math.round((stats?.total_study_minutes || 0) / 30);

  // Check if user has premium access
  const isPremium = profile?.is_premium || false;

  if (!isPremium) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 py-8 px-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center gap-4 mb-8">
              <Button variant="ghost" onClick={() => router.push("/dashboard")}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
              <div>
                <h1 className="text-4xl font-bold">Analytics</h1>
                <p className="text-muted-foreground">Track your learning progress</p>
              </div>
            </div>
            
            <Card className="p-12 text-center">
              <div className="flex justify-center mb-6">
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
                  <Lock className="h-10 w-10 text-primary" />
                </div>
              </div>
              <h2 className="text-2xl font-bold mb-4">Premium Feature</h2>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Weekly analytics dashboard is only available for Premium users. Upgrade to track your progress with detailed charts and insights.
              </p>
              <Button onClick={() => router.push('/premium')} size="lg">
                Upgrade to Premium
              </Button>
            </Card>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 py-8 px-4">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => router.push("/dashboard")}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
              <div>
                <h1 className="text-4xl font-bold">Analytics</h1>
                <p className="text-muted-foreground">Track your learning progress</p>
              </div>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="p-6">
              <div className="flex items-center justify-between mb-2">
                <Award className="w-8 h-8 text-yellow-600" />
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <p className="text-3xl font-bold">{stats?.points || 0}</p>
              <p className="text-sm text-muted-foreground">Total Points</p>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-2">
                <BookOpen className="w-8 h-8 text-blue-600" />
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <p className="text-3xl font-bold">{stats?.slides_completed || 0}</p>
              <p className="text-sm text-muted-foreground">Slides Completed</p>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-2">
                <Clock className="w-8 h-8 text-purple-600" />
                <Activity className="w-5 h-5 text-blue-600" />
              </div>
              <p className="text-3xl font-bold">{totalStudyHours}h</p>
              <p className="text-sm text-muted-foreground">Total Study Time</p>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-2">
                <Target className="w-8 h-8 text-green-600" />
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <p className="text-3xl font-bold">{avgDailyMinutes}m</p>
              <p className="text-sm text-muted-foreground">Avg Daily Study</p>
            </Card>
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Study Time Chart */}
            <Card className="p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Weekly Study Time
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={studyTimeData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="minutes" fill="#8b5cf6" />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            {/* Streak Progress */}
            <Card className="p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Streak Progress
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={streakData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="week" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="streak" stroke="#f59e0b" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>

            {/* Subject Progress */}
            <Card className="p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <BookOpen className="w-5 h-5" />
                Progress by Subject
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={progressBySubject} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="subject" type="category" />
                  <Tooltip />
                  <Bar dataKey="completed" fill="#10b981" />
                  <Bar dataKey="total" fill="#e5e7eb" />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            {/* Completion Pie Chart */}
            <Card className="p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Target className="w-5 h-5" />
                Completion Rate
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={completionData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name}: ${value}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {completionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </div>

          {/* Recent Activity */}
          <Card className="p-6">
            <h3 className="text-lg font-bold mb-4">Recent Activity</h3>
            {progress.length === 0 ? (
              <div className="text-center py-12">
                <Activity className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">No activity yet. Start studying to see your progress!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {progress.slice(0, 5).map((item) => (
                  <div key={item.id} className="flex items-center justify-between p-4 bg-muted rounded-lg">
                    <div className="flex items-center gap-3">
                      <BookOpen className="w-5 h-5 text-primary" />
                      <div>
                        <p className="font-medium">{item.slide_title}</p>
                        <p className="text-sm text-muted-foreground">
                          Page {item.current_page} of {item.total_pages}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium">{item.progress_percentage}%</p>
                      <p className="text-xs text-muted-foreground">
                        {item.time_spent_minutes}m studied
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Insights */}
          <Card className="p-6 mt-6 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20">
            <h3 className="text-lg font-bold mb-4">📊 Insights</h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <TrendingUp className="w-5 h-5 text-green-600 mt-0.5" />
                <div>
                  <p className="font-medium">Great Progress!</p>
                  <p className="text-sm text-muted-foreground">
                    You've completed {stats?.slides_completed || 0} slides. Keep up the momentum!
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Target className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium">Study Consistency</p>
                  <p className="text-sm text-muted-foreground">
                    Your current streak is {stats?.current_streak || 0} days. Try to maintain it!
                  </p>
                </div>
              </div>
              {stats && stats.current_streak < stats.longest_streak && (
                <div className="flex items-start gap-3">
                  <Award className="w-5 h-5 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="font-medium">Beat Your Record</p>
                    <p className="text-sm text-muted-foreground">
                      Your longest streak was {stats.longest_streak} days. You can do it again!
                    </p>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </AuthGuard>
  );
}
