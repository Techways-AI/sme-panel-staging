/**
 * API Configuration and Service Layer
 * Connects the new frontend to the existing backend
 */

// API Base URL - Update this to match your backend deployment
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://sme-panel-staging-production.up.railway.app';
// Token storage key
const TOKEN_KEY = 'sme_access_token';
const USER_KEY = 'sme_user';

// ============================================
// AUTH HELPERS
// ============================================

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser(): any | null {
  if (typeof window === 'undefined') return null;
  const user = localStorage.getItem(USER_KEY);
  return user ? JSON.parse(user) : null;
}

export function setUser(user: any): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ============================================
// API REQUEST HELPER
// ============================================

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  body?: any;
  headers?: Record<string, string>;
  isFormData?: boolean;
}

async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, isFormData = false } = options;
  
  const rawToken = getToken();
  const authHeader = rawToken
    ? rawToken.trim().toLowerCase().startsWith('bearer ')
      ? rawToken.trim()
      : `Bearer ${rawToken.trim()}`
    : null;
  
  const requestHeaders: Record<string, string> = {
    ...headers,
  };
  
  if (authHeader) {
    requestHeaders['Authorization'] = authHeader;
  }
  
  if (!isFormData && body) {
    requestHeaders['Content-Type'] = 'application/json';
  }
  
  const config: RequestInit = {
    method,
    headers: requestHeaders,
    credentials: 'include',
    // Ensure fetch is not delayed by browser
    cache: 'no-store',
  };
  
  if (body) {
    config.body = isFormData ? body : JSON.stringify(body);
  }
  
  // Execute fetch immediately without any delays
  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
  
  if (!response.ok) {
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // If response is not JSON, try to get text
      try {
        const errorText = await response.text();
        if (errorText) errorMessage = errorText;
      } catch {
        // Keep default error message
      }
    }
    throw new Error(errorMessage);
  }
  
  return response.json();
}

// ============================================
// AUTH API
// ============================================

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    is_active: boolean;
    role: string;
    created_at: string;
    last_login: string;
  };
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  role?: string;
}

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiRequest<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: data,
    });
    const normalizedTokenType = (response.token_type || 'Bearer').trim();
    const headerSafeTokenType = normalizedTokenType.toLowerCase().startsWith('bearer')
      ? 'Bearer'
      : normalizedTokenType;
    const tokenToStore = response.access_token
      ? `${headerSafeTokenType} ${response.access_token}`
      : response.access_token;
    setToken(tokenToStore);
    setUser(response.user);
    return response;
  },
  
  register: async (data: RegisterRequest) => {
    return apiRequest('/api/auth/register', {
      method: 'POST',
      body: data,
    });
  },
  
  verify: async () => {
    return apiRequest('/api/auth/verify');
  },
  
  logout: () => {
    removeToken();
  },
  
  getUsers: async () => {
    return apiRequest('/api/auth/users');
  },
};

// ============================================
// ACCESS MANAGEMENT API
// ============================================

export interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  joined_date: string;
  panel?: string | null;
}

export interface CreateAdminUserRequest {
  name: string;
  email: string;
  password: string;
  role: string;
}

export interface UpdateAdminUserRequest {
  name?: string;
  email?: string;
  password?: string;
  role?: string;
  status?: string;
}

export const accessManagementApi = {
  getUsers: async (): Promise<AdminUser[]> => {
    return apiRequest<AdminUser[]>('/api/admin-users');
  },

  addUser: async (data: CreateAdminUserRequest): Promise<AdminUser> => {
    const uiRole = (data.role || '').toLowerCase();
    const dbRole = uiRole === 'admin' ? 'Admin - Full Access' : 'SME - Limited Access';

    return apiRequest<AdminUser>('/api/admin-users', {
      method: 'POST',
      body: { ...data, role: dbRole, status: 'active', panel: 'sme' },
    });
  },

  updateUser: async (id: number, data: UpdateAdminUserRequest): Promise<AdminUser> => {
    const body: UpdateAdminUserRequest = { ...data };

    if (body.role) {
      const uiRole = body.role.toLowerCase();
      body.role = uiRole === 'admin' ? 'Admin - Full Access' : 'SME - Limited Access';
    }

    return apiRequest<AdminUser>(`/api/admin-users/${id}`, {
      method: 'PUT',
      body,
    });
  },

  deleteUser: async (id: number): Promise<void> => {
    await apiRequest(`/api/admin-users/${id}`, {
      method: 'DELETE',
    });
  },
};

