import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests (exclude public auth endpoints)
api.interceptors.request.use((config) => {
  // List of endpoints that should NOT have Authorization header
  const publicEndpoints = [
    "/auth/signup/",
    "/auth/login/",
    "/auth/google-login/",
    "/auth/verify-email/",
    "/auth/forgot-password/",
    "/auth/reset-password/",
    "/auth/class/validate-code/",
    "/auth/payment/verify/",
  ];

  // Check if the current request is to a public endpoint
  const isPublicEndpoint = publicEndpoints.some((endpoint) =>
    config.url?.includes(endpoint),
  );

  // Only add token if NOT a public endpoint
  if (!isPublicEndpoint && typeof window !== "undefined") {
    const token = sessionStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Add response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = sessionStorage.getItem("refreshToken");

        if (!refreshToken) {
          // No refresh token, redirect to login
          if (typeof window !== "undefined") {
            sessionStorage.removeItem("token");
            sessionStorage.removeItem("refreshToken");
            sessionStorage.removeItem("user");
            window.location.href = "/signin";
          }
          return Promise.reject(error);
        }

        // Try to refresh the token
        const response = await axios.post(
          `${API_BASE_URL}/auth/token/refresh/`,
          {
            refresh: refreshToken,
          },
        );

        const newAccessToken = response.data.access;

        // Update token in sessionStorage
        sessionStorage.setItem("token", newAccessToken);

        // Update the failed request with new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

        // Retry the original request
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("token");
          sessionStorage.removeItem("refreshToken");
          sessionStorage.removeItem("user");
          window.location.href = "/signin";
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  },
);

// ==================== TYPES ====================

// Auth Types - CORRECTED to match backend serializer
export type UserProfile = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  photo_url: string | null;
  role: "student" | "brainstormer" | "class_head" | "material_uploader";
  school: number | null;
  school_name: string;
  set_name: string;
  class_group: number | null;
  class_code: string | null;
  subscription_tier: "free" | "premium" | "class_head";
  subscription_expires_at: string | null;
  is_premium: boolean;
  onboarding_completed: boolean;
  email_verified: boolean;
  class_head_verified: boolean;
  class_head_verification_requested: boolean;
  class_head_rejection_reason: string;
  can_access_app: boolean;
  streak: number;
  created_at: string;
};

export type AuthTokens = {
  access: string;
  refresh: string;
};

export type OnboardingQuestion = {
  id: number;
  question_text: string;
  question_type: "text" | "choice" | "select";
  options: string[];
  order: number;
};

export type ClassGroup = {
  id: number;
  code: string;
  school: number;
  school_name: string;
  set_name: string;
  class_heads: Array<{
    id: number;
    name: string;
    email: string;
  }>;
  member_count: number;
  created_at: string;
};

export type Announcement = {
  id: number;
  class_group: number;
  class_code: string;
  created_by: number;
  created_by_name: string;
  is_class_head: boolean;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
};

export type ExamCountdown = {
  id: number;
  class_group: number;
  class_code: string;
  created_by: number;
  created_by_name: string;
  title: string;
  exam_date: string;
  exam_time: string | null;
  description: string;
  subject: string;
  days_remaining: number;
  created_at: string;
  updated_at: string;
};

export type PaymentTransaction = {
  id: number;
  reference: string;
  amount: string;
  currency: string;
  status: "pending" | "success" | "failed";
  subscription_months: number;
  created_at: string;
  verified_at: string | null;
};

export type Subject = {
  id: string;
  name: string;
  description: string;
  order: number;
  created_at: string;
};

export type Topic = {
  id: string;
  name: string;
  description: string;
  order: number;
  sections: Section[];
  created_at: string;
};

export type Section = {
  id: string;
  name: string;
  description: string;
  order: number;
  created_at: string;
};

export type Block = {
  id: string;
  subject: string;
  name: string;
  description: string;
  order: number;
  topics: Topic[];
  sections: Section[];
  created_at: string;
};

