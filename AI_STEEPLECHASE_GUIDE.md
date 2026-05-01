# AI Integration & Steeplechase Implementation Guide

## AI Integration in Reader

### 1. AI Panel Component Structure

```typescript
// components/reader/ai-panel.tsx

interface AIPanelProps {
  slideContent: string // Current slide text content
  highlightedText?: string // User-selected text
  courseId: string
  topicId: string
}

// Features to implement:
// - Chat interface
// - Highlight text → Ask question flow
// - Video suggestions
// - Past question recommendations
// - Key concept highlighting
```

### 2. AI Service API

```typescript
// lib/ai-service.ts

// Question answering
async function askQuestion(
  question: string,
  context: {
    slideContent: string
    highlightedText?: string
    courseId: string
    topicId: string
  }
): Promise<{
  answer: string
  sources: Array<{ type: 'slide' | 'external'; reference: string }>
  relatedVideos?: Array<{ title: string; url: string }>
  relatedQuestions?: Array<{ id: string; question: string }>
}>

// Highlight important concepts
async function highlightConcepts(
  slideContent: string
): Promise<Array<{ text: string; reason: string }>>

// Suggest past questions
async function suggestPastQuestions(
  topicId: string,
  completed: boolean
): Promise<Array<{ id: string; question: string; type: 'mcq' | 'theory' }>>

// Sort uploaded past questions
async function sortPastQuestion(
  question: string,
  options?: string[]
): Promise<{ topicId: string; difficulty: 'easy' | 'medium' | 'hard' }>
```

### 3. AI Interaction Flow

```
User reads slide
  ↓
User highlights text (optional)
  ↓
User clicks AI button
  ↓
AI panel opens
  ↓
User asks question
  ↓
AI analyzes:
  1. Check slide content first
  2. Check highlighted text context
  3. If needed, search external resources
  ↓
AI responds with:
  - Answer
  - Sources (slide page numbers or external links)
  - Related videos (if applicable)
  - Related past questions
  ↓
After topic completion:
  AI suggests quiz with past questions
```

### 4. AI Button Placement

**Desktop:**
```
┌─────────────────────────────────────┐
│                                     │
│         Slide Content               │
│                                     │
│                                     │
│                              [AI]   │ ← Floating button
│                                     │
└─────────────────────────────────────┘
```

**Mobile:**
```
┌──────────────────┐
│                  │
│  Slide Content   │
│                  │
│                  │
│           [AI]   │ ← Floating button
│                  │
└──────────────────┘
```

When clicked, AI panel slides in from right (desktop) or bottom (mobile).

---

## Steeplechase (Spotter) Adaptive System

### 1. Image Database Structure

```typescript
// lib/steeplechase-db.ts

interface SteeplechaseImage {
  id: string
  imageUrl: string
  subject: 'gross-anatomy' | 'histology' | 'embryology'
  topicId: string // Links to curriculum
  difficulty: 'easy' | 'medium' | 'hard' | 'very-hard'
  pins: Array<{
    id: string
    x: number // Percentage from left
    y: number // Percentage from top
    structure: string
    acceptedAnswers: string[] // Variations of correct answer
    explanation: string
  }>
  metadata: {
    source: string
    uploadedBy: string
    uploadedAt: Date
    verified: boolean
  }
}
```

### 2. Adaptive Algorithm

```typescript
// lib/steeplechase-adaptive.ts

interface UserPerformance {
  userId: string
  topicId: string
  currentDifficulty: 'easy' | 'medium' | 'hard' | 'very-hard'
  correctAnswers: number
  totalAttempts: number
  averageTime: number // seconds per question
  streak: number
}

function getNextQuestion(
  performance: UserPerformance,
  availableImages: SteeplechaseImage[]
): SteeplechaseImage {
  // Algorithm:
  // 1. Start with easy questions
  // 2. If 3 consecutive correct → increase difficulty
  // 3. If 2 consecutive incorrect → decrease difficulty
  // 4. Consider average time (too fast = might be guessing)
  // 5. Ensure variety (don't repeat same structures too often)
}

function updateDifficulty(
  performance: UserPerformance,
  wasCorrect: boolean,
  timeSpent: number
): 'easy' | 'medium' | 'hard' | 'very-hard' {
  // Adaptive logic here
}
```