// ============================================
// DOCUMENTS API
// ============================================

export interface FolderStructure {
  courseName: string;
  yearSemester: string;
  subjectName: string;
  unitName: string;
  topic: string;
  curriculum?: string; // e.g., "pci", "jntuh", "osmania"
  university?: string; // e.g., "JNTUH", "Osmania"
}

export interface Document {
  id: string;
  fileName: string;
  fileSize: string;
  uploadDate: string;
  path: string;
  s3_key: string;
  processed: boolean;
  processing: boolean;
  user_id: string;
  folderStructure: FolderStructure & { fullPath: string };
}

export interface DocumentsResponse {
  documents: Document[];
  user: {
    id: string;
    permissions: string[];
  };
}

export interface DocumentStatus {
  id: string;
  processed: boolean;
  processing: boolean;
  fileName: string;
  uploadDate: string;
  fileSize: string;
  folderStructure?: FolderStructure;
  vector_store_compatible?: boolean;
  needs_reprocessing?: boolean;
  vector_store_stats?: Record<string, any>;
  processing_details?: Record<string, any>;
  content_coverage?: Record<string, any>;
  total_chunks?: number;
}

// ============================================
// DASHBOARD API
// ============================================

export interface DashboardSummaryStats {
  documentsTotal: number;
  documentsProcessed: number;
  documentsUnprocessed: number;
  videos: number;
  notes: number;
  universityContent: number;
}

export interface DashboardSummaryDocument {
  title: string;
  subject: string;
  status: 'processed' | 'processing' | 'pending';
}

export interface DashboardSummaryVideo {
  title: string;
  subject: string;
  platform: string;
}

export interface DashboardSummaryResponse {
  stats: DashboardSummaryStats;
  recentDocuments: DashboardSummaryDocument[];
  recentVideos: DashboardSummaryVideo[];
  user: {
    id: string;
  };
}

export interface ContentCoverageResponse {
  documents: {
    count: number;
    total: number;
    percentage: number;
  };
  videos: {
    count: number;
    total: number;
    percentage: number;
  };
  notes: {
    count: number;
    total: number;
    percentage: number;
  };
  overall: number;
}

export interface SubjectCoverage {
  code: string;
  name: string;
  year: number;
  semester: number;
  topics: number;
  docs: number;
  videos: number;
  notes: number;
}

export interface SubjectCoverageResponse {
  subjects: SubjectCoverage[];
  curriculum: {
    id: number;
    display_name: string;
    curriculum_type: string;
  };
}

export interface YearCoverage {
  year: string;
  year_num: number;
  semester1: number;
  semester2: number;
  percentage: number;
}

export interface YearCoverageResponse {
  year_coverage: YearCoverage[];
  curriculum: {
    id: number;
    display_name: string;
    curriculum_type: string;
  };
}

export const dashboardApi = {
  getSummary: async (): Promise<DashboardSummaryResponse> => {
    return apiRequest<DashboardSummaryResponse>('/api/dashboard/summary');
  },
  
  getContentCoverage: async (curriculumId: number): Promise<ContentCoverageResponse> => {
    return apiRequest<ContentCoverageResponse>(`/api/dashboard/content-coverage?curriculum_id=${curriculumId}`);
  },
  
  getSubjectCoverage: async (curriculumId: number): Promise<SubjectCoverageResponse> => {
    return apiRequest<SubjectCoverageResponse>(`/api/dashboard/subject-coverage?curriculum_id=${curriculumId}`);
  },
  
  getYearCoverage: async (curriculumId: number): Promise<YearCoverageResponse> => {
    return apiRequest<YearCoverageResponse>(`/api/dashboard/year-coverage?curriculum_id=${curriculumId}`);
  },
};

