// "use client";

// import { useEffect, useState } from "react";
// import Link from "next/link";
// import { BookOpen, FileText, Loader2, Filter, Brain, Microscope, Baby, Activity, Beaker } from "lucide-react";
// import { curriculumApi } from "@/lib/api";
// import type { Subject, Block, Topic, Section } from "@/lib/api";

// type CourseCard = {
//   id: string;
//   subject: Subject;
//   block: Block;
//   topic?: Topic;
//   section?: Section;
//   displayName: string;
//   path: string;
// };

// // Course theme configuration
// const courseThemes = {
//   anatomy: {
//     color: "from-rose-500 to-pink-600",
//     bgLight: "bg-rose-50",
//     bgDark: "bg-rose-500/10",
//     text: "text-rose-600",
//     border: "border-rose-200",
//     hoverBorder: "hover:border-rose-400",
//     icon: Brain,
//   },
//   physiology: {
//     color: "from-blue-500 to-cyan-600",
//     bgLight: "bg-blue-50",
//     bgDark: "bg-blue-500/10",
//     text: "text-blue-600",
//     border: "border-blue-200",
//     hoverBorder: "hover:border-blue-400",
//     icon: Activity,
//   },
//   "medical-biochemistry": {
//     color: "from-emerald-500 to-teal-600",
//     bgLight: "bg-emerald-50",
//     bgDark: "bg-emerald-500/10",
//     text: "text-emerald-600",
//     border: "border-emerald-200",
//     hoverBorder: "hover:border-emerald-400",
//     icon: Beaker,
//   },
// };

// // Default theme for any subject not in the predefined list
// const defaultTheme = {
//   color: "from-violet-500 to-purple-600",
//   bgLight: "bg-violet-50",
//   bgDark: "bg-violet-500/10",
//   text: "text-violet-600",
//   border: "border-violet-200",
//   hoverBorder: "hover:border-violet-400",
//   icon: BookOpen,
// };
//   const name = blockName.toLowerCase();
//   if (name.includes("gross anatomy")) return Brain;
//   if (name.includes("histology")) return Microscope;
//   if (name.includes("embryology")) return Baby;
//   if (name.includes("physiology")) return Activity;
//   if (name.includes("biochemistry")) return Beaker;
//   // return BookOpen;
// };

// export default function CoursesPage() {
//   const [subjects, setSubjects] = useState<Subject[]>([]);
//   const [allBlocks, setAllBlocks] = useState<Block[]>([]);
//   const [courseCards, setCourseCards] = useState<CourseCard[]>([]);
//   const [filteredCards, setFilteredCards] = useState<CourseCard[]>([]);
//   const [selectedSubject, setSelectedSubject] = useState<string>("all");
//   const [loading, setLoading] = useState(true);

//   useEffect(() => {
//     loadData();
//   }, []);

//   useEffect(() => {
//     if (selectedSubject === "all") {
//       setFilteredCards(courseCards);
//     } else {
//       setFilteredCards(
//         courseCards.filter((card) => card.subject.id === selectedSubject)
//       );
//     }
//   }, [selectedSubject, courseCards]);

//   const loadData = async () => {
//     try {
//       const subjectsData = await curriculumApi.getSubjects();
//       setSubjects(subjectsData);

//       const blocksPromises = subjectsData.map((subject) =>
//         curriculumApi.getBlocks(subject.id)
//       );
//       const blocksArrays = await Promise.all(blocksPromises);
//       const blocks = blocksArrays.flat();
//       setAllBlocks(blocks);

//       const cards: CourseCard[] = [];

//       for (const block of blocks) {
//         const subject = subjectsData.find((s) => s.id === block.subject)!;

