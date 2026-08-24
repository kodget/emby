# Quiz Examination System API Documentation

## Overview

The Quiz Examination System provides a complete assessment platform with MCQ and theory questions, AI-powered evaluation, and subscription-based feature access.

## Base URL
```
Production: https://your-domain.com/api/
Development: http://localhost:8000/api/
```

## Authentication

All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Subscription Tiers

- **Free Tier**: 5 MCQ + 1 theory question per quiz, 1 active quiz at a time
- **Premium Tier**: 100 MCQ + 10 theory questions per quiz, unlimited active quizzes, detailed analysis

---

## Quiz Management Endpoints

### Create Quiz Attempt
Create a new quiz attempt with specified configuration.

**Endpoint:** `POST /quiz-attempts/`

**Request Body:**
```json
{
  "subject": "anatomy",
  "block": "anatomy-block-1", 
  "topic": "bones-and-joints",
  "exam_type": "practice|mock|formal",
  "is_timed": true,
  "duration_minutes": 30,
  "configuration": {
    "mcq_count": 5,
    "theory_count": 1,
    "difficulty": "medium"
  }
}
```

**Success Response (201):**
```json
{
  "id": "abc123def456",
  "status": "in_progress",
  "exam_type": "practice",
  "is_timed": true,
  "duration_minutes": 30,
  "deadline": "2024-03-15T14:30:00Z",
  "mcq_total": 5,
  "theory_total": 1,
  "questions": [
    {
      "id": "q1",
      "question_type": "mcq",
      "question_text": "Which bone is the longest in the human body?",
      "option_a": "Femur",
      "option_b": "Tibia", 
      "option_c": "Humerus",
      "option_d": "Radius",
      "difficulty": "medium"
    }
  ],
  "created_at": "2024-03-15T14:00:00Z"
}
```

**Error Responses:**
```json
// Subscription limit exceeded (403)
{
  "error": "Free tier allows up to 5 MCQ questions. Upgrade to Premium for more questions.",
  "upgrade_required": true
}

// Insufficient questions (400)
{
  "error": "Not enough MCQ questions available for selected criteria. Found 3, need 5.",
  "question_bank_empty": true,
  "available_mcq": 3,
  "requested_mcq": 5
}

// Concurrent attempt limit (429) 
{
  "error": "Free tier allows only 1 active quiz at a time. Complete your current quiz or upgrade to Premium.",
  "upgrade_required": true
}
```

### Submit Answer
Submit or update an answer for a specific question.

**Endpoint:** `POST /quiz-attempts/{id}/submit_answer/`

**Request Body (MCQ):**
```json
{
  "question_id": "q1",
  "selected_option": "A"
}
```

**Request Body (Theory):**
```json
{
  "question_id": "q2", 
  "text_answer": "The femur is the longest and strongest bone in the human body, extending from the hip to the knee..."
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Answer saved successfully",
  "question_id": "q1",
  "answer_updated": true
}
```

### Flag Question
Toggle flag status for a question (for review).

**Endpoint:** `POST /quiz-attempts/{id}/toggle_flag/`

**Request Body:**
```json
{
  "question_id": "q1"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "question_id": "q1", 
  "is_flagged": true,
  "flagged_questions": ["q1", "q3"]
}
```

### Submit Quiz
Manually submit the quiz for grading.

**Endpoint:** `POST /quiz-attempts/{id}/submit/`

**Request Body:** Empty

**Success Response (200):**
```json
{
  "success": true,
  "message": "Quiz submitted successfully",
  "attempt_id": "abc123def456",
  "mcq_score": 4,
  "mcq_total": 5, 
  "mcq_percentage": 80.0,
  "theory_grading_pending": true,
  "submitted_at": "2024-03-15T14:25:30Z"
}
```

### Auto Submit Quiz
Automatically submit quiz when timer expires.

**Endpoint:** `POST /quiz-attempts/{id}/auto_submit/`

**Request Body:** Empty

**Success Response (200):**
```json
{
  "success": true,
  "message": "Quiz auto-submitted due to time limit",
  "attempt_id": "abc123def456", 
  "auto_submitted": true,
  "submitted_at": "2024-03-15T14:30:00Z"
}
```

---

## Results Endpoints

### Get Results
Retrieve quiz results (tiered by subscription).

**Endpoint:** `GET /quiz-attempts/{id}/result/`

**Free Tier Response (200):**
```json
{
  "attempt_id": "abc123def456",
  "status": "graded",
  "overall_percentage": 75.0,
  "mcq_score": 4,
  "mcq_total": 5,
  "mcq_percentage": 80.0,
  "theory_score": 7,
  "theory_total": 10, 
  "theory_percentage": 70.0,
  "passed": true,
  "grade": "B",
  "theory_grading_completed": true,
  "is_premium": false,
  "premium_features_available": [
    "Detailed question breakdown",
    "Topic performance analysis",
    "AI study recommendations" 
  ],
  "upgrade_message": "Upgrade to Premium to unlock detailed analysis and study recommendations."
}
```

