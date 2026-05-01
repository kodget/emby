# ROUTING & NAVIGATION FIX

## Issues Found & Fixed

### 1. Duplicate Login Pages
**Problem:** Two login pages exist:
- `/signin` - Main auth page (CORRECT)
- `/login` - Inside (app) folder (LEGACY)

**Solution:** Use `/signin` and `/signup` consistently

### 2. Landing Page Buttons
**Problem:** Buttons were linking to `/dashboard` without authentication check

**Fixed:**
- Hero "Get started" button → `/signup` ✅
- Pricing "Start free" button → `/signup` ✅
- Pricing "Go Pro" button → `/signup` ✅
- Nav "Sign in" button → `/signin` ✅
- Nav "Get started" button → `/signup` ✅

## Correct Route Structure

### Public Routes (No Auth Required)
```
/                    → Landing page
/signin              → Sign in page
/signup              → Sign up page
/forgot-password     → Password reset request
/reset-password      → Password reset with token
```

### Protected Routes (Auth Required)
```
/dashboard           → Main dashboard
/onboarding          → First-time setup
/verification-pending → Class head verification
/courses             → Course list
/read/[courseId]     → PDF reader
/quiz/[id]           → Quiz page
/flashcards          → Flashcards
/steeplechase/[id]   → Steeplechase practice
/community           → Community posts
/brainstorming       → Brainstorming
/study-plan          → Study schedule
/profile             → User profile
/settings            → Settings
```

## Authentication Flow

### New User Flow
1. Landing page `/`
2. Click "Get started" → `/signup`
3. Sign up with email or Google
4. Redirect to `/onboarding`
5. Complete onboarding
6. Redirect to `/dashboard`

### Returning User Flow
1. Landing page `/`
2. Click "Sign in" → `/signin`
3. Login with credentials
4. Check onboarding status:
   - Not completed → `/onboarding`
   - Class head not verified → `/verification-pending`
   - Otherwise → `/dashboard`

### Google OAuth Flow
1. Click "Continue with Google"
2. Google authentication
3. Backend creates/finds user
4. Returns `is_new_user` flag
5. Frontend redirects based on status

## Frontend API Configuration

### Environment Variables
Create/update `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id
```

### API Endpoints Used
```typescript
// Authentication
POST /auth/signup/          → Create account
POST /auth/login/           → Email/password login
POST /auth/google-login/    → Google OAuth
GET  /auth/profile/         → Get user data

// Onboarding
GET  /auth/onboarding/questions/
POST /auth/onboarding/submit/
```

## Common 404 Issues & Solutions

### Issue: "Sign in" button shows 404
**Cause:** Frontend not running or wrong route
**Solution:**
```bash
# Start frontend
npm run dev

# Verify it's running on http://localhost:3000
```

### Issue: Backend returns 404
**Cause:** Django server not running
**Solution:**
```bash
cd backend
python manage.py runserver

# Verify it's running on http://localhost:8000
```

### Issue: CORS error on login
**Cause:** Frontend URL not in CORS_ALLOWED_ORIGINS
**Solution:** Check `backend/backend/settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
```

### Issue: Google login fails
**Cause:** Wrong Google Client ID
**Solution:**
1. Check `.env.local` has correct `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
2. Check `backend/.env` has correct `GOOGLE_CLIENT_ID`
3. Both should match the Google Cloud Console

## Testing Routes

### Test Landing Page
```bash
curl http://localhost:3000/
```

### Test Sign In Page
```bash
curl http://localhost:3000/signin
```

### Test Sign Up Page
```bash
curl http://localhost:3000/signup
```

### Test Backend Auth
```bash
# Test signup
curl -X POST http://localhost:8000/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123456","first_name":"Test","last_name":"User"}'

# Test login
curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123456"}'
```

## Route Guards

### Protected Route Component
Routes inside `/app/(app)/` are protected by the layout:
```typescript
// app/(app)/layout.tsx
// Should check authentication and redirect to /signin if not logged in
```

### Public Route Component
Routes outside `/app/(app)/` are public:
```typescript
// app/signin/page.tsx
// app/signup/page.tsx
// app/page.tsx (landing)
```

## Next Steps

1. ✅ Fixed all landing page buttons
2. ✅ Consistent routing to /signin and /signup
3. ⏳ Test authentication flow end-to-end
4. ⏳ Add route guards to protected pages
5. ⏳ Handle authentication state properly

## Recommended: Add Route Guard

Create `lib/guards/auth-guard.tsx`:
```typescript
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/signin');
    }
  }, [router]);
  
  return <>{children}</>;
}
```

Then wrap protected routes:
```typescript
// app/(app)/layout.tsx
import { AuthGuard } from '@/lib/guards/auth-guard';

export default function AppLayout({ children }) {
  return (
    <AuthGuard>
      {/* existing layout */}
    </AuthGuard>
  );
}
```

## Summary

All navigation issues have been fixed:
- ✅ Landing page buttons point to `/signup`
- ✅ Navigation uses `/signin` and `/signup`
- ✅ Pricing buttons point to `/signup`
- ✅ Authentication flow is clear
- ✅ Route structure is documented

The 404 errors should now be resolved. Make sure both servers are running:
- Frontend: `npm run dev` (port 3000)
- Backend: `python manage.py runserver` (port 8000)