//         if (block.topics && block.topics.length > 0) {
//           for (const topic of block.topics) {
//             if (topic.sections && topic.sections.length > 0) {
//               for (const section of topic.sections) {
//                 cards.push({
//                   id: `${block.id}-${topic.id}-${section.id}`,
//                   subject,
//                   block,
//                   topic,
//                   section,
//                   displayName: `${subject.name} - ${block.name} - ${topic.name} - ${section.name}`,
//                   path: `/courses/${subject.id}/${block.id}/${topic.id}/${section.id}`,
//                 });
//               }
//             } else {
//               cards.push({
//                 id: `${block.id}-${topic.id}`,
//                 subject,
//                 block,
//                 topic,
//                 displayName: `${subject.name} - ${block.name} - ${topic.name}`,
//                 path: `/courses/${subject.id}/${block.id}/${topic.id}`,
//               });
//             }
//           }
//         } else if (block.sections && block.sections.length > 0) {
//           for (const section of block.sections) {
//             const sectionPath = `/courses/${subject.id}/${block.id}/${section.id}`;
//             console.log(`Creating card for ${block.name} - ${section.name}: ${sectionPath}`);
//             cards.push({
//               id: `${block.id}-${section.id}`,
//               subject,
//               block,
//               section,
//               displayName: `${subject.name} - ${block.name} - ${section.name}`,
//               path: sectionPath,
//             });
//           }
//         } else {
//           // Block without topics or sections - show the block itself
//           cards.push({
//             id: block.id,
//             subject,
//             block,
//             displayName: `${subject.name} - ${block.name}`,
//             path: `/courses/${subject.id}/${block.id}`,
//           });
//         }
//       }

//       setCourseCards(cards);
//       setFilteredCards(cards);
//     } catch (error) {
//       console.error("Failed to load courses:", error);
//     } finally {
//       setLoading(false);
//     }
//   };

//   if (loading) {
//     return (
//       <div className="flex min-h-screen items-center justify-center">
//         <Loader2 className="h-8 w-8 animate-spin text-primary" />
//       </div>
//     );
//   }

//   return (
//     <div className="container mx-auto px-4 py-8 max-w-7xl">
//       {/* Header */}
//       <div className="mb-8">
//         <h1 className="font-serif text-4xl font-bold mb-2">My Courses</h1>
//         <p className="text-muted-foreground">
//           Click on any course to view materials and start reading
//         </p>
//       </div>

//       {/* Filter Buttons */}
//       <div className="mb-8 flex flex-wrap gap-2">
//         <button
//           onClick={() => setSelectedSubject("all")}
//           className={`px-4 py-2 rounded-full font-medium transition-all ${
//             selectedSubject === "all"
//               ? "bg-gradient-to-r from-primary to-primary/80 text-primary-foreground shadow-lg"
//               : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/50"
//           }`}
//         >
//           All Courses ({courseCards.length})
//         </button>
//         {subjects.map((subject) => {
//           const count = courseCards.filter(
//             (card) => card.subject.id === subject.id
//           ).length;
//           const theme = courseThemes[subject.id as keyof typeof courseThemes];

//           if (!theme) return null;

//           const Icon = theme.icon;

//           return (
//             <button
//               key={subject.id}
//               onClick={() => setSelectedSubject(subject.id)}
//               className={`px-4 py-2 rounded-full font-medium transition-all flex items-center gap-2 ${
//                 selectedSubject === subject.id
//                   ? `bg-gradient-to-r ${theme.color} text-white shadow-lg`
//                   : `bg-card border ${theme.border} ${theme.text} hover:${theme.bgLight}`
//               }`}
//             >
//               <Icon className="size-4" />
//               {subject.name} ({count})
//             </button>
//           );
//         })}
//       </div>

//       {/* Course Cards Grid */}
//       {filteredCards.length === 0 ? (
//         <div className="text-center py-12">
//           <BookOpen className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
//           <h3 className="font-serif text-xl mb-2">No courses available</h3>
//           <p className="text-sm text-muted-foreground">
//             Course materials will appear here once they're set up
//           </p>
//         </div>
//       ) : (
//         <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
//           {filteredCards.map((card) => {
//             const theme = courseThemes[card.subject.id as keyof typeof courseThemes];

//             if (!theme) return null;

