# Complete Analysis: Slide Upload & Display Flow

## Current State
- **Database**: Has 3 subjects, 16 blocks, 0 topics
- **Frontend**: Uses hardcoded curriculum with different IDs
- **Backend**: Not running
- **Frontend**: Not running

---

## THE COMPLETE FLOW (What Should Happen)

### 1. USER CLICKS "Upload Slides" Button
**Location**: Top navigation bar (`components/app/app-topbar.tsx`)

**Current Problem**: 
```javascript
onClick={() => dispatch(openUploadModal({
  courseId: "anat-101",  // ❌ HARDCODED - doesn't exist in DB
  moduleId: "anat-101-m1", // ❌ HARDCODED - doesn't exist in DB
}))}
```

**Solution**: Remove hardcoded IDs, let modal handle selection

---

### 2. MODAL OPENS - User Selects Course/Block/Topic
**Location**: `components/app/slide-upload-modal.tsx`

**Current Problem**:
- Uses hardcoded `curriculum` from `lib/curriculum.ts`
- Frontend IDs: `anat-b1`, `phys-b1`, `bioc-b1`
- Database IDs: `anatomy-block-1`, `physiology-block-1`, `biochemistry-block-1`
- **MISMATCH** = slides can't be saved to correct blocks

**Solution**: Fetch curriculum from API instead of hardcoded data

---

### 3. USER UPLOADS FILE
**What Should Happen**:
1. File selected (PDF/PPT)
2. User enters title
3. Clicks "Upload & process slides"

**Current Flow**:
```javascript
// Step 1: Upload to Cloudinary
POST http://localhost:8000/api/upload/
Body: FormData with file
Response: { url: "cloudinary_url" }

// Step 2: Create Slide record
POST http://localhost:8000/api/slides/
Body: {
  title: "...",
  subject: "anatomy",  // ❌ WRONG - should be subject ID
  block: "anat-b1",    // ❌ WRONG - should be "anatomy-block-1"
  topic: "anat-b1-gross", // ❌ WRONG - should match DB topic ID
  file_url: "cloudinary_url",
  file_type: "pdf",
  page_count: 0
}
```

**Problems**:
- Backend expects: `subject`, `block`, `topic` as ForeignKey IDs
- Frontend sends: mismatched IDs from hardcoded curriculum
- Result: **Slide creation fails** or creates orphaned slides

---

### 4. BACKEND PROCESSES SLIDE
**Location**: `backend/curriculum/views.py` - `SlideViewSet.perform_create()`

**What Should Happen**:
1. Validate user has upload permission (class_head or material_uploader)
2. Create Slide record with:
   - `id`: auto-generated UUID
   - `title`: from request
   - `subject`: ForeignKey to Subject
   - `block`: ForeignKey to Block  
   - `topic`: ForeignKey to Topic (optional)
   - `file_url`: Cloudinary URL
   - `uploaded_by`: current user
3. Return slide data with ID

**Current Problem**:
- Slide model requires valid ForeignKey IDs
- Frontend sends IDs that don't exist in DB
- **Slide creation fails silently**

---

### 5. CONTENT EXTRACTION (Missing!)
**What Should Happen**:
1. After slide created, extract content from PDF/PPT
2. Parse text and images from each page
3. Store extracted content for reader

**Current State**: 
- ❌ **NOT IMPLEMENTED**
- No content extraction happening
- Reader has no content to display

**Location to implement**: 
- `backend/curriculum/views.py` - add content extraction after slide creation
- Use `backend/curriculum/content_extractor.py` (if exists) or create it

---

### 6. SLIDES APPEAR IN "MY COURSES"
**Location**: `app/(app)/courses/page.tsx`

**What Should Happen**:
1. Fetch subjects from `/api/subjects/`
2. Fetch blocks from `/api/blocks/`
3. For each block, fetch slides from `/api/slides/?block={block_id}`
4. Display blocks as course cards
5. Show slide count per block

**Current Problem**:
- Frontend fetches from API ✅
- But uses hardcoded curriculum for display logic
- Mismatch between API data and display logic

---

### 7. USER CLICKS COURSE TO READ
**Location**: `app/(app)/courses/[id]/page.tsx`

**What Should Happen**:
1. Fetch course details (block or topic)
2. Fetch slides for that course: `/api/slides/?block={id}` or `/api/slides/?topic={id}`
3. Display list of slides
4. User clicks slide → goes to reader

