"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, HelpCircle, CheckCircle, XCircle, Eye, EyeOff, Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";
import api from "@/lib/api";

interface PracticeQuestion {
  id: string;
  question_text: string;
  question_type: "mcq" | "theory";
  difficulty: "easy" | "medium" | "hard";
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  correct_option?: string;
  explanation?: string;
  model_answer?: string;
  topic_name?: string;
}

interface ReaderPracticePanelProps {
  slideId: string;
  slideTitle?: string;
}

export function ReaderPracticePanel({ slideId, slideTitle }: ReaderPracticePanelProps) {
  const { toast } = useToast();
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [revealedAnswers, setRevealedAnswers] = useState<Set<string>>(new Set());
  const [showModelAnswer, setShowModelAnswer] = useState<Record<string, boolean>>({});
  const [isOpen, setIsOpen] = useState(false);

  const loadQuestions = async () => {
    if (!slideId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/quiz/questions/?slide=${slideId}&practice=true`);
      setQuestions(response.data.questions || []);
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setRevealedAnswers(new Set());
      setShowModelAnswer({});
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || "Failed to load practice questions";
      setError(errorMsg);
      toast({
        title: "Error",
        description: errorMsg,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleMCQSelect = (questionId: string, option: string) => {
    setSelectedAnswers(prev => ({ ...prev, [questionId]: option }));
  };

  const revealAnswer = (questionId: string) => {
    setRevealedAnswers(prev => new Set([...prev, questionId]));
  };

  const toggleModelAnswer = (questionId: string) => {
    setShowModelAnswer(prev => ({ ...prev, [questionId]: !prev[questionId] }));
  };

  const currentQuestion = questions[currentQuestionIndex];
  const hasQuestions = questions.length > 0;

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button 
          variant="outline" 
          className="gap-2 bg-primary/5 border-primary/20 hover:bg-primary/10 text-primary"
          onClick={loadQuestions}
        >
          <Brain className="w-4 h-4" />
          Practice Questions
        </Button>
      </DialogTrigger>
      
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            Practice Questions
            {slideTitle && <span className="text-sm text-muted-foreground">• {slideTitle}</span>}
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center space-y-3">
                <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-sm text-muted-foreground">Loading practice questions...</p>
              </div>
            </div>
          )}

          {error && !loading && (
            <div className="text-center py-12 space-y-3">
              <XCircle className="w-12 h-12 text-rose-500 mx-auto" />
              <div>
                <h3 className="font-semibold text-rose-600">Could not load questions</h3>
                <p className="text-sm text-muted-foreground mt-1">{error}</p>
              </div>
              <Button onClick={loadQuestions} variant="outline" className="mt-4">
                Try Again
              </Button>
            </div>
          )}

          {hasQuestions && !loading && (
            <div className="space-y-6">
              {/* Question Navigator */}
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-1">
                  {questions.map((_, index) => (
                    <Button
                      key={index}
                      variant={index === currentQuestionIndex ? "default" : "outline"}
                      size="sm"
                      className="w-8 h-8 p-0 text-xs"
                      onClick={() => setCurrentQuestionIndex(index)}
                    >
                      {index + 1}
                    </Button>
                  ))}
                </div>
                <Badge variant="secondary">
                  {currentQuestionIndex + 1} of {questions.length}
                </Badge>
              </div>

              <Separator />

              {/* Current Question */}
              <AnimatePresence mode="wait">
                {currentQuestion && (
                  <motion.div
                    key={currentQuestion.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-3">
                          <Badge variant="outline" className="text-xs">
                            {currentQuestion.question_type.toUpperCase()}
                          </Badge>
                          <Badge variant="secondary" className="text-xs capitalize">
                            {currentQuestion.difficulty}
                          </Badge>
                          {currentQuestion.topic_name && (
                            <Badge variant="outline" className="text-xs text-primary border-primary/30">
                              {currentQuestion.topic_name}
                            </Badge>
                          )}
                        </div>
                        <p className="text-lg font-medium leading-relaxed">
                          {currentQuestion.question_text}
                        </p>
                      </div>
                    </div>

                    {/* MCQ Options */}
                    {currentQuestion.question_type === "mcq" && (
                      <div className="space-y-3">
                        {["A", "B", "C", "D"].map((option) => {
                          const optionText = (currentQuestion as any)[`option_${option.toLowerCase()}`];
                          if (!optionText) return null;
                          
                          const isSelected = selectedAnswers[currentQuestion.id] === option;
                          const isRevealed = revealedAnswers.has(currentQuestion.id);
                          const isCorrect = currentQuestion.correct_option === option;
                          
                          return (
                            <motion.button
                              key={option}
                              whileHover={{ scale: 1.01 }}
                              whileTap={{ scale: 0.99 }}
                              onClick={() => handleMCQSelect(currentQuestion.id, option)}
                              className={`w-full text-left p-4 rounded-xl border-2 transition-all flex items-start gap-3
                                ${isSelected ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}
                                ${isRevealed && isCorrect ? "border-emerald-500 bg-emerald-50" : ""}
                                ${isRevealed && isSelected && !isCorrect ? "border-rose-500 bg-rose-50" : ""}
                              `}
                            >
                              <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold
                                ${isSelected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}
                                ${isRevealed && isCorrect ? "bg-emerald-500 text-white" : ""}
                                ${isRevealed && isSelected && !isCorrect ? "bg-rose-500 text-white" : ""}
                              `}>
                                {isRevealed && isCorrect ? <CheckCircle className="w-4 h-4" /> :
                                 isRevealed && isSelected && !isCorrect ? <XCircle className="w-4 h-4" /> :
                                 option}
                              </div>
                              <span className="pt-0.5 leading-relaxed">{optionText}</span>
                            </motion.button>
                          );
                        })}

                        {/* Reveal Answer Button */}
                        <div className="pt-2">
                          {!revealedAnswers.has(currentQuestion.id) ? (
                            <Button
                              onClick={() => revealAnswer(currentQuestion.id)}
                              variant="outline"
                              className="gap-2"
                              disabled={!selectedAnswers[currentQuestion.id]}
                            >
                              <Eye className="w-4 h-4" />
                              Reveal Answer
                            </Button>
                          ) : (
                            <div className="space-y-3">
                              <div className="flex items-center gap-2 text-sm">
                                <CheckCircle className="w-4 h-4 text-emerald-500" />
                                <span>Correct answer: <strong>{currentQuestion.correct_option}</strong></span>
                              </div>
                              {currentQuestion.explanation && (
                                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                                  <p className="text-sm text-emerald-800">
                                    <strong>Explanation:</strong> {currentQuestion.explanation}
                                  </p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Theory Question */}
                    {currentQuestion.question_type === "theory" && (
                      <div className="space-y-4">
                        <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                          <p className="text-sm text-blue-800">
                            This is a theory question. Think through your answer, then reveal the model answer below.
                          </p>
                        </div>
                        
                        <div>
                          <Button
                            onClick={() => toggleModelAnswer(currentQuestion.id)}
                            variant="outline"
                            className="gap-2"
                          >
                            {showModelAnswer[currentQuestion.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            {showModelAnswer[currentQuestion.id] ? "Hide" : "Show"} Model Answer
                          </Button>
                          
                          {showModelAnswer[currentQuestion.id] && currentQuestion.model_answer && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              className="mt-3 p-4 rounded-lg bg-emerald-50 border border-emerald-200"
                            >
                              <h4 className="font-semibold text-emerald-800 mb-2">Model Answer:</h4>
                              <p className="text-sm text-emerald-800 leading-relaxed">
                                {currentQuestion.model_answer}
                              </p>
                            </motion.div>
                          )}
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Navigation */}
              <Separator />
              <div className="flex items-center justify-between">
                <Button
                  variant="outline"
                  onClick={() => setCurrentQuestionIndex(Math.max(0, currentQuestionIndex - 1))}
                  disabled={currentQuestionIndex === 0}
                >
                  Previous
                </Button>
                
                <Button
                  variant="outline"
                  onClick={() => setCurrentQuestionIndex(Math.min(questions.length - 1, currentQuestionIndex + 1))}
                  disabled={currentQuestionIndex === questions.length - 1}
                >
                  Next
                </Button>
              </div>

              {/* Full Exam CTA */}
              <Card className="border-dashed border-primary/30 bg-primary/5">
                <CardContent className="pt-6 text-center">
                  <h3 className="font-semibold mb-2">Ready for a Full Exam?</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Test your knowledge with a comprehensive quiz on this topic
                  </p>
                  <Button 
                    className="gap-2" 
                    onClick={() => {
                      setIsOpen(false);
                      // Navigate to quiz creation with current slide's topic pre-selected
                      window.location.href = "/quiz";
                    }}
                  >
                    <Brain className="w-4 h-4" />
                    Create Full Quiz
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}

          {!hasQuestions && !loading && !error && (
            <div className="text-center py-12 space-y-3">
              <HelpCircle className="w-12 h-12 text-muted-foreground mx-auto" />
              <div>
                <h3 className="font-semibold">No practice questions available</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Questions will be generated as more slides are processed.
                </p>
              </div>
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
