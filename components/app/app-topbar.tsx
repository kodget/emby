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
import { GlobalSearch } from "@/components/app/global-search";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { Crown } from "lucide-react";
import { canUploadMaterials } from "@/lib/guards";
import { useState, useEffect } from "react";

export function AppTopbar() {
  const dispatch = useAppDispatch();
  const { isFree } = useFeatureAccess();
  const user = useAppSelector((s) => s.user);
  const [canUpload, setCanUpload] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setCanUpload(canUploadMaterials());
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 flex min-w-0 h-16 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-md sm:px-6">
        {/* Search */}
        <GlobalSearch />

        <div className="flex items-center gap-2">
          {/* Upgrade prompt for free users */}
          {mounted && isFree && (
            <Link
              href="/premium"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-primary to-primary/80 px-3 py-1.5 text-xs font-medium text-primary-foreground hover:from-primary/90 hover:to-primary/70 transition-colors"
            >
              <Crown className="size-3" aria-hidden="true" />
              <span>Upgrade to Premium</span>
            </Link>
          )}

          {/* AI tutor */}
          <Link
            href="/read"
            className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            <FontAwesomeIcon
              icon={faWandSparkles}
              className="size-3"
              aria-hidden="true"
            />
            <span className="hidden md:inline">Ask AI tutor</span>
          </Link>

          {/* Uploader — only visible to class heads and material uploaders */}
          {mounted && canUpload && (
            <motion.button
              type="button"
              whileTap={{ scale: 0.93 }}
              onClick={() => dispatch(openUploadModal({}))}
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
              aria-label="Upload slides"
            >
              <FontAwesomeIcon
                icon={faCloudArrowUp}
                className="size-3"
                aria-hidden="true"
              />
              <span className="hidden md:inline">Upload slides</span>
            </motion.button>
          )}

          {/* Streak pill */}
          {mounted && (
            <button
              type="button"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:border-primary/50 transition-colors"
              aria-label="Current streak"
            >
              <FontAwesomeIcon
                icon={faFire}
                className="size-3 text-orange-400"
                aria-hidden="true"
              />
              <span>{user.streak || 0}</span>
            </button>
          )}

          {/* Notifications */}
          <motion.button
            type="button"
            whileTap={{ scale: 0.9 }}
            className="flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Notifications"
          >
            <FontAwesomeIcon
              icon={faBell}
              className="size-4"
              aria-hidden="true"
            />
          </motion.button>

          {/* User Menu */}
          <UserMenu />
        </div>
      </header>

      <SlideUploadModal />
    </>
  );
}
