# Implementation Plan: Quiz / Examination System

## Overview

The Quiz/Examination System replaces the existing prototype quiz infrastructure with a production-grade assessment engine. This implementation extends existing models (`QuizQuestion`, `Quiz`, `QuizAnswer`) while introducing new models (`QuizAttempt`, `QuizAttemptResponse`) to support both slide-practice and formal examinations with AI-powered theory evaluation.

The system follows the established Django monolith pattern with DRF ViewSets, Celery tasks, and Next.js 14 App Router pages with Redux state management.

## Tasks

- [x] 1. Phase 1 — Question Bank Extension
  - [x] 1.1 Create database migration for QuizQuestion model extension
    - Add new fields: `ideal_answer`, `marking_rubric`, `maximum_marks`, `source_text`, `question_options_order`
    - Create database indexes for performance optimization
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 1.2 Update QuizQuestion serializers and admin interface
    - Extend QuizQuestionSerializer to include new fields
    - Update Django admin interface for question management
    - _Requirements: 9.4, 9.5_

- [x] 2. Phase 2 — Core Data Models
  - [x] 2.1 Create QuizAttempt model with full field definition
    - Implement QuizAttempt model with status enum, timing fields, configuration JSON, scoring fields
    - Add model properties: `is_expired`, `theory_grading_complete`
    - Create database indexes for user queries and status filtering
    - _Requirements: 1.6, 4.1, 4.6, 5.5_

  - [x] 2.2 Create QuizAttemptResponse model
    - Implement response model with MCQ/theory fields and AI evaluation status
    - Add unique constraints and database indexes
    - _Requirements: 2.3, 3.4, 6.1, 6.3_

  - [x] 2.3 Create Django migrations for new models
    - Generate and review migration files
    - Test migration rollback compatibility
    - _Requirements: 14.4_

- [x] 3. Phase 3 — Subscription Management
  - [x] 3.1 Implement SubscriptionLimiter service class
    - Create `is_premium()` method reading UserProfile fields
    - Implement `check_limits()` with tier-specific quotas
    - Add `premium_feature()` validation method
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]\* 3.2 Write property tests for SubscriptionLimiter
    - **Property P3: Subscription Invariant**
    - **Validates: Requirements 10.1, 10.2**

- [x] 4. Phase 4 — Quiz Attempt Management
  - [x] 4.1 Create QuizAttemptSerializer with nested question serialization
    - Implement serializer with conditional field exposure based on attempt status
    - Add validation for configuration parameters
    - _Requirements: 1.1, 2.4, 12.1_

  - [x] 4.2 Implement QuizAttemptViewSet create action
    - Add subscription limit validation
    - Implement question fetching and randomization logic
    - Create attempt with ordered question IDs and timing configuration
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]\* 4.3 Write property tests for attempt creation
    - **Property P2: Question Completeness**
    - **Property P6: Timer Integrity**
    - **Validates: Requirements 1.6, 4.1**

  - [x] 4.4 Implement answer saving endpoint (POST /attempts/{id}/answer/)
    - Create answer action with autosave functionality
    - Add validation for question ownership and attempt status
    - _Requirements: 2.2, 2.3, 3.2_

  - [x] 4.5 Implement question flagging endpoint (POST /attempts/{id}/flag/)
    - Create flag toggle action updating attempt's flagged_questions array
    - _Requirements: 2.6_

- [x] 5. Phase 5 — Timer Management and Auto-Submit
  - [x] 5.1 Implement manual submit endpoint (POST /attempts/{id}/submit/)
    - Add immediate MCQ scoring logic
    - Queue Celery task for theory evaluation
    - Update attempt status and timestamps
    - _Requirements: 4.5, 5.1, 5.2, 5.3, 5.4_

  - [x] 5.2 Implement auto-submit endpoint (POST /attempts/{id}/auto_submit/)
    - Add timer validation with 30-second buffer
    - Implement same scoring logic as manual submit
    - _Requirements: 4.3, 4.4, 12.2_

  - [ ]\* 5.3 Write unit tests for timer validation
    - Test boundary cases: exact deadline, buffer allowance, late rejection
    - _Requirements: 4.4, 12.2_

