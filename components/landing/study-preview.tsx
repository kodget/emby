"use client";

import { useState } from 'react';
import { ArrowDown, ArrowRight, BookOpen, Check, CheckCheck, CornerDownLeft, FileText, Layers, RotateCcw, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StudyOrbit({ className = '' }: { className?: string }) {
  return <svg viewBox="0 0 400 300" fill="none" aria-hidden="true" className={className}>
    <g stroke="currentColor" strokeWidth="1.5"><ellipse cx="200" cy="150" rx="146" ry="57" transform="rotate(-30 200 150)" /><ellipse cx="200" cy="150" rx="146" ry="57" transform="rotate(30 200 150)" /><ellipse cx="200" cy="150" rx="146" ry="57" transform="rotate(90 200 150)" /></g>
    <circle cx="200" cy="150" r="26" fill="currentColor" /><g fill="var(--studio-lime)"><circle cx="77" cy="112" r="12" /><circle cx="274" cy="62" r="9" /><circle cx="283" cy="230" r="14" /></g><path d="M193 150h14m-7-7v14" stroke="white" strokeWidth="2" strokeLinecap="round" />
  </svg>;
}

const modes = [{ key: 'read', label: 'Read', icon: BookOpen }, { key: 'ask', label: 'Ask', icon: Sparkles }, { key: 'recall', label: 'Recall', icon: Layers }] as const;
export function HeroStudyCanvas() {
  const [mode, setMode] = useState<'read' | 'ask' | 'recall'>('read');
  return <div className="hero-canvas" aria-label="Interactive example of the Emby workspace">
    <div className="hero-note"><span className="font-editorial text-2xl italic">your next lightbulb moment</span><ArrowDown className="mt-2 size-6 rotate-[-20deg]" /></div>
    <div className="hero-paper-back" aria-hidden="true" />
    <div className="hero-paper">
      <div className="flex items-center justify-between border-b border-foreground/10 px-5 py-4"><div className="flex items-center gap-2"><span className="size-2 rounded-full bg-primary" /><span className="text-xs font-semibold">The study desk</span></div><span className="studio-example">Interactive preview</span></div>
      <div role="tablist" aria-label="Explore the study workspace" className="mx-5 mt-5 grid grid-cols-3 rounded-xl bg-[#f1efeb] p-1">{modes.map(({ key, label, icon: Icon }) => <button key={key} id={`preview-tab-${key}`} type="button" role="tab" aria-selected={mode === key} aria-controls={`preview-panel-${key}`} onClick={() => setMode(key)} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = modes[(modes.findIndex(item => item.key === key) + (event.key === 'ArrowRight' ? 1 : 2)) % 3].key; setMode(next); document.getElementById(`preview-tab-${next}`)?.focus(); } }} tabIndex={mode === key ? 0 : -1} className={cn('flex min-h-11 items-center justify-center gap-2 rounded-lg text-xs font-semibold transition-colors', mode === key ? 'bg-white text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground')}><Icon className="size-4" />{label}</button>)}</div>
      <div role="tabpanel" id={`preview-panel-${mode}`} aria-labelledby={`preview-tab-${mode}`} className="min-h-[320px] p-5 sm:p-6">
        {mode === 'read' && <><div className="flex items-center gap-2 text-[11px] text-muted-foreground"><FileText className="size-3.5" />Anatomy <span>/</span> Upper limb <span className="ml-auto">01 / 12</span></div><h3 className="mt-5 text-xl">Make the connections.</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">Trace the path. Name the structure.<br /><mark className="bg-[#e3f0ab] px-1 text-foreground">Explain how it all fits together.</mark></p><StudyOrbit className="mx-auto -my-2 h-[160px] w-full text-primary" /><div className="flex items-center gap-2 border-t border-foreground/10 pt-3 text-xs text-muted-foreground"><span className="flex size-6 items-center justify-center rounded-full bg-primary/10"><Check className="size-3 text-primary" /></span>Your lecture. Your pace.</div></>}
        {mode === 'ask' && <><p className="studio-eyebrow">A little help, right beside you</p><div className="ml-7 mt-5 rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm text-white">How should I break down this slide?</div><div className="mr-4 mt-4 rounded-2xl rounded-tl-sm border border-border bg-[#f8f7f3] p-4"><Sparkles className="mb-3 size-5 text-primary" /><p className="text-sm leading-relaxed">Start with the labelled structures. Describe what each does, then explain how they connect.</p><p className="mt-3 text-sm leading-relaxed">Now hide the labels and test what you remember.</p></div><p className="mt-4 text-[11px] text-muted-foreground">Sample conversation · Your tutor uses your uploaded material.</p></>}
        {mode === 'recall' && <RecallCard compact />}
      </div>
    </div>
    <div className="hero-sticker"><span className="flex size-9 items-center justify-center rounded-full bg-foreground text-white"><CheckCheck className="size-4" /></span><div><span className="block text-xs font-semibold">Less scattered. More connected.</span><span className="text-[11px]">Slides, explanations & practice.</span></div></div>
  </div>;
}

export function RecallCard({ compact = false }: { compact?: boolean }) {
  const [flipped, setFlipped] = useState(false);
  return <div className={cn('flex flex-col', compact ? 'min-h-[272px]' : 'min-h-[310px]')}>
    <div className="flex items-center justify-between text-[11px] font-medium uppercase tracking-[.14em]"><span>Study strategy</span><span className="studio-example">Sample card</span></div>
    <button type="button" aria-label={flipped ? 'Show flashcard question' : 'Reveal flashcard answer'} aria-pressed={flipped} onClick={() => setFlipped(value => !value)} className={cn('group my-5 flex flex-1 flex-col items-center justify-center rounded-2xl border border-current/15 p-6 text-center transition-colors', compact ? 'bg-[#ece8ff]' : 'bg-white/40 hover:bg-white/65')}>
      <span className="text-[10px] uppercase tracking-[.2em] opacity-65">{flipped ? 'The answer' : 'A quick check-in'}</span>
      <span className={cn('my-4 font-editorial leading-tight', compact ? 'text-3xl' : 'text-4xl')}>{flipped ? 'Retrieving an answer before looking at your notes.' : 'What is active recall?'}</span>
      <span className="inline-flex items-center gap-2 text-xs"><RotateCcw className="size-3.5" />{flipped ? 'Back to question' : 'Tap to turn it over'}</span>
    </button>
    <p className="text-xs opacity-70">Small questions. Stronger recall.</p>
  </div>;
}

const prompts = [
  { label: 'Break it down', answer: 'Take one concept at a time. Identify the key terms, describe the relationships, then explain the slide in your own words.' },
  { label: 'Help me revise', answer: 'Read the slide once, close it, and write down the main ideas you remember. Reopen it to find the gaps and turn those gaps into flashcards.' },
  { label: 'Quiz me', answer: 'Try this: what is the central idea of this slide, and how would you explain it to a classmate without using your notes?' },
];
export function TutorPreview() {
  const [prompt, setPrompt] = useState(0);
  return <div className="overflow-hidden rounded-[24px] border border-white/15 bg-white text-foreground shadow-2xl">
    <div className="flex items-center gap-3 border-b border-border p-5"><span className="flex size-10 items-center justify-center rounded-xl bg-primary/10"><Sparkles className="size-5 text-primary" /></span><div><p className="text-sm font-semibold">Your AI tutor</p><p className="text-[11px] text-muted-foreground">A conversation, in context.</p></div><span className="studio-example ml-auto">Preview</span></div>
    <div className="p-5 sm:p-7"><div className="ml-8 rounded-2xl rounded-br-sm bg-[#eeeafd] px-4 py-3 text-sm">{prompts[prompt].label}.</div><div className="mt-6 flex gap-3"><Sparkles className="mt-1 size-4 shrink-0 text-primary" /><p className="min-h-[120px] text-sm leading-7" aria-live="polite">{prompts[prompt].answer}</p></div><div className="mt-3 flex flex-wrap gap-2" aria-label="Try a sample tutor prompt">{prompts.map((item, index) => <button type="button" key={item.label} onClick={() => setPrompt(index)} aria-pressed={index === prompt} className={cn('min-h-11 rounded-full border px-3 text-xs transition-colors', index === prompt ? 'border-primary bg-primary text-white' : 'border-border hover:border-primary')}>{item.label}<CornerDownLeft className="ml-2 inline size-3" /></button>)}</div><p className="mt-5 border-t border-border pt-4 text-[11px] leading-5 text-muted-foreground">These are sample replies. In your workspace, the tutor works with your uploaded slides.</p></div>
  </div>;
}

export function PracticePreview() {
  const [answer, setAnswer] = useState<number | null>(null);
  const options = ['Rereading the same paragraph', 'Recalling an answer before checking notes', 'Highlighting every sentence'];
  return <div className="rounded-[24px] border border-foreground/10 bg-white p-5 sm:p-7">
    <div className="flex items-center justify-between"><span className="studio-eyebrow">A tiny practice round</span><span className="studio-example">Sample MCQ</span></div>
    <h3 className="mt-6 max-w-sm font-editorial text-3xl leading-tight">Which approach is active recall?</h3>
    <div className="mt-6 space-y-2">{options.map((text, index) => <button type="button" key={text} onClick={() => setAnswer(index)} aria-pressed={answer === index} className={cn('flex min-h-14 w-full items-center gap-3 rounded-xl border p-3 text-left text-sm transition-colors', answer === index ? index === 1 ? 'border-[#638327] bg-[#edf5d8]' : 'border-[#ba694b] bg-[#fff0e8]' : 'border-border hover:border-primary hover:bg-primary/5')}><span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-foreground/5 text-xs font-semibold">{String.fromCharCode(65+index)}</span>{text}{answer === index && index === 1 && <Check className="ml-auto size-4 shrink-0" />}</button>)}</div>
    <div className="mt-5 min-h-14 text-sm leading-relaxed" aria-live="polite">{answer === null ? <p className="text-muted-foreground">Pick an answer. See what happens.</p> : <><p className="font-semibold">{answer === 1 ? 'That’s the idea.' : 'A useful habit—but try another option.'}</p><p className="mt-1 text-xs text-muted-foreground">Active recall asks you to retrieve information from memory.</p></>}</div>
    {answer !== null && <button type="button" className="inline-flex min-h-11 items-center gap-2 text-xs font-medium text-primary" onClick={() => setAnswer(null)}>Try again <ArrowRight className="size-3.5" /></button>}
  </div>;
}
