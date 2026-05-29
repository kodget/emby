"use client";

import { useEffect, useState } from "react";
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
import { authApi } from "@/lib/api";
import type { UserProfile } from "@/lib/api";

export default function VerificationPendingPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const profile = await authApi.getProfile();
        setUser(profile);

        // Update sessionStorage with fresh profile data
        sessionStorage.setItem("user", JSON.stringify(profile));

        // If verified, redirect to dashboard
        if (profile.class_head_verified) {
          router.push("/dashboard");
        }
      } catch (error) {
        // If not authenticated, redirect to signin
        router.push("/signin");
      } finally {
        setLoading(false);
      }
    };

    checkStatus();

    // Poll every 30 seconds to check if verified
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return null;
  }

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
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-500/10">
              <Clock className="h-8 w-8 text-yellow-500" />
            </div>
            <CardTitle className="text-2xl">Verification Pending</CardTitle>
            <CardDescription>
              Your class head account is being reviewed
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {user.class_head_rejection_reason ? (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-1">
                    Verification Not Approved
                  </p>
                  <p className="text-sm">{user.class_head_rejection_reason}</p>
                  <p className="text-sm mt-2">
                    Please contact support at support@emby.com for more
                    information.
                  </p>
                </AlertDescription>
              </Alert>
            ) : (
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
                        You'll receive an email once your account is verified
                      </p>
                    </div>
                  </div>
                </div>

                <Alert>
                  <AlertDescription>
                    <p className="font-semibold mb-2">What happens next?</p>
                    <ul className="text-sm space-y-1 list-disc list-inside">
                      <li>Our team will verify your class head credentials</li>
                      <li>You'll receive an email with your class code</li>
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

                <div className="bg-muted/50 rounded-lg p-4">
                  <p className="text-sm text-muted-foreground mb-2">
                    <strong>Verification typically takes:</strong>
                  </p>
                  <p className="text-2xl font-bold">24-48 hours</p>
                </div>
              </>
            )}

            <div className="flex flex-col gap-2">
              <Button variant="outline" asChild className="w-full">
                <Link href="/">Return to Home</Link>
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => {
                  sessionStorage.clear();
                  router.push("/signin");
                }}
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
