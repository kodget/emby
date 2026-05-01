import { BookOpen, Bot, Flame, ImageIcon, Layers, ListChecks, MessagesSquare, Trophy } from "lucide-react"

const features = [
  {
    icon: BookOpen,
    title: "Class-organised content hub",
    body: "No more scattered Google Drive links or WhatsApp PDFs. Class reps upload. Everyone studies the same material.",
  },
  {
    icon: Bot,
    title: "AI tutor that knows your syllabus",
    body: "Trained on your recommended textbook. Highlight a paragraph for an instant explanation or a YouTube dissection video.",
  },
  {
    icon: ListChecks,
    title: "Past questions by topic",
    body: "AI auto-sorts every uploaded past question into topics and modules so you can drill exactly what you’re weak in.",
  },
  {
    icon: ImageIcon,
    title: "Real-world steeplechase",
    body: "Practice with real cadaveric photographs and histology slides — timed, just like the actual exam.",
  },
  {
    icon: Layers,
    title: "Flashcards that never sleep",
    body: "Auto-generated from your notes with spaced repetition. We remind you the moment a card is due.",
  },
  {
    icon: Flame,
    title: "Streaks that actually help",
    body: "A daily plan you can finish in 45 minutes. Miss a day, keep a freeze. The streak is a tool, not guilt.",
  },
  {
    icon: Trophy,
    title: "Weekly class leaderboard",
    body: "Quiet competition with your classmates. Top performers earn the right to contribute revision notes.",
  },
  {
    icon: MessagesSquare,
    title: "Ask, answer, upvote",
    body: "Ask the community anything — class reps and top students get notified. Verified answers rise to the top.",
  },
]

export function LandingFeatures() {
  return (
    <section id="features" className="border-t border-border bg-card/40">
      <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6">
        <div className="flex flex-col gap-3 md:max-w-2xl">
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">Everything you need</p>
          <h2 className="font-serif text-4xl leading-tight tracking-tight text-balance md:text-5xl">
            One calm app instead of <span className="italic">seven WhatsApp groups.</span>
          </h2>
          <p className="text-pretty text-muted-foreground">
            We interviewed BMS students from anatomy, physiology and biochemistry classes. These are the eight things
            they asked for, in order.
          </p>
        </div>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <li
              key={f.title}
              className="flex flex-col gap-3 rounded-2xl border border-border bg-background p-5 transition-colors hover:border-primary/30"
            >
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="size-4" aria-hidden="true" />
              </span>
              <h3 className="font-serif text-lg leading-snug">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
