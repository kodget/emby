import type { ReactNode } from "react";

import { AppSidebar } from "@/components/app/app-sidebar";
import { AppTopbar } from "@/components/app/app-topbar";
import { MobileTabBar } from "@/components/app/mobile-tab-bar";
import { PageTransition } from "@/components/app/page-transition";

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
    <div className="flex min-h-[100dvh] bg-background">
      <AppSidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />

        <main className="scroll-pane flex-1 pb-tabbar md:pb-0">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>

      <MobileTabBar />
    </div>
  );
}
