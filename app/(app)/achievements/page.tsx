"use client";

import { useEffect, useState } from "react";
import { gamificationApi, GamificationAchievement, GamificationProfile } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Trophy, Star, Medal, Zap, BookOpen, Crown, Sword, Flame, CalendarCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState<GamificationAchievement[]>([]);
  const [profile, setProfile] = useState<GamificationProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [achData, profData] = await Promise.all([
          gamificationApi.getAchievements(),
          gamificationApi.getProfile()
        ]);
        setAchievements(achData);
        setProfile(profData);
      } catch (err) {
        console.error("Failed to load gamification data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case "graduation-cap": return <Star className="h-6 w-6" />;
      case "compass": return <BookOpen className="h-6 w-6" />;
      case "crown": return <Crown className="h-6 w-6" />;
      case "book-open": return <BookOpen className="h-6 w-6" />;
      case "sword": return <Sword className="h-6 w-6" />;
      case "flame": return <Flame className="h-6 w-6" />;
      case "calendar-check": return <CalendarCheck className="h-6 w-6" />;
      default: return <Medal className="h-6 w-6" />;
    }
  };

  const getRarityColor = (rarity: string) => {
    switch (rarity) {
      case "COMMON": return "bg-slate-200 text-slate-800";
      case "UNCOMMON": return "bg-green-100 text-green-800";
      case "RARE": return "bg-blue-100 text-blue-800";
      case "EPIC": return "bg-purple-100 text-purple-800";
      case "LEGENDARY": return "bg-orange-100 text-orange-800";
      default: return "bg-slate-200 text-slate-800";
    }
  };

  if (loading) {
    return (
      <div className="container max-w-5xl px-4 md:px-8 py-8 space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-48 rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-5xl px-4 md:px-8 py-8 space-y-12">
      {/* 1. Hero / Hero's Journey Banner */}
      {profile && (
        <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-indigo-950 via-slate-900 to-slate-950 p-8 shadow-2xl shadow-primary/10">
          <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-primary/20 blur-[100px]" />
          <div className="absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-purple-500/20 blur-[100px]" />
          
          <div className="relative z-10 grid gap-8 md:grid-cols-2 items-center">
            <div className="space-y-4">
              <div className="inline-flex items-center rounded-full border border-primary/50 bg-primary/10 px-3 py-1 text-sm font-medium text-primary backdrop-blur-sm">
                <Star className="mr-2 h-4 w-4" /> 
                Level {Math.floor(profile.xp / 1000) + 1} Scholar
              </div>
              <h1 className="text-4xl font-bold tracking-tight text-white flex items-center gap-3">
                <Trophy className="h-10 w-10 text-yellow-500 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]" />
                Quest Log
              </h1>
              <p className="text-slate-400 text-lg">
                Your journey through knowledge. Complete quests to earn legendary rewards and level up your skills.
              </p>
            </div>

            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm font-medium text-slate-300">
                  <span>Experience to next level</span>
                  <span>{profile.xp % 1000} / 1000 XP</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800 border border-slate-700">
                  <div 
                    className="h-full bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 shadow-[0_0_10px_rgba(99,102,241,0.5)] transition-all duration-1000" 
                    style={{ width: `${((profile.xp % 1000) / 1000) * 100}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="flex flex-col items-center justify-center rounded-xl bg-slate-800/50 p-3 border border-slate-700/50 backdrop-blur-sm">
                  <Zap className="mb-1 h-5 w-5 text-yellow-400" />
                  <span className="text-xl font-bold text-white">{profile.xp}</span>
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total XP</span>
                </div>
                <div className="flex flex-col items-center justify-center rounded-xl bg-slate-800/50 p-3 border border-slate-700/50 backdrop-blur-sm">
                  <Medal className="mb-1 h-5 w-5 text-blue-400" />
                  <span className="text-xl font-bold text-white">{profile.badges_count}</span>
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Badges</span>
                </div>
                <div className="flex flex-col items-center justify-center rounded-xl bg-slate-800/50 p-3 border border-slate-700/50 backdrop-blur-sm">
                  <Flame className="mb-1 h-5 w-5 text-orange-500" />
                  <span className="text-xl font-bold text-white">{profile.current_streak}</span>
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Streak</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Active Quests */}
      <div className="space-y-6">
        <div className="flex items-center gap-3 border-b pb-2">
          <Sword className="h-6 w-6 text-primary" />
          <h2 className="text-2xl font-bold tracking-tight">Active Quests</h2>
        </div>
        
        {achievements.filter(a => !a.is_completed).length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
            No active quests. You've completed them all!
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {achievements.filter(a => !a.is_completed).sort((a, b) => b.percentage - a.percentage).map((ach) => (
              <Card 
                key={ach.id} 
                className="group relative overflow-hidden border-border/50 bg-background/50 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-primary/5 hover:border-primary/30"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                
                <CardHeader className="pb-3 relative z-10">
                  <div className="flex justify-between items-start gap-4">
                    <div className="space-y-1.5">
                      <CardTitle className="text-lg leading-tight group-hover:text-primary transition-colors">{ach.name}</CardTitle>
                      <CardDescription className="line-clamp-2">{ach.description}</CardDescription>
                    </div>
                    {ach.badge && (
                      <div className="flex-shrink-0 p-3 rounded-xl bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3 shadow-[0_0_15px_rgba(var(--primary),0.2)]">
                        {getIcon(ach.badge.icon)}
                      </div>
                    )}
                  </div>
                </CardHeader>
                
                <CardContent className="relative z-10">
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium text-muted-foreground">Progress</span>
                        <span className="font-bold text-primary">{ach.progress} / {ach.target_value}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                        <div 
                          className="h-full bg-primary transition-all duration-1000 ease-out" 
                          style={{ width: `${ach.percentage}%` }}
                        />
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between pt-2">
                      {ach.badge && (
                        <Badge 
                          variant="outline" 
                          className={`font-semibold tracking-wide uppercase text-[10px] ${
                            ach.badge.rarity === 'LEGENDARY' ? 'border-orange-500 text-orange-500 drop-shadow-[0_0_5px_rgba(249,115,22,0.5)]' :
                            ach.badge.rarity === 'EPIC' ? 'border-purple-500 text-purple-500 drop-shadow-[0_0_5px_rgba(168,85,247,0.5)]' :
                            ach.badge.rarity === 'RARE' ? 'border-blue-500 text-blue-500 drop-shadow-[0_0_5px_rgba(59,130,246,0.5)]' :
                            ach.badge.rarity === 'UNCOMMON' ? 'border-green-500 text-green-500 drop-shadow-[0_0_5px_rgba(34,197,94,0.5)]' :
                            'border-slate-400 text-slate-500'
                          }`}
                        >
                          {ach.badge.rarity}
                        </Badge>
                      )}
                      {ach.percentage === 0 ? (
                        <span className="text-xs font-medium text-muted-foreground bg-secondary px-2 py-1 rounded-md flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50"></span>
                          Locked
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-muted-foreground bg-secondary px-2 py-1 rounded-md">
                          {100 - ach.percentage}% Remaining
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* 3. Completed Quests (Hall of Fame) */}
      <div className="space-y-6 pt-4">
        <div className="flex items-center gap-3 border-b pb-2">
          <Crown className="h-6 w-6 text-yellow-500" />
          <h2 className="text-2xl font-bold tracking-tight">Hall of Fame</h2>
        </div>
        
        {achievements.filter(a => a.is_completed).length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
            You haven't completed any quests yet. Get out there and learn!
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {achievements.filter(a => a.is_completed).map((ach) => (
              <Card 
                key={ach.id} 
                className="group relative overflow-hidden border-yellow-500/30 bg-gradient-to-br from-yellow-500/5 to-amber-500/10 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-yellow-500/10 hover:border-yellow-400/50"
              >
                {/* Glowing completed edge effect */}
                <div className="absolute top-0 right-0 w-24 h-24 pointer-events-none overflow-hidden z-20">
                  <div className="absolute top-[-30px] right-[-30px] w-64 h-64 bg-gradient-to-bl from-yellow-400/30 via-yellow-400/5 to-transparent rotate-45 transform origin-bottom-left" />
                </div>
                
                <CardHeader className="pb-3 relative z-10">
                  <div className="flex justify-between items-start gap-4">
                    <div className="space-y-1.5">
                      <CardTitle className="text-lg leading-tight text-foreground">{ach.name}</CardTitle>
                      <CardDescription className="line-clamp-2 text-foreground/80">{ach.description}</CardDescription>
                    </div>
                    {ach.badge && (
                      <div className="flex-shrink-0 p-3 rounded-xl bg-gradient-to-br from-yellow-300 to-amber-500 text-amber-950 shadow-[0_0_20px_rgba(252,211,77,0.4)]">
                        {getIcon(ach.badge.icon)}
                      </div>
                    )}
                  </div>
                </CardHeader>
                
                <CardContent className="relative z-10">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between pt-2">
                      {ach.badge && (
                        <Badge 
                          className="bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30 dark:text-yellow-400 font-bold tracking-wider border-0"
                        >
                          {ach.badge.rarity}
                        </Badge>
                      )}
                      <span className="text-sm font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1.5 bg-yellow-500/10 px-3 py-1 rounded-full border border-yellow-500/20">
                        Quest Complete
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
