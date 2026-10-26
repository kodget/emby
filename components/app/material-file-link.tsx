"use client";

import { useState, type ReactNode } from "react";
import { curriculumApi } from "@/lib/api";

/** Obtain a new authorized URL at click time, even on a long-open course page. */
export function MaterialFileLink({ id, className, children }: { id: string; className?: string; children: ReactNode }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <>
    <button id={`material-${id}`} type="button" className={`w-full text-left ${className ?? ''}`} disabled={busy} onClick={async () => {
      setBusy(true); setError("");
      const session = sessionStorage.getItem("user");
      const tab = window.open("about:blank", "_blank");
      if (tab) tab.opener = null;
      try {
        const material = await curriculumApi.getMaterial(id);
        if (session !== sessionStorage.getItem("user")) throw new Error("Account changed");
        const url = new URL(material.file_url);
        if (!["https:", "http:"].includes(url.protocol)) throw new Error("Invalid file URL");
        if (tab) tab.location.replace(url.href);
        else window.location.assign(url.href);
      } catch {
        tab?.close();
        setError("Could not open this file. Please try again.");
      } finally { setBusy(false); }
    }}>{children}</button>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </>;
}
