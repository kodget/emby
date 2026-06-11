"use client";

import { useEffect, useState } from "react";
import { authApi, statsApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import { Sparkles } from "lucide-react";

type GreetingData = {
  timeGreeting: string;
  motivationalMessage: string;
  emoji: string;
};

export function PersonalizedGreeting() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [greeting, setGreeting] = useState<GreetingData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadGreeting();
  }, []);

  const loadGreeting = async () => {
    try {
      const [profileData, statsData] = await Promise.all([
        authApi.getProfile(),
        statsApi.getMyStats().catch(() => null),
      ]);
      
      setProfile(profileData);
      const greetingData = generateGreeting(profileData, statsData);
      setGreeting(greetingData);
    } catch (error) {
      console.error("Failed to load greeting:", error);
    } finally {
      setLoading(false);
    }
  };

  const generateGreeting = (profile: UserProfile, stats: any): GreetingData => {
    const hour = new Date().getHours();
    let timeGreeting = "";
    
    if (hour < 12) {
      timeGreeting = "Good morning";
    } else if (hour < 17) {
      timeGreeting = "Good afternoon";
    } else if (hour < 21) {
      timeGreeting = "Good evening";
    } else {
      timeGreeting = "Hello";
    }

    // Generate motivational message based on user activity
    const messages = generateMotivationalMessages(profile, stats);
    const randomMessage = messages[Math.floor(Math.random() * messages.length)];

    return {
      timeGreeting,
      motivationalMessage: randomMessage.message,
      emoji: randomMessage.emoji,
    };
  };

  const generateMotivationalMessages = (profile: UserProfile, stats: any) => {
    const messages = [];
    // Parse first name from full_name
    const firstName = profile.full_name.split(' ')[0];

    // Streak-based messages
    if (profile.streak === 0) {
      messages.push({
        message: `Start your learning streak today`,
        emoji: "🎯",
      });
    } else if (profile.streak < 3) {
      messages.push({
        message: `You're building momentum. Keep it up!`,
        emoji: "💪",
      });
    } else if (profile.streak < 7) {
      messages.push({
        message: `${profile.streak} days strong! You're on fire!`,
        emoji: "🔥",
      });
    } else if (profile.streak < 14) {
      messages.push({
        message: `${profile.streak}-day streak! Consistency is key!`,
        emoji: "⭐",
      });
    } else if (profile.streak < 30) {
      messages.push({
        message: `${profile.streak} days! You're unstoppable!`,
        emoji: "🚀",
      });
    } else {
      messages.push({
        message: `${profile.streak}-day streak! You're a legend!`,
        emoji: "👑",
      });
    }

    // Points-based messages
    if (stats && stats.points > 0) {
      if (stats.points < 100) {
        messages.push({
          message: `Every point counts. Keep learning!`,
          emoji: "📚",
        });
      } else if (stats.points < 500) {
        messages.push({
          message: `${stats.points} points! You're making progress!`,
          emoji: "🌟",
        });
      } else if (stats.points < 1000) {
        messages.push({
          message: `${stats.points} points! Halfway to mastery!`,
          emoji: "💎",
        });
      } else {
        messages.push({
          message: `${stats.points} points! You're crushing it!`,
          emoji: "🏆",
        });
      }
    }

    // Rank-based messages
    if (stats && stats.rank) {
      if (stats.rank === 1) {
        messages.push({
          message: `You're #1! Keep defending that crown!`,
          emoji: "👑",
        });
      } else if (stats.rank <= 3) {
        messages.push({
          message: `Top 3! The podium is yours!`,
          emoji: "🥇",
        });
      } else if (stats.rank <= 10) {
        messages.push({
          message: `Top 10! You're among the best!`,
          emoji: "🌟",
        });
      }
    }

    // Study time-based messages
    if (stats && stats.total_study_minutes) {
      const hours = Math.floor(stats.total_study_minutes / 60);
      if (hours > 0) {
        messages.push({
          message: `${hours}+ hours of study time! Dedication pays off!`,
          emoji: "⏰",
        });
      }
    }

    // Slides completed messages
    if (stats && stats.slides_completed > 0) {
      if (stats.slides_completed < 10) {
        messages.push({
          message: `${stats.slides_completed} slides down! Keep the momentum!`,
          emoji: "📖",
        });
      } else if (stats.slides_completed < 50) {
        messages.push({
          message: `${stats.slides_completed} slides completed! You're on a roll!`,
          emoji: "🎯",
        });
      } else {
        messages.push({
          message: `${stats.slides_completed} slides! You're a reading machine!`,
          emoji: "📚",
        });
      }
    }

    // Generic motivational messages
    messages.push(
      {
        message: `Ready to conquer today's goals? Let's go!`,
        emoji: "💪",
      },
      {
        message: `Your future self will thank you for studying today!`,
        emoji: "🌟",
      },
      {
        message: `Small steps lead to big achievements!`,
        emoji: "🚀",
      },
      {
        message: `You're one study session away from a breakthrough!`,
        emoji: "✨",
      },
      {
        message: `Excellence is a habit. Let's build it today!`,
        emoji: "🎯",
      },
      {
        message: `Your dedication is inspiring! Keep pushing!`,
        emoji: "💎",
      },
      {
        message: `Success is built one day at a time!`,
        emoji: "🏆",
      },
      {
        message: `You've got this! Let's make today count!`,
        emoji: "🔥",
      }
    );

    return messages;
  };

  if (loading || !greeting || !profile) {
    return (
      <div className="mb-7 animate-pulse">
        <div className="mb-3 h-10 w-3/4 rounded-lg bg-muted" />
        <div className="h-6 w-1/2 rounded-lg bg-muted" />
      </div>
    );
  }

  return (
    <div className="rise-in mb-7">
      <p className="mb-2 inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
        <Sparkles className="size-3.5" aria-hidden="true" />
        {greeting.timeGreeting}
      </p>
      <h1 className="font-serif text-4xl font-semibold leading-[1.05] tracking-tight md:text-5xl">
        <span className="text-foreground">Welcome back, </span>
        <span className="text-gradient">{profile.full_name.split(" ")[0]}</span>
      </h1>
      <p className="mt-3 max-w-xl text-pretty text-base text-muted-foreground md:text-lg">
        {greeting.motivationalMessage}
      </p>
    </div>
  );
}
