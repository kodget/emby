# Course Structure Documentation

## Overview
This document describes the complete course structure for the Emby BMS Edition, including the curriculum hierarchy, upload flow, quiz system, steeplechase (spotter) system, and AI integration.

---

## 1. Curriculum Hierarchy

### Structure
```
Subject (Anatomy, Physiology, Medical Biochemistry)
  └── Block (Block 1, Block 2, Block 3, [Block 4 for Physiology])
       └── Topic (Only for Anatomy & Physiology)
```

### Anatomy
- **Block 1**: Gross Anatomy, Embryology, Histology
- **Block 2**: Gross Anatomy, Embryology, Histology
- **Block 3**: Gross Anatomy, Embryology, Histology

### Physiology
- **Block 1**: General Physiology, ANS, Neuromuscular Physiology, Blood & Body Fluids
- **Block 2**: Respiratory Physiology, Cardiovascular System, Nutrient Metabolism, Gastrointestinal Tract
- **Block 3**: Renal Physiology, Endocrinology, Reproductive Physiology
- **Block 4**: Sensory System, Special Senses, Motor System, Integrative Functions

### Medical Biochemistry
- **Block 1**: No sub-topics (slides uploaded directly to block)
- **Block 2**: No sub-topics (slides uploaded directly to block)
- **Block 3**: No sub-topics (slides uploaded directly to block)

---

## 2. My Courses Page

### Features
1. **Filter Buttons**: All, Anatomy, Physiology, Biochemistry
2. **Recent Courses Section**: Shows 3 most recently accessed courses at the top
3. **Dynamic Progress Indicators**: Progress bars update based on actual slide reading progress
4. **Course Cards**: Display all courses based on selected filter

### Display Logic
- **All**: Shows all courses from all subjects in no particular order
- **Anatomy**: Shows only anatomy blocks/topics
- **Physiology**: Shows only physiology blocks/topics
- **Biochemistry**: Shows only biochemistry blocks

---

## 3. Slide Upload Flow

### For Anatomy & Physiology
1. Select **Subject** (Anatomy or Physiology)
2. Select **Block** (Block 1, 2, 3, or 4)
3. Select **Topic** (e.g., Gross Anatomy, Embryology, Histology for Anatomy)
4. Upload file and enter title
5. Submit

### For Medical Biochemistry
1. Select **Subject** (Medical Biochemistry)
2. Select **Block** (Block 1, 2, or 3)
3. Upload file and enter title (no topic selection needed)
4. Submit

### File Types Supported
- PDF (.pdf)
- PowerPoint (.ppt, .pptx)

---

## 4. Reader & AI Integration

### Reader Layout
- **Desktop**: Large reading area with AI button overlay (not split screen)
- **Mobile**: Full-screen reading with AI button overlay

### AI Features
1. **Contextual Q&A**: Answer questions about highlighted text or entire slide
2. **External Resources**: AI can pull from external sources when needed
3. **Video Suggestions**: AI suggests relevant videos for topics
4. **Highlight Important Parts**: AI can highlight key concepts
5. **Past Questions Integration**: AI sorts and suggests past questions by topic
6. **Post-Topic Quizzes**: After each topic, AI suggests MCQs and theory questions

### AI Interaction Flow
1. User highlights text or asks question
2. AI analyzes from slide content first
3. If needed, AI pulls from external resources
4. AI provides answer with sources
5. AI suggests related past questions and quizzes

---

## 5. Quiz System

### Structure
Similar to courses section:
- Filter by subject, block, or topic
- Choose quiz scope (single topic, entire block, or whole course)
- MCQs are timed
- Theory questions are untimed

### Quiz Types
1. **MCQs**: Multiple choice, timed, auto-graded
2. **Theory**: Written answers, untimed, manual/AI grading

### Past Questions
- Uploaded by class reps/uploaders
- AI automatically sorts them by topic
- AI suggests relevant past questions after completing each topic

---

## 6. Steeplechase (Spotter) System

### Overview
Adaptive image-based question system for Anatomy (Gross Anatomy, Histology, Embryology only)

### Features
1. **Image API**: Large database of real-life anatomy images
2. **Pin System**: Images have pins marking structures to identify
3. **Adaptive Difficulty**: AI adjusts difficulty based on performance
   - Easy → Medium → Difficult → Very Difficult
4. **AI Training**: AI is trained on the pinning system and image database

### Adaptive Reasoning
- Starts with easy questions
- Monitors user performance
- Gradually increases difficulty
- Provides harder questions as user improves
- Goal: Build strong spotter skills through progressive challenge

### Scope
- **Only for Anatomy**: Gross Anatomy, Histology, Embryology
- **Not for**: Physiology, Biochemistry

---

## 7. Dynamic Progress Tracking

### Implementation
Progress indicators must be dynamic and reflect actual user progress:

1. **Slide Reading Progress**
   - Track which slides user has viewed
   - Track time spent on each slide
   - Calculate percentage based on slides completed vs total slides

2. **Course Progress**
   - Aggregate progress across all topics in a course
   - Weight by number of slides in each topic
   - Update in real-time as user progresses

3. **Recent Courses**
   - Track last accessed timestamp for each course
   - Display 3 most recent at top of My Courses page
   - Show last accessed time (e.g., "2 hours ago", "Yesterday")

### Progress Calculation Example
```
Course Progress = (Slides Viewed / Total Slides) × 100
```

---

## 8. Implementation Files

### Key Files Modified
1. **`lib/curriculum.ts`**: Curriculum structure (single source of truth)
2. **`app/(app)/courses/page.tsx`**: My Courses page with filtering and recent courses
3. **`components/app/slide-upload-modal.tsx`**: Hierarchical upload flow

### Files to Create/Update
1. **Reader Component**: Add AI panel integration
2. **Quiz System**: Implement filtering and quiz generation
3. **Steeplechase Component**: Build adaptive spotter system
4. **Progress Tracking**: Implement dynamic progress calculation
5. **AI Service**: Create AI integration for Q&A, suggestions, and past question sorting

---

## 9. Next Steps

### Immediate
- [ ] Test slide upload flow for all subjects
- [ ] Implement dynamic progress tracking
- [ ] Add recent courses tracking

### Short-term
- [ ] Build AI panel in reader
- [ ] Implement quiz filtering system
- [ ] Create past questions upload and sorting

### Long-term
- [ ] Build steeplechase image API
- [ ] Train AI on pinning system
- [ ] Implement adaptive difficulty algorithm
- [ ] Add video suggestions feature

---

## Notes
- All progress indicators must be dynamic, not static mock data
- AI should prioritize slide content before external resources
- Steeplechase is anatomy-specific only
- Biochemistry blocks have no sub-topics
- Recent courses section shows maximum 3 courses
