"use client";

import Link from "next/link";
import { ArrowUpRight, BookOpen, Layers, ListChecks, Microscope, Swords, Timer } from "lucide-react";
import { WorkspaceSectionTitle } from "@/components/ui/workspace-header";

const actions = [
  { label: "Read & explore", detail: "Slides, notes and explanations", href: "/courses", icon: BookOpen, tone: "primary" },
  { label: "Practise questions", detail: "Build confidence, one answer at a time", href: "/quiz", icon: ListChecks, tone: "mastery" },
  { label: "Steeplechase", detail: "Think quickly. Work through stations.", href: "/steeplechase", icon: Timer, tone: "weakness" },
  { label: "Histology", detail: "Look closer. Identify the tissue.", href: "/histology", icon: Microscope, tone: "primary" },
  { label: "Review flashcards", detail: "Bring what you know back to mind", href: "/flashcards", icon: Layers, tone: "review" },
  { label: "Brain Battle", detail: "A little friendly competition", href: "/battles", icon: Swords, tone: "mastery" },
];

export function QuickActions({ className }: { className?: string }) {
  return <section className={className} aria-label="Study tools">
    <WorkspaceSectionTitle title="How would you like to study?" description="Pick a way in. Your progress starts with the next small step." />
    <ul className="grid grid-cols-2 gap-3 lg:grid-cols-3">
      {actions.map(({ label, detail, href, icon: Icon, tone }, index) => <li key={href}>
        <Link href={href} className="studio-action-card" data-tone={tone}>
          <ArrowUpRight className="action-arrow size-4" aria-hidden="true" />
          <span className="action-icon"><Icon className="size-5" aria-hidden="true" /></span>
          <span><span className="workspace-tool-index">0{index + 1}</span><span className="mt-1 block font-display text-sm font-semibold sm:text-base">{label}</span><span className="mt-2 block text-xs leading-5 text-muted-foreground">{detail}</span></span>
        </Link>
      </li>)}
    </ul>
  </section>;
}
