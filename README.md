# Emby — The Study OS for Medical Students

> Course slides, an AI tutor that reads alongside you, past questions, timed quizzes, flashcards, steeplechase practice, brain battles, and a study planner — all in one place, made for BMS students.

Emby is a full-stack, AI-powered educational platform purpose-built for medical and biomedical science students. It combines a curriculum-mapped content library, multiple assessment modes, a per-slide AI tutor, gamified practice sessions, and real-time multiplayer battles into a single Progressive Web App backed by a Django ASGI server and Celery workers.

---

## Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Repository Structure](#-repository-structure)
- [Frontend Deep Dive](#-frontend-deep-dive)
- [Backend Deep Dive](#-backend-deep-dive)
- [AI & LLM Integration](#-ai--llm-integration)
- [Credit & Monetisation System](#-credit--monetisation-system)
- [Gamification Engine](#-gamification-engine)
- [Real-Time Features](#-real-time-features)
- [Authentication & Authorisation](#-authentication--authorisation)
- [Local Development Setup](#-local-development-setup)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Key Features

### Content & Curriculum
- **Hierarchical Curriculum Tree** — Subjects → Blocks → Sub-Blocks → Topics, all admin-managed and mapped to every piece of content.
- **Slide Reader** — PDF slide decks uploaded by class heads and material uploaders, rendered page-by-page with Cloudinary storage and background processing via Celery.
- **RAG-Powered AI Tutor** — Each slide is chunked, embedded with `all-MiniLM-L6-v2`, and indexed. When a student asks a question, the most relevant chunks are retrieved and sent alongside the query to an LLM, grounding every answer in the actual slide content.

### Assessment Modes
- **Quiz Engine** — Configurable MCQ + Theory quizzes by subject, block, topic, difficulty, and exam type (Practice / Mock / Formal). Timed or untimed. MCQs graded instantly; theory answers graded asynchronously by AI.
- **Steeplechase Practice** — Timed image-spot anatomy stations (gross anatomy, radiographs, models) — 30 seconds per station, typed answers + supporting MCQ, with server-side scoring.
- **Histology Practice** — Same mechanic as steeplechase but drawing from a histology-specific station pool.
- **Brain Battles** — Real-time multiplayer quiz duels. A host generates a battle, players join via a 6-character code, and answer competitively. Scoring is server-authoritative with speed bonuses and anti-cheat protections (correct answers never sent to clients during play, replay protection via unique constraints).
- **Flashcards** — AI-generated flashcard decks tied to curriculum nodes, reviewed via spaced repetition.

### AI Features
- **Per-Slide Chat** — Stateless chat where every request includes slide context (extracted text + optional screenshot). Supports explain, resources (YouTube links, textbook references), and MCQ generation modes.
- **Theory Grading** — Free-text answers evaluated asynchronously by LLM, returning a score, correct answer, and detailed feedback.
- **AI Study Plan Generation** — Generates a personalised daily study schedule based on weak areas and curriculum coverage.
- **AI Flashcard Generation** — Automatically creates flashcard decks from slide content.
- **Dashboard Motivational Messages** — AI-generated contextual messages on the student dashboard.

### Analytics & Insights
- **Performance Analytics** — Accuracy trends, topic-level breakdowns, per-assessment-type performance, study minutes, active days, and streak tracking — all derived from a single `LearningEvent` stream.
- **Weak Area Detection** — Exponentially weighted mastery estimates per curriculum node, updated on every scored activity.
- **Question Exposure Tracking** — Knows which questions a student has already seen, preventing repeats and enabling gap analysis.

### Gamification
- **XP System** — Activity-based XP with daily caps, diminishing returns within a day (1st quiz = full XP, 5th = 10%), accuracy scaling, and anti-farming time floors (answering 20 questions in 15 seconds earns zero XP). Streak bonuses up to 30%.
- **Achievements & Badges** — Tiered achievements (Common → Epic) across categories: Quizzes (First Steps, Quiz Explorer, Quiz Master, Certified Scholar), Flashcards (First Review), and more. Each achievement unlocks a rarity-coded badge.
- **Streaks** — Daily activity tracking with streak-at-risk notifications.
- **Leaderboards** — Community ranking by XP.

### Notifications
- **In-App Notifications** — Deduplicated per-day, budget-limited per student, priority-ordered (security > system > announcements > flashcards due > planner > streak > weak area > study goals).
- **Push Notifications** — Service Worker + Web Push API (VAPID) with backend subscription management.
- **Quiet Hours** — Notifications deferred to reasonable times rather than firing at 3 AM.
- **Granular Preferences** — Per-category toggles (academic, community, planner, streak, flashcards, study goals).

### Platform & Admin
- **Progressive Web App** — Service worker for offline caching, `manifest.json`, installable on mobile.
- **Dynamic Admin Dashboard** — A Next.js admin panel that introspects the Django backend schema at runtime and renders CRUD interfaces for every registered model — no frontend changes needed when new models are added.
- **Class System** — Schools, class groups with join codes, up to 3 class heads per group, material uploader roles, announcements, and exam countdowns.
- **Paystack Payments** — Checkout initialisation, HMAC-verified webhooks, idempotent premium activation, and subscription extension.

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client (Browser / PWA)                      │
│  Next.js 16 · TypeScript · Tailwind · shadcn/ui · Framer Motion    │
│  Redux Toolkit (quiz, schedule, user, notifications, progress)      │
│  Zustand (slide viewer) · Axios · Service Worker · Web Push         │
└──────────────────┬──────────────────────┬───────────────────────────┘
                   │ HTTPS / REST         │ WSS / WebSockets
                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Django + Daphne (ASGI Server)                     │
│  DRF ViewSets · JWT Auth · Rate Limiting · CORS                    │
│  Django Channels (battles, notifications)                           │
├─────────────────────────────────────────────────────────────────────┤
│  accounts · curriculum · learning · pastquestions · credits · payments│
└──────┬─────────────┬──────────────┬────────────────┬────────────────┘
       │             │              │                │
       ▼             ▼              ▼                ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐    ┌────────────┐
  │PostgreSQL│  │  Redis   │  │ Celery   │    │ Cloudinary │
  │  (Data)  │  │(Broker / │  │ Workers  │    │  (Media)   │
  │          │  │ Channels)│  │          │    │            │
  └─────────┘  └──────────┘  └────┬─────┘    └────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ LLM API  │  │ Paystack │  │ YouTube  │
              │(Groq /   │  │   API    │  │   API    │
              │Cerebras) │  │          │  │          │
              └──────────┘  └──────────┘  └──────────┘
```

---

## 🔧 Tech Stack

### Frontend
| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack) |
| Language | TypeScript (strict) |
| Global State | Redux Toolkit (`quiz-attempt-slice`, `schedule-slice`, `user-slice`, `notifications-slice`, `progress-slice`, `uploads-slice`, `flashcards-slice`) |
| Local State | Zustand (`slide-store`) |
| Styling | Tailwind CSS 4 + shadcn/ui (Radix primitives, `new-york` style) |
| Animations | Framer Motion |
| Forms | React Hook Form + Zod validation |
| Data Fetching | Axios with interceptors (JWT auto-refresh, retry queue) |
| Charts | Recharts |
| Typography | Inter (body), Sora (headings), Lilita One (UI voice), Anton (display numbers), JetBrains Mono (data/timers) |
| Icons | Lucide React + Font Awesome |
| PWA | Custom service worker, Web Push API (VAPID) |

### Backend
| Layer | Technology |
|---|---|
| Framework | Django 4.x + Django REST Framework |
| ASGI Server | Daphne (HTTP + WebSockets) |
| Real-Time | Django Channels (battles, notifications) |
| Task Queue | Celery with Redis broker |
| Database | PostgreSQL (production), SQLite (development) |
| Caching & Pub/Sub | Redis |
| File Storage | Cloudinary (PDFs, images, slides) |
| AI/LLM | Provider-agnostic OpenAI-compatible client (`curriculum.llm`) — Groq, Cerebras, OpenRouter, local vLLM |
| Embeddings | SentenceTransformers (`all-MiniLM-L6-v2`) for RAG |
| Payments | Paystack (checkout, webhooks, HMAC verification) |
| Video | YouTube Data API v3 |
| Auth | JWT (access + refresh rotation), Google OAuth 2.0 |

---

## 📂 Repository Structure

```
emby/
├── app/                          # Next.js App Router pages
│   ├── (app)/                    # Authenticated student routes
│   │   ├── dashboard/            # Home dashboard with stats, streaks, AI message
│   │   ├── decks/                # Slide deck browser & reader
│   │   ├── quiz/                 # Quiz creation, taking, and results
│   │   ├── flashcards/           # Flashcard review interface
│   │   ├── steeplechase/         # Timed anatomy station practice
│   │   ├── histology/            # Timed histology practice
│   │   ├── battles/              # Brain Battle lobby, play, and results
│   │   ├── analytics/            # Performance analytics dashboard
│   │   ├── study-plan/           # AI study planner
│   │   ├── achievements/         # Badges and achievements showcase
│   │   ├── credits/              # AI credit balance and purchase
│   │   ├── community/            # Class announcements and social
│   │   ├── notifications/        # Notification centre
│   │   ├── premium/              # Upgrade page
│   │   ├── settings/             # User preferences
│   │   ├── profile/              # Profile management
│   │   ├── brainstorming/        # Collaborative study tool
│   │   ├── courses/              # Course browser
│   │   ├── class/                # Class group management
│   │   ├── read/                 # Slide reader
│   │   └── session/              # Study session tracking
│   ├── (admin)/admin/            # Admin dashboard
│   │   ├── curriculum/           # Curriculum CRUD
│   │   ├── users/                # User management
│   │   ├── payments/             # Payment transactions
│   │   └── manage/[app]/[model]/ # Dynamic schema-driven model editor
│   ├── signin/ signup/ forgot-password/ reset-password/
│   ├── onboarding/               # Post-signup onboarding flow
│   ├── payment/                  # Paystack checkout flow
│   └── layout.tsx                # Root layout (Redux, Google Auth, PWA, Toaster)
│
├── components/
│   ├── app/                      # Shell components (sidebar, topbar, tab bar, search)
│   ├── quiz/                     # Quiz UI (question cards, timer, navigation, results)
│   ├── reader/                   # Slide reader with AI chat panel
│   ├── flashcards/               # Flashcard deck and review UI
│   ├── battles/                  # Battle lobby, play grid, leaderboard
│   ├── dashboard/                # Dashboard widgets and stat cards
│   ├── credits/                  # Credit bar, purchase modal
│   ├── practice/                 # Steeplechase and histology station UI
│   ├── premium/                  # Upgrade prompts and feature gates
│   ├── auth/                     # Login/signup forms, Google OAuth provider
│   ├── landing/                  # Marketing landing page components
│   ├── pwa/                      # PWA registration and install prompt
│   └── ui/                       # shadcn/ui primitives (40+ components)
│
├── store/                        # Redux Toolkit slices
│   ├── quiz-attempt-slice.ts     # Quiz lifecycle (load, answer, flag, submit, auto-submit)
│   ├── schedule-slice.ts         # Study planner (server-synced CRUD)
│   ├── user-slice.ts             # Auth state, profile, preferences
│   ├── notifications-slice.ts    # Notification feed
│   ├── progress-slice.ts         # Learning progress tracking
│   ├── uploads-slice.ts          # Slide upload progress
│   ├── flashcards-slice.ts       # Flashcard state
│   └── slide-store.ts            # Zustand store for slide viewer
│
├── hooks/                        # Custom React hooks
│   ├── useAuth.ts                # Auth flow orchestration
│   ├── use-credits.ts            # AI credit balance polling
│   ├── use-feature-access.ts     # Premium feature gating
│   ├── use-push-notifications.ts # Web Push subscription management
│   ├── use-user-init.ts          # User profile bootstrapping
│   └── use-mobile.ts             # Mobile viewport detection
│
├── lib/                          # Shared utilities
│   ├── api.ts                    # 2,400-line Axios client (interceptors, token refresh, 60+ API methods)
│   ├── premium-limits.ts         # Free vs Premium feature limits and gate logic
│   ├── curriculum.ts             # Curriculum tree helpers
│   ├── guards.ts                 # Route protection utilities
│   ├── slides.ts                 # Slide URL resolution and helpers
│   ├── brand.ts                  # Brand constants and theme
│   ├── pricing.ts                # Plan definitions
│   ├── progress.ts               # Progress calculation helpers
│   └── ai.ts                     # AI prompt helpers
│
├── backend/                      # Django project root
│   ├── backend/                  # Django settings, ASGI, Celery, URLs
│   │   ├── settings.py           # Full settings (CORS, Channels, Celery, Cloudinary, JWT, email)
│   │   ├── asgi.py               # ASGI application with Channels routing
│   │   ├── celery.py             # Celery app configuration
│   │   └── urls.py               # Root URL routing
│   ├── accounts/                 # User management Django app
│   │   ├── models.py             # Profile, School, ClassGroup, SubscriptionTier, ClassRole
│   │   ├── views.py              # 38KB — signup, login, Google OAuth, profile, class management
│   │   ├── serializers.py        # User/profile serializers with tier-aware fields
│   │   ├── universal_admin.py    # Schema introspection for dynamic admin dashboard
│   │   └── permissions.py        # RBAC (IsStudent, IsClassHead, IsMaterialUploader, IsAdmin)
│   ├── curriculum/               # Content & AI Django app
│   │   ├── models.py             # 52KB — Subject, Block, SubBlock, Topic, Slide, SlideChunk,
│   │   │                         #   SlideImage, MCQQuestion, TheoryQuestion, FlashcardDeck,
│   │   │                         #   Flashcard, SpotStation, BrainBattle, BattleParticipant,
│   │   │                         #   BattleAnswer, UserStats, DailyStudySession, QuestionExposure
│   │   ├── ai_service.py         # Slide-aware AI chat (explain, resources, MCQ generation)
│   │   ├── ai_views.py           # 27KB — AI API endpoints (chat, explain, resources, flashcards)
│   │   ├── llm.py                # Provider-agnostic LLM client with multi-provider failover
│   │   ├── rag_service.py        # PDF chunking, embedding, similarity search
│   │   ├── slide_renderer.py     # PDF → page images via Cloudinary
│   │   ├── question_generator.py # AI question generation from slide content
│   │   └── consumers.py          # WebSocket consumers for battles and live features
│   ├── learning/                 # Cross-cutting learning infrastructure Django app
│   │   ├── models.py             # 36KB — AICreditAccount, AIUsageEvent, LearningEvent,
│   │   │                         #   XPAward, Achievement, Badge, UserAchievement, UserBadge,
│   │   │                         #   WeakArea, PracticeSession, PracticeAttempt, Notification,
│   │   │                         #   NotificationPreference, ScheduleItem
│   │   ├── events.py             # Single entry point for recording all learning activity
│   │   ├── xp.py                 # XP rules: base amounts, daily caps, diminishing returns,
│   │   │                         #   accuracy scaling, anti-farming time floors, streak bonuses
│   │   ├── credits.py            # AI credit accounting: row-locking spend(), monthly rollover,
│   │   │                         #   tier-based allowances (Free: 60/mo, Premium: 1500/mo)
│   │   ├── gamification.py       # Achievement/badge definitions and unlock logic
│   │   ├── battles.py            # Brain Battle mechanics (server-authoritative scoring)
│   │   ├── practice.py           # Steeplechase/Histology session management and grading
│   │   ├── analytics.py          # Performance overview, trends, topic breakdown, weak areas
│   │   ├── notifications.py      # Notification scheduling, deduplication, quiet hours, budgeting
│   │   ├── generation.py         # Quiz generation with question selection algorithms
│   │   ├── selection.py          # Smart question selection (avoids repeats via exposure tracking)
│   │   ├── dashboard.py          # Dashboard stats aggregation
│   │   └── tasks.py              # Celery tasks (theory grading, slide processing)
│   ├── credits/                  # Credit package Django app
│   │   ├── models.py             # CreditPackage, CreditLot (FIFO expiry), CreditTransaction
│   │   └── views.py              # Credit balance, purchase, and history endpoints
│   ├── payments/                 # Paystack integration Django app
│   │   ├── views.py              # Checkout, webhook (HMAC-verified), plan listing
│   │   └── pricing.py            # Plan catalogue (code, price in Naira, duration)
│   └── pastquestions/            # Past question bank Django app
│       ├── models.py             # PastQuestion model
│       └── views.py              # Past question browsing and filtering
│
├── public/                       # Static assets
│   ├── sw.js                     # Service worker (cache-first for assets, network-first for API)
│   └── manifest.json             # PWA manifest
│
├── render.yaml                   # Render Blueprint (web + worker + scheduler + redis)
└── vercel.json                   # Vercel deployment config (frontend)
```

---

## 🖥 Frontend Deep Dive

### App Shell
The authenticated app shell uses a **split navigation** pattern: desktop gets a collapsible sidebar (`AppSidebar`), mobile gets a thumb-reachable bottom tab bar (`MobileTabBar`). They never share a hamburger menu — the goal is to feel like a native app, not a shrunken website. An `AppTopbar` provides global search, notifications dropdown, and credit balance display.

Page transitions use Framer Motion's `PageTransition` component for smooth cross-route animations.

### State Management Strategy
- **Redux Toolkit** manages complex, server-synced state: quiz attempts (lifecycle from creation through submission), the study schedule (every mutation is a thunk hitting `/api/schedule/`), user profile and auth tokens, notification feeds, upload progress, and learning progress.
- **Zustand** manages ephemeral UI state like the slide viewer's current page and zoom level.
- All Redux slices use `createAsyncThunk` for API calls, keeping components free of `axios` imports and enabling consistent loading/error state patterns.

### API Client (`lib/api.ts`)
A 2,400-line centralised API client built on Axios with:
- **Automatic JWT refresh** — A response interceptor catches 401s, queues concurrent requests while refreshing, then replays them with the new token.
- **Public endpoint exclusion** — Auth endpoints (`/auth/signup/`, `/auth/login/`, etc.) skip the Authorization header.
- **60+ typed API method groups** — `authApi`, `quizApi`, `slideApi`, `flashcardApi`, `battleApi`, `scheduleApi`, `analyticsApi`, `creditApi`, `adminApi`, and more.
- **20-second timeout** with per-call overrides for long AI operations.

### Premium Feature Gating
The `use-feature-access` hook and `premium-limits.ts` module enforce client-side feature gates:

| Feature | Free | Premium |
|---|---|---|
| AI prompts/day | 5 | Unlimited |
| MCQ questions/quiz | 10 | 100 |
| Theory questions/quiz | 0 | 10 |
| Analytics dashboard | ✗ | ✓ |
| Community engagement | ✗ | ✓ |
| Video suggestions | ✗ | ✓ |

Server-side enforcement is the source of truth; client gates are for UX (showing upgrade prompts before the API rejects).

---

## ⚙️ Backend Deep Dive

### Event-Sourced Learning Infrastructure
The `learning` app is the central nervous system. The `events.record()` function is the **single entry point** for all learning activity:

```
record()
  ├── writes LearningEvent          (audit trail for analytics)
  ├── awards XP                     (capped, farm-resistant)
  ├── updates WeakArea              (mastery per curriculum node)
  ├── updates DailyStudySession     (study time tracking)
  └── advances streak               (UserStats)
```

This prevents analytics, XP, weak-area detection, and study-time tracking from ever disagreeing with each other.

### Provider-Agnostic LLM Client (`curriculum/llm.py`)
Emby's LLM integration is designed for zero-downtime on free-tier rate limits:

1. **Multi-provider failover chain** — Primary provider (Groq), then Backup 1 (Cerebras), Backup 2 (OpenRouter). Adding a new provider is a `.env` change, not a code change.
2. **Per-provider fallback models** — If the primary model (e.g., `gpt-oss-120b`) is rate-limited, it tries the fallback model (e.g., `qwen3.8-27b`) on the same provider before moving to the next provider.
3. **Retry with exponential backoff** — Honours `Retry-After` headers. Retries on 429 and 5xx status codes.
4. **Structured output** — Uses strict `json_schema` when available, degrades to `json_object` mode for providers that lack it.
5. **Vision support** — Text-only models are the default; requests carrying images are automatically routed to a multimodal sibling model. Falls back to text-only if vision fails.

### RAG Pipeline (`curriculum/rag_service.py`)
1. **PDF Processing** — Slide PDFs are uploaded to Cloudinary, then a Celery task extracts text page-by-page via `content_extractor.py`.
2. **Chunking** — Extracted text is split into 800-word chunks with 100-word overlap.
3. **Embedding** — Chunks are embedded with `SentenceTransformer('all-MiniLM-L6-v2')`, lazy-loaded on first use with a 15-second timeout to keep server boot fast.
4. **Retrieval** — When a student asks a question, cosine similarity finds the most relevant chunks, which are injected into the LLM prompt alongside the student's question.

---

## 🤖 AI & LLM Integration

| AI Feature | Cost (Credits) | Async? | Description |
|---|---|---|---|
| Chat | 1 | No | Per-slide conversational AI tutor |
| Explain | 1 | No | Detailed explanation of slide content |
| Resources | 1 | No | YouTube links and textbook references |
| Dashboard Message | 1 | No | Motivational/contextual dashboard copy |
| Grade Theory | 2 | Yes (Celery) | Free-text answer evaluation with feedback |
| Generate Flashcards | 3 | No | Create flashcard deck from slide |
| Study Plan | 3 | No | Personalised daily schedule |
| Battle Questions | 4 | No | Generate multiplayer quiz questions |
| Generate Theory Qs | 5 | No | Create theory questions from content |
| Generate MCQs | 8 | No | Create multiple-choice questions from content |

---

## 💰 Credit & Monetisation System

### Dual Credit Architecture
Emby runs **two complementary credit systems** for different purposes:

1. **AI Credit Account** (`learning.models.AICreditAccount`) — Monthly allowance for AI operations.
   - Free: 60 credits/month, Premium: 1,500 credits/month.
   - Uses `SELECT ... FOR UPDATE` row locking so two concurrent AI requests on the same account serialise (a student with 1 credit left cannot spend it twice).
   - Context-manager pattern: `spend()` reserves credits on entry, `charge()` confirms on clean exit, `refund()` gives credits back on exception.

2. **Credit Lots** (`credits.models.CreditLot`) — Purchasable, FIFO-expiring credit packages priced in Naira.
   - Each purchase creates a `CreditLot` with `original_amount`, `remaining_amount`, and optional `expires_at`.
   - Spending drains the oldest non-expired lot first.
   - Full transaction audit trail via `CreditTransaction`.

### Paystack Payment Flow
1. Frontend calls `/api/payment/checkout/` with a plan code.
2. Backend initialises a Paystack transaction and returns an `authorization_url`.
3. User completes payment on Paystack's hosted page.
4. Paystack fires a webhook to `/api/payment/webhook/`.
5. Backend verifies the HMAC-SHA512 signature against `PAYSTACK_SECRET_KEY`.
6. On successful verification, `_activate_premium()` idempotently upgrades the user's `Profile.subscription_tier` and extends `subscription_expires_at`.

---

## 🎮 Gamification Engine

### XP System Design Philosophy
XP tracks *genuine learning*, not button clicking. The rules:

| Rule | Implementation |
|---|---|
| Daily caps per activity | e.g., max 180 XP/day from quizzes |
| Diminishing returns | 1st quiz = 100%, 2nd = 85%, 5th = 40%, 8th+ = 10% |
| Accuracy scaling | Score scales the award; deliberately wrong = 0 XP |
| Anti-farming time floors | < 3 seconds/question answered = 0 XP |
| Streak bonuses | 3-day: +5%, 7-day: +12%, 14-day: +20%, 30-day: +30% |
| Passive presence = 0 XP | No XP for having a tab open |

### Achievements
| Achievement | Category | Target | Rarity |
|---|---|---|---|
| First Steps | Quizzes | 1 quiz completed | Common |
| Quiz Explorer | Quizzes | 10 quizzes | Uncommon |
| Quiz Master | Quizzes | 100 quizzes | Rare |
| Certified Scholar | Quizzes | Pass a formal assessment ≥ 50% | Epic |
| First Review | Flashcards | 1 flashcard reviewed | Common |

---

## ⚡ Real-Time Features

### WebSocket Architecture
Django Channels routes WebSocket connections through Daphne:
- `curriculum/consumers.py` — Battle consumers for real-time question delivery, answer submission, and live leaderboard updates.
- `learning/consumers.py` — Notification delivery for in-app alerts.
- `curriculum/routing.py` and `learning/routing.py` — URL routing for WebSocket endpoints.

### Brain Battle Flow
1. Host creates a battle (selects subject/topic, system generates questions via AI).
2. Players join via 6-character code over WebSocket.
3. Questions delivered one at a time to all participants simultaneously.
4. Answers submitted over WebSocket; server scores immediately (base 100 + up to 50 speed bonus).
5. Correct answers **never** sent to clients during play — only revealed after submission.
6. `BattleAnswer` has a unique constraint per `(participant, question_index)` preventing score inflation via replay.

---

## 🔐 Authentication & Authorisation

### Auth Flow
- **Native Auth** — Email/password signup with email verification token, password reset flow.
- **Google OAuth** — One-tap sign-in via `@react-oauth/google` on frontend, token verification on backend.
- **JWT Tokens** — Short-lived access tokens stored in `sessionStorage`, with refresh token rotation. The Axios interceptor handles transparent refresh and request queuing.

### Role-Based Access Control
| Role | Access |
|---|---|
| Student | Standard app features, free-tier limits |
| Class Head | Upload slides, create announcements/countdowns, manage class group (max 3 per class, admin-verified) |
| Material Uploader | Upload slides to specific curriculum nodes |
| Admin (`is_staff`) | Full admin dashboard access |
| Superuser (`is_superuser`) | All admin + system-level operations |

---

## 🚀 Local Development Setup

### Prerequisites
- **Node.js** 18+
- **Python** 3.11+
- **PostgreSQL** (or use default SQLite for development)
- **Redis** server

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/emby.git
cd emby
```

### 2. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env — minimally set SECRET_KEY, DB credentials, and LLM_API_KEY

# Run database migrations
python manage.py migrate

# Seed curriculum data (optional)
python populate_curriculum.py
python seed_onboarding.py

# Start Redis (ensure it's installed and running)
# Windows: redis-server
# macOS: brew services start redis

# Start Celery worker (separate terminal)
celery -A backend worker --loglevel=info --concurrency=2

# Start the Django development server
python manage.py runserver
```

### 3. Frontend Setup
```bash
# From the project root
npm install

# Configure environment
# Create .env.local and set:
#   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
#   NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id
#   NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY=your-paystack-key

# Start the development server (with Turbopack)
npm run dev
```

Visit `http://localhost:3000`.

---

## 🔑 Environment Variables

### Frontend (`.env.local`)
| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth 2.0 Client ID |
| `NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY` | Paystack public key for checkout |
| `NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET` | Cloudinary unsigned upload preset |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | VAPID public key for push notifications |
| `NEXT_PUBLIC_VERCEL_ANALYTICS` | Enable Vercel Analytics |

### Backend (`.env`)
| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for dev, `False` for production |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `REDIS_URL` | Redis connection string |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins |
| `LLM_BASE_URL` | Primary LLM provider URL (e.g., `https://api.groq.com/openai/v1`) |
| `LLM_API_KEY` | Primary LLM API key |
| `LLM_MODEL` | Primary model (default: `openai/gpt-oss-120b`) |
| `LLM_BACKUP_1_BASE_URL` / `_API_KEY` / `_MODEL` | Backup LLM provider 1 |
| `LLM_BACKUP_2_BASE_URL` / `_API_KEY` / `_MODEL` | Backup LLM provider 2 |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Cloudinary credentials |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID (server-side verification) |
| `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` | Paystack API keys |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials for transactional email |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |
| `VAPID_PRIVATE_KEY` | VAPID private key for push notifications |

---

## 🚢 Deployment

### Frontend → Vercel
Deploy via Vercel CLI (`vercel`) or connect your GitHub repository in the Vercel dashboard. Set all `NEXT_PUBLIC_*` environment variables in the Vercel project settings.

### Backend → Render
The `render.yaml` Blueprint defines four services. The app image includes Python 3.12, LibreOffice and OCR dependencies:

| Service | Type | Runtime | Start Command |
|---|---|---|---|
| `emby-backend` | Web | Docker | `bash render_start.sh web` |
| `emby-celery-worker` | Worker | Docker | `bash render_start.sh worker` |
| `emby-scheduler` | Worker, one instance | Docker | `bash render_start.sh scheduler` |
| `emby-redis` | Redis | Managed | — |

Follow [PRODUCTION_RECOVERY.md](docs/PRODUCTION_RECOVERY.md) before applying the Blueprint. Link web, worker and scheduler to the existing persistent PostgreSQL database and shared integration configuration through the `emby-production` environment group. The web release hook runs guarded migrations; startup never seeds replacement accounts or content. SQLite is refused on Render. Review service plans and verify the container in staging before rollout.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full checklist including Google OAuth domain setup, CORS configuration, and post-deployment verification.

---

## 📚 Documentation

| Document | Description |
|---|---|
| [TECHNICAL_ARCHITECTURE.pdf](TECHNICAL_ARCHITECTURE.pdf) | System design, data flows, infrastructure diagrams |
| [PRD.pdf](PRD.pdf) | Product vision, user personas, feature specifications, roadmap |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | REST endpoint specs, request/response schemas, rate limits |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Vercel + Render deployment guide |

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is proprietary and confidential. Unauthorised copying, distribution, or modification is strictly prohibited.
