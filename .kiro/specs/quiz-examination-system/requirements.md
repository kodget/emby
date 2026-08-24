# Requirements Document: Quiz / Examination System

## Introduction

The Quiz/Examination System is a comprehensive assessment platform for the Emby medical school study application. The system provides two distinct assessment modes: quick practice sessions integrated within the slide reader, and formal timed or untimed examinations launched from a dedicated quiz interface. The system enforces subscription-based access controls and delivers AI-powered evaluation of theory answers to provide meaningful feedback for student learning.

## Glossary

- **System**: The Quiz/Examination System component within the Emby platform
- **Student**: A registered user who takes quizzes and examinations
- **Class_Head**: A verified instructor who has additional privileges and quota limits
- **Admin**: System administrator with full access to all features
- **Attempt**: A single quiz or examination session with a defined start and completion time
- **MCQ**: Multiple Choice Question with four options (A, B, C, D)
- **Theory_Question**: Open-ended question requiring written responses evaluated by AI
- **Free_Tier**: Basic subscription level with limited question quotas
- **Premium_Tier**: Advanced subscription level with expanded quotas and analysis features
- **AI_Evaluator**: Automated system for grading theory questions using Gemini API
- **Practice_Mode**: Informal question review within the slide reader interface
- **Examination_Mode**: Formal assessment sessions with scoring and time management

## Requirements

### Requirement 1: Student Quiz Configuration and Creation

**User Story:** As a Student, I want to configure and start a quiz session, so that I can assess my knowledge on specific medical topics with appropriate difficulty and timing.

#### Acceptance Criteria

1. WHEN a Student accesses the quiz configuration page, THE System SHALL display cascading selectors for Subject, Block, and Topic
2. WHEN a Student selects exam parameters, THE System SHALL enforce subscription tier limits for question quantities
3. WHEN a Free_Tier Student configures an exam, THE System SHALL limit MCQ questions to 5 and Theory_Questions to 1
4. WHEN a Premium_Tier Student or verified Class_Head configures an exam, THE System SHALL allow up to 100 MCQ questions and 10 Theory_Questions
5. WHEN a Student has an exam in progress, THE System SHALL prevent creation of additional concurrent attempts
6. WHEN exam configuration is submitted with valid parameters, THE System SHALL create a new Attempt with randomized question order
7. WHEN insufficient questions exist for the selected criteria, THE System SHALL return a descriptive error message with guidance

### Requirement 2: MCQ Question Presentation and Response Handling

**User Story:** As a Student, I want to answer multiple choice questions with clear options and navigation, so that I can efficiently demonstrate my knowledge.

#### Acceptance Criteria

1. WHEN an MCQ question is displayed, THE System SHALL present the question text with four randomized options labeled A, B, C, D
2. WHEN a Student selects an answer option, THE System SHALL autosave the response within 500 milliseconds
3. WHEN a Student navigates between questions, THE System SHALL preserve all previously selected answers
4. WHEN displaying MCQ questions during an active Attempt, THE System SHALL NOT reveal correct answers or explanations
5. WHEN a Student flags a question, THE System SHALL persist the flag status and update the question navigator
6. THE System SHALL provide a visual question navigator showing answered, unanswered, and flagged question status

### Requirement 3: Theory Question Response and Validation

**User Story:** As a Student, I want to provide written answers to theory questions with appropriate guidance, so that I can demonstrate detailed understanding of medical concepts.

#### Acceptance Criteria

1. WHEN a Theory_Question is displayed, THE System SHALL provide a text input area with live character and word counting
2. WHEN a Student types a theory answer, THE System SHALL autosave the response content with debounced timing
3. WHEN a theory response is under 50 words, THE System SHALL display a helpful hint encouraging more detailed answers
4. WHEN a Student submits a theory answer, THE System SHALL store the complete text response for AI evaluation
5. THE System SHALL accept theory responses of any length up to reasonable system limits

### Requirement 4: Timer Management and Auto-Submission

**User Story:** As a Student, I want clear time awareness during timed exams with automatic submission when time expires, so that I can manage my time effectively and ensure my answers are captured.

#### Acceptance Criteria

1. WHEN a timed Attempt begins, THE System SHALL display a countdown timer showing remaining minutes and seconds
2. WHEN the timer reaches 5 minutes remaining, THE System SHALL change the display to indicate urgency
3. WHEN the timer expires, THE System SHALL automatically submit the Attempt with all saved responses
4. WHEN auto-submission occurs, THE System SHALL allow a 30-second buffer for network delays before rejecting late submissions
5. WHEN a Student manually submits before time expires, THE System SHALL immediately process the submission
6. WHEN an untimed Attempt is created, THE System SHALL NOT display timer controls or enforce time limits

