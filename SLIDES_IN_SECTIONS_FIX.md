# Fix: Slides Not Showing in Subsections (Sections)

## Problem

Slides uploaded to subsections (sections) were not appearing when navigating to those sections. This affected both:

1. Sections that belong directly to blocks (e.g., Physiology → Block 1 → Section)
2. Sections that belong to topics (e.g., Anatomy → Block 1 → Topic → Section)

## Root Causes

### Issue 1: Frontend Path Handling (FIXED EARLIER)

The frontend was incorrectly interpreting URL segments for 3-segment paths.

- **Fixed in**: `app/(app)/courses/[...slug]/page.tsx`
- **Solution**: Correctly identifies section from path segments

### Issue 2: Upload Modal Missing Section Field (MAIN ISSUE)

The upload modal was NOT setting the `section` field when creating slides.

- **Problem**: Only `subject`, `block`, and `topic` were being set
- **Result**: Slides were not associated with any section
- **Impact**: Backend filtering by section returned no results

### Issue 3: Curriculum Loader Not Loading Sections

The `loadCurriculum()` function only loaded subjects → blocks → topics, but NOT sections.

- **Problem**: Upload modal had no section data to display
- **Result**: Users couldn't select sections when uploading

## Solutions Implemented

### 1. Updated Curriculum Type Definitions (`lib/curriculum.ts`)

Added section support to the type system:

```typescript
export type SectionId = string;

export type Section = {
  id: SectionId;
  title: string;
};

export type Topic = {
  id: TopicId;
  title: string;
  shortTitle: string;
  sections: Section[]; // NEW
};

export type Block = {
  id: BlockId;
  title: string;
  subjectId: SubjectId;
  topics: Topic[];
  sections: Section[]; // NEW - for sections directly under block
};
```

### 2. Updated Curriculum Loader (`lib/curriculum.ts`)

Modified `loadCurriculum()` to fetch sections:

- Fetches sections for each topic
- Fetches sections that belong directly to blocks
- Properly structures the hierarchy

### 3. Updated Upload Modal (`components/app/slide-upload-modal.tsx`)

Added section selection UI and logic:

- Added `selectedSection` state
- Added section selector UI (appears after block/topic selection)
- Sections shown are either from selected topic OR directly from block
- Section ID is now sent to the API when creating slides
- Breadcrumb shows full path including section

## Files Modified

1. **lib/curriculum.ts**
   - Added `Section` and `SectionId` types
   - Updated `Topic` and `Block` types to include sections
   - Modified `loadCurriculum()` to fetch sections from API

2. **components/app/slide-upload-modal.tsx**
   - Added `selectedSection` state
   - Added section selector UI
   - Updated API call to include `section` field
   - Updated breadcrumb to show section
   - Updated reset function to clear section

3. **app/(app)/courses/[...slug]/page.tsx** (Already fixed earlier)
   - Correctly handles 3-segment and 4-segment paths
   - Properly filters slides by section

## Testing Steps

### 1. Test Upload to Section

1. Open upload modal
2. Select Subject (e.g., Physiology)
3. Select Block (e.g., Block 1)
4. **NEW**: Select Section (e.g., Cardiovascular System)
5. Upload a slide
6. Verify section appears in breadcrumb

### 2. Test Viewing Slides in Section

1. Navigate to Courses page
2. Click on a section (e.g., Physiology → Block 1 → Cardiovascular System)
3. Verify uploaded slides appear
4. Check browser console for correct filters being sent

### 3. Test Both Section Types

**Type A: Block → Section (3-segment path)**

- URL: `/courses/physiology/physiology-block-1/cardiovascular-system`
- Should show slides uploaded to that section

**Type B: Block → Topic → Section (4-segment path)**

- URL: `/courses/anatomy/anatomy-block-1/gross-anatomy/upper-limb`
- Should show slides uploaded to that section

## Database Verification

To check if slides are properly associated with sections:

```sql
-- Check slides with section associations
SELECT id, title, subject, block, topic, section
FROM curriculum_slide
WHERE section IS NOT NULL;

-- Check specific section
SELECT id, title, section
FROM curriculum_slide
WHERE section = 'cardiovascular-system';
```

## API Verification

Check the API responses:

```bash
# Get slides for a specific section
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/slides/?section=cardiovascular-system"

# Get sections for a block
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/sections/?block=physiology-block-1"
```

## Backward Compatibility

✅ Existing slides without sections will continue to work
✅ Blocks without sections will work as before
✅ Topics without sections will work as before
✅ Section field is optional in the upload modal

## Next Steps

1. **Clear browser cache** to ensure new curriculum structure loads
2. **Test uploading** a new slide to a section
3. **Verify** the slide appears when navigating to that section
4. **Check** that existing slides (without sections) still work

## Related Issues

This fix also addresses:

- Slides not appearing in Physiology subblocks
- Upload modal not showing all hierarchy levels
- Curriculum structure not matching database schema

## Date

2026-05-27
