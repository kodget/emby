# Frontend Authentication - Phase 5: Community Features with RBAC

## Completion Date
[Current Date]

## Overview
Phase 5 implements community features with proper role-based access control. Students, brainstormers, and class heads can create posts and engage in discussions. Material uploaders can view and interact but cannot create posts.

## Files Created

### 1. Community Page (`app/community/page.tsx`)
**Purpose**: Main community feed with post creation and interaction

**Features**:
- **View Posts** (All Users):
  - Feed of all community posts
  - Post type badges (achievement, question, discussion, resource)
  - Author name and profile picture
  - Post timestamp
  - Like count and comment count
  - Full post content

- **Create Posts** (Student, Brainstormer, Class Head):
  - "New Post" button
  - Create post modal with type selection
  - Post types: Discussion, Question, Achievement, Resource
  - Content textarea with validation
  - Submit and cancel actions

- **Interact with Posts** (All Users):
  - Like/unlike posts
  - Add comments
  - View all comments
  - Real-time updates

- **Role-Based UI**:
  - Material uploaders see locked "New Post" button
  - Info banner explaining material uploader role
  - Permission checks before showing create button

**Role Permissions**:
- ✅ Student: Can create posts
- ✅ Brainstormer: Can create posts
- ✅ Class Head: Can create posts
- ❌ Material Uploader: Cannot create posts (can view/like/comment)

### 2. Updated Guards (`lib/guards.ts`)
**New Functions Added**:

```typescript
// Role checks
isBrainstormer(): boolean
isMaterialUploader(): boolean
isStudent(): boolean

// Permission checks
canCreatePosts(): boolean
canUploadMaterials(): boolean
canManageClass(): boolean

// Enhanced feature access
checkFeatureAccess(feature: "premium" | "class_head" | "create_posts" | "upload_materials" | "manage_class"): boolean
```

**Permission Logic**:
- `canCreatePosts()`: Returns true for student, brainstormer, class_head
- `canUploadMaterials()`: Returns true for material_uploader, class_head
- `canManageClass()`: Returns true for class_head only

### 3. RBAC Documentation (`RBAC_DOCUMENTATION.md`)
**Comprehensive role documentation**:
- Detailed permissions for each role
- Permission matrix table
- Feature access control rules
- Implementation examples
- Security considerations
- Testing checklist

## Role-Based Access Control

### 4 User Roles

#### 1. STUDENT
- Primary learner role
- Can create posts and engage in community
- Can upgrade to premium
- Cannot upload materials or manage class

#### 2. BRAINSTORMER
- Active community contributor
- Same permissions as student
- Identified as discussion leader
- Can create posts and engage fully

#### 3. CLASS_HEAD
- Class manager and leader
- All student permissions
- Can create announcements
- Can view analytics
- Can upload materials
- Automatic premium access
- Requires admin verification

#### 4. MATERIAL_UPLOADER
- Content contributor role
- Can upload study materials
- Can view and interact with posts
- **Cannot create posts** (focused on content, not discussions)
- Can upgrade to premium

### Permission Matrix

| Feature | Student | Brainstormer | Class Head | Material Uploader |
|---------|---------|--------------|------------|-------------------|
| Create posts | ✅ | ✅ | ✅ | ❌ |
| Like/comment | ✅ | ✅ | ✅ | ✅ |
| Upload materials | ❌ | ❌ | ✅ | ✅ |
| Manage class | ❌ | ❌ | ✅ | ❌ |
| Premium access | 💰 | 💰 | ✅ Free | 💰 |

## User Flows

### Student/Brainstormer Community Flow
1. Navigate to `/community`
2. See "New Post" button (enabled)
3. Click "New Post" → Modal opens
4. Select post type (discussion, question, achievement, resource)
5. Write content → Submit
6. Post appears in feed
7. Like posts, add comments
8. View others' posts and engage

### Class Head Community Flow
1. Navigate to `/community`
2. See "New Post" button (enabled)
3. Same creation flow as students
4. Additional badge showing class head status
5. Can engage with all posts
6. Posts show class head badge

### Material Uploader Community Flow
1. Navigate to `/community`
2. See "New Post" button (locked/disabled)
3. See info banner: "Material Uploader: You can view and interact with posts, but cannot create new posts"
4. Can view all posts
5. Can like posts
6. Can add comments
7. Cannot create new posts

## API Integration

