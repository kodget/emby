# Requirements Document

## Introduction

This document specifies requirements for enhancing the reader sidebar in the Emby medical student study platform. The reader page displays educational slides to students and includes a sidebar with four tabs: Emby, Textbook, Videos, and Quiz. This enhancement addresses a premium access display bug, adds AI-powered content suggestions for textbooks and videos, implements auto-generated MCQs, removes an unnecessary upload button, and adds pagination for expanded reader mode.

## Glossary

- **Reader_Page**: The page component that displays educational slides to students
- **Sidebar**: The collapsible panel on the reader page containing four tabs (Emby, Textbook, Videos, Quiz)
- **Premium_User**: A user with `is_premium === true` OR `role === 'Class Head'`
- **Free_User**: A user who is NOT a Premium_User
- **Class_Head**: A user with `role === 'Class Head'` and `class_head_verified === true`
- **Emby_Tab**: The first tab in the sidebar showing Emby AI features
- **Textbook_Tab**: The second tab in the sidebar for textbook suggestions
- **Videos_Tab**: The third tab in the sidebar for video suggestions
- **Quiz_Tab**: The fourth tab in the sidebar for quiz generation
- **Premium_Upsell**: A UI component encouraging free users to upgrade to premium
- **AI_Service**: The Google Gemini API service for generating content suggestions
- **MCQ**: Multiple Choice Question with 4 options and one correct answer
- **Expanded_Reader**: The reader mode where slides are displayed in full-screen or expanded view
- **Slide**: An individual page of educational content being displayed
- **Upload_Button**: The button at the top of the reading bar for uploading slides/past questions

## Requirements

### Requirement 1: Fix Premium Access Display Logic

**User Story:** As a Class Head, I want to see premium features directly without upsell prompts, so that I can access the features I'm entitled to without confusion.

#### Acceptance Criteria

1. WHEN a Free_User views THE Emby_Tab, THE Sidebar SHALL display the Premium_Upsell
2. WHEN a Premium_User views THE Emby_Tab, THE Sidebar SHALL display premium features without the Premium_Upsell
3. WHEN a Class_Head views THE Emby_Tab, THE Sidebar SHALL display premium features without the Premium_Upsell
4. THE Premium_Access_Logic SHALL evaluate to true IF the user's `is_premium` property is true OR the user's `role` property equals 'Class Head'
5. THE Premium_Upsell SHALL NOT be displayed to any user where Premium_Access_Logic evaluates to true

### Requirement 2: AI Textbook Suggestions

**User Story:** As a Premium User, I want AI-generated textbook suggestions based on the current slide, so that I can find relevant reading materials to deepen my understanding.

#### Acceptance Criteria

1. WHEN a Premium_User views THE Textbook_Tab, THE AI_Service SHALL generate textbook suggestions based on the current Slide content
2. THE Textbook_Suggestions SHALL include textbook names appropriate for medical student level
3. THE Textbook_Suggestions SHALL include relevant chapter names or section references
4. THE Textbook_Suggestions SHALL include a brief explanation of relevance to the current Slide
5. WHEN a Free_User views THE Textbook_Tab, THE Sidebar SHALL display the Premium_Upsell for this feature
6. WHILE THE AI_Service is generating suggestions, THE Textbook_Tab SHALL display a loading indicator
7. IF THE AI_Service fails to generate suggestions, THEN THE Textbook_Tab SHALL display an error message with retry option
8. THE AI_Service SHALL cache textbook suggestions for each Slide to avoid repeated API calls for the same content

### Requirement 3: AI Video Suggestions

**User Story:** As a Premium User, I want AI-generated video suggestions related to the current slide, so that I can watch supplementary educational videos that reinforce the material.

#### Acceptance Criteria

1. WHEN a Premium_User views THE Videos_Tab, THE AI_Service SHALL generate video suggestions based on the current Slide content
2. THE Video_Suggestions SHALL include video titles
3. THE Video_Suggestions SHALL include video source information (e.g., YouTube channel, platform)
4. THE Video_Suggestions SHALL include a relevance explanation describing how the video relates to the Slide
5. WHEN a Free_User views THE Videos_Tab, THE Sidebar SHALL display the Premium_Upsell for this feature
6. WHILE THE AI_Service is generating suggestions, THE Videos_Tab SHALL display a loading indicator
7. IF THE AI_Service fails to generate suggestions, THEN THE Videos_Tab SHALL display an error message with retry option
8. THE AI_Service SHALL cache video suggestions for each Slide to avoid repeated API calls for the same content

### Requirement 4: Auto-Generate MCQs

**User Story:** As a Premium User, I want automatically generated MCQs from the current slide content, so that I can test my understanding of the material immediately.

#### Acceptance Criteria

1. WHEN a Premium_User views THE Quiz_Tab, THE AI_Service SHALL generate 20 MCQs from the current Slide content
2. THE Generated_MCQ SHALL include a question text that tests understanding of the Slide material
3. THE Generated_MCQ SHALL include exactly 4 answer options labeled A, B, C, and D
4. THE Generated_MCQ SHALL include one correct answer marked clearly
5. THE Generated_MCQ SHALL include an explanation for why the correct answer is correct
6. WHEN a Free_User views THE Quiz_Tab, THE Sidebar SHALL display the Premium_Upsell for this feature
7. WHILE THE AI_Service is generating MCQs, THE Quiz_Tab SHALL display a loading indicator
8. IF THE AI_Service fails to generate MCQs, THEN THE Quiz_Tab SHALL display an error message with retry option
9. THE AI_Service SHALL cache generated MCQs for each Slide to avoid repeated API calls for the same content
10. THE Quiz_Tab SHALL allow users to navigate through the 20 generated MCQs
11. THE Quiz_Tab SHALL track user answers and provide immediate feedback on correctness

