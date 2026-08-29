"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Swords, Trophy, Sparkles, Plus } from "lucide-react";
import { motion } from "framer-motion";

export default function BrainstormingPage() {
  return (
    <div className="min-h-screen bg-background bg-[url('/grid.svg')] flex items-center justify-center p-4">
      <div className="max-w-4xl w-full space-y-12">
        {/* Header Section */}
        <div className="text-center space-y-4">
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", duration: 0.8 }}
            className="w-20 h-20 bg-gradient-to-br from-primary to-indigo-600 rounded-2xl mx-auto flex items-center justify-center shadow-lg shadow-primary/20"
          >
            <Sparkles className="w-10 h-10 text-foreground" />
          </motion.div>
          <motion.h1
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-4xl md:text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white to-white/60 tracking-tight"
          >
            Brain Battles
          </motion.h1>
          <motion.p
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-xl text-muted-foreground max-w-2xl mx-auto"
          >
            Challenge your classmates in real-time, test your knowledge, and claim your spot on the leaderboard.
          </motion.p>
        </div>

        {/* Action Buttons Section */}
        <motion.div
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="grid md:grid-cols-2 gap-6"
        >
          {/* Join Battle */}
          <Link href="/battles">
            <Card className="group relative overflow-hidden bg-card border-border hover:border-primary/50 transition-all duration-300 hover:shadow-2xl hover:shadow-primary/20 p-8 h-full flex flex-col items-center justify-center text-center space-y-6">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-indigo-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              
              <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Swords className="w-12 h-12 text-primary" />
              </div>
              
              <div className="space-y-2 relative z-10">
                <h3 className="text-2xl font-bold text-foreground group-hover:text-primary transition-colors">Join a Battle</h3>
                <p className="text-muted-foreground">
                  Enter an existing lobby, answer fast, and earn points against your peers.
                </p>
              </div>

              <Button size="lg" className="w-full bg-muted hover:bg-primary text-foreground border-0 mt-4">
                Enter Lobby <Trophy className="w-4 h-4 ml-2" />
              </Button>
            </Card>
          </Link>

          {/* Host Battle */}
          <Link href="/battles/create">
            <Card className="group relative overflow-hidden bg-card border-border hover:border-mastery/50 transition-all duration-300 hover:shadow-2xl hover:shadow-mastery/20 p-8 h-full flex flex-col items-center justify-center text-center space-y-6">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-600/10 to-teal-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              
              <div className="w-24 h-24 bg-mastery/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Trophy className="w-12 h-12 text-mastery" />
              </div>
              
              <div className="space-y-2 relative z-10">
                <h3 className="text-2xl font-bold text-foreground group-hover:text-mastery transition-colors">Host a Battle</h3>
                <p className="text-muted-foreground">
                  Create a custom quiz room and act as the gamemaster for your class.
                </p>
              </div>

              <Button size="lg" className="w-full bg-muted hover:bg-emerald-600 text-foreground border-0 mt-4">
                Create Room <Plus className="w-4 h-4 ml-2" />
              </Button>
            </Card>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
