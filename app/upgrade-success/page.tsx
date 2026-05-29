"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Stethoscope, Check, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { paymentApi } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function PaymentSuccessPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const [status, setStatus] = useState<"verifying" | "success" | "failed">(
    "verifying",
  );
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const verifyPayment = async () => {
      const reference = searchParams.get("reference");

      if (!reference) {
        setStatus("failed");
        return;
      }

      try {
        const result = await paymentApi.verifyPayment(reference);

        // Update sessionStorage with new user data
        sessionStorage.setItem("user", JSON.stringify(result.user));
        setUser(result.user);
        setStatus("success");

        toast({
          title: "Payment Successful!",
          description: "Your premium subscription is now active",
        });
      } catch (error: any) {
        setStatus("failed");
        toast({
          title: "Payment Verification Failed",
          description: error.response?.data?.error || "Please contact support",
          variant: "destructive",
        });
      }
    };

    verifyPayment();
  }, [searchParams, toast]);

  if (status === "verifying") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-lg font-medium">Verifying your payment...</p>
          <p className="text-sm text-muted-foreground mt-2">Please wait</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20 p-4">
      <div className="w-full max-w-md">
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
          <CardContent className="p-8">
            {status === "success" ? (
              <div className="text-center space-y-6">
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/10">
                  <Check className="h-10 w-10 text-green-500" />
                </div>

                <div>
                  <h1 className="text-3xl font-bold mb-2">
                    Payment Successful!
                  </h1>
                  <p className="text-muted-foreground">
                    Your premium subscription is now active
                  </p>
                </div>

                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Status</span>
                    <span className="font-medium text-green-500">Active</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Plan</span>
                    <span className="font-medium">Premium</span>
                  </div>
                  {user?.subscription_expires_at && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Expires</span>
                      <span className="font-medium">
                        {new Date(
                          user.subscription_expires_at,
                        ).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    You now have access to:
                  </p>
                  <ul className="text-sm space-y-2">
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      Unlimited AI tutor queries
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      All course materials
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      Advanced analytics
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      Offline access
                    </li>
                  </ul>
                </div>

                <Button
                  className="w-full"
                  size="lg"
                  onClick={() => router.push("/dashboard")}
                >
                  Go to Dashboard
                </Button>
              </div>
            ) : (
              <div className="text-center space-y-6">
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-red-500/10">
                  <XCircle className="h-10 w-10 text-red-500" />
                </div>

                <div>
                  <h1 className="text-3xl font-bold mb-2">Payment Failed</h1>
                  <p className="text-muted-foreground">
                    We couldn't verify your payment
                  </p>
                </div>

                <p className="text-sm text-muted-foreground">
                  If you were charged, please contact support with your
                  transaction reference. We'll resolve this as soon as possible.
                </p>

                <div className="space-y-2">
                  <Button
                    className="w-full"
                    onClick={() => router.push("/payment")}
                  >
                    Try Again
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => router.push("/dashboard")}
                  >
                    Go to Dashboard
                  </Button>
                </div>

                <p className="text-xs text-muted-foreground">
                  Need help?{" "}
                  <a
                    href="mailto:support@emby.com"
                    className="underline hover:text-foreground"
                  >
                    Contact Support
                  </a>
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
