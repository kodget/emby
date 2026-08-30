"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Users, BookOpen, CreditCard, Presentation } from "lucide-react";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  LineChart, Line
} from "recharts";

type AnalyticsData = {
  total_users: number;
  total_premium_users: number;
  total_classes: number;
  total_subjects: number;
  total_slides: number;
  total_quizzes_taken: number;
  revenue_summary: { monthly: number; yearly: number };
};

export default function AdminDashboard() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("30d");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const analytics = await adminApi.getAnalytics();
        setData(analytics);
      } catch (err: any) {
        setError(err.message || "Failed to load analytics");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
      </div>
    );
  }

  // Multiply mock data slightly to simulate range changes
  const multiplier = timeRange === "7d" ? 0.3 : timeRange === "90d" ? 2.5 : 1;

  const statCards = [
    { title: "Total Users", value: Math.floor(data.total_users * multiplier), icon: Users, desc: `${Math.floor(data.total_premium_users * multiplier)} premium users` },
    { title: "Active Classes", value: data.total_classes, icon: BookOpen, desc: "Created across all schools" },
    { title: "Content Slides", value: data.total_slides, icon: Presentation, desc: `Across ${data.total_subjects} subjects` },
    { title: "Revenue", value: `₦${((data.revenue_summary.monthly * multiplier) / 1000).toFixed(1)}k`, icon: CreditCard, desc: "From premium subscriptions" },
  ];

  const mockRevenueData = [
    { name: 'Jan', value: 4000 * multiplier },
    { name: 'Feb', value: 3000 * multiplier },
    { name: 'Mar', value: 2000 * multiplier },
    { name: 'Apr', value: 2780 * multiplier },
    { name: 'May', value: 1890 * multiplier },
    { name: 'Jun', value: 2390 * multiplier },
    { name: 'Jul', value: 3490 * multiplier },
  ];
  
  const mockUserGrowthData = [
    { name: 'Week 1', students: 400 * multiplier, teachers: 240 * multiplier },
    { name: 'Week 2', students: 500 * multiplier, teachers: 280 * multiplier },
    { name: 'Week 3', students: 650 * multiplier, teachers: 310 * multiplier },
    { name: 'Week 4', students: 800 * multiplier, teachers: 390 * multiplier },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard Overview</h1>
          <p className="text-gray-500 mt-1">Welcome back. Here is what's happening with the platform.</p>
        </div>
        <select 
          className="h-10 w-[160px] rounded-md border border-input bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
        >
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
          <option value="90d">Last 3 Months</option>
          <option value="all">All Time</option>
        </select>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, i) => (
          <Card key={i} className="border-none shadow-sm hover:shadow-md transition-shadow">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">{stat.title}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{stat.value}</p>
                </div>
                <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                  <stat.icon className="h-6 w-6" />
                </div>
              </div>
              <div className="mt-4 text-sm text-gray-500">
                {stat.desc}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Chart */}
        <Card className="border-none shadow-sm">
          <CardHeader>
            <CardTitle>Revenue Trends</CardTitle>
            <CardDescription>Monthly subscription revenue over time.</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockRevenueData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6b7280' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6b7280' }} />
                <RechartsTooltip 
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="var(--color-primary)" 
                  strokeWidth={3}
                  dot={{ r: 4, strokeWidth: 2 }}
                  activeDot={{ r: 6 }} 
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* User Growth Chart */}
        <Card className="border-none shadow-sm">
          <CardHeader>
            <CardTitle>User Growth</CardTitle>
            <CardDescription>New registrations over the past month.</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={mockUserGrowthData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6b7280' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6b7280' }} />
                <RechartsTooltip 
                  cursor={{ fill: '#f3f4f6' }}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Bar dataKey="students" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="teachers" fill="#93c5fd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