//             const BlockIcon = getBlockIcon(card.block.name);

//             return (
//               <Link
//                 key={card.id}
//                 href={card.path}
//                 className={`group rounded-2xl ${theme.bgDark} p-5 hover:shadow-xl transition-all`}
//               >
//                 {/* Icon & Header */}
//                 <div className="flex items-start gap-3 mb-4">
//                   <div className={`flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${theme.color} text-white group-hover:scale-110 transition-transform shadow-md`}>
//                     <BlockIcon className="size-6" />
//                   </div>
//                   <div className="flex-1 min-w-0">
//                     <div className={`text-xs font-semibold ${theme.text} mb-1 flex items-center gap-1.5`}>
//                       {theme.icon && <theme.icon className="size-3" />}
//                       {card.subject.name}
//                     </div>
//                     <h3 className="font-serif text-lg font-semibold leading-tight group-hover:text-primary transition-colors">
//                       {card.block.name}
//                     </h3>
//                   </div>
//                 </div>

//                 {/* Details */}
//                 <div className="space-y-2 text-sm mb-4">
//                   {card.topic && (
//                     <div className="flex items-center gap-2 text-muted-foreground">
//                       <div className={`size-1.5 rounded-full ${theme.text}`} />
//                       <span>{card.topic.name}</span>
//                     </div>
//                   )}
//                   {card.section && (
//                     <div className={`flex items-center gap-2 ${theme.text} font-medium`}>
//                       <FileText className="size-4" />
//                       <span>{card.section.name}</span>
//                     </div>
//                   )}
//                 </div>

//                 {/* Footer */}
//                 <div className={`pt-3 border-t border-border/50 flex items-center justify-between text-xs`}>
//                   <span className="text-muted-foreground">Click to view materials</span>
//                   <span className={`${theme.text} group-hover:translate-x-1 transition-transform font-bold`}>→</span>
//                 </div>
//               </Link>
//             );
//           })}
//         </div>
//       )}
//     </div>
//   );
// }

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  FileText,
  Loader2,
  Brain,
  Microscope,
  Baby,
  Activity,
  Beaker,
} from "lucide-react";
import { curriculumApi } from "@/lib/api";
import type { Subject, Block, SubBlock, Topic, Section } from "@/lib/api";

type CourseCard = {
  id: string;
  subject: Subject;
  block: Block;
  sub_block?: SubBlock;
  topic?: Topic;
  section?: Section;
  displayName: string;
  path: string;
};

type CourseTheme = {
  color: string;
  bgLight: string;
  bgDark: string;
  text: string;
  border: string;
  icon: typeof BookOpen;
};

// Available visual themes.
// These are NOT tied to any particular subject.
const availableThemes: CourseTheme[] = [
  {
    color: "from-rose-500 to-pink-600",
    bgLight: "bg-rose-50",
    bgDark: "bg-rose-500/10",
    text: "text-rose-600",
    border: "border-rose-200",
    icon: BookOpen,
  },
  {
    color: "from-blue-500 to-cyan-600",
    bgLight: "bg-blue-50",
    bgDark: "bg-blue-500/10",
    text: "text-blue-600",
    border: "border-blue-200",
    icon: BookOpen,
  },
  {
    color: "from-emerald-500 to-teal-600",
    bgLight: "bg-emerald-50",
    bgDark: "bg-emerald-500/10",
    text: "text-emerald-600",
    border: "border-emerald-200",
    icon: BookOpen,
  },
  {
    color: "from-violet-500 to-purple-600",
    bgLight: "bg-violet-50",
    bgDark: "bg-violet-500/10",
    text: "text-violet-600",
    border: "border-violet-200",
    icon: BookOpen,
  },
  {
    color: "from-orange-500 to-amber-600",
    bgLight: "bg-orange-50",
    bgDark: "bg-orange-500/10",
    text: "text-orange-600",
    border: "border-orange-200",
    icon: BookOpen,
  },
  {
    color: "from-indigo-500 to-blue-600",
    bgLight: "bg-indigo-50",
    bgDark: "bg-indigo-500/10",
    text: "text-indigo-600",
    border: "border-indigo-200",
    icon: BookOpen,
  },
  {
    color: "from-fuchsia-500 to-pink-600",
    bgLight: "bg-fuchsia-50",
    bgDark: "bg-fuchsia-500/10",
    text: "text-fuchsia-600",
    border: "border-fuchsia-200",
    icon: BookOpen,
  },
  {
    color: "from-cyan-500 to-sky-600",
    bgLight: "bg-cyan-50",
    bgDark: "bg-cyan-500/10",
    text: "text-cyan-600",
    border: "border-cyan-200",
    icon: BookOpen,
  },
];

