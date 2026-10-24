# Product Requirements Document (PRD) - Emby Quiz System

## 1. Product Vision
Emby is an intelligent, scalable, and highly interactive educational platform designed to modernize exam preparation. By combining traditional multiple-choice (MCQ) and theory assessments with cutting-edge AI evaluation and Retrieval-Augmented Generation (RAG) study materials, Emby provides students with highly personalized feedback and comprehensive study pathways.

## 2. Target Audience
- **Medical/University Students:** Seeking structured practice (MCQ and Theory) mapped to specific curriculums (Subjects, Blocks, Topics).
- **Educators/Administrators:** Creating curriculums, uploading slide decks, and managing student cohorts.

## 3. User Personas
### 3.1. "The Free-Tier Student"
- Needs quick, accessible practice before exams.
- Limited to 5 MCQs and 1 Theory question per quiz.
- Value proposition: Experiencing the platform's core interface and basic AI grading to encourage conversion.

### 3.2. "The Premium Scholar"
- Requires deep, intensive study sessions.
- Takes full mock exams (100+ MCQs, 10 Theory questions).
- Relies on detailed, AI-generated performance breakdowns, topic-level weaknesses, and recommendations.

### 3.3. "The System Administrator"
- Manages the platform via a dynamic backend-driven admin dashboard.
- Monitors payments, updates curriculum mapping, and oversees user accounts.

## 4. Key Capabilities & Features

### 4.1. Core Assessment Engine
- **Configurable Quizzes:** Users can generate quizzes by selecting Subject, Block, Topic, Exam Type (Practice, Mock, Formal), Duration, and Difficulty.
- **Hybrid Question Support:** Supports instant-graded MCQs and AI-graded Theory questions.
- **Stateful Attempts:** Auto-saving of answers, flagging questions for review, and timed auto-submission.
- **Slide Practice Mode:** Contextual questions linked directly to specific study slides.

### 4.2. AI-Powered Evaluation & Analysis
- **Theory Grading:** Asynchronous grading of free-text answers using LLMs, providing a score, correct answer rationale, and personalized feedback.
- **Performance Analytics:** Breakdown of performance by topic and difficulty.
- **Missed Questions Analysis:** Premium feature offering detailed explanations for incorrect answers to close knowledge gaps.

### 4.3. Subscription & Credit System
- **Tiered Access:** 
  - *Free:* Capped quiz sizes, basic grading, limited concurrent quizzes.
  - *Premium:* Unlimited concurrent quizzes, large question sets, detailed AI analysis.
- **Credit Tracking:** Internal system to monitor API/LLM usage to ensure sustainable unit economics per user.
- **Automated Payments:** Paystack integration for seamless upgrades and webhook-driven account provisioning.

### 4.4. Administrative Dashboard
- **Dynamic Schema Rendering:** Next.js dashboard that dynamically builds UI panels based on the Django backend schema.
- **Full CRUD Operations:** Manage Users, Curriculums, Questions, and Payments directly from the web interface.

## 5. Functional Requirements

### 5.1. User Authentication
- Native email/password registration with verification flow.
- Google OAuth integration for frictionless onboarding.
- Password reset and account recovery flows.

### 5.2. Quiz Taking Experience
- Responsive, distraction-free UI (Next.js + Tailwind).
- Client-side timer synced with server deadlines.
- Offline-resilient local state management (Zustand) with periodic server syncing.

### 5.3. Content Management (RAG)
- Uploading PDF slide decks and processing them into vector embeddings.
- Extracting text and context to generate relevant study questions.

## 6. Non-Functional Requirements
- **Performance:** Quiz generation must take < 2 seconds. API responses (excluding AI) must be < 200ms.
- **Scalability:** Celery workers must autoscale to handle spikes during exam seasons (e.g., thousands of simultaneous theory evaluations).
- **Availability:** 99.9% uptime target.
- **Security:** Strict separation of tenant data. Webhook endpoints must mathematically verify Paystack signatures. JWT tokens must have short lifespans with secure refresh rotation.
- **Responsiveness:** 100% mobile-friendly UI for on-the-go studying.

## 7. Future Roadmap
- **Phase 2:** Gamification (Leaderboards, Streaks, Badges).
- **Phase 3:** Collaborative Study Groups and Peer-to-Peer grading.
- **Phase 4:** Spaced Repetition System (SRS) integration for missed questions.
- **Phase 5:** Native iOS and Android applications.
