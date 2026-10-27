import type { ReactNode } from 'react';
import { ArrowUpRight, Sparkles, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export function WorkspaceHeader({ eyebrow = 'Your study studio', title, description, icon: Icon = Sparkles,
  action, tone = 'violet', className }: { eyebrow?: string; title: ReactNode; description?: ReactNode;
  icon?: LucideIcon; action?: ReactNode; tone?: 'violet' | 'lime' | 'peach' | 'ink'; className?: string }) {
  return <header className={cn('workspace-header', className)} data-tone={tone}>
    <div aria-hidden="true" className="workspace-header-art"><div /><div /><span><Icon /></span></div>
    <div className="relative z-10"><p className="studio-eyebrow flex items-center gap-2 opacity-70"><span className="h-px w-5 bg-current" />{eyebrow}</p>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-5"><div className="min-w-0 flex-1"><h1 className="text-balance font-display text-[clamp(1.75rem,3vw,2.6rem)] font-medium leading-[1.12] tracking-[-.045em]">{title}</h1>{description && <p className="mt-3 max-w-xl text-pretty text-sm leading-6 opacity-75">{description}</p>}</div>{action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}</div>
    </div>
  </header>;
}

export function WorkspaceSectionTitle({ title, description, children }: { title: ReactNode; description?: ReactNode; children?: ReactNode }) {
  return <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><h2 className="font-display text-lg font-semibold tracking-tight">{title}</h2>{description && <p className="mt-1 text-xs leading-6 text-muted-foreground">{description}</p>}</div>{children}</div>;
}

export function WorkspaceEmpty({ title, description, icon: Icon = Sparkles, children }: { title: string; description: string; icon?: LucideIcon; children?: ReactNode }) {
  return <div className="workspace-empty"><div className="workspace-empty-icon" aria-hidden="true"><Icon className="size-7" /><ArrowUpRight className="absolute -right-2 -top-2 size-6 rounded-full bg-[#e1edb0] p-1 text-foreground" /></div><h2 className="mt-5 font-editorial text-3xl font-normal">{title}</h2><p className="mx-auto mt-3 max-w-sm text-sm leading-7 text-muted-foreground">{description}</p>{children && <div className="mt-5 flex flex-wrap justify-center gap-3">{children}</div>}</div>;
}
