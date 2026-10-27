"use client";
import type { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAppSelector } from '@/store/hooks';

export default function ClassLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const canManage = useAppSelector(state => state.user.isVerifiedClassHead);
  const links = [['Overview', '/class'], ['Announcements', '/class/announcements'], ['Classmates', '/class/roster'], ['Exam dates', '/class/exams'], ...(canManage ? [['Curriculum', '/class/curriculum'], ['Class progress', '/class/analytics']] : [])];
  return <><nav aria-label="Class sections" className="overflow-x-auto border-b border-border bg-[#eeece5]/60 px-4 sm:px-6"><div className="mx-auto flex w-max min-w-full gap-5">{links.map(([label,href]) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined} className={`inline-flex min-h-12 shrink-0 items-center border-b-2 py-3 text-xs font-medium ${pathname === href ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{label}</Link>)}</div></nav>{children}</>;
}
