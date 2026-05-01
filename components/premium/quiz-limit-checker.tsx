"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isPremium } from "@/lib/guards";
import { Lock, Crown, AlertCircle } from "lucide-react";

const DAILY_QUIZ_LIMIT = 5;
const STORAGE_KEY = "quiz_attempts";

type QuizAttempt = {
  date: string;
  count: number;
};

export function QuizLimitChecker({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [canTakeQuiz, setCanTakeQuiz] = useState(true);
  const [attemptsLeft, setAttemptsLeft] = useState(DAILY_QUIZ_LIMIT);
  const [showWarning, setShowWarning] = useState(false);
  const hasPremium = isPremium();

  useEffect(() => {
    if (hasPremium) {
      setCanTakeQuiz(true);
      return;
    }

    checkQuizLimit();
  }, [hasPremium]);

  const checkQuizLimit = () => {
    const today = new Date().toDateString();
    const stored = localStorage.getItem(STORAGE_KEY);
    
    let attempts: QuizAttempt = stored ? JSON.parse(stored) : { date: today, count: 0 };

    if (attempts.date !== today) {
      attempts = { date: today, count: 0 };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(attempts));
    }

    const remaining = DAILY_QUIZ_LIMIT - attempts.count;
    setAttemptsLeft(remaining);
    setCanTakeQuiz(remaining > 0);

    if (remaining <= 2 && remaining > 0) {
      setShowWarning(true);
    }
  };

  const incrementAttempt = () => {
    if (hasPremium) return;

    const today = new Date().toDateString();
    const stored = localStorage.getItem(STORAGE_KEY);
    let attempts: QuizAttempt = stored ? JSON.parse(stored) : { date: today, count: 0 };

    if (attempts.date !== today) {
      attempts = { date: today, count: 0 };
    }

    attempts.count += 1;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(attempts));
    checkQuizLimit();
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      (window as any).incrementQuizAttempt = incrementAttempt;
    }
  }, []);

  if (hasPremium) {
    return <>{children}</>;
  }

  if (!canTakeQuiz) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center p-4">
        <div className="max-w-2xl w-full">
          <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
            <div className="bg-gradient-to-r from-orange-500 to-red-500 p-8 text-center">
              <div className="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-4">
                <Lock className="w-10 h-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-white mb-2">Daily Limit Reached</h1>
              <p className="text-orange-100">You've used all your free quiz attempts for today</p>
            </div>

            <div className="p-8">
              <div className="text-center mb-8">
                <AlertCircle className="w-16 h-16 text-orange-600 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  {DAILY_QUIZ_LIMIT} Questions Per Day (Free Tier)
                </h2>
                <p className="text-gray-600">
                  Come back tomorrow for more questions, or upgrade to Premium for unlimited access
                </p>
              </div>

              <div className="space-y-4 mb-8">
                <div className="flex items-start gap-3 p-4 bg-purple-50 rounded-lg">
                  <Crown className="w-6 h-6 text-purple-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">Unlimited Quizzes</h3>
                    <p className="text-sm text-gray-600">Take as many quizzes as you want, anytime</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-4 bg-blue-50 rounded-lg">
                  <Crown className="w-6 h-6 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">Full Community Access</h3>
                    <p className="text-sm text-gray-600">Create posts, like, and comment without limits</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-4 bg-green-50 rounded-lg">
                  <Crown className="w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">Unlimited AI Usage</h3>
                    <p className="text-sm text-gray-600">Use AI study assistant without time restrictions</p>
                  </div>
                </div>
              </div>

              <button
                onClick={() => router.push("/payment")}
                className="w-full px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-bold text-lg hover:from-purple-700 hover:to-blue-700 transition-all shadow-lg hover:shadow-xl"
              >
                Upgrade to Premium
              </button>

              <p className="text-center text-sm text-muted-foreground mt-4">
                Starting from ₦1,499/month
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {showWarning && (
        <div className="bg-yellow-50 border-b border-yellow-200 p-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-600" />
              <p className="text-sm text-yellow-800">
                <strong>Free Tier:</strong> {attemptsLeft} quiz question{attemptsLeft !== 1 ? "s" : ""} remaining today
              </p>
            </div>
            <button
              onClick={() => router.push("/payment")}
              className="text-sm font-semibold text-yellow-800 hover:text-yellow-900 underline"
            >
              Upgrade for unlimited
            </button>
          </div>
        </div>
      )}
      {children}
    </>
  );
}

export function useQuizLimit() {
  const hasPremium = isPremium();

  const incrementAttempt = () => {
    if (hasPremium) return;
    if (typeof window !== "undefined" && (window as any).incrementQuizAttempt) {
      (window as any).incrementQuizAttempt();
    }
  };

  return { incrementAttempt };
}
