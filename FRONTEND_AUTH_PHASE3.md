# Frontend Authentication - Phase 3: Profile, Settings & Auth Guards

## Completion Date
[Current Date]

## Overview
Phase 3 implements user profile management, settings page, authentication guards, email verification banner, and premium feature locks. This phase completes the core authentication infrastructure for the frontend.

## Files Created

### 1. Profile Page (`app/profile/page.tsx`)
**Purpose**: Display and edit user profile information

**Features**:
- Profile image upload with Cloudinary integration
- Edit profile (first name, last name, bio)
- Display user stats (streak, points, rank)
- Show class information (class name, school, class code)
- Display subscription status with upgrade button for free users
- Email verification status indicator
- Role badge display

**Key Components**:
- Profile image with upload button
- Editable form fields (first/last name, bio)
- Stats grid (3 cards: streak, points, rank)
- Class info card (conditional on class_group)
- Subscription info card with upgrade CTA

### 2. Settings Page (`app/settings/page.tsx`)
**Purpose**: Manage account settings and preferences

**Features**:
- **Account Tab**: Edit profile link, logout, delete account
- **Password Tab**: Change password form with validation
- **Notifications Tab**: Toggle notification preferences (email updates, community activity, study reminders, weekly report)

**Key Components**:
- Tabbed interface (Account, Password, Notifications)
- Password change form with current/new/confirm fields
- Notification toggles with descriptions
- Danger zone for account deletion

### 3. Auth Guards (`lib/guards.ts`)
**Purpose**: Utility functions for authentication checks and route protection

**Functions**:
- `isAuthenticated()`: Check if user has access token
- `getStoredProfile()`: Get user profile from localStorage
- `hasCompletedOnboarding()`: Check onboarding status
- `isEmailVerified()`: Check email verification status
- `isClassHeadVerified()`: Check class head verification (auto-true for non-class heads)
- `canAccessApp()`: Combined check for full app access
- `isPremium()`: Check if user has premium/class_head subscription
- `isClassHead()`: Check if user is verified class head
- `getRedirectPath()`: Get appropriate redirect path based on user state
- `checkFeatureAccess()`: Check access to specific features

### 4. Auth Guard Component (`components/auth/auth-guard.tsx`)
**Purpose**: Reusable component to protect routes

**Features**:
- Wraps protected pages
- Checks authentication, onboarding, verification status
- Redirects to appropriate page if checks fail
- Shows loading state during checks
- Configurable requirements (requireAuth, requireOnboarding, requireVerification)

**Usage**:
```tsx
<AuthGuard>
  <ProtectedContent />
</AuthGuard>
```

### 5. Email Verification Banner (`components/auth/email-verification-banner.tsx`)
**Purpose**: Show banner for unverified email addresses

**Features**:
- Yellow banner at top of page
- Resend verification email button
- Dismissible with X button
- Success message after resending
- Loading state during resend

### 6. Premium Lock Components (`components/auth/premium-lock.tsx`)
**Purpose**: Lock premium features for free users

**Components**:
- `PremiumLock`: Wraps content with blur overlay and upgrade prompt
- `PremiumBadge`: Small badge showing "Premium" with crown icon
- `PremiumButton`: Button that shows lock icon for free users

**Usage**:
```tsx
<PremiumLock feature="Advanced Analytics">
  <AdvancedAnalyticsContent />
</PremiumLock>
```

### 7. API Updates (`lib/api.ts`)
**Updates**:
- Fixed `UserProfile` type to match backend structure (nested user, school, class_group objects)
- Added `updateProfile()` method with proper fields
- Added `changePassword()` method
- Added `deleteAccount()` method

## Integration Points

### Dashboard Integration
- Added `AuthGuard` wrapper to dashboard page
- Added `EmailVerificationBanner` for unverified users
- Banner shows at top of dashboard, dismissible

### Profile/Settings Access
- Profile page accessible via `/profile`
- Settings page accessible via `/settings`
- Both pages protected with auth checks
- Profile has "Edit Profile" button in settings

## User Flows

### Profile Management Flow
1. User clicks profile icon/link → `/profile`
2. View profile info, stats, class, subscription
3. Click "Edit Profile" → Enable edit mode
4. Update fields → Click "Save" → API call → Reload profile
5. Upload image → Select file → Upload to Cloudinary → Update profile

