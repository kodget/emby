# Complete Authentication & Onboarding System

## Overview

This system implements a complete user authentication and onboarding flow with:
- Email/password signup and login
- Google OAuth integration
- Email verification
- Role-based onboarding (Student, Brainstormer, Class Head, Material Uploader)
- Class code system for group management
- Free and Premium subscription tiers
- Paystack payment integration

## User Flow

```
Landing Page
    ↓
Sign In / Sign Up Page
    ↓
[New User] → Onboarding → Payment (if Premium) → App
[Existing User] → App (if onboarding completed)
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

New packages:
- `google-auth>=2.23` - Google OAuth verification

### 2. Configure Environment Variables

Update `backend/.env`:

```env
# Google OAuth (Get from Google Cloud Console)
GOOGLE_CLIENT_ID=your_google_client_id_here
```

**How to get Google Client ID:**
1. Go to https://console.cloud.google.com
2. Create a new project or select existing
3. Enable "Google+ API"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: "Web application"
6. Authorized JavaScript origins: `http://localhost:3000`
7. Authorized redirect URIs: `http://localhost:3000`
8. Copy the Client ID

### 3. Run Migrations

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 4. Seed Onboarding Questions

```bash
python manage.py shell -c "exec(open('seed_onboarding.py').read())"
```

### 5. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 6. Start Server

```bash
python manage.py runserver
```

## API Endpoints

### Authentication

#### 1. Email/Password Signup
```http
POST /api/accounts/signup/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

Response:
```json
{
  "message": "Account created successfully. Please check your email to verify.",
  "user": { ... },
  "tokens": {
    "access": "...",
    "refresh": "..."
  }
}
```

#### 2. Email/Password Login
```http
POST /api/accounts/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

Response:
```json
{
  "message": "Login successful",
  "user": { ... },
  "tokens": { ... }
}
```

Error responses:
- Invalid credentials: 401
- Account not found: Suggests creating account

#### 3. Google OAuth Login/Signup
```http
POST /api/accounts/google-login/
Content-Type: application/json

{
  "token": "google_id_token_here"
}
```

Response:
```json
{
  "message": "Login successful",
  "user": { ... },
  "tokens": { ... },
  "is_new_user": false
}
```

#### 4. Verify Email
```http
POST /api/accounts/verify-email/
Content-Type: application/json

{
  "token": "verification_token_from_email"
}
```

#### 5. Resend Verification Email
```http
POST /api/accounts/resend-verification/
Authorization: Bearer <access_token>
```

### Onboarding

#### 1. Get Onboarding Questions
```http
GET /api/accounts/onboarding/questions/
Authorization: Bearer <access_token>
```

Response:
```json
[
  {
    "id": 1,
    "question_text": "What are your primary learning goals?",
    "question_type": "text",
    "options": [],
    "order": 1
  },
  {
    "id": 2,
    "question_text": "How many hours per day can you dedicate to studying?",
    "question_type": "choice",
    "options": ["Less than 1 hour", "1-2 hours", "2-4 hours", "More than 4 hours"],
    "order": 2
  }
]
```

#### 2. Submit Onboarding
```http
POST /api/accounts/onboarding/submit/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "role": "student",  // or "brainstormer", "class_head", "material_uploader"
  "school_name": "University of Lagos",
  "set_name": "2024/2025",
  "class_code": "123456",  // Required for non-class_head roles, optional for class_head
  "subscription_tier": "free",  // or "premium"
  "responses": [
    {
      "question_id": 1,
      "answer": "Master anatomy and physiology"
    },
    {
      "question_id": 2,
      "answer": "2-4 hours"
    }
  ]
}
```

Response:
```json
{
  "message": "Onboarding completed successfully",
  "user": { ... },
  "class_code": "123456"  // Only for class_head role
}
```

**Role-specific behavior:**
- **class_head**: Generates new 6-digit class code automatically
- **student/brainstormer/material_uploader**: Must provide valid class_code to join existing class

#### 3. Update Onboarding Responses
```http
PUT /api/accounts/onboarding/responses/update/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "responses": [
    {
      "question_id": 1,
      "answer": "Updated answer"
    }
  ]
}
```

### Class Management

#### 1. Join Class with Code
```http
POST /api/accounts/class/join/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "class_code": "123456"
}
```

#### 2. Get My Class Info
```http
GET /api/accounts/class/my-class/
Authorization: Bearer <access_token>
```

