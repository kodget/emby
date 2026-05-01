"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faMagnifyingGlass,
  faBookOpen,
  faListCheck,
  faTrophy,
  faLayerGroup,
} from "@fortawesome/free-solid-svg-icons";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { curriculum } from "@/lib/curriculum";
import { getSlidesForCourse } from "@/lib/slides";
import { breadcrumb } from "@/lib/curriculum";

interface SearchResult {
  id: string;
  title: string;
  type: "course" | "slide" | "quiz" | "flashcard" | "steeplechase";
  url: string;
  description: string;
  subject?: string;
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // Generate all searchable items
  const searchItems = useMemo<SearchResult[]>(() => {
    const items: SearchResult[] = [];

    // Add courses
    curriculum.forEach((subject) => {
      subject.blocks.forEach((block) => {
        if (subject.id === "biochemistry") {
          // Biochemistry blocks
          items.push({
            id: block.id,
            title: block.title,
            type: "course",
            url: `/courses/${block.id}`,
            description: `${subject.title} · ${block.title}`,
            subject: subject.title,
          });
        } else {
          // Anatomy and Physiology topics
          block.topics.forEach((topic) => {
            items.push({
              id: topic.id,
              title: topic.title,
              type: "course",
              url: `/courses/${topic.id}`,
              description: `${subject.title} · ${block.title}`,
              subject: subject.title,
            });
          });
        }
      });
    });

    // Add slides
    curriculum.forEach((subject) => {
      subject.blocks.forEach((block) => {
        const courseId =
          subject.id === "biochemistry" ? block.id : block.topics[0]?.id;
        if (courseId) {
          const slides = getSlidesForCourse(courseId);
          slides.forEach((slide) => {
            items.push({
              id: slide.id,
              title: slide.title,
              type: "slide",
              url: `/read/${courseId}/${slide.id}`,
              description: `${breadcrumb(courseId)} · ${slide.pages} pages`,
              subject: subject.title,
            });
          });
        }
      });
    });

    // Add quiz topics (simplified - would need actual quiz data)
    curriculum.forEach((subject) => {
      subject.blocks.forEach((block) => {
        if (subject.id !== "biochemistry") {
          block.topics.forEach((topic) => {
            items.push({
              id: `quiz-${topic.id}`,
              title: `${topic.title} Quiz`,
              type: "quiz",
              url: `/quiz?topic=${topic.id}`,
              description: `${subject.title} · ${block.title}`,
              subject: subject.title,
            });
          });
        }
      });
    });

    // Add flashcards (simplified)
    items.push({
      id: "flashcards",
      title: "Flashcards",
      type: "flashcard",
      url: "/flashcards",
      description: "Review spaced-repetition flashcards",
    });

    // Add steeplechase
    items.push({
      id: "steeplechase",
      title: "Steeplechase Practice",
      type: "steeplechase",
      url: "/steeplechase",
      description: "Practice with spotter questions",
    });

    return items;
  }, []);

  const getIcon = (type: SearchResult["type"]) => {
    switch (type) {
      case "course":
        return faBookOpen;
      case "slide":
        return faBookOpen;
      case "quiz":
        return faListCheck;
      case "flashcard":
        return faLayerGroup;
      case "steeplechase":
        return faTrophy;
      default:
        return faBookOpen;
    }
  };

  const getTypeLabel = (type: SearchResult["type"]) => {
    switch (type) {
      case "course":
        return "Course";
      case "slide":
        return "Slide";
      case "quiz":
        return "Quiz";
      case "flashcard":
        return "Flashcards";
      case "steeplechase":
        return "Steeplechase";
      default:
        return type;
    }
  };

  const handleSelect = (item: SearchResult) => {
    setOpen(false);
    router.push(item.url);
  };

  return (
    <>
      {/* Search trigger */}
      <button
        onClick={() => setOpen(true)}
        className="flex w-full max-w-full flex-1 min-w-0 items-center gap-3"
        aria-label="Open global search"
      >
        <label className="relative flex w-full min-w-0 items-center">
          <FontAwesomeIcon
            icon={faMagnifyingGlass}
            className="pointer-events-none absolute left-3 size-3.5 text-muted-foreground"
            aria-hidden="true"
          />
          <div className="h-10 w-full min-w-0 rounded-full border border-border bg-card pl-9 pr-4 text-left text-sm text-muted-foreground transition-colors hover:border-primary/50 sm:max-w-md">
            <span className="truncate">
              Search axilla, glycolysis, cranial nerves…
            </span>
          </div>
        </label>
      </button>

      {/* Search dialog */}
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Search courses, slides, quizzes…" />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>

          {/* Group by type */}
          {["course", "slide", "quiz", "flashcard", "steeplechase"].map(
            (type) => {
              const items = searchItems.filter((item) => item.type === type);
              if (items.length === 0) return null;

              return (
                <CommandGroup
                  key={type}
                  heading={getTypeLabel(type as SearchResult["type"])}
                >
                  {items.map((item) => (
                    <CommandItem
                      key={item.id}
                      onSelect={() => handleSelect(item)}
                      className="flex items-center gap-3"
                    >
                      <FontAwesomeIcon
                        icon={getIcon(item.type)}
                        className="size-4 text-muted-foreground"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{item.title}</div>
                        <div className="text-xs text-muted-foreground truncate">
                          {item.description}
                        </div>
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              );
            },
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
