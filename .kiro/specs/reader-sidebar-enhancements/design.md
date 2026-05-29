# Design Document

## Architecture Overview

### Frontend Changes

- **Reader Component**: Update sidebar tabs with AI features
- **Premium Access Logic**: Fix class head premium check
- **New Components**: TextbookSuggestions, VideoSuggestions, QuizGenerator
- **Pagination**: Add prev/next navigation for expanded reader

### Backend Changes

- **AI Service**: New service for Gemini Pro API integration
- **New Endpoints**:
  - `/api/ai/textbook-suggestions/`
  - `/api/ai/video-suggestions/`
  - `/api/ai/generate-mcqs/`
- **Premium Middleware**: Check `is_premium OR role == 'Class Head'`

### API Integration

- **Gemini Pro API**: RapidAPI endpoint provided
- **Caching**: Redis/database cache for AI responses
- **Rate Limiting**: Prevent API abuse

## Implementation Plan

1. **Backend AI Service** - Create AI service with Gemini integration
2. **Backend Endpoints** - Add 3 new AI endpoints with premium checks
3. **Frontend Premium Logic** - Fix class head premium access
4. **Frontend Components** - Update sidebar tabs with AI features
5. **Remove Upload Button** - Clean up reader toolbar
6. **Add Pagination** - Implement slide navigation

## Premium Access Logic

```python
def has_premium_access(user):
    return user.profile.is_premium or user.profile.role == 'Class Head'
```

## AI Service Design

- Use provided RapidAPI Gemini endpoint
- Cache responses by slide_id + feature_type
- Handle errors gracefully with fallbacks
- 30-second timeout for API calls
