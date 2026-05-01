# Study Schedule System Documentation

## Overview
Complete study schedule and planning system that allows students to create, manage, and track their daily study activities.

---

## Features

### 1. ✅ Schedule Management
- **Add Activities**: Create new study activities with details
- **Edit Activities**: Modify existing schedule items
- **Delete Activities**: Remove activities from schedule
- **Mark Complete**: Check off completed activities
- **Track Progress**: See completion percentage and remaining time

### 2. ✅ Activity Types
- **Read Slides**: Schedule reading specific slides or courses
- **Take Quiz**: Plan quiz sessions for topics
- **Review Flashcards**: Schedule flashcard review sessions
- **Steeplechase Practice**: Plan spotter practice sessions

### 3. ✅ Scheduling Options
- **Date Selection**: Choose when to study
- **Time Selection**: Set specific time (optional)
- **Duration Estimate**: Set expected study time (5-120 minutes)
- **Course Selection**: Link to specific courses from curriculum
- **Slide Selection**: Choose specific slides (for reading)
- **Notes**: Add personal notes or reminders

---

## User Flow

### Creating a Schedule

1. **Open Schedule Modal**
   - Click the "+" button in Today's Plan section
   - Or click "Add your first activity" if no items exist

2. **Select Activity Type**
   - Choose from: Read Slides, Take Quiz, Review Flashcards, or Steeplechase

3. **Fill in Details**
   - **Title**: Descriptive name (e.g., "Read Axilla boundaries")
   - **Course**: Select from all available courses
   - **Slide** (if reading): Choose specific slide (optional)
   - **Date**: When to do this activity
   - **Time**: Specific time (optional)
   - **Duration**: Estimated minutes (slider: 5-120 min)
   - **Notes**: Any additional reminders (optional)

4. **Submit**
   - Click "Add to Schedule"
   - Activity appears in Today's Plan (if scheduled for today)

### Managing Schedule Items

**Mark as Complete:**
- Click the checkbox next to any item
- Item gets strikethrough and moves to completed state
- Progress bar updates automatically

**Edit Item:**
- Hover over item to reveal edit button
- Click pencil icon
- Modify any details
- Click "Update Schedule"

**Delete Item:**
- Hover over item to reveal delete button
- Click trash icon
- Confirm deletion
- Item removed from schedule

**Start Activity:**
- Click "Start" button on incomplete items
- Redirects to appropriate page:
  - Read → Opens slide in reader
  - Quiz → Opens quiz page
  - Flashcards → Opens flashcards
  - Steeplechase → Opens steeplechase

---

## Data Structure

### Schedule Item
```typescript
{
  id: string                    // Unique identifier
  type: "read" | "quiz" | "flashcards" | "steeplechase"
  title: string                 // Activity title
  courseId: string              // Links to curriculum
  courseName: string            // Display name
  slideId?: string              // For read type
  topicId?: string              // For quiz/flashcards/steeplechase
  estimatedMinutes: number      // Duration estimate
  scheduledDate: string         // ISO date (YYYY-MM-DD)
  scheduledTime?: string        // HH:MM format
  completed: boolean            // Completion status
  completedAt?: string          // ISO timestamp
  notes?: string                // Optional notes
}
```

---

## Redux State Management

### State Structure
```typescript
{
  items: ScheduleItem[]         // All schedule items
  goals: StudyGoal[]            // Study goals (future feature)
  isModalOpen: boolean          // Modal visibility
  editingItem: ScheduleItem | null  // Item being edited
}
```

### Actions
- `addScheduleItem(item)` - Add new schedule item
- `updateScheduleItem(item)` - Update existing item
- `deleteScheduleItem(id)` - Remove item
- `completeScheduleItem(id)` - Mark as complete
- `uncompleteScheduleItem(id)` - Mark as incomplete
- `openScheduleModal(item?)` - Open modal (with item to edit)
- `closeScheduleModal()` - Close modal
- `loadMockSchedule()` - Load sample data (development)

---

## Components

### 1. TodayPlan Component
**Location**: `components/dashboard/today-plan.tsx`

**Features:**
- Displays today's scheduled activities
- Shows progress bar and remaining time
- Allows marking items complete/incomplete
- Edit and delete buttons on hover
- "Start" button to begin activities
- Empty state with "Add first activity" button

**Props:** None (uses Redux)

### 2. ScheduleModal Component
**Location**: `components/dashboard/schedule-modal.tsx`

**Features:**
- Form for creating/editing schedule items
- Activity type selection with icons
- Course dropdown (from curriculum)
- Slide selection (for read type)
- Date and time pickers
- Duration slider (5-120 minutes)
- Notes textarea
- Validation and error handling

**Props:** None (uses Redux)

---

## Integration with Curriculum

The schedule system is fully integrated with the curriculum structure:

```typescript
// Courses are pulled from curriculum
const allCourses = curriculum.flatMap((subject) =>
  subject.blocks.flatMap((block) =>
    block.topics.length > 0
      ? block.topics.map((topic) => ({ id: topic.id, name: topic.title }))
      : [{ id: block.id, name: block.title }]
  )
)

// Slides are pulled from slides system
const availableSlides = getSlidesForCourse(courseId)
```

