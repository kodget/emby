"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Stethoscope,
  Clock,
  CheckCircle2,
  XCircle,
  Mail,
  Loader2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import EmailVerificationBanner from "@/components/auth/email-verification-banner";
import { authApi } from "@/lib/api";
import type { UserProfile } from "@/lib/api";
import { useAppDispatch } from "@/store/hooks";
import { logout, updateUserProfile } from "@/store/user-slice";

export default function VerificationPendingPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const mounted = useRef(false);
  const requestInFlight = useRef(false);

  const applyProfile = useCallback((profile: UserProfile) => {
    setUser(profile);
    sessionStorage.setItem("user", JSON.stringify(profile));
    const verified = profile.class_role === "class_head" && profile.class_head_verified === true;
    dispatch(updateUserProfile({
      id: profile.id.toString(),
      name: profile.full_name,
      username: profile.username,
      email: profile.email,
      photoUrl: profile.photo_url,
      school: profile.school_name,
      setName: profile.set_name,
      backendRole: profile.class_role,
      isVerifiedClassHead: verified,
      isSignedIn: true,
      isOnboarded: profile.onboarding_completed,
      streak: profile.streak,
      subscription: {
        status: profile.is_premium ? "active" : "free",
        tier: profile.is_premium ? "premium" : "free",
        expiresAt: verified ? null : profile.subscription_expires_at,
      },
    }));
    if (!profile.onboarding_completed) router.replace("/onboarding");
    else if (profile.class_role !== "class_head" || verified) router.replace("/dashboard");
  }, [dispatch, router]);

  const handleFailure = useCallback((failure: unknown) => {
    if (isAxiosError(failure) && failure.response?.status === 401) {
      router.replace("/signin");
      return;
    }
    const data = isAxiosError(failure) ? failure.response?.data : null;
    const detail = data?.error || data?.detail;
    setError(typeof detail === "string" ? detail : "We couldn't reach the server. Your account is still signed in; please try again.");
  }, [router]);

  const checkStatus = useCallback(async () => {
    if (!mounted.current || requestInFlight.current) return;
    requestInFlight.current = true;
    setChecking(true);
    try {
      const profile = await authApi.getProfile();
      if (mounted.current) {
        applyProfile(profile);
        setError(null);
      }
    } catch (failure) {
      if (mounted.current) handleFailure(failure);
    } finally {
      requestInFlight.current = false;
      if (mounted.current) {
        setChecking(false);
        setLoading(false);
      }
    }
  }, [applyProfile, handleFailure]);

  useEffect(() => {
    mounted.current = true;
    if (!sessionStorage.getItem("token")) {
      router.replace("/signin");
      return () => { mounted.current = false; };
    }
    void checkStatus();
    const interval = setInterval(() => void checkStatus(), 30000);
    return () => {
      mounted.current = false;
      clearInterval(interval);
    };
  }, [checkStatus, router]);

  const requestReview = async () => {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await authApi.requestClassHeadVerification();
      const profile = result.user ?? await authApi.getProfile();
      if (mounted.current) {
        applyProfile(profile);
        setMessage(result.message);
      }
    } catch (failure) {
      if (mounted.current) handleFailure(failure);
    } finally {
      requestInFlight.current = false;
      if (mounted.current) setSubmitting(false);
    }
  };

  const signOut = () => {
    mounted.current = false;
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("refreshToken");
    sessionStorage.removeItem("user");
    dispatch(logout());
    router.replace("/signin");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const pending = user?.class_head_verification_requested === true;
  const rejected = !!user && !pending && !!user.class_head_rejection_reason;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20 p-4">
      <div className="w-full max-w-2xl">
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <span className="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope className="size-5" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-serif text-2xl">Emby</span>
            <span className="text-xs uppercase tracking-widest text-muted-foreground">
              BMS Edition
            </span>
          </span>
        </Link>

        <Card>
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              {rejected ? <XCircle className="h-8 w-8 text-destructive" /> : <Clock className="h-8 w-8 text-yellow-500" />}
            </div>
            <CardTitle className="text-2xl">{pending ? "Verification Pending" : rejected ? "Verification Not Approved" : "Class-Head Verification"}</CardTitle>
            <CardDescription>
              {pending ? "Your class-head application is waiting for review." : rejected ? "Review the reason below before requesting another review." : user ? "Submit your class-head application for review." : "We couldn't load your current verification status."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {user && !user.email_verified && <EmailVerificationBanner />}
            {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
            {message && <p className="text-sm text-primary" role="status">{message}</p>}
            {rejected && user ? (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-1">
                    Verification Not Approved
                  </p>
                  <p className="text-sm">{user.class_head_rejection_reason}</p>
                  <p className="text-sm mt-2">
                    You can request another review after addressing this feedback.
                  </p>
                </AlertDescription>
              </Alert>
            ) : pending ? (
              <>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-medium">Account Created</p>
                      <p className="text-sm text-muted-foreground">
                        Your account has been successfully created
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-yellow-500/10 text-yellow-500">
                      <Clock className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-medium">Verification in Progress</p>
                      <p className="text-sm text-muted-foreground">
                        Our team is reviewing your class head application
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 opacity-50">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted">
                      <Mail className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-medium">Email Notification</p>
                      <p className="text-sm text-muted-foreground">
                        We will notify you when a decision has been made. You can also check your status here.
                      </p>
                    </div>
                  </div>
                </div>

                <Alert>
                  <AlertDescription>
                    <p className="font-semibold mb-2">What happens next?</p>
                    <ul className="text-sm space-y-1 list-disc list-inside">
                      <li>Our team will verify your class head credentials</li>
                      <li>Your class code will be included in your approval email</li>
                      <li>
                        Once approved, you'll have full access to all premium
                        features
                      </li>
                      <li>
                        Share your class code with your classmates to join
                      </li>
                    </ul>
                  </AlertDescription>
                </Alert>

              </>
            ) : null}

            <div className="flex flex-col gap-2">
              {user && !pending && !user.class_head_verified && (
                <Button className="w-full" disabled={submitting || checking} onClick={() => void requestReview()}>
                  {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {submitting ? "Submitting…" : rejected ? "Request another review" : "Request verification"}
                </Button>
              )}
              <Button variant="outline" className="w-full" disabled={checking || submitting} onClick={() => void checkStatus()}>
                {checking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {checking ? "Checking…" : "Check status"}
              </Button>
              <Button variant="outline" asChild className="w-full">
                <Link href="/">Return to Home</Link>
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                onClick={signOut}
              >
                Sign out
              </Button>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground mt-4">
          Need help? Contact us at{" "}
          <a
            href="mailto:support@emby.com"
            className="underline hover:text-foreground"
          >
            support@emby.com
          </a>
        </p>
      </div>
    </div>
  );
}
