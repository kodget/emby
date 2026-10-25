"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type PublicProfile = { full_name: string; school_name: string; set_name: string; current_streak: number; points: number | null };
export default function PublicProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true); setProfile(null); setError("");
    api.get(`/api/stats/public/${encodeURIComponent(id)}/`).then(({ data }) => { if (active) setProfile(data); })
      .catch((err) => { if (active) setError(err?.response?.status === 404 ? "This profile is private or unavailable in your class." : "The profile could not load. Please try again."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  return <AuthGuard><main className="mx-auto max-w-xl space-y-6 p-6 py-12"><Link href="/class/roster" className="text-primary underline">Back to classmates</Link>
    {loading ? <p role="status">Loading profile…</p> : error ? <p role="alert">{error}</p> : profile && <Card><CardHeader><CardTitle>{profile.full_name}</CardTitle></CardHeader><CardContent className="space-y-3"><p>{profile.school_name} · {profile.set_name}</p><p>{profile.current_streak} day study streak</p>{profile.points !== null && <p>{profile.points} points</p>}</CardContent></Card>}
  </main></AuthGuard>;
}
