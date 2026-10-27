# Emby — Study Studio

Audience: university and medical students. Confident, creative and useful; avoid
children's-app typography, generic gradient heroes and repetitive feature cards.

## Visual language

- Warm paper canvas, deep ink, violet actions. Lime and peach appear as supporting
  study illustrations, not replacements for semantic success/error colors.
- Large editorial display type on marketing sections, readable sans-serif type
  for lessons, forms and navigation; tabular figures for timers and scores.
- Deliberate contrast between expansive marketing compositions and focused study
  screens. Use asymmetric grids, notebook rules, document edges and annotations.
- Build illustrative assets in SVG/CSS so they remain sharp, lightweight and
  responsive. Sample material must be labelled; no invented testimonials or metrics.
- Landing sections should each tell a different part of the story: finding focus,
  reading with context, retrieval practice, class coordination and plan choice.
- Interactive examples must work with pointer, touch and keyboard and explain their
  sample behavior. No decorative fake form controls.

## Application coverage

Audit and update the landing sections, public account/onboarding screens, app shell,
dashboard, course hierarchy and documents, readers and AI tools, search, flashcards,
quizzes and assessments, practical stations, battles, study planner, analytics,
class management, community, profile/settings, notifications, credits and premium.
Keep administrative routes consistent through shared components and layout.

Preserve access checks, saved work, API behavior, billing prices and upload recovery.
Keep primary actions reachable on mobile, readable error/empty/loading states,
visible focus, 44-pixel touch targets and reduced-motion support.

Validate representative desktop/mobile flows with isolated API fixtures, inspect
screenshots at 375/768/1024/1440 widths, and run TypeScript and relevant regressions.