- [x] 6. Phase 6 — MCQ Scoring Engine
  - [x] 6.1 Implement MCQ scoring algorithm in QuizAttemptViewSet
    - Create synchronous scoring logic for multiple choice questions
    - Calculate MCQ percentage and update attempt record
    - _Requirements: 5.1, 5.2_

  - [ ]\* 6.2 Write property tests for MCQ scoring
    - **Property P1: Scoring Boundedness**
    - **Validates: Requirements 5.1, 5.2**

- [ ] 7. Phase 7 — AI Question Generation Services
  - [x] 7.1 Create AIQuestionGenerator service class
    - Implement `generate_mcqs_from_text()` with Gemini API integration
    - Implement `generate_theory_from_text()` with rubric creation
    - Add 429 error handling with partial result return
    - Add idempotency check `questions_exist_for_slide()`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [~] 7.2 Create generate_questions_task Celery task
    - Implement async question generation with retry logic
    - Add exponential backoff for rate limit handling
    - _Requirements: 9.1, 9.3, 9.4_

  - [~] 7.3 Create QuestionGenerationView API endpoint
    - Implement POST /api/quiz/generate_questions/ endpoint
    - Add slide ID validation and task queuing
    - _Requirements: 9.1, 9.4_

  - [ ]\* 7.4 Write property tests for question generation
    - **Property P7: Idempotent Question Generation**
    - **Validates: Requirements 9.3**

- [ ] 8. Phase 8 — AI Theory Evaluation
  - [~] 8.1 Create AITheoryEvaluator service class
    - Implement `evaluate()` method with Gemini API integration
    - Add structured feedback generation and score validation
    - Implement proper error handling without fake scores
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [~] 8.2 Create evaluate_theory_answers_task Celery task
    - Implement async evaluation with retry logic for 429 errors
    - Update QuizAttemptResponse with scores and feedback
    - Recalculate overall attempt percentage
    - _Requirements: 6.1, 6.4, 6.6_

  - [ ]\* 8.3 Write property tests for AI evaluation
    - **Property P4: Evaluation Status Consistency**
    - **Property P5: No Score on Failure**
    - **Validates: Requirements 6.3, 6.5**

- [~] 9. Checkpoint - Backend Core Complete
  - Ensure all backend services are functional, ask the user if questions arise.

- [ ] 10. Phase 9 — Results API Endpoints
  - [~] 10.1 Implement result viewing endpoint (GET /attempts/{id}/result/)
    - Create tiered response based on subscription status
    - Include theory pending status and polling mechanism
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [~] 10.2 Implement missed questions endpoint (GET /attempts/{id}/missed/)
    - Create premium-only endpoint with detailed question analysis
    - Include AI feedback for theory questions
    - _Requirements: 11.1, 11.2, 11.4_

  - [~] 10.3 Implement premium analysis endpoint (GET /attempts/{id}/analysis/)
    - Generate topic performance breakdown
    - Create AI-powered study recommendations
    - _Requirements: 11.3, 11.5_

  - [~] 10.4 Implement flashcard creation endpoint (POST /attempts/{id}/flashcards/)
    - Create flashcards from missed questions for premium users
    - _Requirements: 11.4_

- [ ] 11. Phase 10 — Reader Practice API
  - [~] 11.1 Extend QuizQuestionViewSet for slide-based queries
    - Add GET /api/quiz/questions/?slide=<id> endpoint
    - Expose answers and explanations for practice mode
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [~] 11.2 Create slide practice response formatting
    - Include correct answers and explanations in practice API responses
    - _Requirements: 8.2, 8.3_

- [ ] 12. Phase 11 — Frontend Quiz Configuration
  - [~] 12.1 Create QuizConfigPage component (/quiz)
    - Implement cascading Subject → Block → Topic selectors
    - Add exam type selection cards with tier-based gating
    - Create question quantity sliders with subscription limits
    - Add timed exam toggle with duration selection
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [~] 12.2 Create Redux quizAttemptSlice
    - Define state interface for attempt management
    - Implement actions for attempt creation and updates
    - Add selectors for question navigation and status
    - _Requirements: 1.6, 2.3, 2.6_

  - [~] 12.3 Integrate quiz configuration with API
    - Connect form submission to POST /api/quiz/attempts/
    - Handle subscription limit errors with upgrade messaging
    - Redirect to exam interface on successful creation
    - _Requirements: 1.5, 1.6, 1.7, 10.5_

