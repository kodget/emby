"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { isAxiosError } from "axios";
import { CheckCircle2, Loader2, Mail } from "lucide-react";
import { authApi } from "@/lib/api";
import { getRedirectPath, getStoredProfile, isAuthenticated } from "@/lib/guards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ResendVerification } from "@/components/auth/resend-verification";

function VerificationContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [accountEmail, setAccountEmail] = useState("");
  const [destination, setDestination] = useState("/signin");
  const [canRetry, setCanRetry] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // Strict Mode replays effects. Reuse the pending request so a single-use
  // verification link is not consumed twice by one page visit.
  const pending = useRef<{ token: string; attempt: number; request: Promise<{ message: string }> } | null>(null);

  useEffect(() => {
    let active = true;
    setSignedIn(isAuthenticated());
    setAccountEmail(getStoredProfile()?.email || "");
    setDestination(getRedirectPath());
    setCanRetry(false);
    if (!token) {
      setState("error");
      setMessage("This link is missing its verification token. Open the full link from your email, or request a new one.");
      return;
    }
    setState("loading");
    if (!pending.current || pending.current.token !== token || pending.current.attempt !== attempt) {
      pending.current = { token, attempt, request: authApi.verifyEmail(token) };
    }
    pending.current.request.then(async (result) => {
      if (!active) return;
      setState("success");
      setMessage(result.message);
      // The link may belong to a different account from the signed-in user.
      // Refresh the actual profile instead of marking a cached user verified.
      if (isAuthenticated()) {
        try {
          const profile = await authApi.getProfile();
          if (!active) return;
          sessionStorage.setItem("user", JSON.stringify(profile));
          setDestination(getRedirectPath());
        } catch {
          // Verification succeeded independently of this optional refresh.
        }
      }
    }).catch((error: unknown) => {
      if (!active) return;
      setState("error");
      if (isAxiosError(error)) {
        const serverMessage = error.response?.data?.error;
        setMessage(typeof serverMessage === "string"
          ? serverMessage
          : error.response
            ? "We could not verify this link. Please request a new verification email."
            : "Unable to reach Emby. Check your connection and try again.");
        setCanRetry(!error.response || error.response.status >= 500);
      } else {
        setMessage("We could not verify this link. Please try again.");
        setCanRetry(true);
      }
    });
    return () => { active = false; };
  }, [token, attempt]);

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        {state === "loading" ? <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" aria-hidden="true" />
          : state === "success" ? <CheckCircle2 className="mx-auto h-10 w-10 text-green-600" aria-hidden="true" />
            : <Mail className="mx-auto h-10 w-10 text-primary" aria-hidden="true" />}
        <CardTitle>{state === "loading" ? "Verifying your email" : state === "success" ? "Email verified" : "Email verification"}</CardTitle>
        <CardDescription role={state === "error" ? "alert" : "status"}>
          {state === "loading" ? "Please wait while we check your link." : message}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 text-center">
        {state === "success" && (
          <p className="text-sm text-muted-foreground">Class-head requests are reviewed separately. You can check your approval status after signing in.</p>
        )}
        {state === "error" && canRetry && (
          <Button variant="outline" onClick={() => setAttempt((value) => value + 1)}>Try verification again</Button>
        )}
        {state === "error" && signedIn && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Request a new link for {accountEmail || "your signed-in account"}.</p>
            <ResendVerification onVerified={() => {
              setState("success");
              setMessage("Your signed-in account's email is already verified.");
            }} />
          </div>
        )}
        {state === "error" && !signedIn && (
          <p className="text-sm text-muted-foreground">Sign in to request a new verification email from your account.</p>
        )}
        {state !== "loading" && (
          <Button asChild className="w-full"><Link href={destination}>{signedIn ? "Continue to your account" : "Sign in"}</Link></Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <Suspense fallback={<p role="status">Loading email verification...</p>}>
        <VerificationContent />
      </Suspense>
    </main>
  );
}
