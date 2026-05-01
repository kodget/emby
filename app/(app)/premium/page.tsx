'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Sparkles, Zap, Crown, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { paymentApi } from '@/lib/api';

const features = [
  'Unlimited AI tutor prompts (vs 5/day free)',
  'Enhanced AI explanations with context',
  'YouTube video & textbook suggestions',
  'Weekly study analytics dashboard',
  'Unlimited study plan items (vs 3/day free)',
  'Up to 100 MCQ questions per quiz (vs 10 free)',
  'Access to theory questions (up to 10)',
  'Full community engagement (post, like, comment)',
];

const plans = [
  {
    id: 'monthly',
    name: 'Monthly',
    price: '₦1,499',
    period: '/month',
    months: 1,
    description: 'Perfect for trying out premium features',
  },
  {
    id: 'yearly',
    name: 'Yearly',
    price: '₦15,000',
    period: '/year',
    months: 12,
    description: 'Save ₦2,988 compared to monthly',
    badge: 'Best Value',
  },
];

export default function PremiumPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('yearly');

  const handleSubscribe = async () => {
    setLoading(true);

    try {
      const plan = plans.find(p => p.id === selectedPlan);
      if (!plan) return;

      const result = await paymentApi.initiatePayment(plan.months);

      // Redirect to Paystack payment page
      window.location.href = result.authorization_url;
    } catch (error: any) {
      console.error('Payment initiation failed:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.error || 'Failed to initiate payment',
        variant: 'destructive',
      });
      setLoading(false);
    }
  };

  return (
    <div className="container max-w-6xl py-8">
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center p-2 bg-primary/10 rounded-full mb-4">
          <Crown className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-4xl font-bold mb-4">Upgrade to Premium</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Unlock unlimited access to all features and supercharge your medical studies
        </p>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
        {features.map((feature, index) => (
          <Card key={index} className="border-primary/20">
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
                    <Check className="h-4 w-4 text-primary" />
                  </div>
                </div>
                <p className="text-sm font-medium">{feature}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pricing Plans */}
      <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto mb-8">
        {plans.map((plan) => (
          <Card
            key={plan.id}
            className={`relative cursor-pointer transition-all ${
              selectedPlan === plan.id
                ? 'border-primary shadow-lg scale-105'
                : 'border-border hover:border-primary/50'
            }`}
            onClick={() => setSelectedPlan(plan.id)}
          >
            {plan.badge && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary text-primary-foreground text-xs font-semibold">
                  <Sparkles className="h-3 w-3" />
                  {plan.badge}
                </span>
              </div>
            )}
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                {plan.name}
                {selectedPlan === plan.id && (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary">
                    <Check className="h-4 w-4 text-primary-foreground" />
                  </div>
                )}
              </CardTitle>
              <CardDescription>{plan.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-bold">{plan.price}</span>
                <span className="text-muted-foreground">{plan.period}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Subscribe Button */}
      <div className="text-center">
        <Button
          size="lg"
          onClick={handleSubscribe}
          disabled={loading}
          className="min-w-[200px]"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Zap className="mr-2 h-4 w-4" />
              Subscribe Now
            </>
          )}
        </Button>
        <p className="text-sm text-muted-foreground mt-4">
          Secure payment powered by Paystack. Cancel anytime.
        </p>
      </div>

      {/* FAQ or Additional Info */}
      <div className="mt-16 max-w-3xl mx-auto">
        <h2 className="text-2xl font-bold text-center mb-8">Premium vs Free</h2>
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          <Card>
            <CardHeader>
              <CardTitle>Free</CardTitle>
              <CardDescription>Basic access to get started</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">5 AI prompts per day</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">3 study plan items per day</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">Max 10 MCQ questions per quiz</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">No theory questions</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">Read-only community access</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span className="text-sm">No analytics dashboard</span>
              </div>
            </CardContent>
          </Card>
          <Card className="border-primary">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Crown className="h-5 w-5 text-primary" />
                Premium
              </CardTitle>
              <CardDescription>Unlock your full potential</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Unlimited AI prompts</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Unlimited study planning</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Up to 100 MCQ questions</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Up to 10 theory questions</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Full community engagement</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Weekly analytics dashboard</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-primary mt-0.5" />
                <span className="text-sm font-medium">Video & textbook suggestions</span>
              </div>
            </CardContent>
          </Card>
        </div>
        <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
        <div className="space-y-6">
          <div>
            <h3 className="font-semibold mb-2">Can I cancel anytime?</h3>
            <p className="text-muted-foreground">
              Yes, you can cancel your subscription at any time. You'll continue to have access until the end of your billing period.
            </p>
          </div>
          <div>
            <h3 className="font-semibold mb-2">What payment methods do you accept?</h3>
            <p className="text-muted-foreground">
              We accept all major payment methods through Paystack including cards, bank transfers, and mobile money.
            </p>
          </div>
          <div>
            <h3 className="font-semibold mb-2">Is there a free trial?</h3>
            <p className="text-muted-foreground">
              Free tier users can access basic features. Upgrade to premium anytime to unlock all features.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