**Premium Tier Response (200):**
```json
{
  "attempt_id": "abc123def456",
  "status": "graded",
  "overall_percentage": 75.0,
  "mcq_score": 4,
  "mcq_total": 5,
  "theory_score": 7,
  "theory_total": 10,
  "passed": true,
  "is_premium": true,
  "detailed_breakdown": {
    "by_difficulty": {
      "easy": {"correct": 2, "total": 2},
      "medium": {"correct": 2, "total": 3}, 
      "hard": {"correct": 1, "total": 2}
    }
  },
  "topic_performance": [
    {"topic": "Bone Structure", "percentage": 85.0, "questions": 3},
    {"topic": "Joint Types", "percentage": 65.0, "questions": 2}
  ],
  "study_recommendations": [
    "Review joint classification and movement types",
    "Focus on synovial joint anatomy"
  ]
}
```

### Get Missed Questions (Premium Only)
Retrieve detailed breakdown of incorrect answers.

**Endpoint:** `GET /quiz-attempts/{id}/missed/`

**Success Response (200):**
```json
{
  "attempt_id": "abc123def456",
  "missed_questions": [
    {
      "id": "q2",
      "question_text": "What type of joint is the shoulder?", 
      "question_type": "mcq",
      "selected_option": "B",
      "correct_option": "A",
      "explanation": "The shoulder is a ball-and-socket synovial joint...",
      "topic_name": "Joint Types"
    }
  ],
  "total_missed": 1,
  "is_premium": true
}
```

**Free Tier Error (403):**
```json
{
  "error": "Premium subscription required",
  "feature": "Missed questions analysis", 
  "message": "Upgrade to Premium to access detailed question breakdowns and AI feedback.",
  "upgrade_url": "/pricing"
}
```

### Get Performance Analysis (Premium Only)
Get AI-powered performance analysis and recommendations.

**Endpoint:** `GET /quiz-attempts/{id}/analysis/`

**Success Response (200):**
```json
{
  "attempt_id": "abc123def456",
  "performance_analysis": {
    "strengths": ["Bone anatomy", "Basic joint movements"],
    "weaknesses": ["Joint classification", "Complex movements"],
    "study_recommendations": [
      "Review synovial joint types and their characteristics",
      "Practice identifying joint movements in clinical scenarios"
    ]
  },
  "topic_breakdown": [
    {
      "topic": "Bone Structure",
      "performance": "excellent", 
      "percentage": 90.0,
      "recommendation": "Continue practicing advanced concepts"
    },
    {
      "topic": "Joint Types", 
      "performance": "needs_improvement",
      "percentage": 60.0,
      "recommendation": "Focus on classification and movement patterns"
    }
  ]
}
```

---

## Practice Endpoints

### Get Practice Questions
Retrieve questions for slide-based practice mode.

**Endpoint:** `GET /quiz/questions/?slide={slide_id}&practice=true`

**Success Response (200):**
```json
{
  "slide_id": "slide123",
  "questions": [
    {
      "id": "q1",
      "question_type": "mcq",
      "question_text": "Which structure is highlighted?",
      "option_a": "Femur head", 
      "option_b": "Acetabulum",
      "option_c": "Greater trochanter",
      "option_d": "Lesser trochanter",
      "correct_option": "A",
      "explanation": "The highlighted structure is the femur head...",
      "difficulty": "medium"
    }
  ],
  "practice_mode": true
}
```

---

## Error Responses

### Common Error Codes

**400 Bad Request:**
- Invalid request parameters
- Missing required fields
- Validation errors

**401 Unauthorized:**
- Missing or invalid JWT token
- Expired token

**403 Forbidden:**
- Subscription limit exceeded
- Premium feature access denied
- Insufficient permissions

**404 Not Found:**
- Quiz attempt not found
- Question not found
- User does not own resource

**429 Too Many Requests:**
- Rate limit exceeded
- Concurrent attempt limit (free tier)

**500 Internal Server Error:**
- AI service unavailable
- Database error
- Unexpected server error

### Error Response Format
```json
{
  "error": "Human-readable error message",
  "error_code": "SPECIFIC_ERROR_CODE", 
  "details": {
    "field_errors": {
      "mcq_count": ["Must be between 1 and 100"]
    }
  },
  "upgrade_required": false
}
```

---

## Rate Limits

- **Quiz Creation**: 10 per hour per user
- **Answer Submission**: 100 per minute per user  
- **Practice Questions**: 50 per hour per user
- **Results Access**: 20 per minute per user

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1642694400
```

---

## Webhooks (Coming Soon)

Webhook events will be available for:
- Quiz completion
- Theory grading completion
- Subscription changes

---

## SDKs and Libraries

### JavaScript/TypeScript
```javascript
import { quizApi } from '@/lib/api';

// Create quiz
const quiz = await quizApi.createQuizAttempt({
  subject: 'anatomy',
  exam_type: 'practice',
  configuration: {
    mcq_count: 5,
    theory_count: 1,
    difficulty: 'medium'
  }
});

// Submit answer
await quizApi.submitAnswer(quiz.id, {
  question_id: 'q1',
  selected_option: 'A'
});
```

### Python
```python
import requests

# Create quiz
response = requests.post(
    'https://api.example.com/quiz-attempts/',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'subject': 'anatomy',
        'exam_type': 'practice',
        'configuration': {
            'mcq_count': 5,
            'theory_count': 1,
            'difficulty': 'medium'
        }
    }
)
```

---

## Support

For API support:
- Documentation: https://docs.example.com/api
- Support Email: api-support@example.com
- Status Page: https://status.example.com