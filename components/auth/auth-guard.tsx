"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { canAccessApp, getRedirectPath, isAuthenticated } from "@/lib/guards";

type AuthGuardProps = {
  children: React.ReactNode;
  requireAuth?: boolean;
  requireOnboarding?: boolean;
  requireVerification?: boolean;
};

export default function AuthGuard({
  children,
  requireAuth = true,
  requireOnboarding = true,
  requireVerification = true,
}: AuthGuardProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = () => {
    if (requireAuth && !isAuthenticated()) {
      router.push("/signin");
      return;
    }

    if (requireOnboarding || requireVerification) {
      if (!canAccessApp()) {
        const redirectPath = getRedirectPath();
        router.push(redirectPath);
        return;
      }
    }

    setAuthorized(true);
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!authorized) {
    return null;
  }

  return <>{children}</>;
}