export interface UploadDocumentRequest {
  files: File[];
  folderStructure: FolderStructure;
  videoUrl?: string;
}

export interface ProcessOptions {
  chunkSize?: number;
  chunkOverlap?: number;
}

export const documentsApi = {
  getAll: async (): Promise<DocumentsResponse> => {
    return apiRequest<DocumentsResponse>('/api/documents');
  },
  
  upload: async (data: UploadDocumentRequest) => {
    const formData = new FormData();
    
    // Append files
    data.files.forEach((file) => {
      formData.append('files', file);
    });
    
    // Append folder structure as JSON string
    formData.append('folderStructure', JSON.stringify(data.folderStructure));
    
    // Append video URL if provided
    if (data.videoUrl) {
      formData.append('videoUrl', data.videoUrl);
    }
    
    return apiRequest('/api/documents/upload', {
      method: 'POST',
      body: formData,
      isFormData: true,
    });
  },
  
  process: async (docId: string, options?: ProcessOptions) => {
    return apiRequest(`/api/documents/${docId}/process`, {
      method: 'POST',
      body: options || {},
    });
  },
  
  delete: async (docId: string) => {
    return apiRequest(`/api/documents/${docId}`, {
      method: 'DELETE',
    });
  },
  
  getById: async (docId: string) => {
    return apiRequest(`/api/documents/${docId}`);
  },
  
  getStatus: async (docId: string): Promise<DocumentStatus> => {
    return apiRequest<DocumentStatus>(`/api/documents/${docId}/status`);
  },
};

// ============================================
// VIDEOS API
// ============================================

export interface Video {
  id: string;
  url: string;
  videoId: string;
  platform: string;
  dateAdded: string;
  folderStructure: FolderStructure & { fullPath: string };
  s3_key: string;
}

export interface VideosResponse {
  videos: Video[];
}

export interface UploadVideoRequest {
  videoUrl?: string;
  videoUrls?: string[];
  folderStructure: FolderStructure;
}

export const videosApi = {
  getAll: async (): Promise<VideosResponse> => {
    return apiRequest<VideosResponse>('/api/videos');
  },
  
  upload: async (data: UploadVideoRequest) => {
    return apiRequest('/api/videos/upload', {
      method: 'POST',
      body: data,
    });
  },
  
  validate: async (url: string) => {
    return apiRequest('/api/videos/validate', {
      method: 'POST',
      body: { url },
    });
  },
  
  delete: async (videoId: string) => {
    return apiRequest(`/api/videos/${videoId}`, {
      method: 'DELETE',
    });
  },
  
  update: async (videoId: string, data: Partial<UploadVideoRequest>) => {
    return apiRequest(`/api/videos/${videoId}`, {
      method: 'PUT',
      body: data,
    });
  },
  
  getByFolder: async (folderPath: string) => {
    return apiRequest(`/api/videos/by-folder/${encodeURIComponent(folderPath)}`);
  },
  
  getByTopic: async (topic: string) => {
    return apiRequest(`/api/videos/by-topic/${encodeURIComponent(topic)}`);
  },
};

// ============================================
// FOLDERS API
// ============================================

export const foldersApi = {
  getStructure: async () => {
    return apiRequest('/api/folders/structure');
  },
  
  getSemesters: async () => {
    return apiRequest('/api/folders/semesters');
  },
  
  getUnits: async (semester: string) => {
    return apiRequest(`/api/folders/units/${semester}`);
  },
  
  getTopics: async (semester: string, unit: string) => {
    return apiRequest(`/api/folders/topics/${semester}/${unit}`);
  },
  
  create: async (folderStructure: FolderStructure) => {
    return apiRequest('/api/folders/create', {
      method: 'POST',
      body: folderStructure,
    });
  },
  
  rename: async (oldPath: string, newPath: string) => {
    return apiRequest('/api/folders/rename', {
      method: 'POST',
      body: { old_path: oldPath, new_path: newPath },
    });
  },
  
  delete: async (folderPath: string) => {
    return apiRequest(`/api/folders/${encodeURIComponent(folderPath)}`, {
      method: 'DELETE',
    });
  },
  
  getContents: async (folderPath: string) => {
    return apiRequest(`/api/folders/${encodeURIComponent(folderPath)}/contents`);
  },
};

