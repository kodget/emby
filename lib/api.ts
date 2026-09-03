import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// Create axios instance with default config
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  // Without this, a slow or unreachable backend leaves every request pending forever,
  // so loading skeletons never resolve and the app looks frozen rather than degraded.
  // Long AI calls pass their own larger timeout at the call site.
  timeout: 20000,
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

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token as string);
    }
  });
  failedQueue = [];
};

// Add response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

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

      if (isRefreshing) {
        return new Promise(function (resolve, reject) {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      isRefreshing = true;

      try {
        // Try to refresh the token
        const response = await axios.post(
          `${API_BASE_URL}/auth/token/refresh/`,
          {
            refresh: refreshToken,
          },
        );

        const newAccessToken = response.data.access;
        if (response.data.refresh) {
          sessionStorage.setItem("refreshToken", response.data.refresh);
        }

        // Update token in sessionStorage
        sessionStorage.setItem("token", newAccessToken);

        // Update the failed request with new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

        processQueue(null, newAccessToken);
        // Retry the original request
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Refresh failed, redirect to login
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("token");
          sessionStorage.removeItem("refreshToken");
          sessionStorage.removeItem("user");
          window.location.href = "/signin";
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
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
  class_role: "student" | "class_head" | "material_uploader";
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
  is_superuser?: boolean;
  is_staff?: boolean;
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
  created_at: string;
};

export type Section = Topic;

export type SubBlock = {
  id: string;
  name: string;
  description: string;
  order: number;
  topics: Topic[];
  created_at: string;
};

export type Block = {
  id: string;
  subject: string;
  name: string;
  description: string;
  order: number;
  sub_blocks: SubBlock[];
  topics: Topic[];
  created_at: string;
};

export type Slide = {
  id: string;
  title: string;
  subject: string | null;
  subject_name: string | null;
  block: string | null;
  block_name: string | null;
  sub_block: string | null;
  sub_block_name: string | null;
  topic: string | null;
  topic_name: string | null;
  section?: string | null;
  section_name?: string | null;
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
  usage?: {
    aiQuestionsUsed: number;
    flashcardsCreated: number;
    pastQuestionsUsed: number;
    quizzesTaken: number;
    steeplechaseAttempts: number;
    lastReset: string;
  };
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

export type SteeplechaseQuestion = {
  id: string;
  image_url: string;
  prompt: string;
  accepted_answers: string[];
  explanation: string;
  source_file: string;
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
    class_role: "student" | "class_head" | "material_uploader";
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

  validateClassCode: async (
    class_code: string,
  ): Promise<{ valid: boolean }> => {
    const response = await api.post("/auth/class/validate-code/", {
      class_code,
    });
    return response.data;
  },
};

// ==================== ADMIN API ====================

export const adminApi = {
  getAnalytics: async (): Promise<{
    total_users: number;
    total_premium_users: number;
    total_classes: number;
    total_subjects: number;
    total_slides: number;
    total_quizzes_taken: number;
    revenue_summary: { monthly: number; yearly: number };
  }> => {
    const response = await api.get("/auth/admin/analytics/");
    return response.data;
  },
  getUsers: async (): Promise<UserProfile[]> => {
    const response = await api.get("/auth/admin/users/");
    return response.data;
  },
  getCurriculum: async (): Promise<{
    schools: any[];
    classes: any[];
    subjects: any[];
  }> => {
    const response = await api.get("/auth/admin/curriculum/");
    return response.data;
  },
  getPayments: async (): Promise<any[]> => {
    const response = await api.get("/auth/admin/payments/");
    return response.data;
  },
  getSchema: async (): Promise<any[]> => {
    const response = await api.get("/auth/admin/schema/");
    return response.data;
  },
  getAdminDataList: async (
    appLabel: string,
    modelName: string,
    page: number = 1,
  ): Promise<{
    results: any[];
    total: number;
    page: number;
    limit: number;
  }> => {
    const response = await api.get(
      `/auth/admin/data/${appLabel}/${modelName}/?page=${page}`,
    );
    return response.data;
  },
  getAdminDataDetail: async (
    appLabel: string,
    modelName: string,
    id: string,
  ): Promise<any> => {
    const response = await api.get(
      `/auth/admin/data/${appLabel}/${modelName}/${id}/`,
    );
    return response.data;
  },
  createAdminData: async (
    appLabel: string,
    modelName: string,
    data: any,
  ): Promise<any> => {
    const response = await api.post(
      `/auth/admin/data/${appLabel}/${modelName}/`,
      data,
    );
    return response.data;
  },
  updateAdminData: async (
    appLabel: string,
    modelName: string,
    id: string,
    data: any,
  ): Promise<any> => {
    const response = await api.put(
      `/auth/admin/data/${appLabel}/${modelName}/${id}/`,
      data,
    );
    return response.data;
  },
  deleteAdminData: async (
    appLabel: string,
    modelName: string,
    id: string,
  ): Promise<any> => {
    const response = await api.delete(
      `/auth/admin/data/${appLabel}/${modelName}/${id}/`,
    );
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

  // SubBlocks
  getSubBlocks: async (blockId?: string): Promise<SubBlock[]> => {
    const params = blockId ? { block: blockId } : {};
    const response = await api.get("/api/sub-blocks/", { params });
    return response.data;
  },

  getSubBlock: async (subBlockId: string): Promise<SubBlock> => {
    const response = await api.get(`/api/sub-blocks/${subBlockId}/`);
    return response.data;
  },

  // Topics
  getTopics: async (filters?: {
    sub_block?: string;
    block?: string;
    topic?: string;
  }): Promise<Topic[]> => {
    const params = {
      sub_block: filters?.sub_block || filters?.topic,
      block: filters?.block,
    };
    const response = await api.get("/api/topics/", { params });
    return response.data;
  },

  getTopic: async (topicId: string): Promise<Topic> => {
    const response = await api.get(`/api/topics/${topicId}/`);
    return response.data;
  },

  // Backward compatibility alias methods
  getSections: async (filters?: {
    topic?: string;
    block?: string;
  }): Promise<Topic[]> => {
    return curriculumApi.getTopics({
      sub_block: filters?.topic,
      block: filters?.block,
    });
  },

  getSection: async (sectionId: string): Promise<Topic> => {
    return curriculumApi.getTopic(sectionId);
  },

  // Steeplechase
  getSteeplechaseQuestions: async (): Promise<SteeplechaseQuestion[]> => {
    const response = await api.get("/api/steeplechase/");
    return response.data;
  },

  // Slides
  getSlides: async (filters?: {
    subject?: string;
    block?: string;
    sub_block?: string;
    topic?: string;
    section?: string;
  }): Promise<Slide[]> => {
    const params = {
      ...filters,
      sub_block: filters?.sub_block || filters?.topic,
      topic: filters?.topic || filters?.section,
    };
    const response = await api.get("/api/slides/", { params });
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
    sub_block?: string;
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

  uploadQuestionImages: async (
    id: number,
    frontImage: File | null,
    backImage: File | null,
  ): Promise<any> => {
    const formData = new FormData();
    if (frontImage) formData.append("front_image", frontImage);
    if (backImage) formData.append("back_image", backImage);

    const response = await api.post(
      `/api/curriculum/questions/${id}/upload_images/`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
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

  getSubjectProgress: async (): Promise<
    Array<{
      subject_id: string;
      subject_name: string;
      completion_percentage: number;
    }>
  > => {
    const response = await api.get("/api/progress/subject_progress/");
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

// ==================== STUDY PLANNER API ====================

export interface StudyProfile {
  id?: number;
  exam_date?: string;
  daily_study_minutes?: number;
  target_subjects?: string[];
  focus_areas?: string[];
}

export const studyPlannerApi = {
  getProfile: async (): Promise<StudyProfile | null> => {
    const response = await api.get("/api/study-profile/");
    // returns an array, we want the first element
    return response.data.length > 0 ? response.data[0] : null;
  },

  updateProfile: async (
    id: number,
    data: StudyProfile,
  ): Promise<StudyProfile> => {
    const response = await api.patch(`/api/study-profile/${id}/`, data);
    return response.data;
  },

  createProfile: async (data: StudyProfile): Promise<StudyProfile> => {
    const response = await api.post("/api/study-profile/", data);
    return response.data;
  },

  generatePlan: async (): Promise<{ detail: string }> => {
    const response = await api.post("/api/study-profile/generate_plan/");
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

  getRecommendations: async (): Promise<any> => {
    const response = await api.get("/api/ai/recommendations/");
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

  // Create a new quiz attempt with full configuration
  createQuizAttempt: async (config: {
    subject?: string;
    block?: string;
    topic?: string;
    slide?: string;
    exam_type: "practice" | "mock" | "formal";
    is_timed: boolean;
    duration_minutes?: number;
    configuration: {
      mcq_count: number;
      theory_count: number;
      difficulty: "easy" | "medium" | "hard";
      question_source?: string;
    };
  }): Promise<{ id: string; message: string }> => {
    // Transform the config to match backend expectations
    const payload = {
      subject: config.subject || null,
      block: config.block || null,
      topic: config.topic || null,
      slide: config.slide || null,
      exam_type: config.exam_type,
      is_timed: config.is_timed,
      duration_minutes: config.duration_minutes || null,
      configuration: {
        mcq_count: config.configuration.mcq_count,
        theory_count: config.configuration.theory_count,
        difficulty: config.configuration.difficulty,
        question_source: config.configuration.question_source || "hierarchy",
      },
    };

    const response = await api.post("/api/quiz-attempts/", payload);
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

  getQuizAttempts: async (): Promise<any[]> => {
    const response = await api.get("/api/quiz-attempts/");
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
    recommendations: any[];
    focus_areas: string[];
    flashcards_due?: number;
    practice_topic?: string;
    missed_count?: number;
    slide_to_read?: { id: string; title: string } | null;
    stale_slides?: Array<{ id: string; title: string }>;
    study_plan_items?: Array<{
      id: string;
      title: string;
      item_type: string;
      status: string;
    }>;
    insights?: string;
  }> => {
    const response = await api.get("/api/ai/recommendations/");
    return response.data;
  },

  // New AI endpoints for reader sidebar
  getTextbookSuggestions: async (
    slideId: string,
  ): Promise<{
    textbooks: Array<{
      title: string;
      author: string;
      chapter: string;
      reason: string;
    }>;
  }> => {
    const response = await api.post("/api/ai/textbook-suggestions/", {
      slide_id: slideId,
    });
    return response.data;
  },

  getVideoSuggestions: async (
    slideId: string,
  ): Promise<{
    videos: Array<{
      title: string;
      query: string;
      reason: string;
    }>;
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
      options: string[];
      correct: number;
      explanation: string;
    }>;
  }> => {
    const response = await api.post(
      "/api/ai/generate-mcqs/",
      {
        slide_id: slideId,
      },
      { timeout: 60000 }
    );
    return response.data;
  },

  generateFlashcards: async (
    slideId: string,
    count: number = 5,
    slideImageBase64?: string
  ): Promise<{
    message: string;
    task_id: string;
  }> => {
    const response = await api.post(
      "/api/ai/generate-flashcards/",
      {
        slide_id: slideId,
        count: count,
        slide_image_base64: slideImageBase64,
      },
      { timeout: 60000 }
    );
    return response.data;
  },

  // Slide-aware chat — backend proxy adds Gemini key, never exposed to frontend
  chatWithSlide: async (data: {
    slide_id: string;
    message: string;
    slide_image_base64?: string;
    conversation_history?: Array<{ role: string; content: string }>;
  }): Promise<{
    response: string;
    sources?: string[];
    youtube?: {
      title: string;
      channel: string;
      length: string;
      isDissection: boolean;
    };
  }> => {
    const response = await api.post("/api/ai/chat/", data);
    return response.data;
  },

  // Generate per-slide resources (YouTube, textbooks, MCQs)
  // Cached per-slide on the frontend — only called once per slide
  generateResources: async (data: {
    slide_id: string;
    slide_image_base64?: string;
  }): Promise<{
    youtube: Array<{ title: string; query: string; reason: string }>;
    textbooks: Array<{
      title: string;
      author: string;
      chapter: string;
      reason: string;
    }>;
    mcqs: Array<{
      question: string;
      options: string[];
      correct: number;
      explanation: string;
    }>;
  }> => {
    const response = await api.post("/api/ai/resources/", data, {
      timeout: 60000,
    });
    return response.data;
  },
};

// -------------------------
// FLASHCARD TYPES
// -------------------------
export interface FlashcardProgress {
  id: number;
  due_date: string;
  interval: number;
  repetitions: number;
  ease_factor: number;
  last_reviewed: string | null;
  is_due: boolean;
  created_at: string;
  updated_at: string;
}

export interface Flashcard {
  id: number;
  user: number;
  subject: string | null;
  subject_name: string | null;
  block: string | null;
  block_name: string | null;
  sub_block: number | null;
  sub_block_name: string | null;
  topic: number | null;
  topic_name: string | null;
  source_question: number | null;
  source_question_text: string | null;
  front: string;
  back: string;
  explanation: string;
  source: "manual" | "quiz_mistake" | "ai" | "pdf" | "lecture_note";
  progress: FlashcardProgress | null;
  created_at: string;
  updated_at: string;
}

export interface FlashcardDeckStat {
  subject_id: string;
  subject_name: string;
  total_cards: number;
  due_today: number;
}

export interface FlashcardStats {
  total_cards: number;
  due_today: number;
  total_reviews: number;
  retention_rate: number;
  decks: FlashcardDeckStat[];
}

export type FlashcardRating = "again" | "hard" | "good" | "easy";

export interface FlashcardReviewResult {
  success: boolean;
  rating: FlashcardRating;
  next_review: string;
  interval_days: number;
  interval_minutes: number;
  repetitions: number;
  ease_factor: number;
}

// -------------------------
// FLASHCARD API
// -------------------------
export const flashcardApi = {
  /** List all flashcards for the authenticated user */
  getAll: async (params?: {
    subject?: string;
    block?: string;
    sub_block?: number;
    topic?: number;
    source?: string;
    search?: string;
    slide_id?: string;
  }): Promise<{ count: number; results: Flashcard[] }> => {
    const response = await api.get("/api/flashcards/", { params });
    // DRF router list may return array or paginated object
    const data = response.data;
    if (Array.isArray(data)) {
      return { count: data.length, results: data };
    }
    return data;
  },

  /** Alias for getAll - used by resource panel */
  list: async (params?: {
    subject?: string;
    block?: string;
    sub_block?: number;
    topic?: number;
    source?: string;
    search?: string;
    slide_id?: string;
  }): Promise<{ count: number; results: Flashcard[] }> => {
    const response = await api.get("/api/flashcards/", { params });
    // DRF router list may return array or paginated object
    const data = response.data;
    if (Array.isArray(data)) {
      return { count: data.length, results: data };
    }
    return data;
  },

  /** Get flashcards that are due for review */
  getDue: async (params?: {
    subject?: string;
    block?: string;
    sub_block?: number;
    topic?: number;
    slide_id?: string;
  }): Promise<{ count: number; results: Flashcard[] }> => {
    const response = await api.get("/api/flashcards/due/", { params });
    const data = response.data;
    if (Array.isArray(data)) {
      return { count: data.length, results: data };
    }
    return data;
  },

  /** Get a single flashcard */
  getOne: async (id: number): Promise<Flashcard> => {
    const response = await api.get(`/api/flashcards/${id}/`);
    return response.data;
  },

  /** Create a manual flashcard */
  create: async (data: {
    front: string;
    back: string;
    explanation?: string;
    subject?: string;
    block?: string;
    sub_block?: number;
    topic?: number;
  }): Promise<Flashcard> => {
    const response = await api.post("/api/flashcards/", {
      ...data,
      source: "manual",
    });
    return response.data;
  },

  /** Update a flashcard */
  update: async (
    id: number,
    data: Partial<
      Pick<
        Flashcard,
        | "front"
        | "back"
        | "explanation"
        | "subject"
        | "block"
        | "sub_block"
        | "topic"
      >
    >,
  ): Promise<Flashcard> => {
    const response = await api.patch(`/api/flashcards/${id}/`, data);
    return response.data;
  },

  /** Delete a flashcard */
  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/flashcards/${id}/`);
  },

  /** Submit a review rating */
  review: async (
    id: number,
    rating: FlashcardRating,
  ): Promise<FlashcardReviewResult> => {
    const response = await api.post(`/api/flashcards/${id}/review/`, {
      rating,
    });
    return response.data;
  },

  /** Get aggregate stats + deck overview */
  getStats: async (): Promise<FlashcardStats> => {
    const response = await api.get("/api/flashcards/stats/");
    return response.data;
  },
};

export const challengeApi = {
  getChallenges: async (): Promise<any[]> => {
    const response = await api.get("/api/challenges/");
    return response.data;
  },
  createChallenge: async (data: {
    challenged: number;
    topic?: string;
  }): Promise<any> => {
    const response = await api.post("/api/challenges/", data);
    return response.data;
  },
  acceptChallenge: async (id: number): Promise<any> => {
    const response = await api.post(`/api/challenges/${id}/accept/`);
    return response.data;
  },
  submitScore: async (id: number, score: number): Promise<any> => {
    const response = await api.post(`/api/challenges/${id}/submit_score/`, {
      score,
    });
    return response.data;
  },
};

export interface BattleLookup {
  code: string;
  title: string;
  status: string;
  total_questions: number;
  seconds_per_question: number;
  participants: number;
  host_name: string;
}

export interface BattleJoin {
  battle_id: number;
  code: string;
  title: string;
  status: string;
  total_questions: number;
  seconds_per_question: number;
  host: boolean;
  newly_joined: boolean;
  your_score: number;
}

export interface BattleQuestion {
  index: number;
  total: number;
  question: string;
  options: string[];
  seconds: number;
}

export interface BattleAnswerResult {
  index: number;
  correct: boolean;
  correct_index: number | null;
  explanation: string;
  points: number;
  score: number;
}

export interface BattleStanding {
  rank: number;
  user_id: number;
  name: string;
  score: number;
  answered: number;
  correct: number;
  accuracy: number | null;
  is_host: boolean;
}

export const battleApi = {
  getBattles: async (): Promise<any[]> => {
    const response = await api.get("/api/battles/");
    return response.data;
  },
  createBattle: async (data: {
    title: string;
    description?: string;
    topic?: string;
    num_questions?: number;
  }): Promise<any> => {
    const response = await api.post("/api/battles/", data);
    return response.data;
  },
  joinBattle: async (id: number): Promise<any> => {
    const response = await api.post(`/api/battles/${id}/join/`);
    return response.data;
  },
  startBattle: async (id: number): Promise<any> => {
    const response = await api.post(`/api/battles/${id}/start/`);
    return response.data;
  },
  endBattle: async (id: number): Promise<any> => {
    const response = await api.post(`/api/battles/${id}/end/`);
    return response.data;
  },

  // --- code-based join and server-scored play (learning app) ---------------------

  /** Check a code before committing to join. */
  lookup: async (code: string): Promise<BattleLookup> =>
    (await api.get(`/api/learning/battles/lookup/${encodeURIComponent(code)}/`))
      .data,

  join: async (code: string): Promise<BattleJoin> =>
    (await api.post("/api/learning/battles/join/", { code })).data,

  getQuestion: async (
    battleId: number,
    index: number,
  ): Promise<BattleQuestion> =>
    (await api.get(`/api/learning/battles/${battleId}/question/${index}/`))
      .data,

  answer: async (
    battleId: number,
    payload: {
      index: number;
      selected_index: number | null;
      seconds_taken: number;
    },
  ): Promise<BattleAnswerResult> =>
    (await api.post(`/api/learning/battles/${battleId}/answer/`, payload)).data,

  leaderboard: async (
    battleId: number,
  ): Promise<{ leaderboard: BattleStanding[] }> =>
    (await api.get(`/api/learning/battles/${battleId}/leaderboard/`)).data,

  finish: async (battleId: number) =>
    (await api.post(`/api/learning/battles/${battleId}/finish/`)).data as {
      your_rank: number | null;
      your_score: number;
      answered: number;
      correct: number;
      accuracy: number | null;
      participants: number;
      leaderboard: BattleStanding[];
    },
};

// ==================== LEARNING API ====================
// Cross-cutting systems: image-spot practice, AI credits, weak areas, XP,
// notifications and the cached dashboard message. Mounted at /api/learning/.

export type PracticeMode = "STEEPLECHASE" | "HISTOLOGY";

export interface PracticeEntitlement {
  is_premium: boolean;
  max_stations: number;
  rounds_used: number;
  rounds_limit: number | null;
  rounds_remaining: number | null;
  stations_available: number;
}

export interface PracticeSection {
  code: string;
  label: string;
  count: number;
}

export interface PracticeOptions {
  mode: PracticeMode;
  seconds_per_station: number;
  sections: PracticeSection[];
  entitlement: PracticeEntitlement;
}

/** A station as the student sees it — deliberately carries no answer data. */
export interface PracticeStation {
  id: string;
  index: number;
  total: number;
  seconds: number;
  image_url: string;
  section: string;
  marker: {
    present: boolean;
    type: string;
    x: number | null;
    y: number | null;
  };
  main: { question: string };
  supporting?: { question: string; options: string[] };
  true_false?: { statement: string };
}

/** Returned only after an answer is submitted. */
export interface PracticeReveal {
  station_id: string;
  main: { correct: boolean; answer: string | null; explanation: string };
  supporting: {
    correct: boolean | null;
    correct_index: number | null;
    explanation: string;
  } | null;
  true_false: {
    correct: boolean | null;
    answer: boolean | null;
    explanation: string;
  } | null;
  structure: string;
  timed_out: boolean;
}

export interface PracticeResults {
  session_id: string;
  mode: PracticeMode;
  total_stations: number;
  answered: number;
  accuracy_percent: number;
  main_correct: number;
  supporting_correct: number;
  true_false_correct: number;
  timed_out: number;
  average_seconds: number;
  section_breakdown: Record<
    string,
    { attempted: number; correct: number; accuracy: number }
  >;
  is_premium: boolean;
  upgrade_hint?: string;
  weak_sections?: string[];
  stations?: Array<{
    station_id: string;
    image_url: string;
    section: string;
    question: string;
    your_answer: string;
    correct_answer: string | null;
    main_correct: boolean | null;
    explanation: string;
    structure: string;
    seconds_taken: number;
    timed_out: boolean;
  }>;
}

export const practiceApi = {
  getOptions: async (mode: PracticeMode): Promise<PracticeOptions> => {
    const res = await api.get("/api/learning/practice/options/", {
      params: { mode },
    });
    return res.data;
  },

  start: async (
    mode: PracticeMode,
    sections: string[],
    count: number,
  ): Promise<{
    session_id: string;
    mode: PracticeMode;
    total_stations: number;
    seconds_per_station: number;
    station: PracticeStation;
    entitlement: PracticeEntitlement;
  }> => {
    const res = await api.post("/api/learning/practice/start/", {
      mode,
      sections,
      count,
    });
    return res.data;
  },

  getStation: async (
    sessionId: string,
    index: number,
  ): Promise<PracticeStation> => {
    const res = await api.get(
      `/api/learning/practice/${sessionId}/station/${index}/`,
    );
    return res.data;
  },

  answer: async (
    sessionId: string,
    payload: {
      station_id: string;
      main_answer?: string;
      supporting_choice?: number | null;
      true_false_answer?: boolean | null;
      seconds_taken?: number;
      timed_out?: boolean;
    },
  ): Promise<PracticeReveal> => {
    const res = await api.post(
      `/api/learning/practice/${sessionId}/answer/`,
      payload,
    );
    return res.data;
  },

  complete: async (sessionId: string): Promise<PracticeResults> => {
    const res = await api.post(`/api/learning/practice/${sessionId}/complete/`);
    return res.data;
  },

  getResults: async (sessionId: string): Promise<PracticeResults> => {
    const res = await api.get(`/api/learning/practice/${sessionId}/results/`);
    return res.data;
  },

  getHistory: async (mode: PracticeMode) => {
    const res = await api.get("/api/learning/practice/history/", {
      params: { mode },
    });
    return res.data as Array<{
      session_id: string;
      completed_at: string;
      total_stations: number;
      accuracy_percent: number;
      sections: string[];
    }>;
  },
};

export interface CreditBalance {
  allocated: number;
  used: number;
  remaining: number;
  tier: string;
  period_ends: string;
  costs: Record<string, number>;
}

export const learningApi = {
  getCredits: async (): Promise<CreditBalance> => {
    const res = await api.get("/api/learning/credits/");
    return res.data;
  },

  getCreditHistory: async () =>
    (await api.get("/api/learning/credits/history/")).data,

  getCreditPackages: async (): Promise<any[]> => {
    const res = await api.get("/api/learning/credit-packages/");
    return res.data;
  },

  getCreditLots: async (): Promise<any[]> => {
    const res = await api.get("/api/learning/credit-lots/");
    return res.data;
  },

  getCreditTransactions: async (limit = 50): Promise<any[]> => {
    const res = await api.get("/api/learning/credit-transactions/", {
      params: { limit },
    });
    return res.data;
  },

  getWeakAreas: async (scope = "TOPIC", limit = 5) =>
    (await api.get("/api/learning/weak-areas/", { params: { scope, limit } }))
      .data,

  getXp: async (days = 30) =>
    (await api.get("/api/learning/xp/", { params: { days } })).data,

  getDashboardMessage: async (refresh = false) =>
    (
      await api.get("/api/learning/dashboard/message/", {
        params: refresh ? { refresh: "true" } : {},
      })
    ).data as { headline: string; body: string; cached: boolean },

  getDashboardSnapshot: async () =>
    (await api.get("/api/learning/dashboard/snapshot/")).data,

  getNotifications: async (unreadOnly = false) =>
    (
      await api.get("/api/learning/notifications/", {
        params: unreadOnly ? { unread: "true" } : {},
      })
    ).data,

  markNotificationsRead: async (id?: string) =>
    (await api.post("/api/learning/notifications/read/", id ? { id } : {}))
      .data,
};

export interface AnalyticsReport {
  generated_at: string;
  window_days: number;
  is_premium: boolean;
  include_detail: boolean;
  overview: {
    has_data: boolean;
    attempted: number;
    correct: number;
    incorrect: number;
    accuracy: number | null;
    sessions: number;
    study_minutes: number;
  };
  improvement: {
    direction: "up" | "down" | "flat" | "insufficient_data";
    earlier_accuracy: number | null;
    recent_accuracy: number | null;
    change: number | null;
    note?: string;
  };
  consistency: {
    active_days: number;
    window_days: number;
    active_rate: number;
    current_streak: number;
    longest_streak: number;
    total_minutes: number;
    average_minutes_per_active_day: number;
  };
  daily_activity: Array<{ date: string; minutes: number; sessions: number }>;
  by_assessment: Array<{
    activity: string;
    label: string;
    sessions: number;
    attempted: number;
    correct: number;
    accuracy: number | null;
    minutes: number;
  }>;
  practice: Record<
    string,
    {
      rounds: number;
      stations: number;
      average_accuracy: number | null;
      timed_out: number;
    }
  >;
  topics?: {
    weakest: Array<{
      label: string;
      attempted: number;
      correct: number;
      accuracy: number | null;
      mastery: number;
      priority: number;
    }>;
    strongest: Array<{
      label: string;
      attempted: number;
      correct: number;
      accuracy: number | null;
      mastery: number;
    }>;
    tracked_nodes: number;
  };
  question_bank?: {
    total: number;
    seen: number;
    unseen: number;
    answered: number;
    missed: number;
    percent_seen: number;
  };
}

export const analyticsApi = {
  getReport: async (days = 30): Promise<AnalyticsReport> => {
    const res = await api.get("/api/learning/analytics/", { params: { days } });
    return res.data;
  },
};

// ==================== GAMIFICATION API ====================

export interface GamificationBadge {
  id: string;
  name: string;
  icon: string;
  rarity: "COMMON" | "UNCOMMON" | "RARE" | "EPIC" | "LEGENDARY";
  image_url: string;
}

export interface GamificationAchievement {
  id: string;
  name: string;
  description: string;
  category: string;
  target_metric: string;
  target_value: number;
  progress: number;
  percentage: number;
  is_completed: boolean;
  completed_at: string | null;
  badge: GamificationBadge | null;
}

export interface GamificationUserBadge {
  id: string;
  badge_id: string;
  name: string;
  description: string;
  category: string;
  rarity: string;
  icon: string;
  image_url: string;
  earned_at: string;
}

export interface GamificationProfile {
  xp: number;
  badges_count: number;
  achievements_count: number;
  current_streak: number;
  longest_streak: number;
}

export const gamificationApi = {
  getAchievements: async (): Promise<GamificationAchievement[]> => {
    const res = await api.get("/api/learning/achievements/");
    return res.data;
  },

  getBadges: async (): Promise<GamificationUserBadge[]> => {
    const res = await api.get("/api/learning/badges/");
    return res.data;
  },

  getProfile: async (): Promise<GamificationProfile> => {
    const res = await api.get("/api/learning/gamification/profile/");
    return res.data;
  },
};

export interface CreditPackage {
  id: number;
  name: string;
  credits: number;
  price: number;
  total_price: number;
  service_fee: number;
}

export interface CreditHistoryItem {
  id: number;
  type: string;
  amount: number;
  balance_before: number;
  balance_after: number;
  action: string;
  description: string;
  created_at: string;
}

export const creditsApi = {
  getBalance: async (): Promise<{ balance: number }> => {
    const res = await api.get("/api/credits/balance/");
    return res.data;
  },

  getPackages: async (): Promise<{ packages: CreditPackage[] }> => {
    const res = await api.get("/api/credits/packages/");
    return res.data;
  },

  getHistory: async (limit: number = 50): Promise<{ history: CreditHistoryItem[] }> => {
    const res = await api.get("/api/credits/history/", { params: { limit } });
    return res.data;
  },

  initPurchase: async (packageId: number): Promise<{ authorization_url: string; access_code: string; reference: string }> => {
    const res = await api.post("/api/credits/purchase/", { package_id: packageId });
    return res.data;
  },

  verifyPurchase: async (reference: string): Promise<{ message: string; credits_added: number; new_balance: number }> => {
    const res = await api.post("/api/credits/verify-purchase/", { reference });
    return res.data;
  },
};

export default api;
