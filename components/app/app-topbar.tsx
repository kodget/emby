"use client";

import { UserMenu } from "@/components/auth/user-menu";
import Link from "next/link";
import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faBell,
  faFire,
  faWandSparkles,
  faCloudArrowUp,
} from "@fortawesome/free-solid-svg-icons";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { openUploadModal } from "@/store/uploads-slice";
import { SlideUploadModal } from "@/components/app/slide-upload-modal";
import { NotificationsDropdown } from "@/components/app/notifications-dropdown";
import { GlobalSearch } from "@/components/app/global-search";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { Crown } from "lucide-react";
import { canUploadMaterials } from "@/lib/guards";
import { useState, useEffect } from "react";
import { GlobalCreditBar } from "@/components/credits/global-credit-bar";
import { LibraryTutor } from "@/components/app/library-tutor";

export function AppTopbar() {
  const dispatch = useAppDispatch();
  const { isFree } = useFeatureAccess();
  const user = useAppSelector((s) => s.user);
  const [canUpload, setCanUpload] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [tutorOpen, setTutorOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
    setCanUpload(canUploadMaterials());
  }, []);

  return (
    <>
      <header className="studio-topbar sticky top-0 z-30 flex min-w-0 h-[72px] items-center gap-2 border-b border-border px-3 backdrop-blur-xl sm:px-6">
        {/* Search */}
        <GlobalSearch />

        <div className="flex items-center gap-2">
          {/* Upgrade prompt for free users */}
          {mounted && isFree && (
            <Link
              href="/premium"
              className="hidden 2xl:inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/5 transition-colors"
            >
              <Crown className="size-3" aria-hidden="true" />
              <span>Explore Premium</span>
            </Link>
          )}

          {/* AI tutor */}
          <button
            type="button"
            aria-label="Ask AI tutor"
            onClick={() => setTutorOpen(true)}
            className="inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors focus-visible:outline-2 focus-visible:outline-primary"
          >
            <FontAwesomeIcon
              icon={faWandSparkles}
              className="size-3"
              aria-hidden="true"
            />
            <span className="hidden xl:inline">Ask AI tutor</span>
          </button>

          {/* Uploader — only visible to class heads and material uploaders */}
          {mounted && canUpload && (
            <motion.button
              type="button"
              whileTap={{ scale: 0.93 }}
              onClick={() => dispatch(openUploadModal({}))}
              className="inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
              aria-label="Upload slides"
            >
              <FontAwesomeIcon
                icon={faCloudArrowUp}
                className="size-3"
                aria-hidden="true"
              />
              <span className="hidden xl:inline">Upload slides</span>
            </motion.button>
          )}

          {/* Streak pill */}
          {mounted && (
            <Link
              href="/analytics"
              className="hidden 2xl:inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:border-primary/50 transition-colors"
              aria-label="Current streak"
            >
              <FontAwesomeIcon
                icon={faFire}
                className="size-3 text-review"
                aria-hidden="true"
              />
              <span>{user.streak || 0}</span>
            </Link>
          )}

          {/* Credit Bar */}
          {mounted && <div className="hidden xl:block"><GlobalCreditBar /></div>}

          {/* Notifications */}
          {mounted && <NotificationsDropdown />}

          {/* User Menu */}
          <UserMenu />
        </div>
      </header>

      <SlideUploadModal />
      <LibraryTutor open={tutorOpen} onOpenChange={setTutorOpen} />
    </>
  );
}


