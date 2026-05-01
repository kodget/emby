# FIX FOR 404 ON /signup AND /signin

## Problem
Next.js dev server is serving cached 404 pages for /signup and /signin routes even though the files exist.

## Solution

### Option 1: Restart Dev Server (Quick)
1. Stop the current dev server (Ctrl+C in terminal)
2. Delete .next folder:
   ```bash
   rmdir /s /q .next
   ```
3. Start dev server again:
   ```bash
   npm run dev
   ```

### Option 2: Use Restart Script (Easiest)
Run the provided script:
```bash
restart-dev.bat
```

### Option 3: Manual Process
1. Open Task Manager
2. End all "Node.js" processes
3. Delete the `.next` folder in your project root
4. Run `npm run dev`

## Why This Happens
Next.js caches routes during development. When files are added/moved, the cache can become stale and serve 404s for valid routes.

## Verify Fix
After restarting:
1. Go to http://localhost:3000
2. Click "Get started" → Should load signup page
3. Click "Sign in" → Should load signin page

## If Still Not Working

### Check 1: Verify Files Exist
```bash
dir app\signup\page.tsx
dir app\signin\page.tsx
```
Both should show the files exist.

### Check 2: Check for Syntax Errors
Open the files and look for any red underlines or errors.

### Check 3: Check Terminal Output
Look for any error messages when the dev server starts.

### Check 4: Try Different Port
```bash
npm run dev -- -p 3001
```
Then visit http://localhost:3001

## Files Confirmed Present
✅ app/signup/page.tsx - EXISTS
✅ app/signin/page.tsx - EXISTS
✅ app/page.tsx - EXISTS (landing page)

## Next.js Route Structure
```
app/
├── page.tsx              → / (landing)
├── signin/
│   └── page.tsx          → /signin
├── signup/
│   └── page.tsx          → /signup
├── onboarding/
│   └── page.tsx          → /onboarding
└── (app)/
    └── dashboard/
        └── page.tsx      → /dashboard
```

All routes are correctly structured. The issue is purely a caching problem.
