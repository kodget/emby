import type { ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight, BookOpen, Check, Layers, Sparkles } from 'lucide-react';
import { LOGO_MARK } from '@/lib/brand';

export function AuthStudio({ children, mode = 'signin' }: { children: ReactNode; mode?: 'signin' | 'signup' | 'account' }) {
  return <div className="auth-studio">
    <aside className="auth-story">
      <Link href="/" className="flex w-fit items-center gap-3" aria-label="Emby home"><Image src={LOGO_MARK} width={38} height={38} alt="" priority /><span className="font-display text-2xl font-semibold tracking-tight">Emby.</span></Link>
      <div className="relative my-auto py-14">
        <p className="studio-eyebrow">A little clarity. Every day.</p>
        <h2 className="mt-6 font-editorial text-[clamp(2.7rem,4.5vw,4.7rem)] font-normal leading-[1.06] tracking-[-.055em]">{mode === 'signup' ? <>A fresh page.<br /><em className="text-primary">A place to grow.</em></> : <>Good to have<br /><em className="text-primary">you here.</em></>}</h2>
        <p className="mt-6 max-w-sm text-sm leading-7 text-muted-foreground">Bring your curiosity. We’ll keep your notes, questions and next small steps together.</p>
        <div className="auth-notebook mt-10">
          <div className="flex items-center justify-between border-b border-foreground/10 pb-4"><span className="studio-eyebrow">Your study desk</span><span className="size-2 rounded-full bg-primary" /></div>
          {[{ icon: BookOpen, title: 'Make a connection', body: 'Your class material, close at hand.' }, { icon: Sparkles, title: 'Follow a question', body: 'An AI tutor to explore it with.' }, { icon: Layers, title: 'Remember a little more', body: 'Practice that brings it back.' }].map(({ icon: Icon, title, body }, i) => <div key={title} className="flex items-center gap-4 border-b border-foreground/10 py-5 last:border-0"><span className="font-mono text-[10px] text-muted-foreground">0{i+1}</span><Icon className="size-5 shrink-0 text-primary" /><div><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs text-muted-foreground">{body}</p></div><Check className="ml-auto size-4 text-[#778747]" /></div>)}
        </div>
      </div>
      <Link href="/" className="flex w-fit min-h-11 items-center gap-3 text-xs text-muted-foreground">Explore Emby <ArrowUpRight className="size-4" /></Link>
    </aside>
    <main className="auth-form-area">
      <Link href="/" className="mb-7 flex items-center gap-2 lg:hidden" aria-label="Emby home"><Image src={LOGO_MARK} width={32} height={32} alt="" /><span className="font-display text-xl font-semibold">Emby.</span></Link>
      <div className="w-full max-w-md">{children}</div>
    </main>
  </div>;
}