// ============================================
// AI API
// ============================================

export interface AskQuestionRequest {
  question: string;
  document_id?: string;
  filter?: {
    course?: string;
    year_semester?: string;
    subject?: string;
    unit?: string;
    topic?: string;
  };
}

export interface AskQuestionResponse {
  answer: string;
  sources: Array<{
    content: string;
    metadata: Record<string, any>;
  }>;
  confidence?: number;
}

export const aiApi = {
  ask: async (data: AskQuestionRequest): Promise<AskQuestionResponse> => {
    return apiRequest<AskQuestionResponse>('/api/ai/ask', {
      method: 'POST',
      body: data,
    });
  },
  
  health: async () => {
    return apiRequest('/api/ai/health');
  },
  
  getTemplates: async () => {
    // Lists available template names from the backend
    return apiRequest('/api/ai/templates');
  },
  
  getTemplate: async (templateName: string) => {
    // This endpoint returns plain text, so we bypass apiRequest's JSON handling
    const token = getToken();
    const response = await fetch(`${API_BASE_URL}/api/ai/template/${templateName}`, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Failed to load template');
      throw new Error(errorText || `Failed to load template ${templateName}`);
    }

    return response.text();
  },
  
  updateTemplate: async (templateName: string, content: string) => {
    // Backend expects a raw string body at POST /api/ai/template/{template_name}
    return apiRequest(`/api/ai/template/${templateName}`, {
      method: 'POST',
      body: content,
    });
  },
  
  testVectorStore: async (docId: string) => {
    return apiRequest(`/api/ai/test-vectorstore/${docId}`);
  },
};

// ============================================
// NOTES API
// ============================================

export interface GenerateNotesRequest {
  document_id: string;
  course_name: string;
  subject_name: string;
  unit_name: string;
  topic: string;
  quality?: 'standard' | 'high_quality' | 'fast';
  max_tokens?: number;
}

export interface Note {
  id: string;
  document_id: string;
  content: string;
  generated_at: string;
  quality: string;
  folder_structure: FolderStructure;
}

export interface NotesResponse {
  notes: Note[];
}

export const notesApi = {
  generate: async (data: GenerateNotesRequest) => {
    return apiRequest('/api/notes/generate', {
      method: 'POST',
      body: data,
    });
  },
  
  getAll: async (): Promise<NotesResponse> => {
    return apiRequest<NotesResponse>('/api/notes');
  },
  
  getById: async (notesId: string) => {
    return apiRequest(`/api/notes/${notesId}`);
  },
  
  getByDocumentId: async (documentId: string) => {
    return apiRequest(`/api/notes/document/${documentId}`);
  },
  
  delete: async (notesId: string) => {
    return apiRequest(`/api/notes/${notesId}`, {
      method: 'DELETE',
    });
  },
};

// ============================================
// MODEL PAPERS API
// ============================================

export interface ModelPaper {
  id: string;
  courseName: string;
  year: string;
  yearName?: string;
  semester: string;
  subject: string;
  description: string;
  files: Array<{
    filename: string;
    file_url: string;
    s3_key: string;
    file_size: number;
  }>;
  uploaded_by: string;
  uploaded_at: string;
}

export interface UploadModelPaperRequest {
  files: File[];
  courseName: string;
  year: string;
  yearName?: string;
  semester: string;
  subject: string;
  description?: string;
}