### Requirement 5: Attempt Submission and MCQ Scoring

**User Story:** As a Student, I want immediate scoring of my multiple choice answers upon submission, so that I can quickly understand my performance level.

#### Acceptance Criteria

1. WHEN a Student submits an Attempt, THE System SHALL immediately score all MCQ responses synchronously
2. WHEN MCQ scoring completes, THE System SHALL calculate the percentage score and update the Attempt record
3. WHEN an Attempt contains Theory_Questions, THE System SHALL mark theory evaluation as pending and initiate AI grading
4. WHEN submission processing completes, THE System SHALL redirect the Student to the results page
5. THE System SHALL prevent submission of Attempts that have already been submitted or auto-submitted

### Requirement 6: AI-Powered Theory Question Evaluation

**User Story:** As a Student, I want my written answers automatically evaluated with detailed feedback, so that I can understand my strengths and areas for improvement.

#### Acceptance Criteria

1. WHEN an Attempt with Theory_Questions is submitted, THE System SHALL queue AI evaluation tasks for each theory response
2. WHEN the AI_Evaluator processes a theory answer, THE System SHALL compare it against the ideal answer and marking rubric
3. WHEN AI evaluation succeeds, THE System SHALL assign a numerical score within the question's maximum marks and provide structured feedback
4. WHEN AI evaluation fails due to service limits, THE System SHALL retry with exponential backoff scheduling
5. WHEN AI evaluation encounters permanent errors, THE System SHALL mark the response as failed without assigning a score
6. WHEN all theory evaluations complete, THE System SHALL recalculate the overall Attempt percentage

### Requirement 7: Results Display and Tier-Based Access

**User Story:** As a Student, I want to see my quiz results with appropriate detail based on my subscription level, so that I can understand my performance and identify learning opportunities.

#### Acceptance Criteria

1. WHEN a Free_Tier Student views results, THE System SHALL display overall percentage, MCQ score, and pass/fail status
2. WHEN theory evaluation is pending, THE System SHALL show a "grading in progress" indicator with periodic polling
3. WHEN a Premium_Tier Student or Class_Head views results, THE System SHALL include topic-level performance breakdown and missed question analysis
4. WHEN displaying premium results, THE System SHALL show detailed AI feedback for theory questions with scoring rationale
5. WHEN results are displayed, THE System SHALL provide options to retake the quiz or return to study materials

### Requirement 8: Slide Reader Practice Integration

**User Story:** As a Student, I want to practice questions related to the slide I'm currently studying, so that I can immediately test my understanding of the material.

#### Acceptance Criteria

1. WHEN a Student opens the practice panel from a slide, THE System SHALL display questions specifically related to that slide content
2. WHEN practicing MCQ questions, THE System SHALL immediately reveal correct answers and explanations after selection
3. WHEN practicing theory questions, THE System SHALL allow viewing of model answers without formal grading
4. WHEN practice questions are displayed, THE System SHALL NOT create formal Attempt records or affect scoring history
5. WHEN completing slide practice, THE System SHALL offer to start a formal exam on the related topic

### Requirement 9: Question Generation and Content Management

**User Story:** As a Class_Head or Admin, I want questions automatically generated from slide content, so that students have relevant assessment materials without manual question creation.

#### Acceptance Criteria

1. WHEN new slide content is processed, THE System SHALL automatically queue question generation tasks
2. WHEN generating questions for a slide, THE System SHALL create both MCQ and Theory_Questions based on the content
3. WHEN questions already exist for a slide, THE System SHALL skip generation to prevent duplicates
4. WHEN AI question generation encounters rate limits, THE System SHALL implement partial generation with retry scheduling
5. THE System SHALL ensure all generated questions include proper difficulty ratings and topic associations

### Requirement 10: Subscription Enforcement and Premium Features

**User Story:** As the System, I want to enforce subscription limits and premium feature access, so that the platform maintains appropriate monetization while providing value to all users.

#### Acceptance Criteria

1. WHEN checking user permissions, THE System SHALL verify subscription status from the user profile, never from frontend data
2. WHEN a Free_Tier Student attempts to exceed quota limits, THE System SHALL reject the request with upgrade messaging
3. WHEN a Class_Head has verified status, THE System SHALL grant Premium_Tier access regardless of subscription
4. WHEN premium features are accessed, THE System SHALL validate premium status before displaying detailed analytics
5. THE System SHALL display appropriate upgrade prompts for Free_Tier users viewing limited results

