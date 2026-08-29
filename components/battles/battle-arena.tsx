"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Trophy, Clock, Users, ArrowRight, Play, CheckCircle2, XCircle, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import api from "@/lib/api";

type BattleState = {
  status: 'scheduled' | 'active' | 'completed';
  current_question_index: number;
  total_questions: number;
  current_question?: {
    question: string;
    options: string[];
  };
};

type Participant = {
  id: number;
  user_name: string;
  score: number;
};

type AnswerData = {
  correct_index: number;
  explanation: string;
};

export function BattleArena({ battleId }: { battleId: string }) {
  const router = useRouter();
  const [ws, setWs] = useState<WebSocket | null>(null);
  
  const [battleState, setBattleState] = useState<BattleState | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isHost, setIsHost] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);

  // Gamification States
  const [view, setView] = useState<'lobby' | 'question' | 'leaderboard' | 'podium'>('lobby');
  const [timeLeft, setTimeLeft] = useState<number>(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [answerData, setAnswerData] = useState<AnswerData | null>(null);
  const [pointsEarned, setPointsEarned] = useState<number | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const playSound = (type: 'pop' | 'correct' | 'wrong' | 'tada') => {
    if (!soundEnabled) return;
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    if (type === 'pop') {
      osc.type = 'sine'; osc.frequency.setValueAtTime(440, ctx.currentTime);
      gain.gain.setValueAtTime(1, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
      osc.start(); osc.stop(ctx.currentTime + 0.1);
    } else if (type === 'correct') {
      osc.type = 'sine'; osc.frequency.setValueAtTime(600, ctx.currentTime); osc.frequency.setValueAtTime(800, ctx.currentTime + 0.1);
      gain.gain.setValueAtTime(1, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.start(); osc.stop(ctx.currentTime + 0.3);
    } else if (type === 'wrong') {
      osc.type = 'sawtooth'; osc.frequency.setValueAtTime(300, ctx.currentTime); osc.frequency.linearRampToValueAtTime(200, ctx.currentTime + 0.3);
      gain.gain.setValueAtTime(1, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.start(); osc.stop(ctx.currentTime + 0.3);
    } else if (type === 'tada') {
      osc.type = 'square'; osc.frequency.setValueAtTime(400, ctx.currentTime); osc.frequency.setValueAtTime(600, ctx.currentTime + 0.2); osc.frequency.setValueAtTime(800, ctx.currentTime + 0.4);
      gain.gain.setValueAtTime(1, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
      osc.start(); osc.stop(ctx.currentTime + 0.6);
    }
  };

  useEffect(() => {
    // Check if current user is host
    const userStr = sessionStorage.getItem("user");
    if (userStr) {
      const user = JSON.parse(userStr);
      setCurrentUserId(user.id);
      api.get(`/api/battles/${battleId}/`).then(res => {
        setIsHost(res.data.host === Number(user.id));
      }).catch(console.error);
    }

    const token = sessionStorage.getItem("token");
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const wsBase = baseUrl.replace(/^http/, 'ws');
    const wsUrl = `${wsBase}/ws/battle/${battleId}/?token=${token}`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("WS MESSAGE:", data);

      if (data.type === 'battle_state') {
        setBattleState(data.state);
        setParticipants(data.participants);
        if (data.state.status === 'scheduled') setView('lobby');
        if (data.state.status === 'active') setView('question');
        if (data.state.status === 'completed') setView('podium');
      } 
      else if (data.type === 'new_question') {
        setBattleState(prev => prev ? { 
          ...prev, 
          status: 'active',
          current_question_index: data.question_data.index,
          current_question: {
            question: data.question_data.question,
            options: data.question_data.options
          }
        } : null);
        setSelectedAnswer(null);
        setAnswerData(null);
        setPointsEarned(null);
        setView('question');
        startTimer(20); // TODO: get time from battle model correctly
        playSound('pop');
      }
      else if (data.type === 'show_answer') {
        clearInterval(timerRef.current!);
        setAnswerData(data.answer_data);
        setParticipants(data.participants);
        setView('leaderboard');
      }
      else if (data.type === 'answer_result') {
        setPointsEarned(data.points_earned);
        if (data.points_earned > 0) playSound('correct');
        else playSound('wrong');
      }
      else if (data.type === 'battle_ended') {
        setParticipants(data.participants);
        setView('podium');
        playSound('tada');
      }
    };

    setWs(socket);

    return () => {
      socket.close();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [battleId]);

  const startTimer = (seconds: number) => {
    setTimeLeft(seconds);
    if (timerRef.current) clearInterval(timerRef.current);
    
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          if (isHost && ws) {
            // Automatically show answer when time is up
            ws.send(JSON.stringify({ type: 'host_action', action: 'show_answer' }));
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleStart = () => {
    if (ws && isHost) {
      ws.send(JSON.stringify({ type: 'host_action', action: 'next_question' }));
    }
  };

  const handleNext = () => {
    if (ws && isHost) {
      if (battleState && battleState.current_question_index + 1 >= battleState.total_questions) {
        ws.send(JSON.stringify({ type: 'host_action', action: 'end_battle' }));
      } else {
        ws.send(JSON.stringify({ type: 'host_action', action: 'next_question' }));
      }
    }
  };

  const submitAnswer = (index: number) => {
    if (selectedAnswer !== null || !ws || isHost) return;
    setSelectedAnswer(index);
    ws.send(JSON.stringify({ 
      type: 'submit_answer', 
      answer_index: index,
      time_left_ms: timeLeft * 1000
    }));
  };

  if (!battleState) return <div className="text-center text-white py-20 text-xl animate-pulse">Connecting to Battle Arena...</div>;

  const SoundToggle = () => (
    <Button 
      variant="ghost" 
      size="icon" 
      onClick={() => setSoundEnabled(!soundEnabled)}
      className="absolute top-4 right-4 text-zinc-400 hover:text-white"
    >
      {soundEnabled ? <Volume2 className="h-6 w-6" /> : <VolumeX className="h-6 w-6" />}
    </Button>
  );

  // ==== LOBBY VIEW ====
  if (view === 'lobby') {
    return (
      <div className="max-w-4xl mx-auto text-center space-y-12 py-12 relative">
        <SoundToggle />
        <h1 className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-indigo-400 animate-pulse">
          Waiting for players...
        </h1>
        <div className="flex justify-center flex-wrap gap-4">
          {participants.length === 0 && <p className="text-zinc-400 italic">No one is here yet...</p>}
          {participants.map(p => (
            <Badge key={p.id} className="text-lg py-2 px-4 bg-white/10 hover:bg-white/20 animate-bounce">
              {p.user_name}
            </Badge>
          ))}
        </div>
        {isHost ? (
          <Button size="lg" className="bg-emerald-600 hover:bg-emerald-500 text-xl py-8 px-12 rounded-2xl" onClick={handleStart}>
            <Play className="mr-2 h-6 w-6" /> Start Battle
          </Button>
        ) : (
          <p className="text-zinc-400 text-xl">Waiting for host to start...</p>
        )}
      </div>
    );
  }

  // ==== PODIUM VIEW ====
  if (view === 'podium') {
    return (
      <div className="max-w-4xl mx-auto text-center space-y-12 py-12 relative">
        <SoundToggle />
        <h1 className="text-6xl font-black text-yellow-400 mb-12">Final results</h1>
        <div className="flex justify-center items-end gap-6 h-64">
          {/* 2nd Place */}
          {participants[1] && (
            <div className="flex flex-col items-center animate-fade-in-up delay-100">
              <span className="text-2xl font-bold text-gray-300 mb-2">{participants[1].user_name}</span>
              <div className="w-32 h-40 bg-gray-400 rounded-t-lg flex items-center justify-center text-4xl font-black">2</div>
              <span className="mt-2 text-xl">{participants[1].score} pts</span>
            </div>
          )}
          {/* 1st Place */}
          {participants[0] && (
            <div className="flex flex-col items-center animate-bounce z-10">
              <span className="text-3xl font-bold text-yellow-400 mb-2">{participants[0].user_name}</span>
              <div className="w-40 h-56 bg-yellow-500 rounded-t-lg flex items-center justify-center text-6xl font-black">1</div>
              <span className="mt-2 text-2xl font-bold">{participants[0].score} pts</span>
            </div>
          )}
          {/* 3rd Place */}
          {participants[2] && (
            <div className="flex flex-col items-center animate-fade-in-up delay-200">
              <span className="text-2xl font-bold text-orange-400 mb-2">{participants[2].user_name}</span>
              <div className="w-32 h-32 bg-orange-700 rounded-t-lg flex items-center justify-center text-4xl font-black">3</div>
              <span className="mt-2 text-xl">{participants[2].score} pts</span>
            </div>
          )}
        </div>
        <Button variant="outline" onClick={() => router.push('/battles')}>Back to Dashboard</Button>
      </div>
    );
  }

  // ==== QUESTION / LEADERBOARD VIEW ====
  const q = battleState.current_question;
  const isLeaderboard = view === 'leaderboard';

  return (
    <div className="max-w-5xl mx-auto space-y-8 relative">
      <SoundToggle />
      <div className="flex justify-between items-center bg-muted/10 p-4 rounded-xl border border-muted/20 mt-8">
        <Badge variant="secondary" className="text-lg py-1">Q {battleState.current_question_index + 1} / {battleState.total_questions}</Badge>
        <div className="flex items-center gap-2 text-2xl font-black text-emerald-400">
          <Clock className="h-6 w-6" /> {timeLeft}s
        </div>
      </div>

      {!isLeaderboard && q ? (
        <div className="space-y-8 text-center animate-fade-in">
          <h2 className="text-4xl font-bold text-white leading-tight">{q.question}</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-8">
            {q.options.map((opt, idx) => {
              const colors = ["bg-red-500", "bg-blue-500", "bg-yellow-500", "bg-green-500"];
              const isSelected = selectedAnswer === idx;
              
              return (
                <Button 
                  key={idx}
                  onClick={() => submitAnswer(idx)}
                  className={`h-32 text-2xl font-bold whitespace-normal ${colors[idx % 4]} hover:opacity-80 transition-all ${isSelected ? 'ring-4 ring-white scale-[1.02]' : ''} ${selectedAnswer !== null && !isSelected ? 'opacity-50' : ''}`}
                  disabled={selectedAnswer !== null || isHost}
                >
                  {opt}
                </Button>
              );
            })}
          </div>

          {selectedAnswer !== null && !isHost && (
            <p className="text-xl text-zinc-400 animate-pulse mt-8">Waiting for others...</p>
          )}
        </div>
      ) : isLeaderboard && answerData ? (
        <div className="space-y-8 animate-fade-in">
          <div className="text-center space-y-4">
            <h2 className="text-3xl font-bold text-white">Correct Answer</h2>
            <div className="p-6 bg-green-500/20 border-2 border-green-500 rounded-xl max-w-2xl mx-auto">
              <p className="text-2xl font-bold text-green-400">{q?.options[answerData.correct_index]}</p>
              <p className="text-zinc-400 mt-4 italic">{answerData.explanation}</p>
            </div>
            
            {!isHost && pointsEarned !== null && (
              <div className="py-4">
                {pointsEarned > 0 ? (
                  <div className="flex items-center justify-center text-2xl text-emerald-400 font-bold gap-2">
                    <CheckCircle2 className="h-8 w-8" /> +{pointsEarned} Points!
                  </div>
                ) : (
                  <div className="flex items-center justify-center text-2xl text-red-400 font-bold gap-2">
                    <XCircle className="h-8 w-8" /> Incorrect
                  </div>
                )}
              </div>
            )}
          </div>

          <Card className="bg-muted/10 border-muted/20 max-w-xl mx-auto">
            <CardHeader><CardTitle className="text-center text-2xl">Top 5 Leaderboard</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {participants.map((p, i) => (
                <div key={p.id} className="flex justify-between items-center p-3 rounded-lg bg-white/5">
                  <div className="flex items-center gap-4">
                    <span className="font-black text-xl text-zinc-400 w-6">{i + 1}.</span>
                    <span className="font-bold text-lg text-white">{p.user_name}</span>
                  </div>
                  <Badge variant="secondary" className="text-lg">{p.score}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          {isHost && (
            <div className="text-center pt-8">
              <Button size="lg" className="bg-blue-600 hover:bg-blue-500 text-xl py-6 px-12 rounded-xl" onClick={handleNext}>
                Next Question <ArrowRight className="ml-2" />
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
