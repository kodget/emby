"use client";
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { BarChart3, BookOpen, CalendarDays, Coins, Crown, FileText, GraduationCap, Home, Layers, ListChecks, Menu, Microscope, Search, Settings, Sparkles, Trophy, Users } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { useAppSelector } from '@/store/hooks';
import { cn } from '@/lib/utils';

const tabs = [
  { label: 'Home', href: '/dashboard', icon: Home, match: /^\/dashboard/ },
  { label: 'Learn', href: '/courses', icon: BookOpen, match: /^\/(courses|read|decks)/ },
  { label: 'Practice', href: '/quiz', icon: ListChecks, match: /^\/(quiz|steeplechase|histology)/ },
  { label: 'Flashcards', href: '/flashcards', icon: Layers, match: /^\/flashcards/ },
];
const links = [
  { label: 'Search', href: '/search', icon: Search }, { label: 'My class', href: '/class', icon: Users },
  { label: 'Documents', href: '/decks', icon: FileText }, { label: 'Study plan', href: '/study-plan', icon: CalendarDays },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 }, { label: 'Brain Battle', href: '/battles', icon: Sparkles },
  { label: 'Steeplechase', href: '/steeplechase', icon: Trophy }, { label: 'Histology', href: '/histology', icon: Microscope },
  { label: 'Community', href: '/community', icon: Users }, { label: 'Achievements', href: '/achievements', icon: Trophy },
  { label: 'Profile', href: '/profile', icon: GraduationCap }, { label: 'AI credits', href: '/credits', icon: Coins },
  { label: 'Premium', href: '/premium', icon: Crown }, { label: 'Settings', href: '/settings', icon: Settings },
];
export function MobileTabBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const moreButton = useRef<HTMLButtonElement>(null);
  const head = useAppSelector(state => state.user.isVerifiedClassHead);
  useEffect(() => setOpen(false), [pathname]);
  return <>
    <nav aria-label="Primary" className="studio-mobile-nav fixed inset-x-0 bottom-0 z-40 border-t border-border pb-safe backdrop-blur-xl md:hidden"><ul className="grid grid-cols-5 px-2 py-1">
      {tabs.map(({ label, href, icon: Icon, match }) => <li key={href}><Link href={href} aria-current={match.test(pathname) ? 'page' : undefined} className={cn('flex min-h-16 flex-col items-center justify-center gap-1.5 px-1 text-[10px] font-medium', match.test(pathname) ? 'bg-primary/5 text-primary' : 'text-muted-foreground')}><Icon className="size-5" aria-hidden="true" />{label}</Link></li>)}
      <li><button ref={moreButton} type="button" onClick={() => setOpen(true)} aria-expanded={open} aria-haspopup="dialog" className="flex min-h-16 w-full flex-col items-center justify-center gap-1.5 text-[10px] font-medium text-muted-foreground"><Menu className="size-5" aria-hidden="true" />More</button></li>
    </ul></nav>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent onCloseAutoFocus={event => { event.preventDefault(); moreButton.current?.focus(); }} className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
      <DialogTitle>Your workspace</DialogTitle><DialogDescription>Find your tools, class and account.</DialogDescription>
      <div className="grid grid-cols-3 gap-2">{[...links, ...(head ? [{ label: 'Manage class', href: '/class/curriculum', icon: GraduationCap }] : [])].map(({ label, href, icon: Icon }) => <Link href={href} key={href} onClick={() => setOpen(false)} className={cn('flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border px-2 py-3 text-center text-xs', pathname === href ? 'border-primary/30 bg-primary/5 text-primary' : 'border-border bg-muted/30 hover:bg-accent')}><Icon className="size-5" aria-hidden="true" />{label}</Link>)}</div>
    </DialogContent></Dialog>
  </>;
}
