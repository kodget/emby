# Class Head Verification System

## Key Changes

### 1. Class Code System
- **Generated once** when first class head creates class
- **Stored in database** and sent to class head's email
- **Shared manually** by class head with other members
- **Max 3 class heads** per class (enforced)

### 2. Class Head Benefits
- **Automatic premium access** (no payment required)
- **Full feature access** once verified
- **Cannot be more than 3** class heads per class

### 3. Manual Verification
- Class heads must be **manually verified by admin**
- Cannot access app until verified
- Receive email notification when approved/rejected

## Updated Flow

### For Class Heads:

```
Sign Up → Onboarding (select "Class Head") → 
Request Verification → Wait for Admin Approval → 
Receive Email with Class Code → Access App (Full Premium Features)
```

### For Other Users:

```
Sign Up → Onboarding (enter class code from class head) → 
Choose Free/Premium → Access App
```

## API Changes

### Submit Onboarding (Class Head)

```http
POST /api/accounts/onboarding/submit/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "role": "class_head",
  "school_name": "University of Lagos",
  "set_name": "2024/2025",
  "subscription_tier": "free",  // Ignored for class heads
  "responses": []
}
```

Response:
```json
{
  "message": "Onboarding completed successfully",
  "verification_message": "Your class head account is pending verification. You will receive an email once approved.",
  "user": {
    ...
    "role": "class_head",
    "class_head_verified": false,
    "class_head_verification_requested": true,
    "can_access_app": false,
    "subscription_tier": "class_head"
  },
  "class_code": "123456"
}
```

**Email sent to class head:**
```
Subject: Your Class Code - Emby

Your class code is: 123456

Share this code with your classmates to join.

Note: Your account is pending verification. You will be notified once approved.
```

### Check Verification Status

```http
GET /api/accounts/profile/
Authorization: Bearer <access_token>
```

Response includes:
```json
{
  "class_head_verified": false,
  "class_head_verification_requested": true,
  "class_head_rejection_reason": "",
  "can_access_app": false,
  "is_premium": false  // false until verified
}
```

### Admin: Get Pending Verifications

```http
GET /api/accounts/class-head/pending/
Authorization: Bearer <admin_access_token>
```

Response:
```json
[
  {
    "id": 1,
    "username": "classhead@example.com",
    "email": "classhead@example.com",
    "full_name": "John Doe",
    "role": "class_head",
    "school_name": "University of Lagos",
    "set_name": "2024/2025",
    "class_code": "123456",
    "class_head_verified": false,
    "class_head_verification_requested": true,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

### Admin: Approve Class Head

```http
POST /api/accounts/class-head/verify/
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "user_id": 1,
  "approved": true
}
```

Response:
```json
{
  "message": "Class head verified successfully",
  "user": {
    ...
    "class_head_verified": true,
    "class_head_verification_requested": false,
    "can_access_app": true,
    "is_premium": true,
    "subscription_tier": "class_head"
  }
}
```

**Email sent to class head:**
```
Subject: Class Head Verification Approved - Emby

Congratulations! Your class head account has been verified.

You now have full access to all premium features.

Your class code: 123456
```

### Admin: Reject Class Head

```http
POST /api/accounts/class-head/verify/
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "user_id": 1,
  "approved": false,
  "rejection_reason": "Unable to verify credentials"
}
```

**Email sent to class head:**
```
Subject: Class Head Verification - Emby

Your class head verification request was not approved.

Reason: Unable to verify credentials

