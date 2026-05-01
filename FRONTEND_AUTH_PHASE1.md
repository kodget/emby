# Frontend Authentication Implementation - Phase 1

## ✅ Completed

### 1. API Integration (lib/api.ts)
Added complete authentication API functions:
- `authApi.signup()` - Email/password signup
- `authApi.login()` - Email/password login
- `authApi.googleLogin()` - Google OAuth
- `authApi.verifyEmail()` - Email verification
- `authApi.resendVerification()` - Resend verification
- `authApi.getProfile()` - Get user profile
- `authApi.updateProfile()` - Update profile

Added onboarding API:
- `onboardingApi.getQuestions()` - Get questions
- `onboardingApi.submitOnboarding()` - Submit onboarding
- `onboardingApi.updateResponses()` - Update responses

Added class API:
- `classApi.joinClass()` - Join with code
- `classApi.getMyClass()` - Get class info
- `classApi.getAnnouncements()` - Get announcements
- `classApi.createAnnouncement()` - Create (class head only)

Added payment API:
- `paymentApi.initiatePayment()` - Start payment
- `paymentApi.verifyPayment()` - Verify payment

### 2. Sign In Page (/signin)
- Email/password form
- Google OAuth button
- Error handling with backend messages
- Redirects based on onboarding status
- Redirects to verification-pending for unverified class heads
- Links to signup page

### 3. Sign Up Page (/signup)
- Email/password form with first/last name
- Google OAuth button
- Password validation (min 8 chars)
- Error handling
- Redirects to onboarding after signup
- Links to signin page

### 4. Google Login Button Component
- Uses Google Identity Services
- Handles OAuth flow
- Calls backend API with token
- Returns user, tokens, and isNewUser flag
- Loading states

### 5. Verification Pending Page (/verification-pending)
- For class heads awaiting approval
- Shows verification status
- Polls every 30 seconds for updates
- Shows rejection reason if rejected
- Auto-redirects when verified
- Sign out option

### 6. Landing Page Updates
- Updated nav buttons to point to /signin and /signup
- "Sign in" and "Get started" buttons

### 7. Root Layout
- Added Google Identity Services script
- Loads asynchronously

## 📋 Next Steps (Phase 2)

### 1. Onboarding Flow (4 Steps)
Need to rebuild `/onboarding` page with:
- **Step 1**: Role selection (4 roles with descriptions)
- **Step 2**: School & class info
  - School name input
  - Set name input
  - Class code input (if not class head)
- **Step 3**: Onboarding questions
  - Fetch from API
  - Dynamic form based on question types
- **Step 4**: Subscription tier
  - Free vs Premium comparison
  - Skip for class heads (auto premium)
  - Redirect to payment if premium selected

### 2. Payment Flow
Create `/payment` page:
- Show subscription options (1, 3, 6, 12 months)
- Initiate Paystack payment
- Redirect to Paystack
- Handle callback from `/payment-success`
- Verify payment
- Update user profile
- Redirect to dashboard

### 3. Email Verification UI
Create banner/alert in app:
- Show if `email_verified === false`
- "Resend verification" button
- Dismissible

### 4. Profile Page
Create `/profile` page:
- View profile info
- Edit onboarding responses
- Show class code (if class head)
- Copy class code button
- Subscription status
- Upgrade button (if free)

### 5. Auth Guards
Update app layout to check:
- `can_access_app` - Block class heads if not verified
- `onboarding_completed` - Redirect to onboarding
- Token expiry - Refresh or logout

### 6. Update useAuth Hook
Integrate with new API:
- Use `authApi.getProfile()` instead of old endpoint
- Handle new user structure
- Update Redux state

## File Structure

```
app/
├── signin/
│   └── page.tsx ✅
├── signup/
│   └── page.tsx ✅
├── verification-pending/
│   └── page.tsx ✅
├── onboarding/
│   └── page.tsx ⚠️ (needs rebuild)
├── payment/
│   └── page.tsx ❌ (needs creation)
├── profile/
│   └── page.tsx ❌ (needs creation)
└── page.tsx ✅ (landing)

components/
└── auth/
    └── google-login-button.tsx ✅

lib/
└── api.ts ✅ (all auth APIs added)
```

## Testing Checklist

### Sign Up Flow
- [ ] Email/password signup works
- [ ] Google OAuth signup works
- [ ] Redirects to onboarding
- [ ] Tokens stored in localStorage
- [ ] Error messages display correctly

### Sign In Flow
- [ ] Email/password login works
- [ ] Google OAuth login works
- [ ] Redirects based on onboarding status
- [ ] Class heads redirect to verification-pending if not verified
- [ ] Error messages for invalid credentials
- [ ] Suggestion to create account if not found

### Verification Pending
- [ ] Shows pending status
- [ ] Polls for updates
- [ ] Shows rejection reason if rejected
- [ ] Auto-redirects when verified
- [ ] Sign out works

## Environment Variables Needed

Add to `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here
```

## Backend Requirements

Ensure backend is running:
```bash
cd backend
python manage.py runserver
```

Migrations must be applied:
```bash
python manage.py makemigrations accounts
python manage.py migrate
python manage.py shell -c "exec(open('seed_onboarding.py').read())"
```

## Progress

**Phase 1 (Auth Pages)**: 100% ✅
**Phase 2 (Onboarding)**: 0% ⏳
**Phase 3 (Payment)**: 0% ⏳
**Phase 4 (Profile)**: 0% ⏳
**Phase 5 (Guards)**: 0% ⏳

**Overall Frontend Auth**: ~20% complete