### Settings Flow
1. User navigates to `/settings`
2. **Account Tab**: View account actions, logout, delete
3. **Password Tab**: Enter current/new password → Submit → Success/error
4. **Notifications Tab**: Toggle preferences → Save

### Email Verification Flow
1. Unverified user logs in → Dashboard shows banner
2. Click "Resend email" → API call → "Email sent!" message
3. User checks email → Clicks verification link → Email verified
4. Banner disappears on next page load

### Premium Feature Flow
1. Free user encounters premium feature
2. See blurred content with upgrade prompt
3. Click "Upgrade to Premium" → `/payment`
4. Complete payment → Feature unlocked

## Auth Guard Usage

### Protecting Routes
```tsx
// Full protection (auth + onboarding + verification)
<AuthGuard>
  <DashboardContent />
</AuthGuard>

// Only require auth
<AuthGuard requireOnboarding={false} requireVerification={false}>
  <OnboardingContent />
</AuthGuard>
```

### Checking Permissions
```tsx
import { isPremium, isClassHead, checkFeatureAccess } from '@/lib/guards';

// Check premium status
if (isPremium()) {
  // Show premium content
}

// Check class head status
if (isClassHead()) {
  // Show class head features
}

// Check specific feature
if (checkFeatureAccess('premium')) {
  // Allow access
}
```

## Backend Endpoints Used

### Profile Management
- `GET /api/accounts/profile/` - Get user profile
- `PATCH /api/accounts/profile/` - Update profile
- `DELETE /api/accounts/profile/` - Delete account

### Password Management
- `POST /api/accounts/change-password/` - Change password

### Email Verification
- `POST /api/accounts/resend-verification/` - Resend verification email

### File Upload
- `POST /api/curriculum/upload/` - Upload profile image to Cloudinary

## State Management

### LocalStorage Keys
- `access_token`: JWT access token
- `refresh_token`: JWT refresh token
- `user_profile`: Serialized UserProfile object

### Profile Updates
- Profile updates refresh localStorage
- Dashboard components read from localStorage
- Auth guards check localStorage for quick validation

## Security Features

### Password Requirements
- Minimum 8 characters
- Must match confirmation field
- Requires current password for change

### Account Deletion
- Confirmation dialog before deletion
- Immediate logout after deletion
- Cannot be undone

### Auth Token Management
- Tokens stored in localStorage
- Sent in Authorization header
- Cleared on logout/deletion

## UI/UX Features

### Loading States
- Profile page shows spinner while loading
- Settings shows "Updating..." on password change
- Image upload shows spinner during upload
- Auth guard shows loading screen during checks

### Error Handling
- Alert dialogs for errors
- Form validation messages
- API error display

### Responsive Design
- Profile stats grid (3 columns on desktop)
- Settings tabs (horizontal on desktop)
- Mobile-friendly forms

## Next Steps (Phase 4)

### Class Management Features
- Class head announcements page
- Class roster view
- Class analytics dashboard
- Student join class flow improvements

### Community Features
- Create post functionality
- Add comment functionality
- Edit/delete own posts
- User profile pages in community

### Analytics & Insights
- Weak topics algorithm implementation
- Progress charts and visualizations
- Study time tracking display

## Testing Checklist

- [ ] Profile page loads with user data
- [ ] Profile image upload works
- [ ] Profile edit saves successfully
- [ ] Settings password change works
- [ ] Settings notification toggles work
- [ ] Account deletion works
- [ ] Auth guard redirects correctly
- [ ] Email verification banner shows for unverified users
- [ ] Email verification resend works
- [ ] Premium lock shows for free users
- [ ] Premium features unlock for premium users
- [ ] Dashboard shows verification banner
- [ ] Logout clears tokens and redirects

## Known Issues
- None currently

## Notes
- Profile image upload uses Cloudinary (same as slide uploads)
- Auth guards use localStorage for quick checks (no API call on every route)
- Email verification is optional (users can use app without verifying)
- Class heads must be verified to access app (enforced by auth guard)
- Premium features can be locked individually using PremiumLock component