Please contact support for more information.
```

## Django Admin Interface

### Approve/Reject Class Heads

1. Go to http://localhost:8000/admin/accounts/profile/
2. Filter by:
   - Role: "Class Head"
   - Class head verification requested: "Yes"
   - Class head verified: "No"
3. Select profiles
4. Choose action:
   - "Approve selected class heads"
   - "Reject selected class heads"
5. Click "Go"

### Bulk Actions Available:
- **Approve selected class heads**: Verifies and grants premium access
- **Reject selected class heads**: Rejects verification request

## Frontend Implementation

### 1. Onboarding Page

```typescript
// Check if user selected "class_head" role
if (role === 'class_head') {
  // Don't show subscription tier selection
  // Don't ask for class code
  
  // After submission, show:
  showMessage({
    title: "Verification Pending",
    message: "Your class head account is pending verification. You will receive an email with your class code once approved.",
    type: "info"
  });
  
  // Redirect to waiting page
  router.push('/verification-pending');
}
```

### 2. Verification Pending Page

```tsx
// /verification-pending
export default function VerificationPending() {
  const { user } = useAuth();
  
  if (user.class_head_verified) {
    // Redirect to app if already verified
    router.push('/app');
  }
  
  return (
    <div>
      <h1>Verification Pending</h1>
      <p>Your class head account is being reviewed.</p>
      <p>You will receive an email once approved.</p>
      
      {user.class_head_rejection_reason && (
        <Alert type="error">
          <p>Your verification was not approved.</p>
          <p>Reason: {user.class_head_rejection_reason}</p>
        </Alert>
      )}
    </div>
  );
}
```

### 3. App Access Guard

```typescript
// Protect app routes
if (user.role === 'class_head' && !user.class_head_verified) {
  // Redirect to verification pending page
  router.push('/verification-pending');
  return null;
}

// Check premium access
const hasPremiumAccess = user.is_premium; // true for verified class heads
```

### 4. Class Code Display (for verified class heads)

```tsx
{user.is_class_head && user.class_code && (
  <div className="class-code-card">
    <h3>Your Class Code</h3>
    <div className="code">{user.class_code}</div>
    <button onClick={() => copyToClipboard(user.class_code)}>
      Copy Code
    </button>
    <p>Share this code with your classmates</p>
  </div>
)}
```

## Database Schema Changes

### Profile Model
```python
class Profile(models.Model):
    # ... existing fields ...
    
    # New fields
    class_head_verified = models.BooleanField(default=False)
    class_head_verification_requested = models.BooleanField(default=False)
    class_head_rejection_reason = models.TextField(blank=True)
    
    @property
    def can_access_app(self):
        """Check if user can access the app"""
        if self.role == UserRole.CLASS_HEAD:
            return self.class_head_verified
        return True
    
    @property
    def is_premium(self):
        """Class heads get automatic premium access"""
        if self.role == UserRole.CLASS_HEAD and self.class_head_verified:
            return True
        # ... existing logic ...
```

### ClassGroup Model
```python
class ClassGroup(models.Model):
    # Changed from ForeignKey to ManyToManyField
    class_heads = models.ManyToManyField(User, related_name='managed_classes')
    
    def add_class_head(self, user):
        """Add class head (max 3)"""
        if self.class_heads.count() >= 3:
            raise ValueError("Maximum 3 class heads per class")
        self.class_heads.add(user)
```

## Migration Steps

```bash
# Create migrations
python manage.py makemigrations accounts

# Apply migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Start server
python manage.py runserver
```

## Testing

### Test Class Head Signup
```bash
# 1. Sign up as class head
curl -X POST http://localhost:8000/api/accounts/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "classhead@test.com",
    "password": "Test123!",
    "first_name": "Class",
    "last_name": "Head"
  }'

# 2. Submit onboarding
curl -X POST http://localhost:8000/api/accounts/onboarding/submit/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "class_head",
    "school_name": "Test University",
    "set_name": "2024/2025",
    "subscription_tier": "free"
  }'

# 3. Check profile (should show pending verification)
curl -X GET http://localhost:8000/api/accounts/profile/ \
  -H "Authorization: Bearer <token>"

# 4. Admin approves (login to admin panel)
# Go to http://localhost:8000/admin/accounts/profile/
# Select the profile and approve

# 5. Check profile again (should show verified)
curl -X GET http://localhost:8000/api/accounts/profile/ \
  -H "Authorization: Bearer <token>"
```

## Summary

✅ Class code generated once and emailed to class head
✅ Max 3 class heads per class enforced
✅ Class heads get automatic premium access (no payment)
✅ Manual verification required before app access
✅ Email notifications for approval/rejection
✅ Admin interface for bulk approval/rejection
✅ Frontend can check `can_access_app` property
