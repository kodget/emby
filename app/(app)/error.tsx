"use client";
import Link from 'next/link';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div role="alert" className="mx-auto my-12 max-w-lg rounded-2xl border border-border bg-card p-8 text-center">
    <AlertCircle className="mx-auto mb-4 size-8 text-primary" />
    <h1 className="text-2xl">This page couldn’t open</h1>
    <p className="mt-3 text-muted-foreground">Try loading it again. You can also return to your study dashboard.</p>
    <div className="mt-6 flex flex-wrap justify-center gap-3"><Button onClick={reset}>Try again</Button><Button asChild variant="outline"><Link href="/dashboard">Back to dashboard</Link></Button></div>
  </div>;
}