export const modelPapersApi = {
  getAll: async () => {
    return apiRequest('/api/model-papers');
  },
  
  upload: async (data: UploadModelPaperRequest) => {
    const formData = new FormData();
    
    data.files.forEach((file) => {
      formData.append('files', file);
    });
    
    formData.append('courseName', data.courseName);
    formData.append('year', data.year);
    if (data.yearName) {
      formData.append('yearName', data.yearName);
    }
    formData.append('semester', data.semester);
    formData.append('subject', data.subject);
    
    if (data.description) {
      formData.append('description', data.description);
    }
    
    return apiRequest('/api/model-papers/upload', {
      method: 'POST',
      body: formData,
      isFormData: true,
    });
  },
  
  delete: async (modelPaperId: string) => {
    return apiRequest(`/api/model-papers/${modelPaperId}`, {
      method: 'DELETE',
    });
  },
  
  generatePrediction: async (modelPaperId: string) => {
    return apiRequest(`/api/model-papers/${modelPaperId}/generate-prediction`, {
      method: 'POST',
    });
  },
  
  search: async (params: {
    courseName?: string;
    year?: string;
    semester?: string;
    subject?: string;
  }) => {
    const queryParams = new URLSearchParams();
    if (params.courseName) queryParams.append('courseName', params.courseName);
    if (params.year) queryParams.append('year', params.year);
    if (params.semester) queryParams.append('semester', params.semester);
    if (params.subject) queryParams.append('subject', params.subject);
    
    return apiRequest(`/api/model-papers/search?${queryParams.toString()}`);
  },
  
  getCourses: async () => {
    return apiRequest('/api/model-papers/courses');
  },
};

// ============================================
// PREDICTIONS API
// ============================================

export interface Prediction {
  id: string;
  model_paper_id: string;
  course_name: string;
  year: string;
  academic_year?: string;
  semester: string;
  subject: string;
  predicted_questions: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  processed_at: string;
  error_message?: string;
}

export const predictionsApi = {
  getAll: async () => {
    return apiRequest('/api/model-paper-predictions/predictions');
  },
  
  getById: async (predictionId: string) => {
    return apiRequest(`/api/model-paper-predictions/predictions/${predictionId}`);
  },
  
  predict: async (modelPaperId: string) => {
    return apiRequest(`/api/model-paper-predictions/predict/${modelPaperId}`, {
      method: 'POST',
    });
  },
  
  getByModelPaperId: async (modelPaperId: string) => {
    return apiRequest(`/api/model-paper-predictions/predictions?model_paper_id=${encodeURIComponent(modelPaperId)}`);
  },

  retry: async (predictionId: string) => {
    return apiRequest(`/api/model-paper-predictions/predictions/${predictionId}/retry`, {
      method: 'POST',
    });
  },

  delete: async (predictionId: string) => {
    return apiRequest(`/api/model-paper-predictions/predictions/${predictionId}`, {
      method: 'DELETE',
    });
  },
};

// ============================================
// HEALTH API
// ============================================

export const healthApi = {
  check: async () => {
    return apiRequest('/health');
  },
  
  detailed: async () => {
    return apiRequest('/health/detailed');
  },
  
  vectorStores: async () => {
    return apiRequest('/health/vectorstores');
  },
};

// ============================================
// CURRICULUM API
// ============================================

export interface CurriculumSubject {
  code: string;
  name: string;
  type: string;
  category?: string;
  units: Array<{
    number: string | number;
    title?: string;
    name?: string;
    topics: string[];
  }>;
}

export interface CurriculumData {
  university?: string;
  regulation?: string;
  course: string;
  year?: number;
  semester?: number;
  subjects?: CurriculumSubject[];
  years?: Array<{
    year: number;
    semesters: Array<{
      semester: number;
      subjects: CurriculumSubject[];
    }>;
  }>;
}

export interface CurriculumCreateRequest {
  curriculum_type: "university" | "pci";
  university?: string;
  regulation?: string;
  course: string;
  effective_year?: string;
  curriculum_data: CurriculumData;
  auto_map_pci?: boolean;
}

export interface CurriculumValidationResponse {
  valid: boolean;
  errors: Array<{
    type: "error" | "warning";
    location: string;
    issue: string;
  }>;
  warnings: Array<{
    type: "error" | "warning";
    location: string;
    issue: string;
  }>;
  stats?: {
    years: number;
    semesters: number;
    subjects: number;
    units: number;
    topics: number;
    theory: number;
    practical: number;
    electives: number;
  };
  normalized_data?: CurriculumData;
}

