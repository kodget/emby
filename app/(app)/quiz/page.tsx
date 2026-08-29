"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Clock,
  Target,
  Brain,
  BookOpen,
  Zap,
  Trophy,
  Sparkles,
  ChevronRight,
  Settings,
  Timer,
  Crown,
  CheckCircle,
  ArrowRight,
  Sprout,
  Flame,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import { quizApi } from "@/lib/api";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { PracticeArena } from "@/components/quiz/practice-arena";

interface Subject {
  id: string;
  name: string;
  description?: string;
}
interface Block {
  id: string;
  name: string;
  subject: string;
}
interface Topic {
  id: string;
  name: string;
  block: string;
}

interface QuizConfig {
  subject?: string;
  block?: string;
  topic?: string;
  slide?: string;
  exam_type: "practice" | "mock" | "formal";
  is_timed: boolean;
  duration_minutes?: number;
  configuration: {
    mcq_count: number;
    theory_count: number;
    difficulty: "easy" | "medium" | "hard";
    question_source?: "hierarchy" | "missed_questions" | "weak_areas" | "mixed_revision";
  };
}

const examTypes = [
  {
    type: "practice" as const,
    title: "Practice Quiz",
    description: "Relaxed learning with immediate feedback",
    icon: BookOpen,
    color: "bg-emerald-500",
    features: ["Instant feedback", "No time pressure", "Review answers"],
    premium: false,
  },
  {
    type: "mock" as const,
    title: "Mock Exam",
    description: "Exam simulation with detailed analysis",
    icon: Target,
    color: "bg-amber-500",
    features: ["Timed practice", "Performance analytics", "Detailed breakdown"],
    premium: true,
  },
  {
    type: "formal" as const,
    title: "Formal Assessment",
    description: "Official evaluation with certification",
    icon: Trophy,
    color: "bg-primary",
    features: [
      "Official scoring",
      "Certificate eligible",
      "Comprehensive report",
    ],
    premium: true,
  },
];

const difficultyLevels = [
  {
    value: "easy" as const,
    label: "Easy",
    description: "Foundation concepts",
    color: "text-emerald-600",
    icon: Sprout,
  },
  {
    value: "medium" as const,
    label: "Medium",
    description: "Applied knowledge",
    color: "text-amber-600",
    icon: Flame,
  },
  {
    value: "hard" as const,
    label: "Hard",
    description: "Advanced mastery",
    color: "text-rose-600",
    icon: Zap,
  },
];

import { Suspense } from "react";

function QuizConfigContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { isPremium } = useFeatureAccess();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [step, setStep] = useState<"subject" | "type" | "config" | "review">(
    "subject",
  );
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [creatingPractice, setCreatingPractice] = useState(false);
  const [creatingMissed, setCreatingMissed] = useState(false);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [slides, setSlides] = useState<any[]>([]);

  const [config, setConfig] = useState<QuizConfig>({
    exam_type: "practice",
    is_timed: false,
    configuration: { mcq_count: 5, theory_count: 1, difficulty: "medium", question_source: "hierarchy" },
  });

  useEffect(() => {
    loadSubjects();
  }, []);

  useEffect(() => {
    const subject = searchParams.get("subject") || undefined;
    const block = searchParams.get("block") || undefined;
    const topic = searchParams.get("topic") || undefined;
    const slide = searchParams.get("slide") || undefined;

    if (subject || block || topic || slide) {
      setConfig((prev) => ({
        ...prev,
        subject: subject || prev.subject,
        block: block || prev.block,
        topic: topic || prev.topic,
        slide: slide || prev.slide,
      }));
      setStep("type");
    }
  }, [searchParams]);
  useEffect(() => {
    if (config.subject) loadBlocks(config.subject);
  }, [config.subject]);
  useEffect(() => {
    if (config.block) loadTopics(config.block);
  }, [config.block]);
  useEffect(() => {
    if (config.topic) {
      loadSlides(undefined, config.topic);
    } else if (config.block) {
      loadSlides(config.block, undefined);
    } else {
      setSlides([]);
    }
  }, [config.block, config.topic]);

  const loadSlides = async (blockId?: string, topicId?: string) => {
    try {
      const { default: api } = await import("@/lib/api");
      let url = "";
      if (topicId) {
        url = `/api/slides/?topic=${topicId}`;
      } else if (blockId) {
        url = `/api/slides/?block=${blockId}`;
      } else {
        return;
      }
      const res = await api.get(url);
      setSlides(res.data);
    } catch {
      console.error("Failed to load slides");
    }
  };

  const loadSubjects = async () => {
    try {
      setLoading(true);
      const { default: api } = await import("@/lib/api");
      const res = await api.get("/api/subjects/");
      setSubjects(res.data);
    } catch {
      toast({
        title: "Error",
        description: "Failed to load subjects",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBlocks = async (subjectId: string) => {
    try {
      const { default: api } = await import("@/lib/api");
      const res = await api.get(`/api/blocks/?subject=${subjectId}`);
      setBlocks(res.data);
    } catch {
      console.error("Failed to load blocks");
    }
  };

  const loadTopics = async (blockId: string) => {
    try {
      const { default: api } = await import("@/lib/api");
      const res = await api.get(`/api/topics/?block=${blockId}`);
      setTopics(res.data);
    } catch {
      console.error("Failed to load topics");
    }
  };

  const limits = isPremium
    ? { mcq: 100, theory: 10, total: 110 }
    : { mcq: 5, theory: 1, total: 6 };
  const totalQuestions =
    config.configuration.mcq_count + config.configuration.theory_count;
  const isOverLimit = totalQuestions > limits.total;

  const selectedSubject = subjects.find((s) => s.id === config.subject);
  const selectedBlock = blocks.find((b) => b.id === config.block);
  const selectedTopic = topics.find((t) => t.id === config.topic);
  const selectedSlide = slides.find((sl) => sl.id === config.slide);
  const selectedExamType = examTypes.find((t) => t.type === config.exam_type);

  const startMissedQuestions = async () => {
    try {
      setCreatingMissed(true);
      const res = await quizApi.createQuizAttempt({
        exam_type: "practice",
        is_timed: false,
        configuration: {
          mcq_count: 10,
          theory_count: 0,
          difficulty: "medium",
          question_source: "missed_questions"
        }
      });
      toast({
        title: "Quiz Created!",
        description: "Redirecting to your exam...",
      });
      router.push(`/quiz/attempt/${res.id}`);
    } catch (error: any) {
      console.error("startMissedQuestions error:", error);
      const msg = error.response?.data?.error || "Failed to create quiz. Please try again.";
      toast({ title: "Could not start quiz", description: msg, variant: "destructive" });
    } finally {
      setCreatingMissed(false);
    }
  };

  const createQuiz = async () => {
    if (isOverLimit) {
      toast({
        title: "Error",
        description: "Too many questions for your plan",
        variant: "destructive",
      });
      return;
    }
    try {
      setCreating(true);
      const response = await quizApi.createQuizAttempt(config);
      toast({
        title: "Quiz Created!",
        description: "Redirecting to your exam...",
      });
      router.push(`/quiz/attempt/${response.id}`);
    } catch (error: any) {
      console.error("createQuiz error:", error);
      const data = error.response?.data;
      const msg =
        data?.error ||
        data?.detail ||
        data?.configuration?.[0] ||
        "Failed to create quiz. Please try again.";
      if (data?.upgrade_required) {
        toast({ title: "Upgrade Required", description: msg });
      } else {
        toast({
          title: "Could not start quiz",
          description: msg,
          variant: "destructive",
        });
      }
    } finally {
      setCreating(false);
    }
  };

  const steps = ["subject", "type", "config", "review"];

  if (!showAdvanced) {
    return (
      <PracticeArena
        onMissedQuestions={startMissedQuestions}
        creatingMissed={creatingMissed}
        onAdvanced={() => setShowAdvanced(true)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-linear-90-to-br from-background via-background to-accent/20">
      <div className="container max-w-4xl mx-auto py-8 px-4">
        <div className="flex justify-start mb-4">
          <Button variant="ghost" onClick={() => setShowAdvanced(false)} className="gap-2 text-muted-foreground hover:text-foreground">
            <ChevronRight className="w-4 h-4 rotate-180" /> Back to Practice Arena
          </Button>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-12 h-12 rounded-2xl bg-linear-to-br from-primary to-primary/60 flex items-center justify-center">
              <Brain className="w-6 h-6 text-primary-foreground" />
            </div>
            <h1 className="text-4xl font-display font-bold">
              Create Your Quiz
            </h1>
          </div>
          <p className="text-lg text-muted-foreground">
            Design the perfect assessment experience
          </p>
        </motion.div>

        {/* Progress Steps */}
        <div className="flex items-center justify-center mb-10">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${step === s ? "bg-primary text-primary-foreground shadow-lg" : i < steps.indexOf(step) ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground"}`}
              >
                {i < steps.indexOf(step) ? (
                  <CheckCircle className="w-5 h-5" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 3 && (
                <div
                  className={`w-16 h-1 mx-2 rounded-full transition-all duration-300 ${i < steps.indexOf(step) ? "bg-emerald-500" : "bg-muted"}`}
                />
              )}
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {/* Step 1: Subject */}
          {step === "subject" && (
            <motion.div
              key="subject"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <Card className="border-2 border-dashed border-primary/20 bg-linear-to-br from-primary/5 to-transparent">
                <CardHeader className="text-center">
                  <CardTitle className="text-2xl flex items-center justify-center gap-3">
                    <BookOpen className="w-8 h-8 text-primary" />
                    Choose Your Study Area
                  </CardTitle>
                  <CardDescription>
                    Select where you want to pull questions from
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-3">
                    <p className="text-sm font-medium">Question Source</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                      {[
                        { id: "hierarchy", label: "Specific Topic", icon: BookOpen, desc: "Choose a subject or block" },
                        { id: "missed_questions", label: "Missed Questions", icon: Flame, desc: "Review what you got wrong" },
                        { id: "weak_areas", label: "Weak Areas", icon: Brain, desc: "Target lowest accuracy topics" },
                        { id: "mixed_revision", label: "Mixed Revision", icon: Zap, desc: "Random practice" }
                      ].map((source) => (
                        <Card
                          key={source.id}
                          className={`cursor-pointer transition-all duration-200 hover:shadow-md ${config.configuration.question_source === source.id ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                          onClick={() =>
                            setConfig({
                              ...config,
                              configuration: { ...config.configuration, question_source: source.id as any },
                              subject: source.id === "hierarchy" ? config.subject : undefined,
                              block: source.id === "hierarchy" ? config.block : undefined,
                              topic: source.id === "hierarchy" ? config.topic : undefined,
                              slide: source.id === "hierarchy" ? config.slide : undefined,
                            })
                          }
                        >
                          <CardContent className="p-4 text-center">
                            <div className="flex justify-center mb-2">
                              <source.icon className="w-5 h-5 text-primary" />
                            </div>
                            <div className="font-medium text-sm">
                              {source.label}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              {source.desc}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>

                  {config.configuration.question_source === "hierarchy" && (
                    <div className="space-y-6 border-t pt-6">
                      <div className="space-y-3">
                        <p className="text-sm font-medium">Subject</p>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                          {loading
                            ? Array.from({ length: 6 }).map((_, i) => (
                              <div
                                key={i}
                                className="h-20 bg-muted animate-pulse rounded-lg"
                              />
                            ))
                            : subjects.map((subject) => (
                              <motion.div
                                key={subject.id}
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                              >
                                <Card
                                  className={`cursor-pointer transition-all duration-200 hover:shadow-md ${config.subject === subject.id ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                                  onClick={() =>
                                    setConfig({
                                      ...config,
                                      subject: subject.id,
                                      block: undefined,
                                      topic: undefined,
                                      slide: undefined,
                                    })
                                  }
                                >
                                  <CardContent className="p-4 text-center">
                                    <div className="font-medium text-sm">
                                      {subject.name}
                                    </div>
                                    {subject.description && (
                                      <div className="text-xs text-muted-foreground mt-1">
                                        {subject.description}
                                      </div>
                                    )}
                                  </CardContent>
                                </Card>
                              </motion.div>
                            ))}
                        </div>
                      </div>

                      {config.subject && blocks.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="space-y-3"
                        >
                          <p className="text-sm font-medium">
                            Block{" "}
                            <span className="text-muted-foreground">
                              (Optional)
                            </span>
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <Card
                              className={`cursor-pointer transition-all ${!config.block ? "ring-2 ring-emerald-500 bg-emerald-50" : "hover:border-primary/30"}`}
                              onClick={() =>
                                setConfig({
                                  ...config,
                                  block: undefined,
                                  topic: undefined,
                                  slide: undefined,
                                })
                              }
                            >
                              <CardContent className="p-4 text-center">
                                <div className="font-medium text-sm text-emerald-700">
                                  All Blocks
                                </div>
                              </CardContent>
                            </Card>
                            {blocks.map((block) => (
                              <Card
                                key={block.id}
                                className={`cursor-pointer transition-all ${config.block === block.id ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                                onClick={() =>
                                  setConfig({
                                    ...config,
                                    block: block.id,
                                    topic: undefined,
                                    slide: undefined,
                                  })
                                }
                              >
                                <CardContent className="p-4 text-center">
                                  <div className="font-medium text-sm">
                                    {block.name}
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </motion.div>
                      )}

                      {config.block && topics.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="space-y-3"
                        >
                          <p className="text-sm font-medium">
                            Sub-block{" "}
                            <span className="text-muted-foreground">
                              (Optional)
                            </span>
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <Card
                              className={`cursor-pointer transition-all ${!config.topic ? "ring-2 ring-emerald-500 bg-emerald-50" : "hover:border-primary/30"}`}
                              onClick={() =>
                                setConfig({ ...config, topic: undefined, slide: undefined })
                              }
                            >
                              <CardContent className="p-4 text-center">
                                <div className="font-medium text-sm text-emerald-700">
                                  All Sub-blocks
                                </div>
                              </CardContent>
                            </Card>
                            {topics.map((topic) => (
                              <Card
                                key={topic.id}
                                className={`cursor-pointer transition-all ${config.topic === topic.id ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                                onClick={() =>
                                  setConfig({ ...config, topic: topic.id, slide: undefined })
                                }
                              >
                                <CardContent className="p-4 text-center">
                                  <div className="font-medium text-sm">
                                    {topic.name}
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </motion.div>
                      )}

                      {(config.block || config.topic) && slides.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="space-y-3"
                        >
                          <p className="text-sm font-medium">
                            Topic (Slide){" "}
                            <span className="text-muted-foreground">
                              (Optional)
                            </span>
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <Card
                              className={`cursor-pointer transition-all ${!config.slide ? "ring-2 ring-emerald-500 bg-emerald-50" : "hover:border-primary/30"}`}
                              onClick={() =>
                                setConfig({ ...config, slide: undefined })
                              }
                            >
                              <CardContent className="p-4 text-center">
                                <div className="font-medium text-sm text-emerald-700">
                                  All Topics / Slides
                                </div>
                              </CardContent>
                            </Card>
                            {slides.map((slide) => (
                              <Card
                                key={slide.id}
                                className={`cursor-pointer transition-all ${config.slide === slide.id ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                                onClick={() =>
                                  setConfig({ ...config, slide: slide.id })
                                }
                              >
                                <CardContent className="p-4 text-center">
                                  <div className="font-medium text-sm">
                                    {slide.title}
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </div>
                  )}

                  <div className="flex justify-end pt-4">
                    <Button
                      onClick={() => setStep("type")}
                      disabled={!config.subject}
                      size="lg"
                      className="gap-2 px-8"
                    >
                      Continue <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Step 2: Exam Type */}
          {step === "type" && (
            <motion.div
              key="type"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <Card className="border-2 border-dashed border-primary/20 bg-linear-to-br from-primary/5 to-transparent">
                <CardHeader className="text-center">
                  <CardTitle className="text-2xl flex items-center justify-center gap-3">
                    <Target className="w-8 h-8 text-primary" />
                    Choose Exam Type
                  </CardTitle>
                  <CardDescription>
                    Select the format that matches your learning goals
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid gap-4">
                    {examTypes.map((et) => {
                      const Icon = et.icon;
                      const locked = et.premium && !isPremium;
                      return (
                        <motion.div
                          key={et.type}
                          whileHover={{ scale: locked ? 1 : 1.01 }}
                        >
                          <Card
                            className={`cursor-pointer transition-all relative overflow-hidden ${config.exam_type === et.type ? "ring-2 ring-primary bg-primary/5 shadow-lg" : locked ? "opacity-60 cursor-not-allowed" : "hover:border-primary/30 hover:shadow-md"}`}
                            onClick={() => {
                              if (!locked)
                                setConfig({ ...config, exam_type: et.type });
                            }}
                          >
                            <CardContent className="p-6">
                              <div className="flex items-start gap-4">
                                <div
                                  className={`w-14 h-14 rounded-2xl ${et.color} flex items-center justify-center shrink-0`}
                                >
                                  <Icon className="w-7 h-7 text-white" />
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <h3 className="text-lg font-semibold">
                                      {et.title}
                                    </h3>
                                    {et.premium && (
                                      <Badge
                                        variant={
                                          locked ? "secondary" : "default"
                                        }
                                        className="gap-1"
                                      >
                                        <Crown className="w-3 h-3" />
                                        Premium
                                      </Badge>
                                    )}
                                  </div>
                                  <p className="text-muted-foreground text-sm mb-3">
                                    {et.description}
                                  </p>
                                  <div className="flex flex-wrap gap-2">
                                    {et.features.map((f, i) => (
                                      <Badge
                                        key={i}
                                        variant="outline"
                                        className="text-xs"
                                      >
                                        {f}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                                {config.exam_type === et.type && (
                                  <motion.div
                                    initial={{ scale: 0 }}
                                    animate={{ scale: 1 }}
                                    className="w-6 h-6 rounded-full bg-primary flex items-center justify-center"
                                  >
                                    <CheckCircle className="w-4 h-4 text-primary-foreground" />
                                  </motion.div>
                                )}
                              </div>
                            </CardContent>
                          </Card>
                        </motion.div>
                      );
                    })}
                  </div>
                  <div className="flex justify-between pt-4">
                    <Button
                      variant="outline"
                      onClick={() => setStep("subject")}
                      className="gap-2"
                    >
                      <ChevronRight className="w-4 h-4 rotate-180" />
                      Back
                    </Button>
                    <Button
                      onClick={() => setStep("config")}
                      size="lg"
                      className="gap-2 px-8"
                    >
                      Continue <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Step 3: Configuration */}
          {step === "config" && (
            <motion.div
              key="config"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <Card className="border-2 border-dashed border-primary/20 bg-linear-to-br from-primary/5 to-transparent">
                <CardHeader className="text-center">
                  <CardTitle className="text-2xl flex items-center justify-center gap-3">
                    <Settings className="w-8 h-8 text-primary" />
                    Configure Your Quiz
                  </CardTitle>
                  <CardDescription>
                    Customize difficulty and question distribution
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                  {/* Difficulty */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      <Zap className="w-5 h-5 text-primary" />
                      Difficulty Level
                    </h3>
                    <div className="grid grid-cols-3 gap-4">
                      {difficultyLevels.map((level) => (
                        <motion.div
                          key={level.value}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          <Card
                            className={`cursor-pointer transition-all ${config.configuration.difficulty === level.value ? "ring-2 ring-primary bg-primary/5" : "hover:border-primary/30"}`}
                            onClick={() =>
                              setConfig({
                                ...config,
                                configuration: {
                                  ...config.configuration,
                                  difficulty: level.value,
                                },
                              })
                            }
                          >
                            <CardContent className="p-4 text-center">
                              <level.icon className={`mx-auto mb-2 size-6 ${level.color}`} aria-hidden="true" />
                              <div className={`font-semibold ${level.color}`}>
                                {level.label}
                              </div>
                              <div className="text-xs text-muted-foreground mt-1">
                                {level.description}
                              </div>
                            </CardContent>
                          </Card>
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* Question Counts */}
                  <div className="space-y-6">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      <Brain className="w-5 h-5 text-primary" />
                      Question Distribution
                    </h3>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="font-medium">
                          Multiple Choice Questions
                        </label>
                        <Badge
                          variant={
                            config.configuration.mcq_count > limits.mcq
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {config.configuration.mcq_count} / {limits.mcq}
                        </Badge>
                      </div>
                      <Slider
                        value={[config.configuration.mcq_count]}
                        onValueChange={([v]) =>
                          setConfig({
                            ...config,
                            configuration: {
                              ...config.configuration,
                              mcq_count: v,
                            },
                          })
                        }
                        max={limits.mcq}
                        min={0}
                        step={1}
                      />
                    </div>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="font-medium">Theory Questions</label>
                        <Badge
                          variant={
                            config.configuration.theory_count > limits.theory
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {config.configuration.theory_count} / {limits.theory}
                        </Badge>
                      </div>
                      <Slider
                        value={[config.configuration.theory_count]}
                        onValueChange={([v]) =>
                          setConfig({
                            ...config,
                            configuration: {
                              ...config.configuration,
                              theory_count: v,
                            },
                          })
                        }
                        max={limits.theory}
                        min={0}
                        step={1}
                      />
                    </div>
                    <div className="p-4 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">Total Questions</span>
                        <span
                          className={`font-semibold ${isOverLimit ? "text-destructive" : "text-primary"}`}
                        >
                          {totalQuestions} / {limits.total}
                        </span>
                      </div>
                      <Progress
                        value={(totalQuestions / limits.total) * 100}
                        className="h-2"
                      />
                    </div>
                  </div>

                  <Separator />

                  {/* Timer */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      <Timer className="w-5 h-5 text-primary" />
                      Timer Settings
                    </h3>
                    <div className="flex items-center justify-between p-4 rounded-lg border">
                      <div>
                        <div className="font-medium">Timed Exam</div>
                        <div className="text-sm text-muted-foreground">
                          Add time pressure for realistic simulation
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={config.is_timed}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            is_timed: e.target.checked,
                            duration_minutes: e.target.checked ? 30 : undefined,
                          })
                        }
                        className="w-5 h-5 cursor-pointer"
                      />
                    </div>
                    {config.is_timed && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <label className="font-medium">
                            Duration (minutes)
                          </label>
                          <Badge variant="outline">
                            {config.duration_minutes} min
                          </Badge>
                        </div>
                        <Slider
                          value={[config.duration_minutes || 30]}
                          onValueChange={([v]) =>
                            setConfig({ ...config, duration_minutes: v })
                          }
                          max={180}
                          min={10}
                          step={5}
                        />
                      </motion.div>
                    )}
                  </div>

                  <div className="flex justify-between pt-4">
                    <Button
                      variant="outline"
                      onClick={() => setStep("type")}
                      className="gap-2"
                    >
                      <ChevronRight className="w-4 h-4 rotate-180" />
                      Back
                    </Button>
                    <Button
                      onClick={() => setStep("review")}
                      disabled={totalQuestions === 0}
                      size="lg"
                      className="gap-2 px-8"
                    >
                      Review Quiz <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Step 4: Review */}
          {step === "review" && (
            <motion.div
              key="review"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <Card className="border-2 border-primary bg-linear-to-br from-primary/5 to-transparent">
                <CardHeader className="text-center">
                  <CardTitle className="text-2xl flex items-center justify-center gap-3">
                    <CheckCircle className="w-8 h-8 text-primary" />
                    Review Your Quiz
                  </CardTitle>
                  <CardDescription>
                    Everything look good? Let&apos;s begin!
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="space-y-3">
                      <h3 className="font-semibold">Study Scope</h3>
                      <div className="space-y-2">
                        {selectedSubject && (
                          <div className="flex items-center gap-3 p-3 rounded-lg bg-card">
                            <span className="font-medium">Subject:</span>
                            <span>{selectedSubject.name}</span>
                          </div>
                        )}
                        {selectedBlock && (
                          <div className="flex items-center gap-3 p-3 rounded-lg bg-card">
                            <span className="font-medium">Block:</span>
                            <span>{selectedBlock.name}</span>
                          </div>
                        )}
                        {selectedTopic && (
                          <div className="flex items-center gap-3 p-3 rounded-lg bg-card">
                            <span className="font-medium">Sub-block:</span>
                            <span>{selectedTopic.name}</span>
                          </div>
                        )}
                        {selectedSlide && (
                          <div className="flex items-center gap-3 p-3 rounded-lg bg-card">
                            <span className="font-medium">Topic (Slide):</span>
                            <span>{selectedSlide.title}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-card">
                          <span className="font-medium">Type:</span>
                          <span className="capitalize">{config.exam_type}</span>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <Card>
                        <CardContent className="p-4 text-center">
                          <div className="text-2xl font-bold text-primary">
                            {config.configuration.mcq_count}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            MCQ
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4 text-center">
                          <div className="text-2xl font-bold text-emerald-500">
                            {config.configuration.theory_count}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Theory
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4 text-center">
                          <div className="text-2xl font-bold text-amber-500 capitalize">
                            {config.configuration.difficulty}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Difficulty
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4 text-center">
                          <div className="text-2xl font-bold text-foreground">
                            {config.is_timed
                              ? `${config.duration_minutes}m`
                              : "None"}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Timer
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>

                  <div className="text-center p-6 rounded-xl bg-linear-to-br from-primary/10 to-primary/5 border border-primary/20">
                    <div className="flex items-center justify-center gap-4">
                      <Button
                        variant="outline"
                        onClick={() => setStep("config")}
                        className="gap-2"
                      >
                        <ChevronRight className="w-4 h-4 rotate-180" />
                        Make Changes
                      </Button>
                      <Button
                        onClick={createQuiz}
                        disabled={creating}
                        size="lg"
                        className="gap-2 px-8 bg-linear-to-r from-primary to-primary/80"
                      >
                        {creating ? (
                          <>
                            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            Creating...
                          </>
                        ) : (
                          <>
                            <Flame className="w-4 h-4" />
                            Start Quiz
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function QuizConfigPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin" /></div>}>
      <QuizConfigContent />
    </Suspense>
  );
}
