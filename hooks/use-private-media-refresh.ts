"use client";

import { useCallback, useEffect, useRef } from "react";

/** Renew delivery links before their 15-minute lifetime, including after tab suspension. */
export function usePrivateMediaRefresh<T>(
  scope: string,
  load: () => Promise<T>,
  apply: (value: T) => void,
  denied: () => void,
) {
  const callbacks = useRef({ load, apply, denied });
  callbacks.current = { load, apply, denied };
  const state = useRef({ active: false, version: 0, pending: false, last: 0 });

  const refresh = useCallback(async () => {
    const current = state.current;
    if (!current.active || current.pending || Date.now() - current.last < 30000) return;
    current.pending = true;
    current.last = Date.now();
    const session = sessionStorage.getItem("user");
    const version = current.version;
    try {
      const value = await callbacks.current.load();
      if (current.active && current.version === version && session === sessionStorage.getItem("user")) {
        callbacks.current.apply(value);
      }
    } catch (error: any) {
      if (current.active && current.version === version && session === sessionStorage.getItem("user")
          && [401, 403, 404].includes(error?.response?.status)) {
        callbacks.current.denied();
      }
    } finally {
      if (current.version === version) current.pending = false;
    }
  }, []);

  useEffect(() => {
    const current = state.current;
    current.version++;
    current.active = true;
    current.pending = false;
    current.last = 0;
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    const timer = window.setInterval(() => void refresh(), 10 * 60 * 1000);
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    return () => {
      current.active = false;
      current.version++;
      window.clearInterval(timer);
      window.removeEventListener("focus", visible);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [scope, refresh]);

  return refresh;
}
