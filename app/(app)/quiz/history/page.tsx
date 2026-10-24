"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

type Record = {
  id: string; exam_type: string; status: string; started_at?: string;
  historical_read_only?: boolean; theory_grading_pending?: boolean; overall_percentage?: number;
  configuration?: { assessment_title?: string };
  recorded_result?: { overall_percentage: number } | null;
};

export default function AssessmentHistoryPage() {
  const [records, setRecords] = useState<Record[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [failedPath, setFailedPath] = useState("/api/quiz-attempts/");
  const load = useCallback(async (path: string, replace = false) => {
    setLoading(true); setError(""); setFailedPath(path);
    try {
      const { data } = await api.get(path);
      const rows: Record[] = Array.isArray(data) ? data : data.results || [];
      setRecords(old => [...new Map((replace ? rows : [...old, ...rows]).map(row => [row.id, row])).values()]);
      setNext(Array.isArray(data) || data.next === path ? null : data.next);
    } catch { setError("Could not load assessment history. Your saved records are unchanged."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load("/api/quiz-attempts/", true); }, [load]);
  return <main className="mx-auto max-w-3xl space-y-4 p-6">
    <Link href="/quiz">Back to practice</Link>
    <h1 className="text-2xl font-bold">Assessment history</h1>
    <p className="text-sm text-muted-foreground">Resume an active attempt or revisit a saved result. Historical records without question versions are read-only.</p>
    {error && <div role="alert"><p>{error}</p><Button disabled={loading} onClick={() => load(failedPath)}>Retry history</Button></div>}
    {!loading && !error && !records.length && <p>No assessment attempts are available.</p>}
    {records.map(record => <article key={record.id} className="space-y-2 rounded border p-4">
      <h2 className="font-medium">{record.configuration?.assessment_title || `${record.exam_type} attempt`}</h2>
      {record.started_at && <p className="text-sm">{new Date(record.started_at).toLocaleString()}</p>}
      <p>{record.historical_read_only ? "Historical record — unverified" : record.status === "in_progress" ? "In progress"
        : record.theory_grading_pending ? "Submitted — written grading pending" : `Recorded result: ${Math.round(record.overall_percentage || 0)}%`}</p>
      <Link className="text-primary underline" href={`/quiz/attempt/${record.id}${record.historical_read_only || record.status !== "in_progress" ? "/results" : ""}`}>
        {record.historical_read_only ? "View historical record" : record.status === "in_progress" ? "Resume saved attempt" : "View saved result"}
      </Link>
    </article>)}
    {loading && <p role="status">Loading history…</p>}
    {next && !error && <Button disabled={loading} variant="outline" onClick={() => load(next)}>Load more attempts</Button>}
  </main>;
}
