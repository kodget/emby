"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Clock, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExamTimerProps {
  totalSeconds: number;
  remainingSeconds: number;
  onTick: () => void;
  onExpire: () => void;
  active: boolean;
}

function formatTime(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return h + ":" + String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
  return String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
}

export function ExamTimer({ totalSeconds, remainingSeconds, onTick, onExpire, active }: ExamTimerProps) {
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active) return;
    ref.current = setInterval(onTick, 1000);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [active, onTick]);

  useEffect(() => {
    if (remainingSeconds === 0) {
      if (ref.current) clearInterval(ref.current);
      onExpire();
    }
  }, [remainingSeconds, onExpire]);

  let pct = totalSeconds > 0 ? (remainingSeconds / totalSeconds) * 100 : 0;
  if (isNaN(pct) || !isFinite(pct)) pct = 0;
  const warn = pct <= 25;
  const danger = pct <= 10;
  const C = 2 * Math.PI * 18;

  return (
    <div className={cn(
      "flex items-center gap-2 px-3 py-2 rounded-xl border transition-all",
      danger ? "bg-rose-50 border-rose-200" : warn ? "bg-amber-50 border-amber-200" : "bg-card"
    )}>
      <div className="relative w-10 h-10">
        <svg className="w-10 h-10 -rotate-90" viewBox="0 0 40 40">
          <circle cx="20" cy="20" r="18" fill="none" strokeWidth="3"
            className={cn("transition-colors", danger ? "stroke-rose-100" : warn ? "stroke-amber-100" : "stroke-muted")} />
          <circle cx="20" cy="20" r="18" fill="none" strokeWidth="3" strokeLinecap="round"
            strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)}
            className={cn("transition-all duration-1000", danger ? "stroke-rose-500" : warn ? "stroke-amber-500" : "stroke-primary")} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          {danger
            ? <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1 }}>
                <AlertTriangle className="w-4 h-4 text-rose-500" />
              </motion.div>
            : <Clock className={cn("w-4 h-4", warn ? "text-amber-500" : "text-primary")} />
          }
        </div>
      </div>
      <span className={cn("font-mono font-semibold text-base tabular-nums",
        danger ? "text-rose-600" : warn ? "text-amber-600" : "text-foreground")}>
        {formatTime(remainingSeconds)}
      </span>
    </div>
  );
}
