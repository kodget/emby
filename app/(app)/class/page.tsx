"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authApi, classApi, ClassGroup, UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { canAccessAdmin } from "@/lib/guards";
import { BookOpen, Calendar, ClipboardList, Megaphone, Users, BarChart3, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ClassPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [classData, setClassData] = useState<ClassGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const account = await authApi.getProfile();
      setProfile(account);
      setClassData(account.class_group ? await classApi.getMyClass() : null);
    } catch {
      setError("Your class could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void loadData(); }, [loadData]);

  const canManage = canAccessAdmin(profile) || (profile?.class_role === "class_head" && profile.class_head_verified);
  const links = [
    { href: "/class/announcements", title: "Announcements", description: "Read updates from your class heads.", icon: Megaphone },
    { href: "/class/roster", title: "Class roster", description: "Find classmates and class heads.", icon: Users },
    { href: "/courses", title: "Class subjects", description: "Open your subjects, modules and uploaded slides.", icon: BookOpen },
    { href: "/class/exams", title: "Exam countdowns", description: "See upcoming exam dates and time remaining.", icon: Calendar },
    { href: "/quiz/assessments", title: "Assessments", description: "Open formal class assessments.", icon: ClipboardList },
    ...(canManage ? [
      { href: "/class/curriculum", title: "Manage curriculum", description: "Organize subjects, modules and class materials.", icon: BookOpen },
      { href: "/class/analytics", title: "Class analytics", description: "Review class participation and progress.", icon: BarChart3 },
    ] : []),
  ];

  return (
    <AuthGuard>
      <main className="mx-auto max-w-5xl space-y-6 p-4 py-8 sm:p-8">
        <header><h1 className="text-3xl font-bold">My class</h1><p className="mt-2 text-muted-foreground">Your class updates, classmates and learning materials.</p></header>
        {loading ? <p role="status" className="flex items-center gap-2"><Loader2 className="h-5 w-5 animate-spin" />Loading your class…</p> : error ? (
          <Card><CardContent className="space-y-4 pt-6"><p role="alert">{error}</p><Button onClick={loadData}>Try again</Button></CardContent></Card>
        ) : !classData ? (
          <Card><CardHeader><CardTitle>Join your class</CardTitle><CardDescription>Use the class code from your class head to see your class materials and announcements.</CardDescription></CardHeader>
            <CardContent><Button asChild><Link href="/onboarding">Set up class membership</Link></Button></CardContent>
          </Card>
        ) : (
          <>
            <Card><CardHeader><CardTitle>{classData.set_name}</CardTitle><CardDescription>{classData.school_name}</CardDescription></CardHeader>
              <CardContent className="space-y-2"><p>{classData.member_count} class members</p>
                <p>Class heads: {classData.class_heads.map(head => head.name || "Class head").join(", ") || "Awaiting approval"}</p>
                {classData.code && <p>Class code: <strong className="font-mono">{classData.code}</strong></p>}
              </CardContent>
            </Card>
            <div className="grid gap-4 sm:grid-cols-2">
              {links.map(({ href, title, description, icon: Icon }) => (
                <Link href={href} key={href} className="rounded-xl border bg-card p-5 transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-primary">
                  <Icon className="mb-3 h-6 w-6 text-primary" aria-hidden="true" /><h2 className="text-lg font-semibold">{title}</h2><p className="mt-1 text-sm text-muted-foreground">{description}</p>
                </Link>
              ))}
            </div>
          </>
        )}
      </main>
    </AuthGuard>
  );
}
