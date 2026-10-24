"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { useAppDispatch, useContentSessionKey } from "@/store/hooks";
import { updateUserProfile } from "@/store/user-slice";

/** Keep the shared header/sidebar current after navigation, activity and tab return. */
export function ProgressSync() {
  const pathname = usePathname();
  const sessionKey = useContentSessionKey();
  const dispatch = useAppDispatch();
  useEffect(() => {
    let controller: AbortController | undefined;
    let version = 0;
    const refresh = async () => {
      const current = ++version;
      controller?.abort();
      if (!sessionStorage.getItem("token")) return;
      const identity = sessionStorage.getItem("user");
      controller = new AbortController();
      try {
        const { data } = await api.get("/api/stats/me/", { signal: controller.signal });
        if (current !== version || identity !== sessionStorage.getItem("user")) return;
        if (Number.isInteger(data.current_streak) && data.current_streak >= 0) {
          dispatch(updateUserProfile({ streak: data.current_streak }));
        }
      } catch { /* Keep the last confirmed value; retry on navigation or tab return. */ }
    };
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    void refresh();
    window.addEventListener("emby:progress-changed", refresh);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      version++;
      controller?.abort();
      window.removeEventListener("emby:progress-changed", refresh);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [pathname, sessionKey, dispatch]);
  return null;
}
