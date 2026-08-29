"use client";

/**
 * Join a Brain Battle by code.
 *
 * Battles used to be discoverable only through your own class group, so there was
 * nothing for a host to share. The host now gets a six-character code; this is where a
 * participant types it.
 *
 * The code is looked up before joining, so someone who mistypes gets told immediately
 * and sees what they are about to join rather than landing in the wrong battle.
 */

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Users } from "lucide-react";

import { Axo } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { battleApi, type BattleLookup } from "@/lib/api";
import { cn } from "@/lib/utils";

const CODE_LENGTH = 6;

export function JoinBattle({ className }: { className?: string }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [preview, setPreview] = useState<BattleLookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [joining, setJoining] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Look the code up as soon as it is complete, so a typo is caught before joining.
  useEffect(() => {
    if (code.length !== CODE_LENGTH) {
      setPreview(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setChecking(true);
    (async () => {
      try {
        const found = await battleApi.lookup(code);
        if (!cancelled) {
          setPreview(found);
          setError(null);
        }
      } catch (err: any) {
        if (!cancelled) {
          setPreview(null);
          setError(err?.response?.data?.detail ?? "Could not check that code.");
        }
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code]);

  const join = async () => {
    setJoining(true);
    setError(null);
    try {
      const joined = await battleApi.join(code);
      router.push(`/battles/${joined.battle_id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Could not join that battle.");
      setJoining(false);
    }
  };

  return (
    <section className={cn("card-3d p-5", className)}>
      <div className="flex items-start gap-3">
        <Icon3D name="battle" size="md" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-base font-semibold">Join a battle</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Enter the code the host shared with you.
          </p>
        </div>
      </div>

      <label htmlFor="battle-code" className="sr-only">
        Battle code
      </label>
      <input
        id="battle-code"
        ref={inputRef}
        value={code}
        onChange={(e) =>
          // Codes are uppercase and alphanumeric; normalise as they type so pasting a
          // lowercase or spaced code still works.
          setCode(
            e.target.value
              .toUpperCase()
              .replace(/[^A-Z0-9]/g, "")
              .slice(0, CODE_LENGTH),
          )
        }
        onKeyDown={(e) => {
          if (e.key === "Enter" && preview && !joining) void join();
        }}
        inputMode="text"
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        placeholder="ABC123"
        aria-describedby="battle-code-status"
        className="mt-4 h-14 w-full rounded-xl border border-input bg-background text-center font-mono text-2xl font-semibold uppercase tracking-[0.35em] outline-none transition-colors focus:border-primary"
      />

      <div id="battle-code-status" aria-live="polite" className="mt-3 min-h-[3rem]">
        {checking && (
          <p className="text-sm text-muted-foreground">Checking that code…</p>
        )}

        {error && (
          <p className="rounded-xl border border-weakness/30 bg-weakness/10 px-3.5 py-2.5 text-sm text-weakness">
            {error}
          </p>
        )}

        {preview && !error && (
          <div className="flex items-center gap-3 rounded-xl border border-mastery/30 bg-mastery/10 px-3.5 py-2.5">
            <Axo pose="celebrate" size="xs" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{preview.title}</p>
              <p className="text-xs text-muted-foreground">
                {preview.host_name} · {preview.total_questions} question
                {preview.total_questions === 1 ? "" : "s"} ·{" "}
                <span className="inline-flex items-center gap-1">
                  <Users className="size-3" />
                  {preview.participants}
                </span>
              </p>
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => void join()}
        disabled={!preview || joining || checking}
        className="press mt-1 h-12 w-full rounded-full bg-primary text-sm font-semibold text-primary-foreground disabled:opacity-50"
      >
        {joining ? "Joining…" : "Join battle"}
      </button>
    </section>
  );
}

/**
 * The host's view of their own code — large, selectable, and copyable, because it exists
 * to be read aloud or pasted into a group chat.
 */
export function BattleCode({ code, className }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be blocked; the code is selectable on screen either way.
    }
  };

  return (
    <div className={cn("rounded-2xl border border-primary/20 plinth p-5 text-center", className)}>
      <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
        Share this code
      </p>
      <p className="mt-1.5 select-all font-mono text-4xl font-bold tracking-[0.3em] text-primary">
        {code}
      </p>
      <button
        type="button"
        onClick={() => void copy()}
        className="press mt-3 rounded-full border border-border bg-card px-4 py-1.5 text-xs font-medium"
      >
        {copied ? "Copied" : "Copy code"}
      </button>
    </div>
  );
}
