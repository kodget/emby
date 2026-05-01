'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Stethoscope, Check, Loader2, CreditCard } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { paymentApi, authApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

const subscriptionPlans = [
  {
    months: 1,
    price: 1499,
    label: '1 Month',
    savings: null,
  },
  {
    months: 3,
    price: 4497,
    label: '3 Months',
    savings: null,
  },
  {
    months: 6,
    price: 8994,
    label: '6 Months',
    savings: null,
  },
  {
    months: 12,
    price: 15000,
    label: '12 Months',
    savings: 'Save 17%',
  },
];

const premiumFeatures = [
  'Unlimited course materials access',
  'Unlimited AI tutor queries',
  'Advanced progress analytics',
  'Custom study plans',
  'Offline access to materials',
  'Priority customer support',
  'Ad-free experience',
  'Early access to new features',
];

export default function PaymentPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [selectedPlan, setSelectedPlan] = useState(1);
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const profile = await authApi.getProfile();
        setUser(profile);

        // If already premium, redirect to dashboard
        if (profile.is_premium) {
          toast({
            title: 'Already Premium',
            description: 'You already have an active premium subscription',
          });
          router.push('/dashboard');
        }
      } catch (error) {
        router.push('/signin');
      }
    };

    checkAuth();
  }, [router, toast]);

  const handlePayment = async () => {
    setLoading(true);

    try {
      const result = await paymentApi.initiatePayment(selectedPlan);
      
      // Redirect to Paystack
      window.location.href = result.authorization_url;
    } catch (error: any) {
      toast({
        title: 'Payment Failed',
        description: error.response?.data?.error || 'Failed to initiate payment',
        variant: 'destructive',
      });
      setLoading(false);
    }
  };

  const selectedPlanDetails = subscriptionPlans.find(p => p.months === selectedPlan);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 p-4">
      <div className="mx-auto max-w-4xl py-8">
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

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Plan Selection */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Choose Your Plan</CardTitle>
                <CardDescription>
                  Select a subscription duration that works for you
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <RadioGroup
                  value={selectedPlan.toString()}
                  onValueChange={(value) => setSelectedPlan(parseInt(value))}
                >
                  <div className="grid gap-4 sm:grid-cols-2">
                    {subscriptionPlans.map((plan) => (
                      <div key={plan.months} className="relative">
                        <RadioGroupItem
                          value={plan.months.toString()}
                          id={`plan-${plan.months}`}
                          className="peer sr-only"
                        />
                        <Label
                          htmlFor={`plan-${plan.months}`}
                          className="flex flex-col items-center justify-between rounded-lg border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer"
                        >
                          <div className="text-center w-full">
                            <p className="font-semibold text-lg">{plan.label}</p>
                            <p className="text-2xl font-bold mt-2">
                              ₦{plan.price.toLocaleString()}
                            </p>
                            <p className="text-sm text-muted-foreground mt-1">
                              ₦{Math.round(plan.price / plan.months).toLocaleString()}/month
                            </p>
                          </div>
                        </Label>
                      </div>
                    ))}
                  </div>
                </RadioGroup>

                <Alert>
                  <CreditCard className="h-4 w-4" />
                  <AlertDescription>
                    <p className="font-semibold mb-1">Secure Payment</p>
                    <p className="text-sm">
                      Payments are processed securely through Paystack. We never store your card details.
                    </p>
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  <h3 className="font-semibold">Premium Features</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {premiumFeatures.map((feature, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                        <span className="text-sm">{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Order Summary */}
          <div>
            <Card>
              <CardHeader>
                <CardTitle>Order Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Plan</span>
                    <span className="font-medium">{selectedPlanDetails?.label}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Duration</span>
                    <span className="font-medium">{selectedPlan} month(s)</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Price per month</span>
                    <span className="font-medium">
                      ₦{selectedPlanDetails && Math.round(selectedPlanDetails.price / selectedPlan).toLocaleString()}
                    </span>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold">Total</span>
                    <span className="text-2xl font-bold">
                      ₦{selectedPlanDetails?.price.toLocaleString()}
                    </span>
                  </div>
                </div>

                <Button
                  className="w-full"
                  size="lg"
                  onClick={handlePayment}
                  disabled={loading}
                >
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Proceed to Payment
                </Button>

                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => router.push('/dashboard')}
                  disabled={loading}
                >
                  Continue with Free
                </Button>

                <p className="text-xs text-center text-muted-foreground">
                  By proceeding, you agree to our{' '}
                  <Link href="/terms" className="underline hover:text-foreground">
                    Terms of Service
                  </Link>
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