- [ ] 13. Phase 12 — Exam Interface Components
  - [~] 13.1 Create ExamInterface page component (/quiz/attempt/[id])
    - Implement main exam layout with question display area
    - Add question navigator grid component
    - Integrate timer display and management
    - _Requirements: 2.1, 2.6, 4.1, 4.2_

  - [~] 13.2 Create MCQQuestionCard component
    - Implement radio button option selection
    - Add randomized option display based on attempt configuration
    - Handle answer selection and autosave
    - _Requirements: 2.1, 2.2_

  - [~] 13.3 Create TheoryQuestionCard component
    - Implement textarea with live word/character counting
    - Add 50-word minimum guidance hint
    - Handle autosave with debouncing
    - _Requirements: 3.1, 3.2, 3.5_

  - [~] 13.4 Create ExamTimer component
    - Implement countdown display with minute/second formatting
    - Add urgency styling at 5-minute threshold
    - Trigger auto-submit on expiration
    - _Requirements: 4.1, 4.2, 4.3_

  - [~] 13.5 Create QuestionNavigator component
    - Implement 10×N grid of status chips
    - Show answered/unanswered/flagged states with color coding
    - Handle question navigation clicks
    - _Requirements: 2.6_

  - [~] 13.6 Implement exam interface functionality
    - Add focus mode toggle for full-screen experience
    - Implement browser navigation warnings for in-progress attempts
    - Connect flag toggle with API persistence
    - Handle autosave for all question types
    - _Requirements: 2.2, 2.3, 2.5, 2.6_

- [ ] 14. Phase 13 — Results Display
  - [~] 14.1 Create ResultsPage component (/quiz/attempt/[id]/results)
    - Implement automatic tier detection and view routing
    - Add theory evaluation polling mechanism
    - _Requirements: 7.1, 7.2_

  - [~] 14.2 Create FreeResultsView component
    - Display score badge, MCQ percentage, pass/fail status
    - Show theory grading progress with polling
    - Add retake button functionality
    - _Requirements: 7.1, 7.2, 7.5_

  - [~] 14.3 Create PremiumResultsView component
    - Implement topic performance bar charts
    - Display missed questions with detailed analysis
    - Show AI recommendations and feedback
    - _Requirements: 7.3, 7.4, 11.1, 11.2, 11.3_

  - [~] 14.4 Create MissedQuestionCard component
    - Display question text, student answer, and correct answer
    - Show AI feedback in expandable sections for theory questions
    - Include explanation text and study recommendations
    - _Requirements: 11.1, 11.2_

- [ ] 15. Phase 14 — Reader Practice Integration
  - [~] 15.1 Create ReaderPracticePanel component
    - Implement slide-contextual question modal
    - Load questions via slide-specific API calls
    - _Requirements: 8.1_

  - [~] 15.2 Implement practice question display
    - Show MCQ questions with immediate answer reveal
    - Display theory questions with model answer toggle
    - Add CTA for full exam on current topic
    - _Requirements: 8.2, 8.3, 8.5_

- [~] 16. Checkpoint - Frontend Core Complete
  - Ensure all frontend components render and function properly, ask the user if questions arise.

- [ ] 17. Phase 15 — Integration and Signal Handlers
  - [~] 17.1 Create post_save signal handler for slide processing
    - Trigger question generation when new slides are processed
    - Connect to existing slide content workflow
    - _Requirements: 9.1, 14.1_

  - [~] 17.2 Integrate with existing authentication system
    - Ensure quiz endpoints respect existing auth patterns
    - Validate JWT payload handling for premium status display
    - _Requirements: 14.5, 12.3_

- [ ] 18. Phase 16 — Error Handling and Recovery
  - [~] 18.1 Implement comprehensive error handling in ViewSets
    - Add graceful degradation for AI service failures
    - Create descriptive error messages for client handling
    - _Requirements: 15.1, 15.2, 15.4_

  - [~] 18.2 Add frontend error boundaries and retry logic
    - Handle network connectivity issues during exams
    - Implement automatic retry for failed autosaves
    - Add progress preservation on browser refresh
    - _Requirements: 15.1, 15.3_

  - [~] 18.3 Create audit logging for critical operations
    - Log attempt creation, submission, and scoring events
    - Track AI evaluation results and failures
    - Record subscription limit enforcement
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

