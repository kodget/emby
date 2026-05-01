# Role-Based Access Control (RBAC) Documentation

## User Roles

### 1. STUDENT
**Primary Purpose**: Regular student learning and participating

**Permissions**:
- ✅ View all courses and materials
- ✅ Track progress and earn points
- ✅ Create community posts (discussions, questions, achievements, resources)
- ✅ Like and comment on posts
- ✅ View class roster and announcements
- ✅ Join class with code
- ✅ Access free features
- ✅ Upgrade to premium subscription
- ❌ Cannot upload study materials
- ❌ Cannot manage class
- ❌ Cannot create announcements

**Subscription Tiers**:
- Free: Basic access
- Premium: Full access to all features

---

### 2. BRAINSTORMER
**Primary Purpose**: Active community contributor and discussion leader

**Permissions**:
- ✅ All STUDENT permissions
- ✅ Create community posts (discussions, questions, achievements, resources)
- ✅ Like and comment on posts
- ✅ View class roster and announcements
- ✅ Join class with code
- ✅ Access free features
- ✅ Upgrade to premium subscription
- ❌ Cannot upload study materials
- ❌ Cannot manage class
- ❌ Cannot create announcements

**Subscription Tiers**:
- Free: Basic access
- Premium: Full access to all features

**Note**: Brainstormers have the same permissions as students but are identified as active community contributors.

---

### 3. CLASS_HEAD
**Primary Purpose**: Class management and leadership

**Permissions**:
- ✅ All STUDENT permissions
- ✅ Create, edit, delete class announcements
- ✅ View class analytics dashboard
- ✅ View detailed class roster with stats
- ✅ Manage class (view members, performance)
- ✅ Upload study materials
- ✅ Create community posts
- ✅ Automatic premium access (no payment required)
- ✅ Access all premium features

**Verification Required**:
- ❗ Must be manually verified by admin before accessing app
- ❗ Max 3 class heads per class
- ❗ Verification can be rejected with reason

**Subscription Tier**:
- Automatic "class_head" tier (equivalent to premium)
- No payment required
- Full access to all features

**Special Features**:
- Class analytics dashboard
- Announcement management
- Class roster with detailed stats
- Material upload capability

---

### 4. MATERIAL_UPLOADER
**Primary Purpose**: Upload and manage study materials

**Permissions**:
- ✅ View all courses and materials
- ✅ Upload study materials (slides, PDFs, etc.)
- ✅ Edit/delete own uploaded materials
- ✅ Track progress and earn points
- ✅ Like and comment on community posts
- ✅ View class roster and announcements
- ✅ Join class with code
- ✅ Access free features
- ✅ Upgrade to premium subscription
- ❌ Cannot create community posts
- ❌ Cannot manage class
- ❌ Cannot create announcements

**Subscription Tiers**:
- Free: Basic access + upload capability
- Premium: Full access + upload capability

**Note**: Material uploaders focus on content contribution, not community discussions.

---

## Permission Matrix

| Feature | Student | Brainstormer | Class Head | Material Uploader |
|---------|---------|--------------|------------|-------------------|
| View courses/materials | ✅ | ✅ | ✅ | ✅ |
| Track progress | ✅ | ✅ | ✅ | ✅ |
| Create posts | ✅ | ✅ | ✅ | ❌ |
| Like/comment posts | ✅ | ✅ | ✅ | ✅ |
| Upload materials | ❌ | ❌ | ✅ | ✅ |
| Create announcements | ❌ | ❌ | ✅ | ❌ |
| View class analytics | ❌ | ❌ | ✅ | ❌ |
| Manage class | ❌ | ❌ | ✅ | ❌ |
| Premium access | 💰 | 💰 | ✅ Free | 💰 |

**Legend**:
- ✅ = Allowed
- ❌ = Not allowed
- 💰 = Requires premium subscription

---

## Feature Access Control

### Community Posts
**Who can create**: Student, Brainstormer, Class Head
**Who cannot**: Material Uploader

**Reason**: Material uploaders focus on content, not discussions.

