import type { ReactNode } from "react";

import { AppSidebar } from "@/components/app/app-sidebar";
import { AppTopbar } from "@/components/app/app-topbar";
import { MobileTabBar } from "@/components/app/mobile-tab-bar";
import { PageTransition } from "@/components/app/page-transition";
import { ProgressSync } from "@/components/app/progress-sync";
import { UploadProgressStrip } from "@/components/app/upload-progress-strip";

/**
 * The authenticated app shell.
 *
 * Navigation is split by device rather than shared: desktop gets the collapsible
 * sidebar, mobile gets a thumb-reachable bottom tab bar. They no longer share a
 * hamburger, which is what previously made the phone experience feel like a shrunken
 * website instead of an app.
 *
 * `pb-tabbar` keeps page content clear of the tab bar and the home indicator; the main
 * region is the only scroll container so the page never rubber-bands as a whole.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="studio-app flex min-h-[100dvh]">
      <a href="#main-content" className="sr-only z-[100] rounded-lg bg-primary px-4 py-3 text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Skip to content</a>
      <ProgressSync />
      <AppSidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <UploadProgressStrip />

        <main id="main-content" tabIndex={-1} className="scroll-pane min-w-0 flex-1 pb-tabbar md:pb-0">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>

      <MobileTabBar />
    </div>
  );
}
