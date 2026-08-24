"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, Layers, ListChecks, ArrowRight, RefreshCw, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { statsApi } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

interface Recommendation {
  type: "flashcard" | "quiz_missed" | "quiz_weak" | "mixed";
  title: string;
  description: string;
  action_label: string;
  action_url: string;
}

export function StudyRecommendations() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const data = await statsApi.getRecommendations();
        setRecommendations(data.recommendations || []);
      } catch (error) {
        console.error("Failed to fetch recommendations", error);
      } finally {
        setLoading(false);
      }
    }

    fetchRecommendations();
  }, []);

  const getIcon = (type: string) => {
    switch (type) {
      case "flashcard": return <Layers className="w-5 h-5 text-violet-500" />;
      case "quiz_missed": return <RefreshCw className="w-5 h-5 text-amber-500" />;
      case "quiz_weak": return <ArrowRight className="w-5 h-5 text-rose-500" />;
      case "mixed": return <ListChecks className="w-5 h-5 text-emerald-500" />;
      default: return <Brain className="w-5 h-5 text-primary" />;
    }
  };

  const getBgColor = (type: string) => {
    switch (type) {
      case "flashcard": return "bg-violet-50 border-violet-100";
      case "quiz_missed": return "bg-amber-50 border-amber-100";
      case "quiz_weak": return "bg-rose-50 border-rose-100";
      case "mixed": return "bg-emerald-50 border-emerald-100";
      default: return "bg-slate-50 border-slate-100";
    }
  };

  if (loading) {
    return <Skeleton className="h-48 w-full rounded-2xl" />;
  }

  if (recommendations.length === 0) return null;

  return (
    <section className="rounded-3xl border border-border bg-card p-6 shadow-sm overflow-hidden relative">
      <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
        <Brain className="w-32 h-32" />
      </div>
      
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-primary" />
          <h2 className="text-xl font-bold tracking-tight">What to Study Now</h2>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <AnimatePresence>
          {recommendations.map((rec, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className={`p-4 rounded-2xl border ${getBgColor(rec.type)} flex flex-col justify-between h-full group hover:shadow-md transition-all cursor-pointer`}
            >
              <Link href={rec.action_url} className="absolute inset-0 z-10" aria-label={rec.title} />
              <div>
                <div className="flex items-start gap-3 mb-2">
                  <div className="mt-0.5 bg-white p-2 rounded-xl shadow-sm">
                    {getIcon(rec.type)}
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">{rec.title}</h3>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{rec.description}</p>
                  </div>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-end">
                <span className="text-xs font-medium text-foreground flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                  {rec.action_label} <ChevronRight className="w-3 h-3" />
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}
