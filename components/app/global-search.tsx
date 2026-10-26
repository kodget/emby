"use client";
import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { SearchPanel } from '@/components/search/search-panel';
import { useContentSessionKey } from '@/store/hooks';

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const sessionKey = useContentSessionKey();
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); setOpen(value => !value);
      }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  return <>
    <button type="button" onClick={() => setOpen(true)} aria-label="Open global search"
      className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-xl border border-input bg-card px-3 text-left text-sm text-muted-foreground transition-colors hover:border-primary/50 sm:max-w-lg">
      <Search className="size-4 shrink-0" aria-hidden="true" />
      <span className="truncate sm:hidden">Search</span><span className="hidden truncate sm:block">Search your study library</span>
      <kbd className="ml-auto hidden shrink-0 rounded border border-border px-1.5 py-0.5 text-[11px] lg:block">Ctrl / ⌘ K</kbd>
    </button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[90dvh] gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <div className="border-b border-border px-5 py-4 pr-14">
          <DialogTitle className="text-lg">Find it in Emby</DialogTitle>
          <DialogDescription className="mt-1">Search your class materials and personal flashcards.</DialogDescription>
        </div>
        <SearchPanel key={sessionKey} compact onNavigate={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  </>;
}