export type Slide = {
  id: string;
  title: string;
  subject: string | null;
  subject_name: string | null;
  block: string | null;
  block_name: string | null;
  topic: string | null;
  topic_name: string | null;
  section: string | null;
  section_name: string | null;
  file_url: string;
  file_type: string;
  page_count: number;
  uploaded_by: number;
  uploaded_by_name: string;
  created_at: string;
  updated_at: string;
};

// New Slide Deck Types (PDF/PPTX/DOCX rendering)
export type SlidePage = {
  id: number;
  slide_number: number;
  image_url: string;
  width: number;
  height: number;
  extracted_text: string;
  created_at: string;
};

export type SlideDeck = {
  id: string;
  title: string;
  file_type: "pdf" | "pptx" | "ppt" | "docx";
  file_size: number;
  processing_status: "pending" | "processing" | "completed" | "failed";
  processing_error?: string;
  page_count: number;
  uploaded_by: number;
  uploaded_by_name: string;
  pages?: SlidePage[];
  created_at: string;
  updated_at: string;
};

export type Material = {
  id: string;
  title: string;
  description: string;
  material_type:
    | "video"
    | "image"
    | "pdf"
    | "pptx"
    | "docx"
    | "past_question"
    | "other";
  subject: string;
  subject_name: string;
  block: string;
  block_name: string;
  topic: string | null;
  topic_name: string | null;
  section: string | null;
  section_name: string | null;
  file_url: string;
  file_size: number;
  uploaded_by: number;
  uploaded_by_name: string;
  created_at: string;
  updated_at: string;
};

export type UserProgress = {
  id: number;
  slide: string;
  slide_title: string;
  current_page: number;
  total_pages: number;
  completed: boolean;
  last_accessed: string;
  time_spent_minutes: number;
  progress_percentage: number;
};