### Requirement 5: Remove Upload Button

**User Story:** As a student using the reader interface, I want a cleaner reading experience without unnecessary buttons, so that I can focus on the content without distractions.

#### Acceptance Criteria

1. THE Reader_Page SHALL NOT display the Upload_Button at the top of the reading bar
2. THE Upload_Button removal SHALL NOT affect any other functionality on the Reader_Page

### Requirement 6: Pagination for Expanded Reader

**User Story:** As a student, I want to navigate through slides one page at a time when the reader is expanded, so that I can focus on individual slides without distraction.

#### Acceptance Criteria

1. WHEN THE Expanded_Reader is active, THE Reader_Page SHALL display one Slide per page
2. WHEN THE Expanded_Reader is active, THE Reader_Page SHALL display a Previous navigation button
3. WHEN THE Expanded_Reader is active, THE Reader_Page SHALL display a Next navigation button
4. WHEN a user clicks the Previous button AND the current Slide is not the first Slide, THE Reader_Page SHALL navigate to the previous Slide
5. WHEN a user clicks the Next button AND the current Slide is not the last Slide, THE Reader_Page SHALL navigate to the next Slide
6. WHEN a user presses the left arrow key AND the current Slide is not the first Slide, THE Reader_Page SHALL navigate to the previous Slide
7. WHEN a user presses the right arrow key AND the current Slide is not the last Slide, THE Reader_Page SHALL navigate to the next Slide
8. WHEN the current Slide is the first Slide, THE Previous button SHALL be disabled
9. WHEN the current Slide is the last Slide, THE Next button SHALL be disabled
10. THE Reader_Page SHALL display the current Slide number and total Slide count (e.g., "3 / 25")
11. THE Pagination feature SHALL be available to all users regardless of premium status

### Requirement 7: AI Service Integration

**User Story:** As a developer, I want robust AI service integration with proper error handling, so that the application remains stable even when the AI service experiences issues.

#### Acceptance Criteria

1. THE AI_Service SHALL use the Google Gemini API for all AI-powered features
2. THE AI_Service SHALL accept an API key from environment configuration
3. WHEN THE AI_Service receives a request, THE AI_Service SHALL include the current Slide content as context
4. WHEN THE AI_Service receives a request, THE AI_Service SHALL include the Slide title and subject information as context
5. IF THE AI_Service API call fails due to network error, THEN THE AI_Service SHALL return an error response with a user-friendly message
6. IF THE AI_Service API call fails due to rate limiting, THEN THE AI_Service SHALL return an error response indicating rate limit exceeded
7. IF THE AI_Service API call fails due to invalid API key, THEN THE AI_Service SHALL return an error response indicating authentication failure
8. THE AI_Service SHALL implement a timeout of 30 seconds for API calls
9. IF THE AI_Service API call exceeds the timeout, THEN THE AI_Service SHALL return an error response indicating timeout
10. THE AI_Service SHALL cache successful responses using the Slide ID as the cache key
11. WHEN THE AI_Service receives a request for a Slide with cached responses, THE AI_Service SHALL return the cached response without making an API call

### Requirement 8: Premium Upsell Display

**User Story:** As a Free User, I want to understand the benefits of premium features, so that I can make an informed decision about upgrading.

#### Acceptance Criteria

1. THE Premium_Upsell SHALL display a clear heading describing the premium feature
2. THE Premium_Upsell SHALL list specific benefits of the premium feature
3. THE Premium_Upsell SHALL include a call-to-action button to upgrade to premium
4. WHEN a Free_User clicks the upgrade button, THE Reader_Page SHALL navigate to the premium subscription page
5. THE Premium_Upsell SHALL use consistent styling across all tabs (Textbook_Tab, Videos_Tab, Quiz_Tab)
6. THE Premium_Upsell SHALL NOT be displayed on the Emby_Tab to Premium_Users or Class_Heads

### Requirement 9: Loading States

**User Story:** As a user, I want to see clear loading indicators when AI content is being generated, so that I know the system is working and not frozen.

#### Acceptance Criteria

1. WHILE THE AI_Service is processing a request, THE active tab SHALL display a loading spinner
2. WHILE THE AI_Service is processing a request, THE active tab SHALL display loading text indicating content is being generated
3. THE loading indicator SHALL be visually centered in the tab content area
4. THE loading indicator SHALL prevent user interaction with the tab content until loading completes
5. WHEN THE AI_Service completes the request, THE loading indicator SHALL be removed and replaced with the generated content

### Requirement 10: Error Handling and Recovery

**User Story:** As a user, I want clear error messages and recovery options when AI generation fails, so that I can understand what went wrong and try again.

#### Acceptance Criteria

1. WHEN THE AI_Service returns an error, THE active tab SHALL display an error message describing the issue
2. THE error message SHALL be user-friendly and avoid technical jargon
3. THE error message SHALL include a "Try Again" button
4. WHEN a user clicks the "Try Again" button, THE AI_Service SHALL retry the failed request
5. IF THE AI_Service fails three consecutive times for the same request, THEN THE active tab SHALL display a message suggesting the user try again later
6. THE error display SHALL use consistent styling across all AI-powered tabs