export interface CurriculumResponse {
  id: number;
  university?: string;
  regulation?: string;
  course: string;
  effective_year?: string;
  curriculum_type: string;
  stats?: {
    years: number;
    semesters: number;
    subjects: number;
    units: number;
    topics: number;
    theory: number;
    practical: number;
    electives: number;
  };
  status: string;
  created_at: string;
  updated_at?: string;
  display_name: string;
}

export interface CurriculumListResponse {
  curricula: CurriculumResponse[];
  total: number;
}

export interface CurriculumBatchCreateRequest {
  items: CurriculumCreateRequest[];
}

export interface CurriculumBatchItemResult {
  index: number;
  success: boolean;
  id?: number;
  display_name?: string;
  error?: string;
}

export interface CurriculumBatchResponse {
  results: CurriculumBatchItemResult[];
  inserted: number;
}

export const curriculumApi = {
  validate: async (data: CurriculumCreateRequest): Promise<CurriculumValidationResponse> => {
    return apiRequest<CurriculumValidationResponse>('/api/curriculum/validate', {
      method: 'POST',
      body: data,
    });
  },

  create: async (data: CurriculumCreateRequest): Promise<CurriculumResponse> => {
    return apiRequest<CurriculumResponse>('/api/curriculum', {
      method: 'POST',
      body: data,
    });
  },

  createBatch: async (data: CurriculumBatchCreateRequest): Promise<CurriculumBatchResponse> => {
    return apiRequest<CurriculumBatchResponse>('/api/curriculum/batch', {
      method: 'POST',
      body: data,
    });
  },

  getAll: async (curriculum_type?: string): Promise<CurriculumListResponse> => {
    const url = curriculum_type 
      ? `/api/curriculum?curriculum_type=${curriculum_type}`
      : '/api/curriculum';
    return apiRequest<CurriculumListResponse>(url);
  },

  getById: async (curriculumId: number): Promise<any> => {
    return apiRequest(`/api/curriculum/${curriculumId}`);
  },

  getBatch: async (ids: number[]): Promise<{ curricula: any[] }> => {
    const idsParam = ids.join(',');
    return apiRequest<{ curricula: any[] }>(`/api/curriculum/batch?ids=${idsParam}`);
  },

  update: async (curriculumId: number, data: CurriculumCreateRequest): Promise<CurriculumResponse> => {
    return apiRequest<CurriculumResponse>(`/api/curriculum/${curriculumId}`, {
      method: 'PUT',
      body: data,
    });
  },
};

// Topic Mapping Types and API
export interface TopicMappingItem {
  university_topic: string;
  university_unit_number: number;
  pci_topic: string;
  pci_subject_code?: string;
  pci_unit_number?: number;
  pci_unit_title?: string;
}

export interface TopicMappingSaveRequest {
  university_name: string;
  regulation?: string;
  university_subject_code: string;
  topic_mappings: TopicMappingItem[];
}

export interface TopicMappingSaveResponse {
  success: boolean;
  saved_count: number;
  message: string;
}

export interface TopicMappingResponse {
  id: number;
  topic_slug: string;
  pci_topic: string;
  pci_subject_code?: string;
  pci_unit_number?: number;
  pci_unit_title?: string;
  university_topic: string;
  university_subject_code: string;
  university_unit_number: number;
  university_name?: string;
  regulation?: string;
  created_at?: string;
  updated_at?: string;
}

export const topicMappingApi = {
  save: async (data: TopicMappingSaveRequest): Promise<TopicMappingSaveResponse> => {
    return apiRequest<TopicMappingSaveResponse>('/api/curriculum/topic-mappings', {
      method: 'POST',
      body: data,
    });
  },
  
  get: async (university_name?: string, university_subject_code?: string): Promise<TopicMappingResponse[]> => {
    const params = new URLSearchParams();
    if (university_name) params.append('university_name', university_name);
    if (university_subject_code) params.append('university_subject_code', university_subject_code);
    const queryString = params.toString();
    const url = queryString ? `/api/curriculum/topic-mappings?${queryString}` : '/api/curriculum/topic-mappings';
    return apiRequest<TopicMappingResponse[]>(url);
  },
};

// Export API base URL for reference
export { API_BASE_URL };