### Requirement 11: Missed Questions Analysis and Learning Tools

**User Story:** As a Premium_Tier Student, I want detailed analysis of incorrect answers and learning recommendations, so that I can focus my study efforts on areas needing improvement.

#### Acceptance Criteria

1. WHEN a Premium_Tier Student views missed questions, THE System SHALL display their answer alongside the correct answer with explanations
2. WHEN theory questions are answered incorrectly, THE System SHALL show AI feedback highlighting missing points and incorrect statements
3. WHEN premium analysis is requested, THE System SHALL generate topic-specific performance insights and study recommendations
4. WHEN missed questions are reviewed, THE System SHALL offer to create flashcards for reinforcement learning
5. THE System SHALL track performance trends across multiple attempts for longitudinal learning insights

### Requirement 12: Security and Data Protection

**User Story:** As a Student and System Administrator, I want secure handling of quiz data and prevention of cheating, so that assessment integrity is maintained while protecting personal information.

#### Acceptance Criteria

1. WHEN displaying active quiz questions, THE System SHALL NOT expose correct answers or explanations in API responses
2. WHEN validating timer submissions, THE System SHALL use server-side time as authoritative to prevent client manipulation
3. WHEN processing quiz attempts, THE System SHALL ensure students can only access their own attempt data
4. WHEN storing theory responses, THE System SHALL treat all text content as data and never execute it as code
5. THE System SHALL implement rate limiting to prevent abuse of question generation and assessment features

### Requirement 13: Performance and Scalability Requirements

**User Story:** As a Student and System Administrator, I want responsive quiz performance and reliable operation under load, so that assessments can be completed efficiently without technical interruption.

#### Acceptance Criteria

1. WHEN creating a quiz attempt, THE System SHALL respond within 2 seconds for question sets up to 100 questions
2. WHEN autosaving responses, THE System SHALL persist changes within 500 milliseconds of user input
3. WHEN processing MCQ scoring, THE System SHALL complete evaluation within 5 seconds regardless of question count
4. WHEN multiple students access the system concurrently, THE System SHALL maintain response times within acceptable limits
5. WHEN AI evaluation is queued, THE System SHALL process theory questions within 2 minutes under normal load conditions

### Requirement 14: Integration with Existing Platform Components

**User Story:** As a Student and System Administrator, I want seamless integration with existing slide processing and user management systems, so that the quiz functionality feels like a natural part of the platform.

#### Acceptance Criteria

1. WHEN slide content is updated or processed, THE System SHALL automatically trigger relevant question generation workflows
2. WHEN user subscription status changes, THE System SHALL immediately reflect new access permissions for quiz features
3. WHEN students navigate between quiz and study modes, THE System SHALL maintain consistent user experience and session state
4. WHEN quiz data is created or modified, THE System SHALL respect existing database transaction patterns and consistency requirements
5. THE System SHALL integrate with existing authentication, authorization, and user profile management systems

### Requirement 15: Error Handling and Recovery

**User Story:** As a Student and System Administrator, I want graceful handling of errors and system issues, so that temporary problems don't result in lost work or corrupted assessments.

#### Acceptance Criteria

1. WHEN network connectivity is temporarily lost during an exam, THE System SHALL preserve autosaved responses and allow continuation when connectivity returns
2. WHEN AI evaluation services are temporarily unavailable, THE System SHALL queue retries and inform students of delayed grading
3. WHEN system errors occur during quiz taking, THE System SHALL preserve student progress and provide clear recovery instructions
4. WHEN database constraints are violated, THE System SHALL return helpful error messages without exposing internal system details
5. THE System SHALL log all significant errors for administrative review while maintaining student privacy

### Requirement 16: Audit Trail and Analytics

**User Story:** As an Admin and Class_Head, I want comprehensive tracking of student assessment activity, so that I can monitor platform usage and identify learning patterns.

#### Acceptance Criteria

1. WHEN students complete assessments, THE System SHALL record attempt metadata including timing, configuration, and performance metrics
2. WHEN AI evaluation occurs, THE System SHALL maintain audit trails of evaluation decisions and feedback generation
3. WHEN subscription limits are enforced, THE System SHALL log access patterns for platform optimization and business intelligence
4. WHEN errors occur during assessments, THE System SHALL capture sufficient diagnostic information for troubleshooting
5. THE System SHALL provide aggregated analytics while protecting individual student privacy and assessment integrity