**Current State**: ✅ Mostly working, but no slides to display

---

### 8. READER DISPLAYS SLIDE CONTENT
**Location**: `app/(app)/read/[courseId]/[materialId]/page.tsx`

**What Should Happen**:
1. Fetch slide: `/api/slides/{materialId}/`
2. Fetch slide content: `/api/slides/{materialId}/content/`
3. Display extracted text and images page by page
4. Track progress

**Current Problem**:
- ❌ No content extraction = no content to display
- Reader shows empty or just PDF embed

---

## ROOT CAUSES SUMMARY

### 🔴 CRITICAL ISSUES

1. **ID Mismatch**
   - Frontend: `anat-b1`, `phys-b1`, `bioc-b1`
   - Database: `anatomy-block-1`, `physiology-block-1`, `biochemistry-block-1`
   - **Impact**: Slides can't be created or linked correctly

2. **Hardcoded Curriculum**
   - `lib/curriculum.ts` has static data
   - Should fetch from API dynamically
   - **Impact**: Can't adapt to database changes

3. **Missing Content Extraction**
   - No PDF/PPT parsing after upload
   - No text/image extraction
   - **Impact**: Reader has nothing to display

4. **Backend Not Running**
   - API endpoints not accessible
   - **Impact**: Nothing works

### 🟡 MEDIUM ISSUES

5. **No Topics in Database**
   - Database has 0 topics
   - Frontend expects topics for anatomy/physiology
   - **Impact**: Can't upload slides to specific topics

6. **Slide Model Confusion**
   - Model has `subject`, `block`, `topic`, `section` (all optional)
   - Frontend only sends `subject`, `block`, `topic`
   - Unclear which fields are required

---

## SOLUTIONS IN ORDER

### Phase 1: Fix Database & IDs (CRITICAL)
1. ✅ Create proper curriculum in database (DONE - but needs topics)
2. Update `lib/curriculum.ts` to fetch from API
3. OR: Update database IDs to match frontend
4. OR: Create ID mapping layer

### Phase 2: Fix Upload Flow
1. Remove hardcoded IDs from topbar button
2. Update SlideUploadModal to use API data
3. Fix ID mapping when creating slides
4. Test slide creation end-to-end

### Phase 3: Implement Content Extraction
1. Create content extraction service
2. Extract text/images from PDF/PPT after upload
3. Store extracted content in database
4. Create API endpoint to serve content

### Phase 4: Fix Reader
1. Fetch extracted content from API
2. Display content page by page
3. Add navigation controls
4. Track reading progress

---

## IMMEDIATE NEXT STEPS

1. **Start Backend**: `cd backend && python manage.py runserver`
2. **Start Frontend**: `npm run dev`
3. **Choose ID Strategy**:
   - Option A: Update database to use frontend IDs
   - Option B: Update frontend to use database IDs
   - Option C: Create mapping layer
4. **Add Topics to Database** (anatomy/physiology need them)
5. **Test Upload Flow** with correct IDs
6. **Implement Content Extraction**

---

## FILES THAT NEED CHANGES

### Frontend
- `lib/curriculum.ts` - Replace hardcoded data with API calls
- `components/app/app-topbar.tsx` - Remove hardcoded IDs
- `components/app/slide-upload-modal.tsx` - Use API data
- `app/(app)/courses/page.tsx` - Ensure using API data
- `app/(app)/read/[courseId]/[materialId]/page.tsx` - Add content display

### Backend
- `curriculum/models.py` - Clarify Slide model requirements
- `curriculum/views.py` - Add content extraction after slide creation
- `curriculum/content_extractor.py` - Create if doesn't exist
- `curriculum/serializers.py` - Add content serializer
- `curriculum/urls.py` - Add content endpoint

---

## TESTING CHECKLIST

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Can fetch subjects from API
- [ ] Can fetch blocks from API
- [ ] Can fetch topics from API (if any)
- [ ] Upload button appears for class heads
- [ ] Modal shows correct subjects/blocks/topics
- [ ] Can select course hierarchy
- [ ] Can upload PDF file
- [ ] File uploads to Cloudinary
- [ ] Slide record created in database
- [ ] Slide appears in "My Courses"
- [ ] Can click slide to open reader
- [ ] Reader displays slide content
- [ ] Content is readable and formatted
