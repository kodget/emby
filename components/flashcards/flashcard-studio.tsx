"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Flashcard } from "@/lib/data";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Layers,
  Flame,
  RefreshCw,
  Check,
  X,
  ArrowRight,
  SkipBack,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDispatch } from "react-redux";
import { addCard } from "@/store/flashcards-slice";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { UpgradePrompt } from "@/components/upgrade-prompt";
import { useAppSelector } from "@/store/hooks";

type Difficulty = "again" | "hard" | "good" | "easy";

export function FlashcardStudio({ cards }: { cards: Flashcard[] }) {
  const { hasAccess, isFree } = useFeatureAccess();
  const usage = useAppSelector((s) => s.user.usage);
  const hasSpacedRepetition = hasAccess("spaced_repetition_flashcards");
  const dispatch = useDispatch();

  const [selectedDeck, setSelectedDeck] = useState<string | null>(null);
  const [onlyDue, setOnlyDue] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [deck, setDeck] = useState("");
  const [autoText, setAutoText] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  const handleAutoGenerate = async () => {
    if (!autoText.trim() || !deck.trim()) return;
    setIsGenerating(true);
    try {
      // TODO: Call AI API to generate flashcards
      // For now, create a sample card
      const generatedFront = `What is ${autoText}?`;
      const generatedBack = `This is a sample answer for ${autoText}.`;
      setFront(generatedFront);
      setBack(generatedBack);
    } catch (error) {
      console.error("Failed to generate flashcard:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreate = () => {
    if (front.trim() && back.trim() && deck.trim()) {
      dispatch(
        addCard({
          front: front.trim(),
          back: back.trim(),
          deck: deck.trim(),
          topic: deck.trim(),
        }),
      );
      setFront("");
      setBack("");
      setDeck("");
      setAutoText("");
      setCreateOpen(false);
    }
  };

  const decks = useMemo(() => {
    const map = new Map<string, { total: number; due: number }>();
    for (const c of cards) {
      const d = map.get(c.deck) ?? { total: 0, due: 0 };
      d.total += 1;
      if (c.due) d.due += 1;
      map.set(c.deck, d);
    }
    return Array.from(map.entries());
  }, [cards]);

  const filtered = useMemo(() => {
    return cards.filter(
      (c) => (!selectedDeck || c.deck === selectedDeck) && (!onlyDue || c.due),
    );
  }, [cards, selectedDeck, onlyDue]);

  if (selectedDeck) {
    return (
      <StudySession
        cards={filtered}
        deckName={selectedDeck}
        onlyDue={onlyDue}
        onBack={() => setSelectedDeck(null)}
      />
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:py-12">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            <Layers className="h-3.5 w-3.5 text-primary" />
            Spaced repetition
          </div>
          <h1 className="mt-3 font-serif text-4xl font-semibold tracking-tight md:text-5xl">
            Flashcards
          </h1>
          <p className="mt-2 max-w-xl text-muted-foreground">
            High-yield cards from your lecturers&apos; past questions. The
            algorithm schedules what you&apos;re about to forget.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Flashcard
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Flashcard</DialogTitle>
                <DialogDescription>
                  Add a custom flashcard to your collection.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="deck">Deck</Label>
                  <Input
                    id="deck"
                    value={deck}
                    onChange={(e) => setDeck(e.target.value)}
                    placeholder="e.g., Anatomy, Physiology"
                  />
                </div>
                <div>
                  <Label htmlFor="autoText">Auto Generate from Text</Label>
                  <Textarea
                    id="autoText"
                    value={autoText}
                    onChange={(e) => setAutoText(e.target.value)}
                    placeholder="Paste text or topic to generate flashcard"
                    rows={2}
                  />
                  <Button
                    onClick={handleAutoGenerate}
                    disabled={isGenerating || !autoText.trim() || !deck.trim()}
                    variant="outline"
                    className="mt-2 w-full"
                  >
                    {isGenerating ? "Generating..." : "Auto Generate"}
                  </Button>
                </div>
                <div>
                  <Label htmlFor="front">Front</Label>
                  <Textarea
                    id="front"
                    value={front}
                    onChange={(e) => setFront(e.target.value)}
                    placeholder="Question or term"
                    rows={3}
                  />
                </div>
                <div>
                  <Label htmlFor="back">Back</Label>
                  <Textarea
                    id="back"
                    value={back}
                    onChange={(e) => setBack(e.target.value)}
                    placeholder="Answer or definition"
                    rows={3}
                  />
                </div>
                <Button onClick={handleCreate} className="w-full">
                  Create Flashcard
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          <label className="flex cursor-pointer items-center gap-2 rounded-full border border-border bg-card px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={onlyDue}
              onChange={(e) => setOnlyDue(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Only due today
          </label>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {decks.map(([deck, stats]) => (
          <Card
            key={deck}
            className="group cursor-pointer border-border/60 p-6 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
            onClick={() => setSelectedDeck(deck)}
          >
            <div className="flex items-start justify-between">
              <div className="flex size-11 items-center justify-center rounded-xl bg-secondary text-primary">
                <Layers className="h-5 w-5" />
              </div>
              {stats.due > 0 && (
                <Badge className="bg-accent text-accent-foreground hover:bg-accent">
                  <Flame className="mr-1 h-3 w-3" />
                  {stats.due} due
                </Badge>
              )}
            </div>
            <h3 className="mt-4 font-serif text-xl font-semibold">{deck}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {stats.total} cards in deck
            </p>

            <div className="mt-4">
              <div className="mb-1 flex justify-between text-xs">
                <span className="text-muted-foreground">Mastery</span>
                <span className="font-medium">
                  {Math.round(((stats.total - stats.due) / stats.total) * 100)}%
                </span>
              </div>
              <Progress
                value={((stats.total - stats.due) / stats.total) * 100}
                className="h-1.5"
              />
            </div>

            <div className="mt-5 flex items-center text-sm font-medium text-primary">
              Study deck
              <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </div>
          </Card>
        ))}
      </div>

      <Card className="mt-10 flex flex-col items-start gap-4 border-dashed border-border bg-muted/30 p-6 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="font-serif text-lg font-semibold">
            Your mistakes, compounded
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Every wrong quiz answer and missed steeplechase station is
            automatically turned into a card.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/dashboard">
            Back to dashboard
            <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
      </Card>
    </div>
  );
}

function StudySession({
  cards,
  deckName,
  onlyDue,
  onBack,
}: {
  cards: Flashcard[];
  deckName: string;
  onlyDue: boolean;
  onBack: () => void;
}) {
  const { hasAccess, isFree } = useFeatureAccess();
  const usage = useAppSelector((s) => s.user.usage);
  const hasSpacedRepetition = hasAccess("spaced_repetition_flashcards");

  if (isFree && usage.flashcardsCreated >= 1) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <UpgradePrompt
          feature="Daily Flashcard Study"
          description="Study unlimited flashcard decks with spaced repetition"
        />
        <div className="mt-4 text-center">
          <Button variant="outline" onClick={onBack}>
            Back to Decks
          </Button>
        </div>
      </div>
    );
  }

  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [ratings, setRatings] = useState<Record<string, Difficulty>>({});

  if (cards.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Check className="h-6 w-6" />
        </div>
        <h1 className="mt-6 font-serif text-3xl font-semibold">
          Nothing {onlyDue ? "due" : "here"} in {deckName}.
        </h1>
        <p className="mt-2 text-muted-foreground">
          Come back later, or study all cards in this deck.
        </p>
        <Button onClick={onBack} className="mt-6">
          <SkipBack className="mr-2 h-4 w-4" />
          Back to decks
        </Button>
      </div>
    );
  }

  const card = cards[index];
  const done = index >= cards.length - 1 && ratings[card.id];

  function rate(diff: Difficulty) {
    setRatings((r) => ({ ...r, [card.id]: diff }));
    setTimeout(() => {
      if (index + 1 < cards.length) {
        setIndex((i) => i + 1);
        setFlipped(false);
      }
    }, 150);
  }

  if (done && index === cards.length - 1) {
    const tally = Object.values(ratings);
    const easy = tally.filter((r) => r === "easy").length;
    const good = tally.filter((r) => r === "good").length;
    const hard = tally.filter((r) => r === "hard").length;
    const again = tally.filter((r) => r === "again").length;
    return (
      <div className="mx-auto max-w-2xl px-4 py-12">
        <Card className="overflow-hidden border-border/60 p-0">
          <div className="bg-primary p-8 text-primary-foreground">
            <p className="text-sm uppercase tracking-wider text-primary-foreground/70">
              Session complete
            </p>
            <h1 className="mt-2 font-serif text-4xl font-semibold">
              {cards.length} cards reviewed
            </h1>
            <p className="mt-2 text-primary-foreground/80">
              {deckName} · saved to your spaced-repetition schedule
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 p-6 md:grid-cols-4">
            <SessionStat
              label="Again"
              value={again}
              color="bg-destructive/10 text-destructive"
            />
            <SessionStat
              label="Hard"
              value={hard}
              color="bg-accent/15 text-accent"
            />
            <SessionStat
              label="Good"
              value={good}
              color="bg-primary/10 text-primary"
            />
            <SessionStat
              label="Easy"
              value={easy}
              color="bg-secondary text-primary"
            />
          </div>
          <div className="flex justify-end gap-2 border-t border-border bg-muted/30 p-6">
            <Button variant="outline" onClick={onBack}>
              Back to decks
            </Button>
            <Button asChild>
              <Link href="/dashboard">Dashboard</Link>
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <SkipBack className="h-4 w-4" />
          All decks
        </button>
        <div className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            {index + 1} / {cards.length}
          </span>{" "}
          · {deckName}
        </div>
      </div>
      <Progress
        value={((index + 1) / cards.length) * 100}
        className="mb-8 h-1.5"
      />

      <button
        onClick={() => setFlipped((f) => !f)}
        className={cn(
          "group relative block w-full min-h-[280px] rounded-3xl border border-border bg-card p-8 text-left transition-all md:min-h-[360px] md:p-10",
          "hover:border-primary/40",
        )}
        aria-label="Flip flashcard"
      >
        <div className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {flipped ? "Back" : "Front"}
        </div>
        <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
          {card.topic}
        </p>
        <div className="mt-3 min-h-[180px] md:min-h-[220px]">
          {!flipped ? (
            <p className="font-serif text-2xl leading-snug md:text-3xl">
              {card.front}
            </p>
          ) : (
            <p className="text-base leading-relaxed md:text-lg">{card.back}</p>
          )}
        </div>
        {!flipped && (
          <p className="mt-6 inline-flex items-center gap-2 text-sm text-muted-foreground group-hover:text-foreground">
            <RefreshCw className="h-4 w-4" />
            Click card to reveal answer
          </p>
        )}
      </button>

      {flipped && (
        <div className="mt-6 grid grid-cols-2 gap-2 md:grid-cols-4">
          <RateButton
            label="Again"
            desc="< 1m"
            color="destructive"
            onClick={() => rate("again")}
          />
          <RateButton
            label="Hard"
            desc="6m"
            color="accent"
            onClick={() => rate("hard")}
          />
          <RateButton
            label="Good"
            desc="1d"
            color="primary"
            onClick={() => rate("good")}
          />
          <RateButton
            label="Easy"
            desc="4d"
            color="primary"
            onClick={() => rate("easy")}
          />
        </div>
      )}

      {!flipped && (
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Think hard. Flip when you have an answer in mind.
        </p>
      )}
    </div>
  );
}

function RateButton({
  label,
  desc,
  color,
  onClick,
}: {
  label: string;
  desc: string;
  color: "destructive" | "accent" | "primary";
  onClick: () => void;
}) {
  const colors = {
    destructive:
      "border-destructive/30 hover:border-destructive hover:bg-destructive/5 text-destructive",
    accent:
      "border-accent/40 hover:border-accent hover:bg-accent/5 text-accent",
    primary:
      "border-primary/30 hover:border-primary hover:bg-primary/5 text-primary",
  };
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-center gap-0.5 rounded-xl border-2 bg-card px-4 py-3 font-medium transition-colors",
        colors[color],
      )}
    >
      <span className="text-base">{label}</span>
      <span className="text-[11px] uppercase tracking-wider opacity-70">
        {desc}
      </span>
    </button>
  );
}

function SessionStat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className={cn("rounded-xl p-3 text-center", color)}>
      <p className="font-serif text-2xl font-semibold">{value}</p>
      <p className="text-[11px] font-medium uppercase tracking-wider opacity-80">
        {label}
      </p>
    </div>
  );
}
