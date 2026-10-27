"use client";
import { WorkspaceHeader, WorkspaceEmpty } from "@/components/ui/workspace-header";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { CalendarDays, ArrowLeft, Pencil, Plus, Trash2 } from 'lucide-react';
import { authApi, classApi, type ExamCountdown, type UserProfile } from '@/lib/api';
import AuthGuard from '@/components/auth/auth-guard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';

export default function ExamCountdownsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [exams, setExams] = useState<ExamCountdown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [saving, setSaving] = useState(false);
  const canManage = profile?.class_role === 'class_head' && profile.class_head_verified;
  async function load() {
    setLoading(true); setError('');
    try { const [user, rows] = await Promise.all([authApi.getProfile(), classApi.getExamCountdowns()]); setProfile(user); setExams(rows); }
    catch { setError('Your exam dates could not be loaded. Please try again.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!loading && window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'center' });
  }, [loading]);
  function edit(exam?: ExamCountdown) { setEditing(exam?.id ?? null); setTitle(exam?.title ?? ''); setDate(exam?.exam_date ?? ''); setFormError(''); setOpen(true); }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setFormError('');
    try {
      const values = { title: title.trim(), exam_date: date };
      if (editing) await classApi.updateExamCountdown(editing, values); else await classApi.createExamCountdown(values);
      setOpen(false); await load();
    } catch { setFormError('This exam date was not saved. Please try again.'); }
    finally { setSaving(false); }
  }
  async function remove(exam: ExamCountdown) {
    if (!window.confirm(`Delete “${exam.title}” from your class exam dates?`)) return;
    try { await classApi.deleteExamCountdown(exam.id); await load(); }
    catch { setError('This exam date could not be deleted. Please try again.'); }
  }
  return <AuthGuard><div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
    <Link href="/class" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-primary"><ArrowLeft className="size-4" />My class</Link>
    <WorkspaceHeader tone="peach" eyebrow="Something to work towards" title="Exam countdowns" description="See what’s coming up and give your revision a clear target." action={canManage && <Button onClick={() => edit()}><Plus className="size-4" />Add exam</Button>} />
    {error && <div role="alert" className="rounded-xl border border-destructive/25 bg-card p-5"><p>{error}</p><Button variant="outline" onClick={load} className="mt-3">Try again</Button></div>}
    {loading ? <p role="status" className="py-12 text-center text-muted-foreground">Loading exam dates…</p> : !error && exams.length === 0 ? <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center"><CalendarDays className="mx-auto mb-4 size-8 text-primary" /><h2 className="text-xl">No exam dates yet</h2><p className="mt-2 text-sm text-muted-foreground">{canManage ? 'Add the next exam so everyone can plan their revision.' : 'Exam dates will appear here when your class head adds them.'}</p></div> : <div className="space-y-4">{exams.map(exam => <article id={`exam-${exam.id}`} key={exam.id} className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-card p-6">
      <div className="min-w-0"><h2 className="break-words text-lg">{exam.title}</h2><p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground"><CalendarDays className="size-4" />{new Date(exam.exam_date + 'T12:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}</p></div>
      <div className="flex items-center gap-2"><span className="rounded-lg bg-primary/7 px-3 py-2 text-sm font-medium text-primary">{exam.days_remaining < 0 ? 'Past exam' : exam.days_remaining === 0 ? 'Today' : `${exam.days_remaining} days to go`}</span>{canManage && <><Button size="icon" variant="ghost" aria-label={`Edit ${exam.title}`} onClick={() => edit(exam)}><Pencil className="size-4" /></Button><Button size="icon" variant="ghost" aria-label={`Delete ${exam.title}`} onClick={() => remove(exam)}><Trash2 className="size-4" /></Button></>}</div>
    </article>)}</div>}
    <Dialog open={open} onOpenChange={value => { if (!saving) setOpen(value); }}><DialogContent><DialogTitle>{editing ? 'Edit exam date' : 'Add an exam date'}</DialogTitle><DialogDescription>This date will be visible to your class.</DialogDescription><form onSubmit={save} className="space-y-4"><div className="space-y-2"><Label htmlFor="exam-title">Exam title</Label><Input id="exam-title" required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></div><div className="space-y-2"><Label htmlFor="exam-date">Exam date</Label><Input id="exam-date" type="date" required value={date} onChange={e => setDate(e.target.value)} /></div>{formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<div className="flex gap-3"><Button type="submit" disabled={saving || !title.trim()}>{saving ? 'Saving…' : 'Save exam'}</Button><Button type="button" variant="outline" disabled={saving} onClick={() => setOpen(false)}>Cancel</Button></div></form></DialogContent></Dialog>
  </div></AuthGuard>;
}
