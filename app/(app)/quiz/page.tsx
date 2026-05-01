'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, Loader2, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { curriculumApi, quizApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useAppSelector } from '@/store/hooks';
import { UpgradeAlert } from '@/components/premium/upgrade-prompt';

export default function QuizSetupPage() {
  const router = useRouter();
  const { toast } = useToast();
  const user = useAppSelector(state => state.user);
  const isPremium = user.profile?.is_premium || false;

  const [loading, setLoading] = useState(false);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);

  const [quizType, setQuizType] = useState<'mcq' | 'theory'>('mcq');
  const [subject, setSubject] = useState('');
  const [block, setBlock] = useState('');
  const [topic, setTopic] = useState('');
  const [numQuestions, setNumQuestions] = useState(10);

  const maxQuestions = quizType === 'mcq' ? (isPremium ? 100 : 10) : 10;

  useEffect(() => {
    loadSubjects();
  }, []);

  useEffect(() => {
    if (subject) {
      loadBlocks(subject);
    }
  }, [subject]);

  useEffect(() => {
    if (block) {
      loadTopics(block);
    }
  }, [block]);

  const loadSubjects = async () => {
    try {
      const data = await curriculumApi.getSubjects();
      setSubjects(data);
    } catch (error) {
      console.error('Failed to load subjects:', error);
    }
  };

  const loadBlocks = async (subjectId: string) => {
    try {
      const data = await curriculumApi.getBlocks(subjectId);
      setBlocks(data);
      setBlock('');
      setTopic('');
    } catch (error) {
      console.error('Failed to load blocks:', error);
    }
  };

  const loadTopics = async (blockId: string) => {
    try {
      const data = await curriculumApi.getTopics(blockId);
      setTopics(data);
      setTopic('');
    } catch (error) {
      console.error('Failed to load topics:', error);
    }
  };

  const handleStartQuiz = async () => {
    if (!subject) {
      toast({
        title: 'Subject Required',
        description: 'Please select a subject to continue',
        variant: 'destructive',
      });
      return;
    }

    setLoading(true);

    try {
      const quiz = await quizApi.generateQuiz({
        quiz_type: quizType,
        subject,
        block: block || undefined,
        topic: topic || undefined,
        num_questions: numQuestions,
      });

      router.push(`/quiz/${quiz.id}`);
    } catch (error: any) {
      console.error('Failed to generate quiz:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.error || 'Failed to generate quiz',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container max-w-4xl py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Start a Quiz</h1>
        <p className="text-muted-foreground">
          Test your knowledge with MCQ or theory questions
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quiz Configuration</CardTitle>
          <CardDescription>
            Select your preferences to generate a personalized quiz
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Quiz Type */}
          <div className="space-y-3">
            <Label>Quiz Type</Label>
            <RadioGroup value={quizType} onValueChange={(v) => setQuizType(v as 'mcq' | 'theory')}>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="mcq" id="mcq" />
                <Label htmlFor="mcq" className="font-normal cursor-pointer">
                  Multiple Choice Questions (MCQ)
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="theory" id="theory" disabled={!isPremium} />
                <Label htmlFor="theory" className={`font-normal ${!isPremium ? 'text-muted-foreground' : 'cursor-pointer'}`}>
                  Theory Questions {!isPremium && <Lock className="inline h-3 w-3 ml-1" />}
                </Label>
              </div>
            </RadioGroup>
            {quizType === 'theory' && !isPremium && (
              <UpgradeAlert message="Theory questions are only available for Premium users. Upgrade to access up to 10 theory questions per quiz." />
            )}
          </div>

          {/* Subject */}
          <div className="space-y-3">
            <Label>Subject</Label>
            <Select value={subject} onValueChange={setSubject}>
              <SelectTrigger>
                <SelectValue placeholder="Select subject" />
              </SelectTrigger>
              <SelectContent>
                {subjects.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Block (Optional) */}
          {subject && blocks.length > 0 && (
            <div className="space-y-3">
              <Label>Block (Optional)</Label>
              <Select value={block} onValueChange={setBlock}>
                <SelectTrigger>
                  <SelectValue placeholder="All blocks" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All blocks</SelectItem>
                  {blocks.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Topic (Optional) */}
          {block && topics.length > 0 && (
            <div className="space-y-3">
              <Label>Topic (Optional)</Label>
              <Select value={topic} onValueChange={setTopic}>
                <SelectTrigger>
                  <SelectValue placeholder="All topics" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All topics</SelectItem>
                  {topics.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Number of Questions */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Number of Questions</Label>
              <span className="text-sm font-medium">{numQuestions}</span>
            </div>
            <Slider
              value={[numQuestions]}
              onValueChange={(v) => setNumQuestions(v[0])}
              min={5}
              max={maxQuestions}
              step={5}
            />
            <p className="text-xs text-muted-foreground">
              {isPremium
                ? quizType === 'mcq'
                  ? 'Premium: Up to 100 MCQ questions'
                  : 'Premium: Up to 10 theory questions'
                : 'Free: Up to 10 MCQ questions'}
            </p>
          </div>

          {!isPremium && quizType === 'mcq' && (
            <UpgradeAlert message="Upgrade to Premium to access up to 100 MCQ questions per quiz and unlock theory questions." />
          )}

          <Button
            onClick={handleStartQuiz}
            disabled={loading || !subject}
            className="w-full"
            size="lg"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating Quiz...
              </>
            ) : (
              <>
                <Brain className="mr-2 h-4 w-4" />
                Start Quiz
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