export type ScheduleItem = {
  id: number;
  activity_type: "read" | "quiz" | "flashcards" | "steeplechase";
  title: string;
  slide: string | null;
  slide_title: string | null;
  topic: string | null;
  topic_name: string | null;
  block: string | null;
  block_name: string | null;
  scheduled_date: string;
  scheduled_time: string | null;
  estimated_minutes: number;
  completed: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UserStats = {
  id: number;
  username: string;
  name: string;
  points: number;
  rank: number;
  current_streak: number;
  longest_streak: number;
  school: string;
  set_name: string;
  public_profile: boolean;
  public_rank: boolean;
  total_study_minutes: number;
  slides_completed: number;
  quizzes_taken: number;
};

export type CommunityPost = {
  id: number;
  user: number;
  user_name: string;
  user_photo: string | null;
  post_type: "achievement" | "question" | "discussion" | "resource";
  content: string;
  slide: string | null;
  topic: string | null;
  likes_count: number;
  comments_count: number;
  comments: PostComment[];
  created_at: string;
  updated_at: string;
};

export type PostComment = {
  id: number;
  user: number;
  user_name: string;
  content: string;
  created_at: string;
};

export type UpcomingTest = {
  id: number;
  title: string;
  description: string;
  subject: string;
  subject_name: string;
  topics: string[];
  topics_list: Topic[];
  test_date: string;
  test_time: string | null;
  duration_minutes: number;
  created_at: string;
};

export type QuizQuestion = {
  id: string;
  question_type: "mcq" | "theory";
  difficulty: "easy" | "medium" | "hard";
  subject: string;
  subject_name: string;
  block: string | null;
  block_name: string | null;
  topic: string | null;
  topic_name: string | null;
  question_text: string;
  explanation: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: string;
  model_answer: string;
  source_type: "past_question" | "ai_generated" | "manual";
  created_at: string;
};

export type QuizAnswer = {
  id: number;
  quiz: string;
  question: QuizQuestion;
  selected_option: string;
  text_answer: string;
  is_correct: boolean;
  ai_score: number | null;
  ai_feedback: string;
  time_taken_seconds: number;
  created_at: string;
};

export type Quiz = {
  id: string;
  user: number;
  quiz_type: "mcq" | "theory";
  subject: string | null;
  subject_name: string | null;
  block: string | null;
  block_name: string | null;
  topic: string | null;
  topic_name: string | null;
  questions_list: QuizQuestion[];
  total_questions: number;
  score: number;
  completed: boolean;
  completed_at: string | null;
  created_at: string;
  answers: QuizAnswer[];
};

// ==================== AUTHENTICATION API ====================

export const authApi = {
  // Signup with email/password
  signup: async (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }): Promise<{ message: string; user: UserProfile; tokens: AuthTokens }> => {
    const response = await api.post("/auth/signup/", data);
    return response.data;
  },

  // Login with email/password
  login: async (data: {
    email: string;
    password: string;
  }): Promise<{ message: string; user: UserProfile; tokens: AuthTokens }> => {
    const response = await api.post("/auth/login/", data);
    return response.data;
  },

  // Google OAuth login
  googleLogin: async (
    token: string,
  ): Promise<{
    message: string;
    user: UserProfile;
    tokens: AuthTokens;
    is_new_user: boolean;
  }> => {
    const response = await api.post("/auth/google-login/", { token });
    return response.data;
  },

  // Verify email
  verifyEmail: async (token: string): Promise<{ message: string }> => {
    const response = await api.post("/auth/verify-email/", { token });
    return response.data;
  },

  // Resend verification email
  resendVerification: async (): Promise<{ message: string }> => {
    const response = await api.post("/auth/resend-verification/");
    return response.data;
  },

  // Get current user profile
  getProfile: async (): Promise<UserProfile> => {
    const response = await api.get("/auth/profile/");
    return response.data;
  },

  // Update profile
  updateProfile: async (data: {
    first_name?: string;
    last_name?: string;
    photo_url?: string;
  }): Promise<{ message: string; user: UserProfile }> => {
    const response = await api.put("/auth/profile/update/", data);
    return response.data;
  },

  // Change password
  changePassword: async (data: {
    old_password: string;
    new_password: string;
  }): Promise<{ message: string }> => {
    const response = await api.post("/auth/change-password/", data);
    return response.data;
  },

  // Delete account
  deleteAccount: async (): Promise<{ message: string }> => {
    const response = await api.delete("/auth/profile/");
    return response.data;
  },

  // Forgot password
  forgotPassword: async (email: string): Promise<{ message: string }> => {
    const response = await api.post("/auth/forgot-password/", { email });
    return response.data;
  },

  // Reset password
  resetPassword: async (
    token: string,
    new_password: string,
  ): Promise<{ message: string }> => {
    const response = await api.post("/auth/reset-password/", {
      token,
      new_password,
    });
    return response.data;
  },
};

// ==================== ONBOARDING API ====================

export const onboardingApi = {
  // Get onboarding questions
  getQuestions: async (): Promise<OnboardingQuestion[]> => {
    const response = await api.get("/auth/onboarding/questions/");
    return response.data;
  },

  // Submit onboarding
  submitOnboarding: async (data: {
    role: "student" | "brainstormer" | "class_head" | "material_uploader";
    school_name: string;
    set_name: string;
    class_code?: string;
    subscription_tier: "free" | "premium";
    responses?: Array<{ question_id: number; answer: string }>;
  }): Promise<{
    message: string;
    user: UserProfile;
    class_code: string | null;
    verification_message?: string;
  }> => {
    const response = await api.post("/auth/onboarding/submit/", data);
    return response.data;
  },

  // Update onboarding responses
  updateResponses: async (
    responses: Array<{ question_id: number; answer: string }>,
  ): Promise<{ message: string }> => {
    const response = await api.put("/auth/onboarding/responses/update/", {
      responses,
    });
    return response.data;
  },

  // Validate class code without submitting
  validateClassCode: async (
    class_code: string,
  ): Promise<{ valid: boolean }> => {
    const response = await api.post("/auth/class/validate-code/", {
      class_code,
    });
    return response.data;
  },
};

// ==================== CLASS API ====================

