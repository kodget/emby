"use client";

import { useMemo, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { awardPoints } from "@/store/user-slice";

const simulatedContestants = [
  { name: "Ifeoma U.", time: 6000, points: 1000 },
  { name: "Kelechi E.", time: 8200, points: 500 },
  { name: "Segun A.", time: 10400, points: 200 },
];

export default function BrainstormingPage() {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.user);
  const canHost = user.role === "class-rep" || user.role === "brainstormer";
  const [question, setQuestion] = useState("");
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [sessionActive, setSessionActive] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState("");
  const [winnerList, setWinnerList] = useState<
    Array<{ name: string; points: number; time: number }>
  >([]);
  const [hasAnswered, setHasAnswered] = useState(false);

  const questionLive = useMemo(
    () =>
      sessionActive &&
      question.trim().length > 0 &&
      correctAnswer.trim().length > 0,
    [question, correctAnswer, sessionActive],
  );

  const startSession = () => {
    if (!question.trim() || !correctAnswer.trim()) {
      setMessage("Enter a question and the correct answer before launching.");
      return;
    }
    setSessionActive(true);
    setStartedAt(Date.now());
    setWinnerList([]);
    setMessage(
      "Brainstorming session launched. Students can submit answers now.",
    );
    setHasAnswered(false);
  };

  const endSession = () => {
    setSessionActive(false);
    setMessage("Session ended. Review the top answers and award points.");
  };

  const submitAnswer = () => {
    if (!questionLive || hasAnswered) return;
    if (!answer.trim()) {
      setMessage("Enter your answer before submitting.");
      return;
    }
    if (!startedAt) return;

    const elapsed = Date.now() - startedAt;
    const isCorrect =
      answer.trim().toLowerCase() === correctAnswer.trim().toLowerCase();
    const entries = [...simulatedContestants];
    const userEntry = { name: user.name, time: elapsed, points: 0 };

    if (isCorrect) {
      entries.push(userEntry);
      const sorted = entries.sort((a, b) => a.time - b.time).slice(0, 3);
      const rank = sorted.findIndex((entry) => entry.name === user.name);
      if (rank >= 0) {
        const awarded = [1000, 500, 200][rank];
        setWinnerList(
          sorted.map((entry, index) => ({
            ...entry,
            points: [1000, 500, 200][index] || entry.points || 0,
          })),
        );
        dispatch(awardPoints(awarded));
        setMessage(
          `Nice work! You were number ${rank + 1} and earned ${awarded} points.`,
        );
      } else {
        setWinnerList(sorted);
        setMessage(
          "Correct answer, but the first three spots were already taken.",
        );
      }
    } else {
      setWinnerList(simulatedContestants);
      setMessage("That answer is not correct yet. Try again faster next time.");
    }

    setHasAnswered(true);
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[1.5fr_0.9fr]">
        <section className="rounded-3xl border border-border bg-card p-6">
          <div className="mb-6">
            <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">
              Brainstorming
            </p>
            <h1 className="mt-2 text-3xl font-semibold">
              Host or join a live session
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Brainstormers can drop questions and award points to the first
              three fast correct answers.
            </p>
          </div>

          {!canHost && (
            <div className="rounded-3xl border border-border bg-background p-6">
              <p className="text-sm font-semibold text-foreground">
                Student view
              </p>
              <p className="mt-3 text-sm text-muted-foreground">
                Your class rep or brainstorming organizer can launch a session
                so you can answer live questions.
              </p>
            </div>
          )}

          {canHost && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Question
                </label>
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Type the brainstorming question here"
                  className="mt-2 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Correct answer
                </label>
                <input
                  value={correctAnswer}
                  onChange={(event) => setCorrectAnswer(event.target.value)}
                  placeholder="Enter the expected answer"
                  className="mt-2 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary"
                />
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={startSession}
                  className="inline-flex h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Launch session
                </button>
                <button
                  type="button"
                  onClick={endSession}
                  disabled={!sessionActive}
                  className="inline-flex h-12 items-center justify-center rounded-2xl border border-border bg-card px-5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  End session
                </button>
              </div>
            </div>
          )}

          <div className="mt-8 rounded-3xl border border-border bg-background p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Live question
            </p>
            {questionLive ? (
              <div className="mt-4 space-y-4">
                <p className="text-lg font-semibold">{question}</p>
                <p className="text-sm text-muted-foreground">
                  Answer quickly and correctly to earn points.
                </p>
                <div>
                  <label className="block text-sm font-medium text-muted-foreground">
                    Your answer
                  </label>
                  <input
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    disabled={!sessionActive || hasAnswered}
                    placeholder="Type your answer"
                    className="mt-2 w-full rounded-2xl border border-border bg-card px-4 py-3 text-sm outline-none transition-colors focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </div>
                <button
                  type="button"
                  onClick={submitAnswer}
                  disabled={!sessionActive || hasAnswered}
                  className="inline-flex h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Submit answer
                </button>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">
                No active brainstorm session right now. Wait for the host to
                launch one.
              </p>
            )}
            {message && (
              <p className="mt-4 rounded-2xl bg-primary/10 px-4 py-3 text-sm text-primary">
                {message}
              </p>
            )}
          </div>

          <div className="mt-6 rounded-3xl border border-border bg-card p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Recent winners
            </p>
            <div className="mt-4 space-y-3">
              {winnerList.length > 0 ? (
                winnerList.map((winner, index) => (
                  <div
                    key={`${winner.name}-${index}`}
                    className="rounded-2xl border border-border bg-background px-4 py-3"
                  >
                    <p className="font-medium">
                      {index + 1}. {winner.name}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {winner.points} points · {Math.round(winner.time / 1000)}s
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  First three correct answers will appear here.
                </p>
              )}
            </div>
          </div>
        </section>

        <aside className="space-y-6 rounded-3xl border border-border bg-card p-6">
          <div className="rounded-3xl border border-border bg-background p-4">
            <p className="text-sm text-muted-foreground">Your role</p>
            <p className="mt-1 text-lg font-semibold">
              {user.role.replace("-", " ")}
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-background p-4">
            <p className="text-sm text-muted-foreground">Points</p>
            <p className="mt-1 text-lg font-semibold">{user.points}</p>
          </div>

          <div className="rounded-3xl border border-border bg-background p-4">
            <p className="text-sm text-muted-foreground">Rank</p>
            <p className="mt-1 text-lg font-semibold">#{user.rank}</p>
          </div>

          <div className="rounded-3xl border border-border bg-background p-4">
            <p className="text-sm text-muted-foreground">School / set</p>
            <p className="mt-1 text-base font-semibold">
              {user.school} · {user.setName}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
