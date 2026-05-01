"use client";

import { useState } from "react";
import { Mail, X } from "lucide-react";
import { authApi } from "@/lib/api";

export default function EmailVerificationBanner() {
  const [visible, setVisible] = useState(true);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleResend = async () => {
    setSending(true);
    try {
      await authApi.resendVerification();
      setSent(true);
      setTimeout(() => setSent(false), 5000);
    } catch (error) {
      console.error("Failed to resend verification:", error);
      alert("Failed to resend verification email");
    } finally {
      setSending(false);
    }
  };

  if (!visible) return null;

  return (
    <div className="bg-yellow-50 border-b border-yellow-200">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Mail className="w-5 h-5 text-yellow-600" />
            <div>
              <p className="text-sm font-medium text-yellow-800">
                Please verify your email address
              </p>
              <p className="text-xs text-yellow-700">
                Check your inbox for a verification link
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {sent ? (
              <span className="text-sm text-green-600 font-medium">Email sent!</span>
            ) : (
              <button
                onClick={handleResend}
                disabled={sending}
                className="text-sm font-medium text-yellow-800 hover:text-yellow-900 underline disabled:opacity-50"
              >
                {sending ? "Sending..." : "Resend email"}
              </button>
            )}
            <button
              onClick={() => setVisible(false)}
              className="text-yellow-600 hover:text-yellow-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
