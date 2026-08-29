"use client";

/**
 * The whole practice flow for one mode: setup → round → results.
 *
 * Steeplechase and Histology differ only by the `mode` passed in, so both routes mount
 * this and nothing about the mechanic is written twice.
 */

import { useState } from "react";

import AuthGuard from "@/components/auth/auth-guard";
import { PracticeResultsView } from "@/components/practice/practice-results";
import { PracticeRunner } from "@/components/practice/practice-runner";
import { PracticeSetup } from "@/components/practice/practice-setup";
import type { PracticeMode, PracticeStation } from "@/lib/api";

type Phase =
  | { name: "setup" }
  | {
      name: "running";
      sessionId: string;
      station: PracticeStation;
      total: number;
      seconds: number;
    }
  | { name: "results"; sessionId: string };

export function PracticeScreen({ mode }: { mode: PracticeMode }) {
  const [phase, setPhase] = useState<Phase>({ name: "setup" });

  return (
    <AuthGuard>
      {phase.name === "setup" && (
        <PracticeSetup
          mode={mode}
          onStarted={(payload) =>
            setPhase({
              name: "running",
              sessionId: payload.session_id,
              station: payload.station,
              total: payload.total_stations,
              seconds: payload.seconds_per_station,
            })
          }
        />
      )}

      {phase.name === "running" && (
        <PracticeRunner
          // Remounting per session guarantees no timer or answer state survives a round.
          key={phase.sessionId}
          mode={mode}
          sessionId={phase.sessionId}
          firstStation={phase.station}
          totalStations={phase.total}
          secondsPerStation={phase.seconds}
          onFinished={(sessionId) => setPhase({ name: "results", sessionId })}
        />
      )}

      {phase.name === "results" && (
        <PracticeResultsView
          sessionId={phase.sessionId}
          onAgain={() => setPhase({ name: "setup" })}
        />
      )}
    </AuthGuard>
  );
}