- [ ] 19. Phase 17 — Performance Optimization
  - [~] 19.1 Implement database query optimization
    - Add select_related and prefetch_related for question loading
    - Optimize scoring queries with bulk operations
    - _Requirements: 13.1, 13.2, 13.3_

  - [~] 19.2 Add frontend performance optimizations
    - Implement question preloading for smooth navigation
    - Add debounced autosave with offline queue
    - Optimize Redux state updates for large question sets
    - _Requirements: 13.2, 13.4_

- [ ] 20. Phase 18 — Testing Suite
  - [ ]\* 20.1 Create comprehensive unit tests for ViewSets
    - Test all API endpoints with various subscription tiers
    - Test error conditions and edge cases
    - _Requirements: All API-related requirements_

  - [ ]\* 20.2 Create integration tests for full exam lifecycle
    - Test complete create → answer → submit → results flow
    - Test timer auto-submission functionality
    - Test premium vs free tier feature access
    - _Requirements: 1.6, 4.3, 5.4, 7.1, 10.4_

  - [ ]\* 20.3 Create frontend component tests
    - Test exam interface interactions and state management
    - Test results page rendering with different subscription tiers
    - Test practice panel functionality
    - _Requirements: Frontend component requirements_

  - [ ]\* 20.4 Create Celery task tests
    - Test question generation with rate limit simulation
    - Test theory evaluation with various AI responses
    - Test retry logic and error handling
    - _Requirements: 6.4, 9.4_

- [ ] 21. Final Integration and Deployment Preparation
  - [~] 21.1 Run comprehensive system tests
    - Test end-to-end workflows with realistic data
    - Validate subscription enforcement across all features
    - Test concurrent user scenarios
    - _Requirements: 13.4, 14.4_

  - [~] 21.2 Create database migration deployment strategy
    - Plan zero-downtime migration for model extensions
    - Create data migration scripts for existing quiz data
    - _Requirements: 14.4_

  - [~] 21.3 Update API documentation
    - Document all new endpoints with request/response examples
    - Create integration guide for frontend developers
    - _Requirements: 14.3_

- [~] 22. Final Checkpoint - Complete System Validation
  - Ensure all tests pass and system performs according to requirements, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability and validation
- The implementation follows established Django + Next.js patterns used throughout the codebase
- Backend extends existing models rather than replacing them to maintain data integrity
- AI evaluation runs asynchronously to provide immediate MCQ feedback while theory questions are processed
- All subscription enforcement occurs server-side for security
- Frontend components are designed for reusability and maintainability
- Property tests validate critical business logic and security boundaries
- Integration tests ensure end-to-end functionality across subscription tiers

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4", "4.5", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3", "6.1"] },
    { "id": 7, "tasks": ["6.2", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 9, "tasks": ["8.1"] },
    { "id": 10, "tasks": ["8.2", "8.3"] },
    { "id": 11, "tasks": ["10.1", "10.2", "10.3", "10.4"] },
    { "id": 12, "tasks": ["11.1", "11.2"] },
    { "id": 13, "tasks": ["12.1", "12.2"] },
    { "id": 14, "tasks": ["12.3", "13.1"] },
    { "id": 15, "tasks": ["13.2", "13.3", "13.4", "13.5"] },
    { "id": 16, "tasks": ["13.6"] },
    { "id": 17, "tasks": ["14.1"] },
    { "id": 18, "tasks": ["14.2", "14.3"] },
    { "id": 19, "tasks": ["14.4", "15.1"] },
    { "id": 20, "tasks": ["15.2"] },
    { "id": 21, "tasks": ["17.1", "17.2"] },
    { "id": 22, "tasks": ["18.1", "18.2", "18.3"] },
    { "id": 23, "tasks": ["19.1", "19.2"] },
    { "id": 24, "tasks": ["20.1", "20.2", "20.3", "20.4"] },
    { "id": 25, "tasks": ["21.1", "21.2", "21.3"] }
  ]
}
```