Response:
```json
{
  "id": 1,
  "code": "123456",
  "school": 1,
  "school_name": "University of Lagos",
  "set_name": "2024/2025",
  "class_head": 5,
  "class_head_name": "John Doe",
  "member_count": 25,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Profile

#### 1. Get Profile
```http
GET /api/accounts/profile/
Authorization: Bearer <access_token>
```

Response:
```json
{
  "id": 1,
  "username": "user@example.com",
  "email": "user@example.com",
  "full_name": "John Doe",
  "photo_url": "https://...",
  "role": "student",
  "school": 1,
  "school_name": "University of Lagos",
  "set_name": "2024/2025",
  "class_group": 1,
  "class_code": "123456",
  "subscription_tier": "free",
  "subscription_expires_at": null,
  "is_premium": false,
  "onboarding_completed": true,
  "email_verified": true,
  "streak": 5,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 2. Update Profile
```http
PUT /api/accounts/profile/update/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "photo_url": "https://new-photo.jpg",
  "set_name": "Updated Set Name"
}
```

### Announcements (Class Head Only)

#### 1. List Announcements
```http
GET /api/accounts/announcements/
Authorization: Bearer <access_token>
```

#### 2. Create Announcement (Class Head Only)
```http
POST /api/accounts/announcements/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "title": "Important: Exam Schedule",
  "content": "The midterm exam will be held on..."
}
```

#### 3. Update/Delete Announcement
```http
PUT /api/accounts/announcements/{id}/
DELETE /api/accounts/announcements/{id}/
Authorization: Bearer <access_token>
```

### Payment (Premium Subscription)

#### 1. Initiate Payment
```http
POST /api/accounts/payment/initiate/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "months": 1  // Number of months (1, 3, 6, 12)
}
```

Response:
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "reference": "EMBY-123-abc..."
}
```

**Pricing:**
- 1 month: ₦5,000
- 3 months: ₦15,000
- 6 months: ₦30,000
- 12 months: ₦60,000

#### 2. Verify Payment
```http
POST /api/accounts/payment/verify/
Content-Type: application/json

{
  "reference": "EMBY-123-abc..."
}
```

Response:
```json
{
  "message": "Payment verified successfully",
  "user": {
    ...
    "subscription_tier": "premium",
    "subscription_expires_at": "2024-02-15T10:30:00Z",
    "is_premium": true
  }
}
```

## Database Models

### Profile
- `user` - OneToOne with Django User
- `role` - student, brainstormer, class_head, material_uploader
- `school` - ForeignKey to School
- `set_name` - Class set (e.g., "2024/2025")
- `class_group` - ForeignKey to ClassGroup
- `subscription_tier` - free or premium
- `subscription_expires_at` - Premium expiry date
- `onboarding_completed` - Boolean
- `email_verified` - Boolean
- `email_verification_token` - For email verification
- `streak` - Current study streak

### School
- `name` - School/institution name (unique)

### ClassGroup
- `code` - 6-digit unique code
- `school` - ForeignKey to School
- `set_name` - Class set name
- `class_head` - ForeignKey to User (class head)
- `is_active` - Boolean

### OnboardingQuestion
- `question_text` - Question text
- `question_type` - text, choice, select
- `options` - JSON array for choice/select
- `order` - Display order
- `is_active` - Boolean

### OnboardingResponse
- `user` - ForeignKey to User
- `question` - ForeignKey to OnboardingQuestion
- `answer` - User's answer

### Announcement
- `class_group` - ForeignKey to ClassGroup
- `created_by` - ForeignKey to User (class head)
- `title` - Announcement title
- `content` - Announcement content

### PaymentTransaction
- `user` - ForeignKey to User
- `reference` - Paystack reference (unique)
- `amount` - Payment amount
- `status` - pending, success, failed
- `subscription_months` - Number of months
- `verified_at` - Verification timestamp

## Frontend Integration

### 1. Landing Page
- Show "Get Started" buttons
- Redirect to `/signin` or `/signup`

### 2. Sign In Page (`/signin`)
- Email/password form
- Google OAuth button
- Link to "Create Account" (`/signup`)
- On success: Check `onboarding_completed`
  - If true: Redirect to `/app`
  - If false: Redirect to `/onboarding`

### 3. Sign Up Page (`/signup`)
- Email/password form
- Google OAuth button
- Link to "Sign In" (`/signin`)
- On success: Redirect to `/onboarding`

### 4. Onboarding Page (`/onboarding`)
Steps:
1. **Role Selection**: Choose role (student, brainstormer, class_head, material_uploader)
2. **School & Class**: Enter school name, set name
   - If class_head: Skip class code (will be generated)
   - If other roles: Enter class code from class head
3. **Questions**: Answer onboarding questions
4. **Subscription**: Choose Free or Premium
   - If Free: Complete onboarding → Redirect to `/app`
   - If Premium: Complete onboarding → Redirect to Paystack → Verify payment → Redirect to `/app`

### 5. App (`/app`)
- Check `email_verified` - Show banner if false
- Check `is_premium` - Show upgrade prompts for free users
- Display class code if user is class_head
- Show announcements from class_head

## Email Verification

For development, emails are printed to console. For production:

1. Update `settings.py`:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
```

2. Add to `.env`:
```env
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## Testing

### Test Signup Flow
```bash
curl -X POST http://localhost:8000/api/accounts/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### Test Login Flow
```bash
curl -X POST http://localhost:8000/api/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'
```

### Test Onboarding
```bash
curl -X POST http://localhost:8000/api/accounts/onboarding/submit/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "class_head",
    "school_name": "Test University",
    "set_name": "2024/2025",
    "subscription_tier": "free",
    "responses": []
  }'
```

## Security Features

1. **Password Validation**: Django's built-in validators
2. **JWT Authentication**: Secure token-based auth
3. **Email Verification**: Prevents fake accounts
4. **Class Code System**: 6-digit unique codes
5. **Role-based Permissions**: Class heads can create announcements
6. **Payment Verification**: Paystack webhook verification

## Next Steps

1. Update frontend to use new auth endpoints
2. Implement Google OAuth button in frontend
3. Create onboarding UI flow
4. Integrate Paystack payment flow
5. Add email templates for verification
6. Implement password reset flow
7. Add profile picture upload
8. Create class management dashboard for class heads