### Existing Endpoints Used
- `GET /api/community/` - Get all posts
- `POST /api/community/` - Create post (with role check)
- `POST /api/community/:id/like/` - Like post
- `POST /api/community/:id/unlike/` - Unlike post
- `POST /api/community/:id/comment/` - Add comment
- `GET /api/accounts/profile/` - Get user profile with role

### Backend Validation
Backend should validate:
- User role before allowing post creation
- Only student, brainstormer, class_head can create posts
- Material uploaders get 403 Forbidden if they try to create posts

## UI/UX Features

### Role-Based UI Elements

**For Users Who Can Create Posts**:
- Enabled "New Post" button (purple, clickable)
- No restrictions or warnings
- Full access to create modal

**For Material Uploaders**:
- Disabled "New Post" button (gray, locked icon)
- Info banner explaining role restrictions
- Can still interact with existing posts
- Clear visual feedback about limitations

### Post Type Colors
- **Achievement**: Green badge
- **Question**: Blue badge
- **Discussion**: Purple badge
- **Resource**: Orange badge

### Interactive Elements
- Like button with count
- Comment button with count
- Comment input with send button
- Real-time updates after actions
- Loading states during submission

### Empty States
- No posts: Encouraging message with create button
- Only shows create button if user has permission

## Security Implementation

### Frontend Checks
```typescript
// Check before showing create button
const canCreate = canCreatePosts();

// Check before opening modal
if (!canCreatePosts()) {
  alert("You don't have permission to create posts");
  return;
}
```

### Backend Checks (Required)
```python
# In Django view
if request.user.profile.role not in ['student', 'brainstormer', 'class_head']:
    return Response(
        {"error": "You don't have permission to create posts"},
        status=403
    )
```

### Defense in Depth
- Frontend hides UI elements
- Frontend validates before API calls
- Backend validates all requests
- Database constraints enforce rules

## Testing Checklist

### Role-Based Access
- [ ] Students can create posts
- [ ] Brainstormers can create posts
- [ ] Class heads can create posts
- [ ] Material uploaders cannot create posts
- [ ] Material uploaders see locked button
- [ ] Material uploaders see info banner
- [ ] All users can like posts
- [ ] All users can comment on posts

### Post Creation
- [ ] Create modal opens correctly
- [ ] Post type selection works
- [ ] Content validation works
- [ ] Submit creates post successfully
- [ ] Cancel closes modal
- [ ] New post appears in feed

### Post Interaction
- [ ] Like button works
- [ ] Like count updates
- [ ] Comment input works
- [ ] Comment submit works
- [ ] Comments appear in post
- [ ] Enter key submits comment

### UI/UX
- [ ] Post type badges show correct colors
- [ ] Profile pictures display correctly
- [ ] Timestamps format correctly
- [ ] Empty state shows when no posts
- [ ] Loading states work
- [ ] Mobile responsive design works

## Known Limitations

### Features Not Implemented
- Edit own posts
- Delete own posts
- Report inappropriate posts
- Post search/filter
- Post pagination (loads all posts)
- Post attachments (images, files)
- Mentions (@username)
- Hashtags (#topic)
- Post reactions (beyond like)
- Nested comments (replies to comments)

### Backend Dependencies
- Backend must validate role permissions
- Backend must return proper error messages
- Backend must handle post creation for allowed roles

## Future Enhancements

### Post Management
- Edit own posts (within time limit)
- Delete own posts
- Pin important posts (class heads)
- Archive old posts

### Advanced Interactions
- Reply to specific comments
- React with emojis
- Share posts
- Save/bookmark posts
- Follow users

### Content Moderation
- Report posts/comments
- Moderator role for content review
- Auto-moderation for spam
- Content guidelines enforcement

### Discovery Features
- Search posts by keyword
- Filter by post type
- Sort by recent/popular
- Trending topics
- Recommended posts

### Notifications
- New post notifications
- Comment notifications
- Like notifications
- Mention notifications
- Email digests

## Integration with Other Features

### Dashboard Integration
- Community feed widget already exists
- Shows recent posts
- Links to full community page

### Profile Integration
- User posts visible on profile (future)
- Post count in profile stats (future)
- Community reputation score (future)

### Class Integration
- Class-specific community feed (future)
- Announcements vs community posts distinction
- Class head moderation powers (future)

## Notes
- Material uploader role is intentionally restricted from creating posts
- This keeps them focused on content contribution (materials)
- They can still engage with community through likes and comments
- Role permissions are enforced both frontend and backend
- Clear UI feedback helps users understand their permissions
- Info banners explain role limitations without being intrusive
