"use client";

import { useState, useEffect } from "react";
import { X, Calendar, Clock, BookOpen, Wand2, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { studyPlannerApi, curriculumApi, StudyProfile, Subject } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface StudyPlannerWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function StudyPlannerWizard({ isOpen, onClose, onSuccess }: StudyPlannerWizardProps) {
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<StudyProfile | null>(null);
  
  const [examDate, setExamDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(120);
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>([]);
  const [availableSubjects, setAvailableSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(false);
  
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      loadProfileAndSubjects();
      setStep(1);
    }
  }, [isOpen]);

  const loadProfileAndSubjects = async () => {
    try {
      const [existing, subjects] = await Promise.all([
        studyPlannerApi.getProfile(),
        curriculumApi.getSubjects()
      ]);
      setAvailableSubjects(subjects);
      
      if (existing) {
        setProfile(existing);
        if (existing.exam_date) setExamDate(existing.exam_date);
        if (existing.daily_study_minutes) setDailyMinutes(existing.daily_study_minutes);
        if (existing.target_subjects) setSelectedSubjects(existing.target_subjects);
      }
    } catch (error) {
      console.error("Failed to load profile or subjects", error);
    }
  };

  const toggleSubject = (subjectId: string) => {
    setSelectedSubjects((prev) =>
      prev.includes(subjectId)
        ? prev.filter((id) => id !== subjectId)
        : [...prev, subjectId]
    );
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const data: StudyProfile = {
        exam_date: examDate || undefined,
        daily_study_minutes: dailyMinutes,
        target_subjects: selectedSubjects.length > 0 ? selectedSubjects : undefined,
      };
      
      if (profile && profile.id) {
        await studyPlannerApi.updateProfile(profile.id, data);
      } else {
        await studyPlannerApi.createProfile(data);
      }
      
      setStep(2); // Move to generation step
    } catch (error) {
      toast({
        title: "Error saving profile",
        description: "Please check your inputs and try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const result = await studyPlannerApi.generatePlan();
      toast({
        title: "Plan Generated!",
        description: result.detail,
      });
      onSuccess();
      onClose();
    } catch (error: any) {
      toast({
        title: "Error generating plan",
        description: error.response?.data?.detail || "Something went wrong.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-border bg-card shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border p-6">
          <div>
            <h2 className="font-serif text-2xl font-semibold">Study Planner</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {step === 1 ? "Configure your goals" : "Generate your schedule"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {step === 1 && (
            <div className="space-y-6">
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <Calendar className="size-4 text-primary" /> Target Exam Date
                  </label>
                  <input
                    type="date"
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground">
                    We'll schedule your study sessions leading up to this date.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <Clock className="size-4 text-primary" /> Daily Study Time (minutes)
                  </label>
                  <input
                    type="number"
                    min="15"
                    step="15"
                    value={dailyMinutes}
                    onChange={(e) => setDailyMinutes(parseInt(e.target.value) || 120)}
                    className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground">
                    How much time can you commit to studying every day?
                  </p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <BookOpen className="size-4 text-primary" /> Target Subjects
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Select the subjects you want to focus on. Leave empty to include all subjects.
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1 max-h-40 overflow-y-auto pr-2 pb-2">
                    {availableSubjects.map((subject) => {
                      const isSelected = selectedSubjects.includes(subject.id);
                      return (
                        <button
                          key={subject.id}
                          onClick={() => toggleSubject(subject.id)}
                          className={cn(
                            "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                            isSelected
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                          )}
                        >
                          {isSelected && <Check className="size-3" />}
                          {subject.name || (subject as any).title}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col items-center justify-center py-8 text-center space-y-4">
              <div className="rounded-full bg-primary/10 p-4">
                <Wand2 className="size-10 text-primary animate-pulse" />
              </div>
              <h3 className="font-serif text-xl">Generate Adaptive Plan</h3>
              <p className="text-sm text-muted-foreground max-w-sm">
                We'll analyze your past quiz performance, identify weak areas, and 
                create a balanced mix of reading, quizzes, and flashcards leading up to your exam.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-border bg-muted/20 p-6">
          <Button variant="outline" onClick={onClose} disabled={loading} className="rounded-full px-6">
            Cancel
          </Button>
          
          {step === 1 ? (
            <Button 
              onClick={handleSave} 
              disabled={loading || !examDate} 
              className="rounded-full px-6 bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {loading ? "Saving..." : "Next Step"}
            </Button>
          ) : (
            <Button 
              onClick={handleGenerate} 
              disabled={loading} 
              className="rounded-full px-6 bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              <Wand2 className="mr-2 size-4" />
              {loading ? "Generating..." : "Generate Plan"}
            </Button>
          )}
        </div>

      </div>
    </div>
  );
}
