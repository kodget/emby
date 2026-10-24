"use client";

import { useState } from "react";
import { Mail, X } from "lucide-react";
import { ResendVerification } from "@/components/auth/resend-verification";

export default function EmailVerificationBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="bg-yellow-50 border-b border-yellow-200">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Mail className="w-5 h-5 text-yellow-600" />
            <div>
              <p className="text-sm font-medium text-yellow-800">
                Please verify your email address
              </p>
              <p className="text-xs text-yellow-700">
                Check your inbox and spam folder, or request a new link.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <ResendVerification onVerified={() => setVisible(false)} />
            <button
              type="button"
              aria-label="Dismiss email verification reminder"
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