### Material Upload
**Who can upload**: Material Uploader, Class Head
**Who cannot**: Student, Brainstormer

**Reason**: Controlled content quality and management.

### Class Management
**Who can manage**: Class Head only
**Who cannot**: Student, Brainstormer, Material Uploader

**Features**:
- Create/edit/delete announcements
- View class analytics
- Access detailed roster
- Manage class settings

### Premium Features
**Who gets free access**: Class Head
**Who needs to pay**: Student, Brainstormer, Material Uploader

**Premium features**:
- Advanced analytics
- Unlimited study materials
- Priority support
- Ad-free experience
- Custom study plans

---

## Implementation

### Frontend Guards (`lib/guards.ts`)

```typescript
// Role checks
isStudent() // Check if user is student
isBrainstormer() // Check if user is brainstormer
isClassHead() // Check if user is class head (verified)
isMaterialUploader() // Check if user is material uploader

// Permission checks
canCreatePosts() // Student, Brainstormer, Class Head
canUploadMaterials() // Material Uploader, Class Head
canManageClass() // Class Head only
isPremium() // Premium or Class Head tier

// Feature access
checkFeatureAccess("create_posts")
checkFeatureAccess("upload_materials")
checkFeatureAccess("manage_class")
checkFeatureAccess("premium")
```

### Usage Examples

```typescript
// Community page
if (canCreatePosts()) {
  // Show "Create Post" button
} else {
  // Show locked button with explanation
}

// Material upload page
if (canUploadMaterials()) {
  // Show upload form
} else {
  // Redirect or show access denied
}

// Class analytics
if (canManageClass()) {
  // Show analytics dashboard
} else {
  // Redirect to class overview
}
```

---

## Verification Process

### Class Head Verification
1. User signs up with "class_head" role
2. Completes onboarding
3. Redirected to verification-pending page
4. Admin reviews request in Django admin
5. Admin approves or rejects
6. If approved:
   - `class_head_verified = True`
   - `subscription_tier = "class_head"`
   - User can access app
7. If rejected:
   - `class_head_rejection_reason` set
   - User sees rejection message
   - Can contact support

### Other Roles
- No verification required
- Immediate access after onboarding
- Can start using app right away

---

## Subscription Tiers

### FREE
- Available to: Student, Brainstormer, Material Uploader
- Features: Basic access, limited materials, ads

### PREMIUM
- Available to: Student, Brainstormer, Material Uploader
- Cost: ₦1,000 - ₦10,000 (1-12 months)
- Features: Full access, unlimited materials, no ads

### CLASS_HEAD
- Available to: Class Head only
- Cost: Free (automatic)
- Features: All premium features + class management

---

## Security Considerations

### Frontend Validation
- All role checks done in `lib/guards.ts`
- UI elements hidden/disabled based on permissions
- Redirects for unauthorized access

### Backend Validation
- All API endpoints check user role
- Django permissions enforce access control
- Database constraints prevent invalid data

### Best Practices
- Never trust frontend checks alone
- Always validate on backend
- Log permission violations
- Show clear error messages
- Provide upgrade paths when appropriate

---

## Future Enhancements

### Potential New Roles
- **TEACHER**: Similar to class head but for multiple classes
- **ADMIN**: Full system access
- **MODERATOR**: Community moderation powers

### Potential New Permissions
- Edit others' posts (moderators)
- Delete any content (admins)
- Create quizzes (teachers)
- Bulk upload materials (admins)
- Export class data (class heads)

---

## Testing Checklist

- [ ] Students can create posts
- [ ] Brainstormers can create posts
- [ ] Class heads can create posts
- [ ] Material uploaders cannot create posts
- [ ] Material uploaders can upload materials
- [ ] Class heads can upload materials
- [ ] Students cannot upload materials
- [ ] Class heads can create announcements
- [ ] Students cannot create announcements
- [ ] Class heads can access analytics
- [ ] Students cannot access analytics
- [ ] Class heads get free premium access
- [ ] Students need to pay for premium
- [ ] Unverified class heads cannot access app
- [ ] Verified class heads can access app