// Gets a block-specific icon.
// The visual theme itself is completely independent of the block.
function getBlockIcon(blockName: string) {
  const name = blockName.toLowerCase();

  if (name.includes("gross anatomy")) return Brain;
  if (name.includes("histology")) return Microscope;
  if (name.includes("embryology")) return Baby;
  if (name.includes("physiology")) return Activity;
  if (name.includes("biochemistry")) return Beaker;

  return BookOpen;
}

// Randomly select a theme.
function getRandomTheme(): CourseTheme {
  const randomIndex = Math.floor(Math.random() * availableThemes.length);

  return availableThemes[randomIndex];
}

export default function CoursesPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [allBlocks, setAllBlocks] = useState<Block[]>([]);
  const [courseCards, setCourseCards] = useState<CourseCard[]>([]);
  const [filteredCards, setFilteredCards] = useState<CourseCard[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  // Stores one randomly assigned theme per subject.
  const [subjectThemes, setSubjectThemes] = useState<
    Record<string, CourseTheme>
  >({});

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedSubject === "all") {
      setFilteredCards(courseCards);
    } else {
      setFilteredCards(
        courseCards.filter((card) => card.subject.id === selectedSubject),
      );
    }
  }, [selectedSubject, courseCards]);

  const loadData = async () => {
    try {
      const subjectsData = await curriculumApi.getSubjects();

      setSubjects(subjectsData);

      /*
       * Assign a random theme to every subject exactly once.
       *
       * The subject name/id is NOT used to determine the theme.
       */
      const generatedThemes: Record<string, CourseTheme> = {};

      subjectsData.forEach((subject) => {
        generatedThemes[subject.id] = getRandomTheme();
      });

      setSubjectThemes(generatedThemes);

      const blocksPromises = subjectsData.map((subject) =>
        curriculumApi.getBlocks(subject.id),
      );

      const blocksArrays = await Promise.all(blocksPromises);
      const blocks = blocksArrays.flat();

      setAllBlocks(blocks);

      const cards: CourseCard[] = [];

      for (const block of blocks) {
        const subject = subjectsData.find((s) => s.id === block.subject);

        // Protect against a block referencing a subject
        // that doesn't exist in the subjects response.
        if (!subject) {
          console.warn(`Subject not found for block: ${block.name}`);
          continue;
        }

        const subBlocks = (block as any).sub_blocks || [];
        const blockTopics = (block as any).topics || [];

        if (subBlocks.length > 0) {
          for (const subBlock of subBlocks) {
            const subBlockTopics = subBlock.topics || [];
            if (subBlockTopics.length > 0) {
              for (const topic of subBlockTopics) {
                cards.push({
                  id: `${block.id}-${subBlock.id}-${topic.id}`,
                  subject,
                  block,
                  sub_block: subBlock,
                  topic: subBlock,
                  section: topic,
                  displayName: `${subject.name} - ${block.name} - ${subBlock.name} - ${topic.name}`,
                  path: `/courses/${subject.id}/${block.id}/${subBlock.id}/${topic.id}`,
                });
              }
            } else {
              cards.push({
                id: `${block.id}-${subBlock.id}`,
                subject,
                block,
                sub_block: subBlock,
                topic: subBlock,
                displayName: `${subject.name} - ${block.name} - ${subBlock.name}`,
                path: `/courses/${subject.id}/${block.id}/${subBlock.id}`,
              });
            }
          }
        } else if (blockTopics.length > 0) {
          for (const topic of blockTopics) {
            const sectionPath = `/courses/${subject.id}/${block.id}/${topic.id}`;

            cards.push({
              id: `${block.id}-${topic.id}`,
              subject,
              block,
              section: topic,
              displayName: `${subject.name} - ${block.name} - ${topic.name}`,
              path: sectionPath,
            });
          }
        } else {
          // Block without sub-blocks or topics.
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
    <div className="container mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="mb-2 font-serif text-4xl font-bold">My Courses</h1>

        <p className="text-muted-foreground">
          Click on any course to view materials and start reading
        </p>
      </div>

      {/* Filter Buttons */}
      <div className="mb-8 flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedSubject("all")}
          className={`rounded-full px-4 py-2 font-medium transition-all ${
            selectedSubject === "all"
              ? "bg-gradient-to-r from-primary to-primary/80 text-primary-foreground shadow-lg"
              : "border border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
          }`}
        >
          All Courses ({courseCards.length})
        </button>

        {subjects.map((subject) => {
          const count = courseCards.filter(
            (card) => card.subject.id === subject.id,
          ).length;

          const theme = subjectThemes[subject.id];

          // Theme may not exist during the very first render.
          if (!theme) return null;

          return (
            <button
              key={subject.id}
              onClick={() => setSelectedSubject(subject.id)}
              className={`flex items-center gap-2 rounded-full px-4 py-2 font-medium transition-all ${
                selectedSubject === subject.id
                  ? `bg-gradient-to-r ${theme.color} text-white shadow-lg`
                  : `border ${theme.border} bg-card ${theme.text} hover:${theme.bgLight}`
              }`}
            >
              <BookOpen className="size-4" />
              {subject.name} ({count})
            </button>
          );
        })}
      </div>

      {/* Course Cards */}
      {filteredCards.length === 0 ? (
        <div className="py-12 text-center">
          <BookOpen className="mx-auto mb-4 h-16 w-16 text-muted-foreground" />

          <h3 className="mb-2 font-serif text-xl">No courses available</h3>

          <p className="text-sm text-muted-foreground">
            Course materials will appear here once they&apos;re set up
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCards.map((card) => {
            const theme = subjectThemes[card.subject.id];

            if (!theme) return null;

            const BlockIcon = getBlockIcon(card.block.name);

            return (
              <Link
                key={card.id}
                href={card.path}
                className={`group rounded-2xl ${theme.bgDark} p-5 transition-all hover:shadow-xl`}
              >
                {/* Icon & Header */}
                <div className="mb-4 flex items-start gap-3">
                  <div
                    className={`flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${theme.color} text-white shadow-md transition-transform group-hover:scale-110`}
                  >
                    <BlockIcon className="size-6" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div
                      className={`mb-1 flex items-center gap-1.5 text-xs font-semibold ${theme.text}`}
                    >
                      <BookOpen className="size-3" />
                      {card.subject.name}
                    </div>

                    <h3 className="font-serif text-lg font-semibold leading-tight transition-colors group-hover:text-primary">
                      {card.block.name}
                    </h3>
                  </div>
                </div>

                {/* Details */}
                <div className="mb-4 space-y-2 text-sm">
                  {card.topic && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <div className={`size-1.5 rounded-full ${theme.text}`} />
                      <span>{card.topic.name}</span>
                    </div>
                  )}

                  {card.section && (
                    <div
                      className={`flex items-center gap-2 font-medium ${theme.text}`}
                    >
                      <FileText className="size-4" />
                      <span>{card.section.name}</span>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between border-t border-border/50 pt-3 text-xs">
                  <span className="text-muted-foreground">
                    Click to view materials
                  </span>

                  <span
                    className={`font-bold ${theme.text} transition-transform group-hover:translate-x-1`}
                  >
                    →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