This ensures:
- All courses are available for scheduling
- Slides are linked correctly
- Navigation works seamlessly

---

## Future Enhancements

### Study Goals (Planned)
```typescript
type StudyGoal = {
  id: string
  title: string
  targetDate: string
  items: string[]  // Schedule item IDs
  progress: number // 0-100
}
```

**Features:**
- Create long-term study goals
- Link multiple schedule items to goals
- Track overall goal progress
- Deadline reminders

### Calendar View (Planned)
- Monthly calendar view
- Drag-and-drop rescheduling
- Week view with time blocks
- Color coding by activity type

### Recurring Schedules (Planned)
- Daily/weekly/monthly recurrence
- Custom recurrence patterns
- Bulk schedule creation

### Smart Scheduling (Planned)
- AI-suggested study times
- Optimal spacing based on forgetting curve
- Workload balancing
- Exam preparation plans

### Analytics (Planned)
- Study time tracking
- Completion rates
- Most productive times
- Subject distribution

---

## Database Schema (Future)

```sql
CREATE TABLE schedule_items (
  id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  type VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  course_id VARCHAR NOT NULL,
  course_name VARCHAR NOT NULL,
  slide_id VARCHAR,
  topic_id VARCHAR,
  estimated_minutes INT NOT NULL,
  scheduled_date DATE NOT NULL,
  scheduled_time TIME,
  completed BOOLEAN DEFAULT FALSE,
  completed_at TIMESTAMP,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_schedule_user_date ON schedule_items(user_id, scheduled_date);
CREATE INDEX idx_schedule_course ON schedule_items(course_id);
```

---

## API Endpoints (Future)

```typescript
// Get schedule items
GET /api/schedule?date=2024-01-15
GET /api/schedule?startDate=2024-01-15&endDate=2024-01-21

// Create schedule item
POST /api/schedule
Body: ScheduleItem

// Update schedule item
PUT /api/schedule/:id
Body: Partial<ScheduleItem>

// Delete schedule item
DELETE /api/schedule/:id

// Mark complete
POST /api/schedule/:id/complete

// Mark incomplete
POST /api/schedule/:id/uncomplete
```

---

## Testing Checklist

### Basic Functionality
- [ ] Click "+" button opens modal
- [ ] All activity types selectable
- [ ] Course dropdown shows all courses
- [ ] Slide dropdown shows slides for selected course
- [ ] Date picker works
- [ ] Time picker works
- [ ] Duration slider updates display
- [ ] Form validation works
- [ ] Submit creates new item
- [ ] Item appears in Today's Plan

### Item Management
- [ ] Checkbox marks item complete
- [ ] Checkbox unchecks item
- [ ] Progress bar updates correctly
- [ ] Remaining time calculates correctly
- [ ] Edit button opens modal with data
- [ ] Update saves changes
- [ ] Delete removes item
- [ ] Start button navigates correctly

### Edge Cases
- [ ] Empty state shows correctly
- [ ] No courses selected shows validation
- [ ] Past dates allowed
- [ ] Future dates allowed
- [ ] Multiple items same time allowed
- [ ] Long titles truncate properly
- [ ] Modal closes on backdrop click
- [ ] Modal closes on X button

---

## Usage Examples

### Example 1: Schedule Reading Session
```typescript
{
  type: "read",
  title: "Read Axilla boundaries & contents",
  courseId: "anat-b1-gross",
  courseName: "Gross Anatomy First Block",
  slideId: "slide-anat-b1-gross-1",
  scheduledDate: "2024-01-15",
  scheduledTime: "09:00",
  estimatedMinutes: 25,
  notes: "Focus on boundaries and clinical correlations"
}
```

### Example 2: Schedule Quiz
```typescript
{
  type: "quiz",
  title: "Cardiovascular System Quiz",
  courseId: "phys-b2-cvs",
  courseName: "Cardiovascular System",
  topicId: "phys-b2-cvs",
  scheduledDate: "2024-01-15",
  scheduledTime: "14:00",
  estimatedMinutes: 15,
  notes: "Review Wiggers diagram before quiz"
}
```

### Example 3: Schedule Steeplechase
```typescript
{
  type: "steeplechase",
  title: "Upper Limb Spotter Practice",
  courseId: "anat-b1-gross",
  courseName: "Gross Anatomy First Block",
  topicId: "anat-b1-gross",
  scheduledDate: "2024-01-15",
  scheduledTime: "16:00",
  estimatedMinutes: 20,
  notes: "Focus on brachial plexus structures"
}
```

---

## Summary

✅ **Complete schedule management system**
✅ **Integrated with curriculum and slides**
✅ **Full CRUD operations**
✅ **Progress tracking**
✅ **Smart navigation**
✅ **Redux state management**
✅ **Responsive design**
✅ **Ready for database integration**

**The schedule system is fully functional and ready to use!** 🎉
