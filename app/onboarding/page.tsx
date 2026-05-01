'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Stethoscope, Loader2, Users, GraduationCap, Upload, Sparkles, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { onboardingApi, authApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import type { OnboardingQuestion } from '@/lib/api';
import Link from 'next/link';

const roles = [
  {
    value: 'student',
    title: 'Student',
    description: 'Access course materials, track progress, and study with your classmates',
    icon: GraduationCap,
  },
  {
    value: 'brainstormer',
    title: 'Brainstormer',
    description: 'Organize brainstorming sessions and quiz competitions for your class',
    icon: Sparkles,
  },
  {
    value: 'class_head',
    title: 'Class Head',
    description: 'Manage your class, make announcements, and get full premium access',
    icon: Users,
  },
  {
    value: 'material_uploader',
    title: 'Material Uploader',
    description: 'Upload and share study materials with your classmates',
    icon: Upload,
  },
];

const subscriptionTiers = [
  {
    value: 'free',
    title: 'Free',
    price: '₦0',
    features: [
      'Access to basic course materials',
      'Limited AI tutor queries',
      'Basic progress tracking',
      'Community access',
    ],
  },
  {
    value: 'premium',
    title: 'Premium',
    price: '₦1,499/month',
    features: [
      'Unlimited course materials',
      'Unlimited AI tutor',
      'Advanced analytics',
      'Priority support',
      'Offline access',
      'Custom study plans',
    ],
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<OnboardingQuestion[]>([]);
  const [error, setError] = useState('');

  // Form data
  const [role, setRole] = useState('');
  const [schoolName, setSchoolName] = useState('');
  const [setName, setSetName] = useState('');
  const [classCode, setClassCode] = useState('');
  const [subscriptionTier, setSubscriptionTier] = useState('free');
  const [responses, setResponses] = useState<Record<number, string>>({});

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/signin');
      return;
    }

    // Fetch onboarding questions
    const fetchQuestions = async () => {
      try {
        const data = await onboardingApi.getQuestions();
        setQuestions(data);
      } catch (error) {
        console.error('Failed to fetch questions:', error);
      }
    };

    fetchQuestions();
  }, [router]);

  const handleNext = async () => {
    setError('');

    if (step === 1 && !role) {
      setError('Please select a role');
      return;
    }

    if (step === 2) {
      if (!schoolName.trim()) {
        setError('Please enter your school name');
        return;
      }
      if (!setName.trim()) {
        setError('Please enter your set name');
        return;
      }
      if (role !== 'class_head') {
        if (!classCode.trim()) {
          setError('Please enter the class code from your class head');
          return;
        }
        setLoading(true);
        try {
          await onboardingApi.validateClassCode(classCode.trim().toUpperCase());
        } catch (err: any) {
          setError(err.response?.data?.error || 'Invalid class code');
          setLoading(false);
          return;
        } finally {
          setLoading(false);
        }
      }
    }

    if (step < 4) {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
      setError('');
    }
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);

    try {
      // Check if user is still authenticated
      const token = localStorage.getItem('token');
      if (!token) {
        setError('Session expired. Please login again.');
        toast({
          title: 'Session Expired',
          description: 'Please login again to continue.',
          variant: 'destructive',
        });
        router.push('/signin');
        return;
      }

      // Prepare responses array
      const responsesArray = Object.entries(responses).map(([questionId, answer]) => ({
        question_id: parseInt(questionId),
        answer,
      }));

      const data = {
        role: role as any,
        school_name: schoolName,
        set_name: setName,
        class_code: role === 'class_head' ? undefined : classCode.trim().toUpperCase(),
        subscription_tier: subscriptionTier as any,
        responses: responsesArray,
      };

      console.log('Submitting onboarding data:', data);

      const result = await onboardingApi.submitOnboarding(data);

      console.log('Onboarding result:', result);

      // Update localStorage with new user data
      localStorage.setItem('user', JSON.stringify(result.user));

      toast({
        title: 'Onboarding complete!',
        description: result.message,
      });

      // Handle different scenarios
      if (result.verification_message) {
        // Class head pending verification
        toast({
          title: 'Verification Required',
          description: result.verification_message,
          duration: 5000,
        });
        router.push('/verification-pending');
      } else if (subscriptionTier === 'premium') {
        // Redirect to payment
        router.push('/payment');
      } else {
        // Go to dashboard
        router.push('/dashboard');
      }
    } catch (err: any) {
      console.error('Onboarding error:', err);
      console.error('Error response:', err.response?.data);
      
      // Handle 401 Unauthorized (token expired)
      if (err.response?.status === 401) {
        setError('Your session has expired. Please login again.');
        toast({
          title: 'Session Expired',
          description: 'Please login again to continue.',
          variant: 'destructive',
        });
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setTimeout(() => router.push('/signin'), 2000);
        return;
      }
      
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Failed to complete onboarding';
      setError(errorMessage);
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const progress = (step / 4) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 p-4">
      <div className="mx-auto max-w-3xl py-8">
        {/* Header */}
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

        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-muted-foreground mb-2">
            <span>Step {step} of 4</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <Card>
          <CardContent className="p-6 sm:p-8">
            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Step 1: Role Selection */}
            {step === 1 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Choose your role</h2>
                  <p className="text-muted-foreground">
                    Select the role that best describes you
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  {roles.map((roleOption) => {
                    const Icon = roleOption.icon;
                    return (
                      <button
                        key={roleOption.value}
                        onClick={() => setRole(roleOption.value)}
                        className={`relative p-6 rounded-lg border-2 text-left transition-all ${
                          role === roleOption.value
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        {role === roleOption.value && (
                          <div className="absolute top-4 right-4">
                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
                              <Check className="h-4 w-4" />
                            </div>
                          </div>
                        )}
                        <Icon className="h-8 w-8 mb-3 text-primary" />
                        <h3 className="font-semibold mb-2">{roleOption.title}</h3>
                        <p className="text-sm text-muted-foreground">
                          {roleOption.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Step 2: School & Class Info */}
            {step === 2 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold mb-2">School & Class Information</h2>
                  <p className="text-muted-foreground">
                    Help us connect you with your classmates
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="school">School Name</Label>
                    <Input
                      id="school"
                      placeholder="e.g., University of Lagos"
                      value={schoolName}
                      onChange={(e) => setSchoolName(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="set">Set Name</Label>
                    <Input
                      id="set"
                      placeholder="e.g., 2024/2025 or Year 3"
                      value={setName}
                      onChange={(e) => setSetName(e.target.value)}
                    />
                  </div>

                  {role !== 'class_head' && (
                    <div className="space-y-2">
                      <Label htmlFor="classCode">Class Code</Label>
                      <Input
                        id="classCode"
                        placeholder="6-digit code from your class head"
                        value={classCode}
                        onChange={(e) => setClassCode(e.target.value.trim().toUpperCase())}
                        maxLength={6}
                      />
                      <p className="text-xs text-muted-foreground">
                        Get this code from your class head to join your class
                      </p>
                    </div>
                  )}

                  {role === 'class_head' && (
                    <Alert>
                      <AlertDescription>
                        <p className="font-semibold mb-1">Class Head Benefits</p>
                        <p className="text-sm">
                          As a class head, you'll receive a unique class code via email after verification.
                          Share this code with your classmates to give them access to your class materials.
                        </p>
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              </div>
            )}

            {/* Step 3: Onboarding Questions */}
            {step === 3 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Tell us about yourself</h2>
                  <p className="text-muted-foreground">
                    Help us personalize your experience
                  </p>
                </div>

                <div className="space-y-6">
                  {questions.map((question) => (
                    <div key={question.id} className="space-y-3">
                      <Label>{question.question_text}</Label>
                      
                      {question.question_type === 'text' && (
                        <Textarea
                          placeholder="Your answer..."
                          value={responses[question.id] || ''}
                          onChange={(e) =>
                            setResponses({ ...responses, [question.id]: e.target.value })
                          }
                          rows={3}
                        />
                      )}

                      {question.question_type === 'choice' && (
                        <RadioGroup
                          value={responses[question.id] || ''}
                          onValueChange={(value) =>
                            setResponses({ ...responses, [question.id]: value })
                          }
                        >
                          {question.options.map((option) => (
                            <div key={option} className="flex items-center space-x-2">
                              <RadioGroupItem value={option} id={`${question.id}-${option}`} />
                              <Label htmlFor={`${question.id}-${option}`} className="font-normal">
                                {option}
                              </Label>
                            </div>
                          ))}
                        </RadioGroup>
                      )}
                    </div>
                  ))}

                  {questions.length === 0 && (
                    <p className="text-center text-muted-foreground py-8">
                      No questions available. Click continue to proceed.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Step 4: Subscription Tier */}
            {step === 4 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Choose your plan</h2>
                  <p className="text-muted-foreground">
                    {role === 'class_head'
                      ? 'Class heads get full premium access for free!'
                      : 'Select the plan that works best for you'}
                  </p>
                </div>

                {role === 'class_head' ? (
                  <Alert>
                    <AlertDescription>
                      <p className="font-semibold mb-2">🎉 Premium Access Included</p>
                      <p className="text-sm">
                        As a class head, you automatically get full access to all premium features at no cost.
                        This includes unlimited AI tutor, advanced analytics, and all course materials.
                      </p>
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {subscriptionTiers.map((tier) => (
                      <button
                        key={tier.value}
                        onClick={() => setSubscriptionTier(tier.value)}
                        className={`relative p-6 rounded-lg border-2 text-left transition-all ${
                          subscriptionTier === tier.value
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        {subscriptionTier === tier.value && (
                          <div className="absolute top-4 right-4">
                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
                              <Check className="h-4 w-4" />
                            </div>
                          </div>
                        )}
                        <h3 className="font-semibold text-lg mb-1">{tier.title}</h3>
                        <p className="text-2xl font-bold mb-4">{tier.price}</p>
                        <ul className="space-y-2">
                          {tier.features.map((feature, index) => (
                            <li key={index} className="flex items-start gap-2 text-sm">
                              <Check className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Navigation */}
            <div className="flex justify-between mt-8 pt-6 border-t">
              <Button
                variant="outline"
                onClick={handleBack}
                disabled={step === 1 || loading}
              >
                Back
              </Button>
              
              {step < 4 ? (
                <Button onClick={handleNext} disabled={loading}>
                  Continue
                </Button>
              ) : (
                <Button onClick={handleSubmit} disabled={loading}>
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {role === 'class_head'
                    ? 'Submit for Verification'
                    : subscriptionTier === 'premium'
                    ? 'Proceed to Payment'
                    : 'Complete Setup'}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
