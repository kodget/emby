"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, FileText, Loader2, Filter, Brain, Microscope, Baby, Activity, Beaker } from "lucide-react";
import { curriculumApi } from "@/lib/api";
import type { Subject, Block, Topic, Section } from "@/lib/api";

type CourseCard = {
  id: string;
  subject: Subject;
  block: Block;
  topic?: Topic;
  section?: Section;
  displayName: string;
  path: string;
};

// Course theme configuration
const courseThemes = {
  anatomy: {
    color: "from-rose-500 to-pink-600",
    bgLight: "bg-rose-50",
    bgDark: "bg-rose-500/10",
    text: "text-rose-600",
    border: "border-rose-200",
    hoverBorder: "hover:border-rose-400",
    icon: Brain,
  },
  physiology: {
    color: "from-blue-500 to-cyan-600",
    bgLight: "bg-blue-50",
    bgDark: "bg-blue-500/10",
    text: "text-blue-600",
    border: "border-blue-200",
    hoverBorder: "hover:border-blue-400",
    icon: Activity,
  },
  "medical-biochemistry": {
    color: "from-emerald-500 to-teal-600",
    bgLight: "bg-emerald-50",
    bgDark: "bg-emerald-500/10",
    text: "text-emerald-600",
    border: "border-emerald-200",
    hoverBorder: "hover:border-emerald-400",
    icon: Beaker,
  },
};

// Block-specific icons
const getBlockIcon = (blockName: string) => {
  const name = blockName.toLowerCase();
  if (name.includes("gross anatomy")) return Brain;
  if (name.includes("histology")) return Microscope;
  if (name.includes("embryology")) return Baby;
  if (name.includes("physiology")) return Activity;
  if (name.includes("biochemistry")) return Beaker;
  return BookOpen;
};

export default function CoursesPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [allBlocks, setAllBlocks] = useState<Block[]>([]);
  const [courseCards, setCourseCards] = useState<CourseCard[]>([]);
  const [filteredCards, setFilteredCards] = useState<CourseCard[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedSubject === "all") {
      setFilteredCards(courseCards);
    } else {
      setFilteredCards(
        courseCards.filter((card) => card.subject.id === selectedSubject)
      );
    }
  }, [selectedSubject, courseCards]);

  const loadData = async () => {
    try {
      const subjectsData = await curriculumApi.getSubjects();
      setSubjects(subjectsData);

      const blocksPromises = subjectsData.map((subject) =>
        curriculumApi.getBlocks(subject.id)
      );
      const blocksArrays = await Promise.all(blocksPromises);
      const blocks = blocksArrays.flat();
      setAllBlocks(blocks);

      const cards: CourseCard[] = [];

      for (const block of blocks) {
        const subject = subjectsData.find((s) => s.id === block.subject)!;

        if (block.topics && block.topics.length > 0) {
          for (const topic of block.topics) {
            if (topic.sections && topic.sections.length > 0) {
              for (const section of topic.sections) {
                cards.push({
                  id: `${block.id}-${topic.id}-${section.id}`,
                  subject,
                  block,
                  topic,
                  section,
                  displayName: `${subject.name} - ${block.name} - ${topic.name} - ${section.name}`,
                  path: `/courses/${subject.id}/${block.id}/${topic.id}/${section.id}`,
                });
              }
            } else {
              cards.push({
                id: `${block.id}-${topic.id}`,
                subject,
                block,
                topic,
                displayName: `${subject.name} - ${block.name} - ${topic.name}`,
                path: `/courses/${subject.id}/${block.id}/${topic.id}`,
              });
            }
          }
        } else if (block.sections && block.sections.length > 0) {
          for (const section of block.sections) {
            const sectionPath = `/courses/${subject.id}/${block.id}/${section.id}`;
            console.log(`Creating card for ${block.name} - ${section.name}: ${sectionPath}`);
            cards.push({
              id: `${block.id}-${section.id}`,
              subject,
              block,
              section,
              displayName: `${subject.name} - ${block.name} - ${section.name}`,
              path: sectionPath,
            });
          }
        } else {
          // Block without topics or sections - show the block itself
          cards.push({
            id: block.id,
            subject,
            block,
            displayName: `${subject.name} - ${block.name}`,
            path: `/courses/${subject.id}/${block.id}`,
          });
        }
      }

      setCourseCards(cards);
      setFilteredCards(cards);
    } catch (error) {
      console.error("Failed to load courses:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-4xl font-bold mb-2">My Courses</h1>
        <p className="text-muted-foreground">
          Click on any course to view materials and start reading
        </p>
      </div>

      {/* Filter Buttons */}
      <div className="mb-8 flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedSubject("all")}
          className={`px-4 py-2 rounded-full font-medium transition-all ${
            selectedSubject === "all"
              ? "bg-gradient-to-r from-primary to-primary/80 text-primary-foreground shadow-lg"
              : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/50"
          }`}
        >
          All Courses ({courseCards.length})
        </button>
        {subjects.map((subject) => {
          const count = courseCards.filter(
            (card) => card.subject.id === subject.id
          ).length;
          const theme = courseThemes[subject.id as keyof typeof courseThemes];
          
          if (!theme) return null;
          
          const Icon = theme.icon;
          
          return (
            <button
              key={subject.id}
              onClick={() => setSelectedSubject(subject.id)}
              className={`px-4 py-2 rounded-full font-medium transition-all flex items-center gap-2 ${
                selectedSubject === subject.id
                  ? `bg-gradient-to-r ${theme.color} text-white shadow-lg`
                  : `bg-card border ${theme.border} ${theme.text} hover:${theme.bgLight}`
              }`}
            >
              <Icon className="size-4" />
              {subject.name} ({count})
            </button>
          );
        })}
      </div>

      {/* Course Cards Grid */}
      {filteredCards.length === 0 ? (
        <div className="text-center py-12">
          <BookOpen className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="font-serif text-xl mb-2">No courses available</h3>
          <p className="text-sm text-muted-foreground">
            Course materials will appear here once they're set up
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCards.map((card) => {
            const theme = courseThemes[card.subject.id as keyof typeof courseThemes];
            
            if (!theme) return null;
            
            const BlockIcon = getBlockIcon(card.block.name);
            
            return (
              <Link
                key={card.id}
                href={card.path}
                className={`group rounded-2xl ${theme.bgDark} p-5 hover:shadow-xl transition-all`}
              >
                {/* Icon & Header */}
                <div className="flex items-start gap-3 mb-4">
                  <div className={`flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${theme.color} text-white group-hover:scale-110 transition-transform shadow-md`}>
                    <BlockIcon className="size-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-xs font-semibold ${theme.text} mb-1 flex items-center gap-1.5`}>
                      {theme.icon && <theme.icon className="size-3" />}
                      {card.subject.name}
                    </div>
                    <h3 className="font-serif text-lg font-semibold leading-tight group-hover:text-primary transition-colors">
                      {card.block.name}
                    </h3>
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-2 text-sm mb-4">
                  {card.topic && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <div className={`size-1.5 rounded-full ${theme.text}`} />
                      <span>{card.topic.name}</span>
                    </div>
                  )}
                  {card.section && (
                    <div className={`flex items-center gap-2 ${theme.text} font-medium`}>
                      <FileText className="size-4" />
                      <span>{card.section.name}</span>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className={`pt-3 border-t border-border/50 flex items-center justify-between text-xs`}>
                  <span className="text-muted-foreground">Click to view materials</span>
                  <span className={`${theme.text} group-hover:translate-x-1 transition-transform font-bold`}>→</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
