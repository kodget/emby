"use client";

import { useEffect, useState } from "react";
import { Plus, Users, Play, Clock, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import api from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

type Battle = {
  id: number;
  title: string;
  topic: string;
  difficulty: string;
  status: 'scheduled' | 'active' | 'completed';
  participants_count: number;
  time_per_question: number;
  created_at: string;
  host_name: string;
  host: number;
};

export function BattlesDashboard() {
  const [battles, setBattles] = useState<Battle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);

  useEffect(() => {
    const userStr = sessionStorage.getItem("user");
    if (userStr) setCurrentUserId(Number(JSON.parse(userStr).id));
    fetchBattles();
  }, []);

  const fetchBattles = async () => {
    try {
      const response = await api.get('/api/brain-battles/');
      setBattles(response.data.results || response.data);
    } catch (error) {
      console.error("Failed to fetch battles", error);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch(status) {
      case 'active': return <Badge className="bg-red-500 hover:bg-red-600 animate-pulse">Live Now</Badge>;
      case 'completed': return <Badge variant="secondary">Completed</Badge>;
      default: return <Badge variant="outline" className="border-emerald-500/50 text-emerald-500">Scheduled</Badge>;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-2">
            <Trophy className="h-8 w-8 text-yellow-500" />
            Brain Battles
          </h1>
          <p className="text-zinc-400 mt-1">
            Compete with your classmates in real-time quiz challenges!
          </p>
        </div>
        <Button asChild className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500">
          <Link href="/battles/create">
            <Plus className="mr-2 h-4 w-4" />
            Create Battle
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1,2,3].map(i => <Skeleton key={i} className="h-48 w-full rounded-xl bg-muted/20" />)}
        </div>
      ) : battles.length === 0 ? (
        <Card className="bg-muted/5 border-muted/20 border-dashed text-center py-12">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted/10 mb-4">
            <Trophy className="h-8 w-8 text-zinc-400" />
          </div>
          <CardTitle className="text-white text-xl">No Battles Yet</CardTitle>
          <p className="text-zinc-400 mt-2 mb-6">
            There are currently no active or scheduled battles for your class.
          </p>
          <Button asChild variant="outline" className="border-white/10 text-white">
            <Link href="/battles/create">Be the first to host one!</Link>
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {battles.map((battle) => (
            <Card key={battle.id} className="bg-muted/5 border-muted/20 hover:border-violet-500/50 transition-colors flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start mb-2">
                  {getStatusBadge(battle.status)}
                  <div className="flex items-center text-xs text-zinc-400 bg-white/10 px-2 py-1 rounded-full">
                    <Clock className="h-3 w-3 mr-1 text-zinc-400" />
                    {battle.time_per_question}s / Q
                  </div>
                </div>
                <CardTitle className="text-white text-lg line-clamp-1">{battle.title}</CardTitle>
                <CardDescription className="line-clamp-1 text-zinc-400">Host: {battle.host_name}</CardDescription>
              </CardHeader>
              
              <CardContent className="flex-grow">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Topic</span>
                    <span className="font-medium text-white line-clamp-1 text-right max-w-[150px]">{battle.topic}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Difficulty</span>
                    <span className="font-medium text-white capitalize">{battle.difficulty}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Participants</span>
                    <span className="font-medium text-white flex items-center">
                       <Users className="h-3 w-3 mr-1 text-zinc-400" />
                      {battle.participants_count}
                    </span>
                  </div>
                </div>
              </CardContent>
              
              <CardFooter className="pt-3 border-t border-muted/10">
                <Button 
                  asChild 
                  className={`w-full ${battle.status === 'active' ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : ''}`}
                  variant={battle.status === 'completed' ? 'secondary' : 'default'}
                >
                  <Link href={`/battles/${battle.id}`}>
                    {battle.status === 'active' ? (
                      <><Play className="mr-2 h-4 w-4" /> {currentUserId === battle.host ? "Host Battle" : "Join Battle"}</>
                    ) : battle.status === 'completed' ? (
                      <><Trophy className="mr-2 h-4 w-4" /> View Results</>
                    ) : (
                      <><Users className="mr-2 h-4 w-4" /> {currentUserId === battle.host ? "Host Battle" : "Enter Lobby"}</>
                    )}
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
