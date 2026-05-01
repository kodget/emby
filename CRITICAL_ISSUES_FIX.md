# CRITICAL ISSUES - MUST FIX IMMEDIATELY

## Issue 1: DUPLICATE ROUTES (CRITICAL - BREAKS ROUTING)

### Problem
Created new routes outside `(app)` folder that duplicate existing routes:

**Duplicates:**
- `app/(app)/community/` AND `app/community/` ❌
- `app/(app)/profile/` AND `app/profile/` ❌
- `app/(app)/steeplechase/` AND `app/steeplechase/` ❌

### Solution
**DELETE** the following directories (keep only the ones in `(app)` folder):
- `app/community/` (delete - use `app/(app)/community/` instead)
- `app/profile/` (delete - use `app/(app)/profile/` instead)  
- `app/steeplechase/` (delete - use `app/(app)/steeplechase/` instead)

**KEEP** these new routes (they don't have duplicates):
- `app/signin/`
- `app/signup/`
- `app/onboarding/`
- `app/payment/`
- `app/upgrade-success/`
- `app/verification-pending/`
- `app/class/`
- `app/materials/`
- `app/settings/`

---

## Issue 2: BACKEND API MISMATCH (CRITICAL - BREAKS DATA FLOW)

### Problem
Frontend TypeScript types don't match backend serializer response.

### Backend Profile Serializer Returns:
```python
{
    'id': int,
    'username': str,  # from user.username
    'email': str,  # from user.email
    'full_name': str,  # from user.get_full_name()
    'photo_url': str | null,  # NOT profile_image
    'role': str,
    'school': int | null,
    'school_name': str,
    'set_name': str,
    'class_group': int | null,
    'class_code': str | null,  # from class_group.code
    'subscription_tier': str,
    'subscription_expires_at': datetime | null,  # NOT subscription_end_date
    'is_premium': bool,
    'onboarding_completed': bool,
    'email_verified': bool,
    'class_head_verified': bool,
    'class_head_verification_requested': bool,
    'class_head_rejection_reason': str,
    'can_access_app': bool,
    'streak': int,  # NOT streak_days
    'created_at': datetime
}
```

### Frontend Type (WRONG):
```typescript
export type UserProfile = {
  id: number;
  user: {  // ❌ WRONG - backend returns flat structure
    id: number;
    email: string;
    first_name: string;
    last_name: string;
  };
  role: string;
  school: {  // ❌ WRONG - backend returns just ID
    id: number;
    name: string;
  } | null;
  class_group: {  // ❌ WRONG - backend returns just ID
    id: number;
    name: string;
    class_code: string;
    school: {...};
  } | null;
  subscription_tier: string;
  subscription_end_date: string | null;  // ❌ WRONG - should be subscription_expires_at
  profile_image: string | null;  // ❌ WRONG - should be photo_url
  bio: string | null;  // ❌ WRONG - doesn't exist in backend
  streak_days: number;  // ❌ WRONG - should be streak
  total_points: number;  // ❌ WRONG - doesn't exist in Profile model
  rank: number | null;  // ❌ WRONG - doesn't exist in Profile model
  // ... other fields
};
```

### Correct Frontend Type:
```typescript
export type UserProfile = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  photo_url: string | null;
  role: 'student' | 'brainstormer' | 'class_head' | 'material_uploader';
  school: number | null;
  school_name: string;
  set_name: string;
  class_group: number | null;
  class_code: string | null;
  subscription_tier: 'free' | 'premium' | 'class_head';
  subscription_expires_at: string | null;
  is_premium: boolean;
  onboarding_completed: boolean;
  email_verified: boolean;
  class_head_verified: boolean;
  class_head_verification_requested: boolean;
  class_head_rejection_reason: string;
  can_access_app: boolean;
  streak: number;
  created_at: string;
};
```

### ClassGroup Type (WRONG):
```typescript
export type ClassGroup = {
  id: number;
  code: string;  // ✅ CORRECT
  school: number;
  school_name: string;
  set_name: string;
  class_heads: Array<{...}>;
  member_count: number;
  created_at: string;
};
```
This one is actually CORRECT!

---

## Issue 3: COMPONENT USAGE OF WRONG FIELDS

### Files Using Wrong Fields:
1. **Profile Page** (`app/profile/page.tsx` - DELETE THIS FILE)
   - Uses `profile.user.first_name` ❌ should be `profile.full_name`
   - Uses `profile.user.last_name` ❌ should be `profile.full_name`
   - Uses `profile.user.email` ❌ should be `profile.email`
   - Uses `profile.profile_image` ❌ should be `profile.photo_url`
   - Uses `profile.bio` ❌ doesn't exist in backend
   - Uses `profile.streak_days` ❌ should be `profile.streak`
   - Uses `profile.total_points` ❌ doesn't exist (need UserStats API)
   - Uses `profile.rank` ❌ doesn't exist (need UserStats API)
   - Uses `profile.subscription_end_date` ❌ should be `profile.subscription_expires_at`
   - Uses `profile.class_group.name` ❌ should fetch ClassGroup separately
   - Uses `profile.class_group.school.name` ❌ should use `profile.school_name`
   - Uses `profile.class_group.class_code` ❌ should use `profile.class_code`

2. **Settings Page** (`app/settings/page.tsx` - DELETE THIS FILE)
   - Same issues as profile page

3. **Class Pages** (`app/class/*` - KEEP THESE)
   - Uses `profile.class_group.name` ❌
   - Uses `profile.class_group.school.name` ❌
   - Uses `profile.class_group.class_code` ❌

4. **Community Page** (`app/community/page.tsx` - DELETE THIS FILE)
   - Uses `profile.role` ✅ CORRECT

5. **Materials Upload** (`app/materials/upload/page.tsx` - KEEP THIS)
   - Uses `profile.role` ✅ CORRECT
   - Uses `profile.user.id` ❌ should be `profile.id`

6. **Personalized Greeting** (`components/dashboard/personalized-greeting.tsx`)
   - Uses `profile.user.first_name` ❌ should parse `profile.full_name`
   - Uses `profile.streak_days` ❌ should be `profile.streak`

7. **Class Info Widget** (`components/dashboard/class-info-widget.tsx`)
   - Uses `profile.class_group.name` ❌
   - Uses `profile.class_group.school.name` ❌
   - Uses `profile.class_group.class_code` ❌

---

## Issue 4: MISSING BACKEND ENDPOINTS

### Endpoints That Don't Exist Yet:
1. **Exam Countdowns** (all mock data)
   - `GET /api/accounts/class/exam-countdowns/`
   - `POST /api/accounts/class/exam-countdowns/`
   - `PUT /api/accounts/class/exam-countdowns/:id/`
   - `DELETE /api/accounts/class/exam-countdowns/:id/`

2. **Class Members** (mock data)
   - `GET /api/accounts/class/members/`

3. **Class Analytics** (mock data)
   - `GET /api/accounts/class/analytics/`

4. **Profile Update** (might not exist)
   - `PATCH /api/accounts/profile/` - Need to verify

5. **Change Password** (might not exist)
   - `POST /api/accounts/change-password/` - Need to verify

6. **Delete Account** (might not exist)
   - `DELETE /api/accounts/profile/` - Need to verify

---

## IMMEDIATE ACTION PLAN

### Step 1: Delete Duplicate Routes
```bash
rm -rf app/community
rm -rf app/profile
rm -rf app/steeplechase
```

### Step 2: Fix TypeScript Types in `lib/api.ts`
- Update `UserProfile` type to match backend
- Remove nested `user`, `school`, `class_group` objects
- Change field names to match backend

### Step 3: Update All Components
- Replace `profile.user.first_name` with parsed `profile.full_name`
- Replace `profile.user.email` with `profile.email`
- Replace `profile.profile_image` with `profile.photo_url`
- Replace `profile.streak_days` with `profile.streak`
- Replace `profile.subscription_end_date` with `profile.subscription_expires_at`
- Replace `profile.class_group.name` with separate API call or use `profile.set_name`
- Replace `profile.class_group.class_code` with `profile.class_code`
- Replace `profile.class_group.school.name` with `profile.school_name`

### Step 4: Move Correct Pages to `(app)` Folder
- Move `app/settings/page.tsx` to `app/(app)/settings/page.tsx`
- Update `app/(app)/profile/page.tsx` with correct fields
- Update `app/(app)/community/page.tsx` with correct fields
- Update `app/(app)/steeplechase/page.tsx` with correct fields

### Step 5: Fix All Widget Components
- Update `PersonalizedGreeting` component
- Update `ClassInfoWidget` component
- Update all class management pages

### Step 6: Test Everything
- Test profile page loads
- Test settings page works
- Test community page works
- Test class pages work
- Test materials upload works

---

## FILES TO DELETE
1. `app/community/page.tsx`
2. `app/profile/page.tsx`
3. `app/steeplechase/page.tsx`
4. `app/settings/page.tsx`

## FILES TO UPDATE
1. `lib/api.ts` - Fix UserProfile type
2. `app/(app)/profile/page.tsx` - Update to use correct fields
3. `app/(app)/settings/page.tsx` - Create new with correct fields
4. `app/(app)/community/page.tsx` - Update to use correct fields
5. `app/(app)/steeplechase/page.tsx` - Update to use correct fields
6. `components/dashboard/personalized-greeting.tsx` - Fix field names
7. `components/dashboard/class-info-widget.tsx` - Fix field names
8. `app/class/page.tsx` - Fix field names
9. `app/class/announcements/page.tsx` - Fix field names
10. `app/class/roster/page.tsx` - Fix field names
11. `app/class/analytics/page.tsx` - Fix field names
12. `app/class/exams/page.tsx` - Fix field names
13. `app/materials/upload/page.tsx` - Fix field names
14. `app/materials/page.tsx` - Fix field names

---

## PRIORITY ORDER
1. **CRITICAL**: Delete duplicate routes (breaks routing)
2. **CRITICAL**: Fix UserProfile type in lib/api.ts (breaks all API calls)
3. **HIGH**: Update all components to use correct fields
4. **MEDIUM**: Move/create correct pages in (app) folder
5. **LOW**: Add missing backend endpoints

---

## NOTES
- Backend uses flat structure, not nested objects
- Backend doesn't have `bio`, `total_points`, `rank` in Profile model
- Need to call separate UserStats API for points and rank
- ClassGroup details need separate API call if needed
- All new auth pages (signin, signup, onboarding, etc.) are in correct location
