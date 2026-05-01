import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Crown, Lock, X, Check } from "lucide-react";

const lockedFeatures: Record<string, { locked: string[]; unlocked: string[] }> = {
  default: {
    locked: [
      "Unlimited quizzes & steeplechase",
      "Unlimited AI tutor explanations",
      "Post & reply in community",
      "Spaced-repetition flashcards",
      "Advanced analytics & weak topics",
      "Offline PDF reader",
    ],
    unlocked: [
      "Your class materials",
      "Daily study plan (30 min)",
      "1 quiz + 1 flashcard deck / day",
      "Community read-only",
    ],
  },
  quiz: {
    locked: [
      "Unlimited quizzes per day",
      "Full past questions bank",
      "Steeplechase practice mode",
      "Detailed quiz analytics",
    ],
    unlocked: ["5 quiz questions per day"],
  },
  ai: {
    locked: [
      "Unlimited AI tutor queries",
      "AI explanations while reading",
      "Ask AI about any slide",
    ],
    unlocked: ["3 AI queries per day"],
  },
  community: {
    locked: [
      "Create posts & discussions",
      "Like & comment on posts",
      "Share resources with class",
    ],
    unlocked: ["Read community posts"],
  },
  flashcards: {
    locked: [
      "Unlimited flashcard decks",
      "Spaced-repetition algorithm",
      "Create custom decks",
    ],
    unlocked: ["1 flashcard deck per day"],
  },
};

interface UpgradePromptProps {
  feature?: keyof typeof lockedFeatures;
  title?: string;
  compact?: boolean;
}

export function UpgradePrompt({
  feature = "default",
  title,
  compact = false,
}: UpgradePromptProps) {
  const features = lockedFeatures[feature] ?? lockedFeatures.default;

  if (compact) {
    return (
      <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-4 text-center">
        <Crown className="mx-auto mb-2 h-6 w-6 text-primary" />
        <p className="text-sm font-medium mb-1">{title ?? "Premium feature"}</p>
        <ul className="mb-3 space-y-1">
          {features.locked.slice(0, 3).map((f) => (
            <li key={f} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <X className="h-3 w-3 text-destructive flex-shrink-0" />
              <span>{f}</span>
            </li>
          ))}
        </ul>
        <Link href="/premium">
          <Button size="sm" className="w-full">
            <Crown className="mr-1.5 h-3.5 w-3.5" />
            Upgrade · ₦1,499/mo
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10">
      <CardHeader className="text-center pb-2">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Lock className="h-6 w-6 text-primary" />
        </div>
        <CardTitle className="text-xl">{title ?? "Unlock Premium"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* What you have */}
        <div className="rounded-lg border border-border bg-background/60 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Your free plan includes</p>
          <ul className="space-y-1.5">
            {features.unlocked.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                <Check className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* What you're missing */}
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary">Premium unlocks</p>
          <ul className="space-y-1.5">
            {features.locked.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm font-medium">
                <Crown className="h-4 w-4 text-primary flex-shrink-0" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>

        <Link href="/premium" className="block">
          <Button className="w-full" size="lg">
            <Crown className="mr-2 h-4 w-4" />
            Upgrade to Premium · ₦1,499/mo
          </Button>
        </Link>
        <p className="text-center text-xs text-muted-foreground">or ₦15,000/year · save 17%</p>
      </CardContent>
    </Card>
  );
}