export const classApi = {
  // Join class with code
  joinClass: async (
    class_code: string,
  ): Promise<{ message: string; class: ClassGroup }> => {
    const response = await api.post("/auth/class/join/", { class_code });
    return response.data;
  },

  // Get my class
  getMyClass: async (): Promise<ClassGroup> => {
    const response = await api.get("/auth/class/my-class/");
    return response.data;
  },

  // Get class members
  getClassMembers: async (): Promise<any[]> => {
    const response = await api.get("/auth/class/members/");
    return response.data;
  },

  // Get announcements
  getAnnouncements: async (): Promise<Announcement[]> => {
    const response = await api.get("/auth/announcements/");
    return response.data;
  },

  // Create announcement (class head only)
  createAnnouncement: async (data: {
    title: string;
    content: string;
  }): Promise<Announcement> => {
    const response = await api.post("/auth/announcements/", data);
    return response.data;
  },

  // Update announcement
  updateAnnouncement: async (
    id: number,
    data: { title?: string; content?: string },
  ): Promise<Announcement> => {
    const response = await api.put(`/auth/announcements/${id}/`, data);
    return response.data;
  },

  // Delete announcement
  deleteAnnouncement: async (id: number): Promise<void> => {
    await api.delete(`/auth/announcements/${id}/`);
  },

  // Get exam countdowns
  getExamCountdowns: async (): Promise<ExamCountdown[]> => {
    const response = await api.get("/auth/exam-countdowns/");
    return response.data;
  },

  // Create exam countdown (class head only)
  createExamCountdown: async (data: {
    title: string;
    exam_date: string;
    exam_time?: string;
    description?: string;
    subject?: string;
  }): Promise<ExamCountdown> => {
    const response = await api.post("/auth/exam-countdowns/", data);
    return response.data;
  },

  // Update exam countdown
  updateExamCountdown: async (
    id: number,
    data: Partial<ExamCountdown>,
  ): Promise<ExamCountdown> => {
    const response = await api.put(`/auth/exam-countdowns/${id}/`, data);
    return response.data;
  },

  // Delete exam countdown
  deleteExamCountdown: async (id: number): Promise<void> => {
    await api.delete(`/auth/exam-countdowns/${id}/`);
  },
};

// ==================== PAYMENT API ====================

export const paymentApi = {
  // Initiate payment
  initiatePayment: async (
    months: number,
  ): Promise<{ authorization_url: string; reference: string }> => {
    const response = await api.post("/auth/payment/initiate/", { months });
    return response.data;
  },

  // Verify payment
  verifyPayment: async (
    reference: string,
  ): Promise<{ message: string; user: UserProfile }> => {
    const response = await api.post("/auth/payment/verify/", { reference });
    return response.data;
  },
};

// ==================== CURRICULUM API ====================