### 3. Steeplechase UI Flow

```
User selects Steeplechase
  ↓
Choose subject: Gross Anatomy / Histology / Embryology
  ↓
Choose scope: Specific topic / Block / All
  ↓
AI loads first question (easy difficulty)
  ↓
Display image with pin
  ↓
User types answer
  ↓
AI checks answer (fuzzy matching for variations)
  ↓
Show result:
  - Correct: Green checkmark, explanation, next question
  - Incorrect: Red X, show correct answer, explanation, next question
  ↓
AI adjusts difficulty based on performance
  ↓
Continue until:
  - User completes set number of questions
  - User exits
  - Time limit reached (if timed mode)
```

### 4. Answer Matching System

```typescript
// lib/steeplechase-matching.ts

function matchAnswer(
  userAnswer: string,
  acceptedAnswers: string[]
): { isCorrect: boolean; matchedAnswer?: string; confidence: number } {
  // Fuzzy matching algorithm:
  // 1. Normalize: lowercase, trim, remove extra spaces
  // 2. Check exact match
  // 3. Check partial match (Levenshtein distance)
  // 4. Check for common abbreviations
  // 5. Return confidence score (0-100)
  
  // Examples:
  // "brachial artery" matches "Brachial Artery"
  // "brachial a." matches "brachial artery"
  // "brachialartery" matches "brachial artery"
  // "brachial" might match "brachial artery" with lower confidence
}
```

### 5. Training the AI

**Data Requirements:**
1. Large dataset of anatomy images (1000+ images)
2. Each image labeled with:
   - Structure names
   - Pin coordinates
   - Difficulty level
   - Topic/block association
3. Variations of correct answers for each structure

**Training Process:**
1. Upload images to database
2. Medical experts verify pin placements
3. Add accepted answer variations
4. Classify by difficulty
5. Link to curriculum topics
6. AI learns patterns:
   - Which structures are commonly confused
   - Which angles/views are harder
   - Which topics need more practice

**Continuous Improvement:**
- Track user answers
- Identify common wrong answers
- Add them as accepted variations if valid
- Adjust difficulty ratings based on user performance data

---

## Implementation Priority

### Phase 1: Core Structure ✅
- [x] Curriculum structure
- [x] Course filtering
- [x] Upload flow
- [x] Progress tracking utilities

### Phase 2: Reader & AI (Next)
- [ ] Update reader component with AI button
- [ ] Build AI panel component
- [ ] Implement AI service API
- [ ] Add highlight-to-ask feature
- [ ] Integrate video suggestions

### Phase 3: Quiz System
- [ ] Build quiz filtering
- [ ] Implement MCQ timer
- [ ] Add theory questions
- [ ] Past question upload
- [ ] AI-powered question sorting

### Phase 4: Steeplechase
- [ ] Design image database schema
- [ ] Build image upload system
- [ ] Implement pin placement tool
- [ ] Create adaptive algorithm
- [ ] Build steeplechase UI
- [ ] Train AI on image dataset

### Phase 5: Integration & Polish
- [ ] Connect all systems
- [ ] Real-time progress updates
- [ ] Performance optimization
- [ ] User testing
- [ ] Bug fixes

---

## API Endpoints Needed

```typescript
// AI Service
POST /api/ai/ask-question
POST /api/ai/highlight-concepts
GET  /api/ai/suggest-videos
GET  /api/ai/suggest-questions

// Past Questions
POST /api/past-questions/upload
POST /api/past-questions/sort
GET  /api/past-questions/by-topic/:topicId

// Steeplechase
GET  /api/steeplechase/images
POST /api/steeplechase/submit-answer
GET  /api/steeplechase/next-question
POST /api/steeplechase/upload-image

// Progress
GET  /api/progress/courses
POST /api/progress/update-slide
POST /api/progress/update-course
GET  /api/progress/recent
```

---

## Notes

- AI should always prioritize slide content over external sources
- Steeplechase is ONLY for anatomy (gross, histo, embryo)
- Progress must be real-time and persistent
- All user data should be stored securely
- Consider offline mode for reader (cache slides)
- Implement rate limiting for AI API calls
- Add analytics to track feature usage
