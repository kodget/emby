"use client";

import { useEffect, useState } from "react";
import { Clock, Calendar } from "lucide-react";
import { classApi, ExamCountdown } from "@/lib/api";

export function ExamCountdownWidget() {
  const [countdowns, setCountdowns] = useState<ExamCountdown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCountdowns();
  }, []);

  const loadCountdowns = async () => {
    try {
      const data = await classApi.getExamCountdowns();
      const sorted = data.sort((a, b) => 
        new Date(a.exam_date).getTime() - new Date(b.exam_date).getTime()
      );
      setCountdowns(sorted.slice(0, 3));
    } catch (error) {
      console.error("Failed to load countdowns:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (countdowns.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <Calendar className="w-6 h-6 text-purple-600" />
        <h3 className="text-lg font-bold text-gray-900">Upcoming Exams</h3>
      </div>

      <div className="space-y-3">
        {countdowns.slice(0, 3).map((countdown) => (
          <div key={countdown.id} className="p-3 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg">
            <div className="font-semibold text-gray-900 mb-1">{countdown.title}</div>
            <div className="flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-gray-600" />
              <span className={`font-bold ${
                countdown.days_remaining <= 7 ? "text-red-600" :
                countdown.days_remaining <= 14 ? "text-orange-600" :
                "text-green-600"
              }`}>
                {countdown.days_remaining} days
              </span>
              <span className="text-gray-600">remaining</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