export const curriculumApi = {
  // Subjects
  getSubjects: async (): Promise<Subject[]> => {
    const response = await api.get("/api/subjects/");
    return response.data;
  },

  // Blocks
  getBlocks: async (subjectId?: string): Promise<Block[]> => {
    const params = subjectId ? { subject: subjectId } : {};
    const response = await api.get("/api/blocks/", { params });
    return response.data;
  },

  getBlock: async (blockId: string): Promise<Block> => {
    const response = await api.get(`/api/blocks/${blockId}/`);
    return response.data;
  },

  // Topics
  getTopics: async (blockId?: string): Promise<Topic[]> => {
    const params = blockId ? { block: blockId } : {};
    const response = await api.get("/api/topics/", { params });
    return response.data;
  },

  getTopic: async (topicId: string): Promise<Topic> => {
    const response = await api.get(`/api/topics/${topicId}/`);
    return response.data;
  },

  // Sections
  getSections: async (filters?: {
    topic?: string;
    block?: string;
  }): Promise<Section[]> => {
    const response = await api.get("/api/sections/", { params: filters });
    return response.data;
  },

  getSection: async (sectionId: string): Promise<Section> => {
    const response = await api.get(`/api/sections/${sectionId}/`);
    return response.data;
  },

  // Slides
  getSlides: async (filters?: {
    subject?: string;
    block?: string;
    topic?: string;
    section?: string;
  }): Promise<Slide[]> => {
    const response = await api.get("/api/slides/", { params: filters });
    return response.data;
  },

  getSlide: async (slideId: string): Promise<Slide> => {
    const response = await api.get(`/api/slides/${slideId}/`);
    return response.data;
  },

  createSlide: async (data: {
    title: string;
    subject?: string;
    block?: string;
    topic?: string;
    section?: string;
    file_url: string;
    file_type: string;
    page_count: number;
  }): Promise<Slide> => {
    const response = await api.post("/api/slides/", data);
    return response.data;
  },

  updateSlide: async (
    slideId: string,
    data: Partial<Slide>,
  ): Promise<Slide> => {
    const response = await api.patch(`/api/slides/${slideId}/`, data);
    return response.data;
  },

  deleteSlide: async (slideId: string): Promise<void> => {
    await api.delete(`/api/slides/${slideId}/`);
  },

  getSlideContent: async (
    slideId: string,
  ): Promise<{
    slide_id: string;
    title: string;
    total_pages: number;
    pages: Array<{
      page_number: number;
      image_url: string;
      width: number;
      height: number;
      text_blocks: any[];
    }>;
  }> => {
    const response = await api.get(`/api/slides/${slideId}/content/`);
    return response.data;
  },

  getSuggestedVideos: async (
    slideId: string,
  ): Promise<{
    videos: Array<{
      title: string;
      url: string;
      reason: string;
    }>;
  }> => {
    const response = await api.get(`/api/slides/${slideId}/suggest-videos/`);
    return response.data;
  },

  // Materials
  getMaterials: async (filters?: {
    subject?: string;
    block?: string;
    topic?: string;
    section?: string;
    type?: string;
  }): Promise<Material[]> => {
    const response = await api.get("/api/materials/", { params: filters });
    return response.data;
  },

  getMaterial: async (materialId: string): Promise<Material> => {
    const response = await api.get(`/api/materials/${materialId}/`);
    return response.data;
  },

  createMaterial: async (data: {
    title: string;
    description?: string;
    material_type: string;
    subject: string;
    block: string;
    topic?: string;
    section?: string;
    file_url: string;
    file_size?: number;
  }): Promise<Material> => {
    const response = await api.post("/api/materials/", data);
    return response.data;
  },

  updateMaterial: async (
    materialId: string,
    data: Partial<Material>,
  ): Promise<Material> => {
    const response = await api.patch(`/api/materials/${materialId}/`, data);
    return response.data;
  },

  deleteMaterial: async (materialId: string): Promise<void> => {
    await api.delete(`/api/materials/${materialId}/`);
  },
};

// ==================== SLIDE DECK API (PDF/PPTX/DOCX) ====================

