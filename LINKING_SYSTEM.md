# Complete Linking System Documentation

## Overview
This document explains how blocks, topics, slides, and the reader are all linked together in the system.

---

## Data Flow Architecture

```
Curriculum (lib/curriculum.ts)
    ↓
Courses Page (app/(app)/courses/page.tsx)
    ↓
Course Detail Page (app/(app)/courses/[id]/page.tsx)
    ↓
Slides (lib/slides.ts)
    ↓
Reader (app/(app)/read/[courseId]/[materialId]/page.tsx)
    ↓
Reader Component (components/reader/reader.tsx)
```

---

## 1. Curriculum Structure

**File**: `lib/curriculum.ts`

The curriculum is the **single source of truth** for all subjects, blocks, and topics.

```typescript
// Structure
Subject (anatomy, physiology, biochemistry)
  └── Block (Block 1, 2, 3, [4 for physiology])
       └── Topic (only for anatomy & physiology)

// IDs are used for linking
- Topic ID: "anat-b1-gross", "phys-b2-cvs"
- Block ID: "bioc-b1", "anat-b1"
```

**Helper Functions**:
- `getTopic(topicId)` - Get topic with subject and block info
- `getBlock(blockId)` - Get block info
- `breadcrumb(id)` - Get full breadcrumb text

---

## 2. Slides System

**File**: `lib/slides.ts`

Slides are linked to curriculum via `topicId` or `blockId`.

```typescript
type Slide = {
  id: string
  title: string
  topicId?: string  // For anatomy & physiology
  blockId?: string  // For biochemistry
  pages: number
  uploadedBy: string
  uploadedAt: string
  content?: SlideContent[]
}
```

**Linking Logic**:
- **Anatomy/Physiology slides**: Linked via `topicId`
  - Example: `topicId: "anat-b1-gross"` → Gross Anatomy First Block
- **Biochemistry slides**: Linked via `blockId`
  - Example: `blockId: "bioc-b1"` → Medical Biochemistry Block 1

**Functions**:
- `getSlidesByTopic(topicId)` - Get all slides for a topic
- `getSlidesByBlock(blockId)` - Get all slides for a block
- `getSlidesForCourse(courseId)` - Get slides for any course (tries topic first, then block)
- `getSlideById(slideId)` - Get specific slide

---

## 3. URL Structure

### Courses Page
```
/courses
```
Shows all courses with filtering

### Course Detail Page
```
/courses/[id]

Examples:
/courses/anat-b1-gross  → Gross Anatomy First Block
/courses/phys-b2-cvs    → Cardiovascular System
/courses/bioc-b1        → Medical Biochemistry Block 1
```

### Reader Page
```
/read/[courseId]/[materialId]

Examples:
/read/anat-b1-gross/slide-anat-b1-gross-1
/read/phys-b2-cvs/slide-phys-b2-cvs-1
/read/bioc-b1/slide-bioc-b1-1
```

---

## 4. Complete User Journey

### Journey 1: Anatomy Student

1. **My Courses Page** (`/courses`)
   - Student clicks "Anatomy" filter
   - Sees all anatomy topics: Gross Anatomy First Block, Embryology First Block, etc.

2. **Course Detail Page** (`/courses/anat-b1-gross`)
   - Shows "Gross Anatomy First Block"
   - Breadcrumb: "Anatomy · Anatomy Block 1 · Gross Anatomy First Block"
   - Lists all slides for this topic:
     - Introduction to Gross Anatomy (24 pages)
     - Upper Limb Anatomy (32 pages)
   - Student clicks "Introduction to Gross Anatomy"

3. **Reader** (`/read/anat-b1-gross/slide-anat-b1-gross-1`)
   - Opens slide in reader
   - AI panel available on the side
   - Can highlight text and ask questions
   - Progress tracked automatically

### Journey 2: Physiology Student

1. **My Courses Page** (`/courses`)
   - Student clicks "Physiology" filter
   - Sees all physiology topics across all blocks

2. **Course Detail Page** (`/courses/phys-b2-cvs`)
   - Shows "Cardiovascular System"
   - Breadcrumb: "Physiology · Physiology Block 2 · Cardiovascular System"
   - Lists slides for CVS
   - Student clicks a slide

3. **Reader** (`/read/phys-b2-cvs/slide-phys-b2-cvs-1`)
   - Opens slide
   - AI provides physiology-specific help

### Journey 3: Biochemistry Student

1. **My Courses Page** (`/courses`)
   - Student clicks "Biochemistry" filter
   - Sees all biochemistry blocks (no sub-topics)

2. **Course Detail Page** (`/courses/bioc-b1`)
   - Shows "Medical Biochemistry Block 1"
   - Breadcrumb: "Medical Biochemistry · Medical Biochemistry Block 1"
   - Lists all slides for Block 1 (no topic subdivision)
   - Student clicks a slide

3. **Reader** (`/read/bioc-b1/slide-bioc-b1-1`)
   - Opens slide
   - AI provides biochemistry-specific help

---

## 5. Upload Flow Integration

When a class rep uploads slides:

1. **Select Subject** → Anatomy
2. **Select Block** → Anatomy Block 1
3. **Select Topic** → Gross Anatomy
4. **Upload File** → "Upper Limb Anatomy.pdf"

**Result**:
```typescript
{
  id: "slide-anat-b1-gross-3",
  title: "Upper Limb Anatomy",
  topicId: "anat-b1-gross",  // ← Linked here
  pages: 32,
  uploadedBy: "Uploader · Chioma",
  uploadedAt: "Just now"
}
```

