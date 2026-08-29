"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Trophy, ArrowLeft, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import api from "@/lib/api";

type HierarchyItem = { id: number; name: string };

export function CreateBattle() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [title, setTitle] = useState("");
  const [difficulty, setDifficulty] = useState("mixed");
  const [numQuestions, setNumQuestions] = useState([10]);
  const [timePerQuestion, setTimePerQuestion] = useState([20]);

  // Hierarchy Data
  const [subjects, setSubjects] = useState<HierarchyItem[]>([]);
  const [blocks, setBlocks] = useState<HierarchyItem[]>([]);
  const [subBlocks, setSubBlocks] = useState<HierarchyItem[]>([]);
  const [topics, setTopics] = useState<HierarchyItem[]>([]);

  // Selected Hierarchy
  const [subjectId, setSubjectId] = useState<string>("");
  const [blockId, setBlockId] = useState<string>("");
  const [subBlockId, setSubBlockId] = useState<string>("");
  const [topicId, setTopicId] = useState<string>("");

  useEffect(() => {
    api.get('/api/subjects/').then(res => setSubjects(res.data.results || res.data)).catch(console.error);
  }, []);

  useEffect(() => {
    if (subjectId) {
      api.get(`/api/blocks/?subject=${subjectId}`).then(res => setBlocks(res.data.results || res.data)).catch(console.error);
      setBlockId(""); setSubBlockId(""); setTopicId("");
    }
  }, [subjectId]);

  useEffect(() => {
    if (blockId) {
      api.get(`/api/sub-blocks/?block=${blockId}`).then(res => setSubBlocks(res.data.results || res.data)).catch(console.error);
      setSubBlockId(""); setTopicId("");
    }
  }, [blockId]);

  useEffect(() => {
    if (subBlockId) {
      api.get(`/api/topics/?sub_block=${subBlockId}`).then(res => setTopics(res.data.results || res.data)).catch(console.error);
      setTopicId("");
    }
  }, [subBlockId]);

  const handleCreate = async () => {
    if (!title) return alert("Please enter a title");
    setIsSubmitting(true);
    
    try {
      const payload = {
        title,
        difficulty,
        num_questions: numQuestions[0],
        time_per_question: timePerQuestion[0],
        linked_subject: subjectId || null,
        linked_block: blockId || null,
        linked_sub_block: subBlockId || null,
        linked_topic: topicId || null,
        topic: title // fallback for AI if hierarchy is empty
      };
      
      const response = await api.post('/api/battles/', payload);
      router.push(`/battles/${response.data.id}`);
    } catch (error) {
      console.error("Failed to create battle", error);
      alert("Failed to create battle. Make sure you belong to a Class Group.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild className="rounded-full">
          <Link href="/battles"><ArrowLeft className="h-5 w-5" /></Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-2">
            <Trophy className="h-8 w-8 text-yellow-500" />
            Host a Brain Battle
          </h1>
          <p className="text-zinc-400 mt-1">Configure your game and let AI generate the questions.</p>
        </div>
      </div>

      <Card className="bg-white/5 border-white/10 shadow-2xl backdrop-blur-md">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-violet-400" /> Game Settings
          </CardTitle>
          <CardDescription className="text-zinc-400">Setup the rules and content for your battle.</CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label className="text-white">Battle Title <span className="text-red-500">*</span></Label>
            <Input 
              placeholder="e.g., Friday Anatomy Showdown!" 
              value={title} 
              onChange={e => setTitle(e.target.value)} 
              className="bg-white/5 border-white/10 hover:border-white/20 focus:border-violet-500/50 text-white placeholder:text-zinc-500 transition-colors"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-white">Subject</Label>
                <Select value={subjectId} onValueChange={setSubjectId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white data-[placeholder]:text-zinc-400 [&_svg]:text-zinc-400">
                    <SelectValue placeholder="Select Subject" />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map(s => <SelectItem key={s.id} value={s.id.toString()}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-white">Block</Label>
                <Select value={blockId} onValueChange={setBlockId} disabled={!subjectId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white data-[placeholder]:text-zinc-400 [&_svg]:text-zinc-400">
                    <SelectValue placeholder="Select Block" />
                  </SelectTrigger>
                  <SelectContent>
                    {blocks.map(b => <SelectItem key={b.id} value={b.id.toString()}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-white">Sub-Block</Label>
                <Select value={subBlockId} onValueChange={setSubBlockId} disabled={!blockId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white data-[placeholder]:text-zinc-400 [&_svg]:text-zinc-400">
                    <SelectValue placeholder="Select Sub-Block" />
                  </SelectTrigger>
                  <SelectContent>
                    {subBlocks.map(sb => <SelectItem key={sb.id} value={sb.id.toString()}>{sb.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-white">Topic</Label>
                <Select value={topicId} onValueChange={setTopicId} disabled={!subBlockId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white data-[placeholder]:text-zinc-400 [&_svg]:text-zinc-400">
                    <SelectValue placeholder="Select Topic" />
                  </SelectTrigger>
                  <SelectContent>
                    {topics.map(t => <SelectItem key={t.id} value={t.id.toString()}>{t.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-muted/10">
            <div className="space-y-2">
              <Label className="text-white">Difficulty</Label>
              <Select value={difficulty} onValueChange={setDifficulty}>
                <SelectTrigger className="bg-white/5 border-white/10 text-white data-[placeholder]:text-zinc-400 [&_svg]:text-zinc-400">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">Easy</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="hard">Hard</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-4">
              <div className="flex justify-between">
                <Label className="text-white">Number of Questions</Label>
                <span className="text-violet-400 font-bold">{numQuestions[0]}</span>
              </div>
              <Slider 
                value={numQuestions} 
                onValueChange={setNumQuestions} 
                min={5} max={40} step={1}
                className="py-2"
              />
            </div>

            <div className="space-y-4">
              <div className="flex justify-between">
                <Label className="text-white">Time per Question</Label>
                <span className="text-violet-400 font-bold">{timePerQuestion[0]}s</span>
              </div>
              <Slider 
                value={timePerQuestion} 
                onValueChange={setTimePerQuestion} 
                min={10} max={60} step={5}
                className="py-2"
              />
            </div>
          </div>
        </CardContent>
        <CardFooter className="pt-6 border-t border-muted/10">
          <Button 
            className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-6 text-lg rounded-xl shadow-lg shadow-violet-500/20"
            onClick={handleCreate}
            disabled={isSubmitting || !title}
          >
            {isSubmitting ? (
              <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Generating Questions...</>
            ) : (
              <><Trophy className="mr-2 h-5 w-5" /> Create & Generate Questions</>
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