export const deckApi = {
  /**
   * Upload a new document (PDF, PPTX, PPT, DOCX)
   * Returns SlideDeck with processing status
   */
  uploadDeck: async (file: File, title: string): Promise<SlideDeck> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);

    const response = await api.post("/api/decks/", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  /**
   * List all slide decks for the current user
   */
  listDecks: async (): Promise<SlideDeck[]> => {
    const response = await api.get("/api/decks/");
    return response.data;
  },

  /**
   * Get a specific slide deck with all pages
   */
  getDeck: async (deckId: string): Promise<SlideDeck> => {
    const response = await api.get(`/api/decks/${deckId}/`);
    return response.data;
  },

  /**
   * Get all pages of a slide deck
   */
  getPages: async (deckId: string): Promise<SlidePage[]> => {
    const response = await api.get(`/api/decks/${deckId}/pages/`);
    return response.data;
  },

  /**
   * Get a specific page from a slide deck
   */
  getPage: async (deckId: string, pageNumber: number): Promise<SlidePage> => {
    const response = await api.get(`/api/decks/${deckId}/page/`, {
      params: { page: pageNumber },
    });
    return response.data;
  },

  /**
   * Delete a slide deck and all its pages
   */
  deleteDeck: async (deckId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/api/decks/${deckId}/delete_deck/`);
    return response.data;
  },

  /**
   * Poll deck status (for checking if processing is complete)
   */
  checkStatus: async (deckId: string): Promise<SlideDeck> => {
    const response = await api.get(`/api/decks/${deckId}/`);
    return response.data;
  },
};

// ==================== PROGRESS API ====================

export const progressApi = {
  getProgress: async (): Promise<UserProgress[]> => {
    const response = await api.get("/api/progress/");
    return response.data;
  },

  getRecentProgress: async (): Promise<UserProgress[]> => {
    const response = await api.get("/api/progress/recent/");
    return response.data;
  },

  updateProgress: async (data: {
    slide_id: string;
    current_page: number;
    total_pages: number;
    time_spent_minutes?: number;
  }): Promise<UserProgress> => {
    const response = await api.post("/api/progress/update_progress/", data);
    return response.data;
  },

  getWeeklyStudyData: async (): Promise<{
    week_data: Array<{
      day: string;
      date: string;
      minutes: number;
      sessions: number;
    }>;
    total_minutes: number;
    total_hours: number;
    remaining_minutes: number;
  }> => {
    const response = await api.get("/api/study-time/weekly/");
    return response.data;
  },

  logStudyTime: async (data: {
    minutes: number;
    date?: string;
  }): Promise<{
    message: string;
    total_today: number;
    total_overall: number;
  }> => {
    const response = await api.post("/api/study-time/log/", data);
    return response.data;
  },
};

// ==================== SCHEDULE API ====================

export const scheduleApi = {
  getSchedule: async (): Promise<ScheduleItem[]> => {
    const response = await api.get("/api/schedule/");
    return response.data;
  },

  getTodaySchedule: async (): Promise<ScheduleItem[]> => {
    const response = await api.get("/api/schedule/today/");
    return response.data;
  },

  getUpcomingSchedule: async (): Promise<ScheduleItem[]> => {
    const response = await api.get("/api/schedule/upcoming/");
    return response.data;
  },

  createScheduleItem: async (data: {
    activity_type: "read" | "quiz" | "flashcards" | "steeplechase";
    title: string;
    slide?: string;
    topic?: string;
    block?: string;
    scheduled_date: string;
    scheduled_time?: string;
    estimated_minutes: number;
  }): Promise<ScheduleItem> => {
    const response = await api.post("/api/schedule/", data);
    return response.data;
  },

  updateScheduleItem: async (
    id: number,
    data: Partial<ScheduleItem>,
  ): Promise<ScheduleItem> => {
    const response = await api.patch(`/api/schedule/${id}/`, data);
    return response.data;
  },

  deleteScheduleItem: async (id: number): Promise<void> => {
    await api.delete(`/api/schedule/${id}/`);
  },

  completeScheduleItem: async (id: number): Promise<ScheduleItem> => {
    const response = await api.post(`/api/schedule/${id}/complete/`);
    return response.data;
  },

  uncompleteScheduleItem: async (id: number): Promise<ScheduleItem> => {
    const response = await api.post(`/api/schedule/${id}/uncomplete/`);
    return response.data;
  },
};

// ==================== STATS API ====================

export const statsApi = {
  getMyStats: async (): Promise<UserStats> => {
    const response = await api.get("/api/stats/me/");
    return response.data;
  },

  getLeaderboard: async (limit: number = 10): Promise<UserStats[]> => {
    const response = await api.get("/api/stats/leaderboard/", {
      params: { limit },
    });
    return response.data;
  },

  awardPoints: async (points: number, reason: string): Promise<UserStats> => {
    const response = await api.post("/api/stats/award_points/", {
      points,
      reason,
    });
    return response.data;
  },

  updateStreak: async (): Promise<UserStats> => {
    const response = await api.post("/api/stats/update_streak/");
    return response.data;
  },
};

// ==================== COMMUNITY API ====================

export const communityApi = {
  getPosts: async (): Promise<CommunityPost[]> => {
    const response = await api.get("/api/community/");
    return response.data;
  },

  createPost: async (data: {
    post_type: "achievement" | "question" | "discussion" | "resource";
    content: string;
    slide?: string;
    topic?: string;
  }): Promise<CommunityPost> => {
    const response = await api.post("/api/community/", data);
    return response.data;
  },

  likePost: async (
    postId: number,
  ): Promise<{ liked: boolean; likes_count: number }> => {
    const response = await api.post(`/api/community/${postId}/like/`);
    return response.data;
  },

  unlikePost: async (
    postId: number,
  ): Promise<{ liked: boolean; likes_count: number }> => {
    const response = await api.post(`/api/community/${postId}/unlike/`);
    return response.data;
  },

  addComment: async (postId: number, content: string): Promise<PostComment> => {
    const response = await api.post(`/api/community/${postId}/comment/`, {
      content,
    });
    return response.data;
  },

  // Update post (owner only)
  updatePost: async (
    postId: number,
    data: { content: string; post_type?: string },
  ): Promise<CommunityPost> => {
    const response = await api.put(`/api/community/${postId}/`, data);
    return response.data;
  },

  // Delete post (owner only)
  deletePost: async (postId: number): Promise<void> => {
    await api.delete(`/api/community/${postId}/`);
  },
};

// ==================== TESTS API ====================

export const testsApi = {
  getUpcomingTests: async (): Promise<UpcomingTest[]> => {
    const response = await api.get("/api/tests/");
    return response.data;
  },

  createTest: async (data: {
    title: string;
    description: string;
    subject: string;
    topics?: string[];
    test_date: string;
    test_time?: string;
    duration_minutes: number;
  }): Promise<UpcomingTest> => {
    const response = await api.post("/api/tests/", data);
    return response.data;
  },
};

// ==================== QUIZ API ====================

export const quizApi = {
  generateQuiz: async (data: {
    quiz_type: "mcq" | "theory";
    subject?: string;
    block?: string;
    topic?: string;
    num_questions: number;
  }): Promise<Quiz> => {
    const response = await api.post("/api/quiz/generate/", data);
    return response.data;
  },

  submitAnswer: async (data: {
    quiz_id: string;
    question_id: string;
    selected_option?: string;
    text_answer?: string;
    time_taken_seconds: number;
  }): Promise<QuizAnswer> => {
    const response = await api.post("/api/quiz/answer/", data);
    return response.data;
  },

  completeQuiz: async (quizId: string): Promise<Quiz> => {
    const response = await api.post(`/api/quiz/${quizId}/complete/`);
    return response.data;
  },

  getQuizHistory: async (): Promise<Quiz[]> => {
    const response = await api.get("/api/quiz/history/");
    return response.data;
  },
};

// ==================== AI API ====================

export const aiApi = {
  chat: async (data: {
    message: string;
    slide_id?: string;
    history?: Array<{ role: string; content: string }>;
  }): Promise<{ reply: string }> => {
    const response = await api.post("/api/ai/tutor/", data);
    return response.data;
  },

  getRecommendations: async (): Promise<{
    recommendations: string[];
    focus_areas: string[];
  }> => {
    const response = await api.get("/api/ai/recommendations/");
    return response.data;
  },

  // New AI endpoints for reader sidebar
  getTextbookSuggestions: async (
    slideId: string,
  ): Promise<{
    suggestions: Array<{
      textbook: string;
      chapter: string;
      relevance: string;
    }>;
    slide_title: string;
    subject: string;
  }> => {
    const response = await api.post("/api/ai/textbook-suggestions/", {
      slide_id: slideId,
    });
    return response.data;
  },

  getVideoSuggestions: async (
    slideId: string,
  ): Promise<{
    suggestions: Array<{
      title: string;
      channel: string;
      description: string;
      duration: string;
    }>;
    slide_title: string;
    subject: string;
  }> => {
    const response = await api.post("/api/ai/video-suggestions/", {
      slide_id: slideId,
    });
    return response.data;
  },

  generateMCQs: async (
    slideId: string,
  ): Promise<{
    mcqs: Array<{
      question: string;
      options: {
        A: string;
        B: string;
        C: string;
        D: string;
      };
      correct_answer: string;
      explanation: string;
    }>;
    total_questions: number;
    slide_title: string;
    subject: string;
  }> => {
    const response = await api.post("/api/ai/generate-mcqs/", {
      slide_id: slideId,
    });
    return response.data;
  },
};

export default api;