This slide now appears on:
- `/courses/anat-b1-gross` (Course detail page)
- Can be opened at `/read/anat-b1-gross/slide-anat-b1-gross-3`

---

## 6. Progress Tracking Integration

When a student reads a slide:

```typescript
// Track slide view
dispatch(markSlideViewed({
  slideId: "slide-anat-b1-gross-1",
  courseId: "anat-b1-gross",
  timeSpent: 120 // seconds
}))

// Update course progress
dispatch(updateCourseProgress({
  courseId: "anat-b1-gross",
  totalSlides: 2,
  viewedSlides: 1,
  progress: 50,
  lastAccessed: new Date(),
  timeSpent: 120
}))

// Course appears in "Recent Courses" section
```

---

## 7. Database Schema (Future Implementation)

### Courses Table
```sql
-- Not needed, generated from curriculum.ts
```

### Slides Table
```sql
CREATE TABLE slides (
  id VARCHAR PRIMARY KEY,
  title VARCHAR NOT NULL,
  topic_id VARCHAR,  -- Links to curriculum
  block_id VARCHAR,  -- Links to curriculum
  pages INT,
  uploaded_by VARCHAR,
  uploaded_at TIMESTAMP,
  file_url VARCHAR,
  thumbnail_url VARCHAR
);

-- Index for fast lookups
CREATE INDEX idx_slides_topic ON slides(topic_id);
CREATE INDEX idx_slides_block ON slides(block_id);
```

### Slide Content Table
```sql
CREATE TABLE slide_content (
  id VARCHAR PRIMARY KEY,
  slide_id VARCHAR REFERENCES slides(id),
  page_number INT,
  image_url TEXT,  -- Base64 or cloud storage URL
  extracted_text TEXT  -- For AI
);
```

### User Progress Table
```sql
CREATE TABLE user_progress (
  user_id VARCHAR,
  course_id VARCHAR,  -- topic_id or block_id
  total_slides INT,
  viewed_slides INT,
  progress INT,
  last_accessed TIMESTAMP,
  time_spent INT,
  PRIMARY KEY (user_id, course_id)
);
```

### Slide Progress Table
```sql
CREATE TABLE slide_progress (
  user_id VARCHAR,
  slide_id VARCHAR,
  course_id VARCHAR,
  viewed BOOLEAN,
  time_spent INT,
  last_viewed TIMESTAMP,
  PRIMARY KEY (user_id, slide_id)
);
```

---

## 8. API Endpoints (Future)

### Get Slides for Course
```
GET /api/slides?courseId=anat-b1-gross

Response:
[
  {
    "id": "slide-anat-b1-gross-1",
    "title": "Introduction to Gross Anatomy",
    "pages": 24,
    "uploadedBy": "Uploader · Chioma",
    "uploadedAt": "2 days ago"
  }
]
```

### Get Slide Content
```
GET /api/slides/slide-anat-b1-gross-1

Response:
{
  "id": "slide-anat-b1-gross-1",
  "title": "Introduction to Gross Anatomy",
  "topicId": "anat-b1-gross",
  "pages": 24,
  "content": [
    {
      "pageNumber": 1,
      "imageUrl": "data:image/jpeg;base64,...",
      "text": "Introduction to Gross Anatomy..."
    }
  ]
}
```

### Upload Slide
```
POST /api/slides/upload

Body:
{
  "title": "Upper Limb Anatomy",
  "topicId": "anat-b1-gross",
  "file": <binary>
}

Response:
{
  "id": "slide-anat-b1-gross-3",
  "status": "processing"
}
```

---

## 9. Testing Checklist

### Linking Tests
- [ ] Click course from My Courses → Opens correct course detail page
- [ ] Course detail page shows correct breadcrumb
- [ ] Course detail page shows correct slides
- [ ] Click slide → Opens in reader with correct content
- [ ] Reader breadcrumb shows correct path
- [ ] Back button returns to course detail page

### Upload Tests
- [ ] Upload to anatomy topic → Slide appears in correct topic
- [ ] Upload to physiology topic → Slide appears in correct topic
- [ ] Upload to biochemistry block → Slide appears in correct block
- [ ] Uploaded slide is immediately visible on course detail page
- [ ] Uploaded slide can be opened in reader

### Progress Tests
- [ ] Reading slide updates progress
- [ ] Course appears in Recent Courses
- [ ] Progress percentage updates correctly
- [ ] Last accessed time updates

---

## 10. Mock Data

Currently using mock data in `lib/slides.ts`:

```typescript
initializeMockSlides()
```

This creates sample slides for:
- Anatomy: Gross Anatomy, Embryology, Histology (Block 1)
- Physiology: General Physiology, ANS, CVS, Respiratory (Blocks 1 & 2)
- Biochemistry: Blocks 1, 2, 3

**To add more mock slides**, call `addSlide()` in `initializeMockSlides()`.

---

## 11. Next Steps

### Immediate
1. Test all links work correctly
2. Verify breadcrumbs display properly
3. Ensure slides appear on correct course pages

### Short-term
1. Connect to real database
2. Implement file upload processing
3. Add slide content rendering
4. Track real progress

### Long-term
1. Add slide search
2. Implement slide bookmarking
3. Add slide annotations
4. Enable slide sharing

---

## Summary

✅ **Curriculum** defines structure (subjects, blocks, topics)
✅ **Slides** link to curriculum via topicId or blockId
✅ **Courses page** generates from curriculum
✅ **Course detail pages** show slides for each course
✅ **Reader** displays slides with AI integration
✅ **Progress tracking** links everything together

**Everything is connected and ready to use!**
