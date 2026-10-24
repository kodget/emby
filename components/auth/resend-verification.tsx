"use client";

import { useEffect, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { authApi } from "@/lib/api";

export function ResendVerification({ onVerified }: { onVerified?: () => void }) {
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [hasError, setHasError] = useState(false);
  const [retryUntil, setRetryUntil] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const inFlight = useRef(false);

  useEffect(() => {
    if (!retryUntil) return;
    const update = () => setRemaining(Math.max(0, Math.ceil((retryUntil - Date.now()) / 1000)));
    update();
    const interval = window.setInterval(update, 1000);
    return () => window.clearInterval(interval);
  }, [retryUntil]);

  const startCooldown = (seconds: unknown) => {
    const value = Number(seconds);
    if (Number.isFinite(value) && value > 0) {
      setRemaining(Math.ceil(value));
      setRetryUntil(Date.now() + value * 1000);
    }
  };

  const resend = async () => {
    if (inFlight.current || remaining > 0) return;
    inFlight.current = true;
    setSending(true);
    setMessage("");
    setHasError(false);
    try {
      const result = await authApi.resendVerification();
      startCooldown(result.retry_after);
      if (result.email_status === "unavailable" || result.email_status === "failed") {
        setHasError(true);
      }
      setMessage(result.message);
      if (result.email_status === "already_verified") onVerified?.();
    } catch (error: unknown) {
      setHasError(true);
      if (isAxiosError(error)) {
        startCooldown(error.response?.data?.retry_after ?? error.response?.headers["retry-after"]);
        const serverMessage = error.response?.data?.error;
        setMessage(typeof serverMessage === "string"
          ? serverMessage
          : error.response?.status === 401 || error.response?.status === 403
            ? "Please sign in again to request a verification email."
            : error.response
              ? "The email could not be sent. Please try again later."
              : "Unable to reach Emby. Check your connection and try again.");
      } else {
        setMessage("The email could not be sent. Please try again later.");
      }
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={resend}
        disabled={sending || remaining > 0}
        className="text-sm font-medium underline underline-offset-4 disabled:opacity-50"
      >
        {sending ? "Sending..." : remaining > 0 ? `Resend in ${remaining}s` : "Resend verification email"}
      </button>
      {message && (
        <p role={hasError ? "alert" : "status"} className={`text-sm ${hasError ? "text-destructive" : "text-green-700 dark:text-green-400"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
