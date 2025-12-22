# SME Admin Panel - Backend Development Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Data Models](#data-models)
4. [API Endpoints](#api-endpoints)
5. [Authentication & Authorization](#authentication--authorization)
6. [Feature-wise Implementation Guide](#feature-wise-implementation-guide)
7. [File Storage Requirements](#file-storage-requirements)
8. [AI Integration](#ai-integration)
9. [Database Schema](#database-schema)

---

## 1. Project Overview

### What is this project?
The SME Admin Panel is an educational content management system designed for pharmaceutical education (B.Pharm). It allows Subject Matter Experts (SMEs) and administrators to:
- Upload and manage educational documents, videos, and notes
- Organize content according to PCI (Pharmacy Council of India) master curriculum
- Map multiple university curricula to the PCI standard
- Generate AI-powered study notes and exam predictions
- Manage university-specific content like previous year question papers

### Key Concepts

#### PCI Master Curriculum
- The standardized curriculum defined by Pharmacy Council of India
- Acts as the "single source of truth" for content organization
- Structure: Subject → Unit → Topic
- All content is stored against PCI topics and then "mapped" to university syllabi

#### University Curricula
- Universities like JNTUH, Osmania have their own syllabi
- These are mapped to PCI master curriculum
- Content uploaded to PCI automatically becomes available to all mapped universities
- University-specific content (PYQs, notifications) is stored separately

---

## 2. System Architecture

### Frontend
- Next.js 16 (App Router)
- React 19
- Tailwind CSS with shadcn/ui components
- Client-side state management with React hooks and SWR

### Backend Requirements
- RESTful API or GraphQL
- File storage system (S3-compatible recommended)
- Database (PostgreSQL recommended)
- AI/LLM integration for notes and predictions
- Real-time capabilities (optional, for processing status)

---

## 3. Data Models

### 3.1 User
\`\`\`typescript
interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "sme";
  status: "active" | "inactive";
  createdAt: Date;
  updatedAt: Date;
  lastActiveAt: Date;
}
\`\`\`

**Role Permissions:**
- **Admin**: Full access to all features
  - Upload Documents, Videos, Model Papers
  - Generate Notes, Predictions
  - AI Assistant access
  - Manage Prompt Templates
  - View Directory
  - Manage Users
  - Curriculum Management
  
- **SME**: Limited content creation access
  - Upload Documents, Videos, Model Papers
  - Generate Notes
  - AI Assistant access

### 3.2 PCI Curriculum

\`\`\`typescript
interface PCISubject {
  id: string;
  code: string;              // e.g., "BP101T"
  name: string;              // e.g., "Human Anatomy and Physiology I"
  type: "Theory" | "Practical";
  credits: number;
  semester: number;          // 1-8
  year: number;              // 1-4
  units: PCIUnit[];
  createdAt: Date;
  updatedAt: Date;
}

interface PCIUnit {
  id: string;
  subjectId: string;
  number: number;            // 1, 2, 3, etc.
  title: string;
  topics: PCITopic[];
}

interface PCITopic {
  id: string;
  unitId: string;
  name: string;
  order: number;             // For sorting
}
\`\`\`

### 3.3 University Curriculum

\`\`\`typescript
interface University {
  id: string;
  name: string;              // e.g., "JNTUH"
  regulation: string;        // e.g., "R20"
  displayName: string;       // e.g., "JNTUH R20 - B.Pharm"
  course: string;            // e.g., "B.Pharm"
  effectiveYear: string;     // e.g., "2020"
  status: "active" | "inactive";
  createdAt: Date;
  updatedAt: Date;
}

interface UniversitySubject {
  id: string;
  universityId: string;
  code: string;
  name: string;
  type: "Theory" | "Practical" | "Mandatory";
  year: number;
  semester: number;
  credits: number;
  pciMappingId: string | null;     // Link to PCI subject
  isUniSpecific: boolean;          // No PCI equivalent
  units: UniversityUnit[];
}

interface UniversityUnit {
  id: string;
  universitySubjectId: string;
  number: number;
  title: string;
  pciUnitId: string | null;        // Link to PCI unit
}
\`\`\`

### 3.4 Documents

\`\`\`typescript
interface Document {
  id: string;
  filename: string;
  originalFilename: string;
  fileUrl: string;                  // S3/storage URL
  fileSize: number;                 // In bytes
  mimeType: string;
  
  // Location in PCI curriculum
  pciSubjectId: string;
  pciUnitId: string;
  pciTopicId: string;
  
  status: "pending" | "processing" | "processed" | "failed";
  processingError?: string;
  
  // RAG processing results
  embeddingsGenerated: boolean;
  chunksCount: number;
  
  // Coverage tracking
  coveragePercentage?: number;
  
  uploadedBy: string;               // User ID
  createdAt: Date;
  updatedAt: Date;
}
\`\`\`

### 3.5 Videos

\`\`\`typescript
interface Video {
  id: string;
  title: string;
  url: string;                      // YouTube/Vimeo URL
  platform: "youtube" | "vimeo" | "other";
  duration?: number;                // In seconds
  thumbnailUrl?: string;
  
  // Location in PCI curriculum
  pciSubjectId: string;
  pciUnitId: string;
  pciTopicId: string;
  
  uploadedBy: string;
  createdAt: Date;
  updatedAt: Date;
}
\`\`\`

### 3.6 Notes

\`\`\`typescript
interface GeneratedNotes {
  id: string;
  documentId: string;               // Source document
  content: string;                  // Markdown content
  
  // AI generation metadata
  modelUsed: string;
  promptTemplateId: string;
  tokensUsed: number;
  
  generatedBy: string;              // User ID
  createdAt: Date;
  updatedAt: Date;
}
\`\`\`

### 3.7 Predictions

\`\`\`typescript
interface Prediction {
  id: string;
  title: string;
  
  // Scope
  universityId: string;
  subjectId: string;
  
  // Source documents used
  documentIds: string[];
  
  status: "processing" | "completed" | "failed";
  confidence: number;               // 0-100
  
  // Results
  result?: PredictionResult;
  error?: string;
  
  generatedBy: string;
  createdAt: Date;
  updatedAt: Date;
}

interface PredictionResult {
  predictedTopics: Array<{
    topic: string;
    probability: number;
    unit: string;
    reasoning: string;
  }>;
  examPattern?: {
    sections: Array<{
      name: string;
      marks: number;
      questionsCount: number;
    }>;
  };
}
\`\`\`

### 3.8 Prompt Templates

\`\`\`typescript
interface PromptTemplate {
  id: string;
  name: string;                     // e.g., "Summary", "Questions", "Study Notes"
  category: string;
  content: string;                  // Template with {{placeholders}}
  isDefault: boolean;
  createdBy: string;
  createdAt: Date;
  updatedAt: Date;
}
\`\`\`

### 3.9 University-Specific Content

\`\`\`typescript
// Previous Year Question Papers
interface PreviousYearPaper {
  id: string;
  universityId: string;
  subjectId: string;                // University subject ID
  examYear: number;                 // 2020, 2021, etc.
  examType: "regular" | "supplementary";
  semester: number;
  
  filename: string;
  fileUrl: string;
  fileSize: number;
  
  uploadedBy: string;
  createdAt: Date;
}

// Exam Patterns
interface ExamPattern {
  id: string;
  universityId: string;
  year: number;
  description: string;
  
  filename: string;
  fileUrl: string;
  
  uploadedBy: string;
  createdAt: Date;
}

// University Notifications
interface UniversityNotification {
  id: string;
  universityId: string;
  title: string;
  description?: string;
  
  filename?: string;
  fileUrl?: string;
  
  uploadedBy: string;
  createdAt: Date;
}

// Extra Materials
interface ExtraMaterial {
  id: string;
  universityId: string;
  subjectId?: string;
  title: string;
  description?: string;
  
  filename: string;
  fileUrl: string;
  
  uploadedBy: string;
  createdAt: Date;
}
\`\`\`

### 3.10 Content Migration Tracking

\`\`\`typescript
interface MigrationItem {
  id: string;
  documentId: string;
  
  // Old location (before PCI migration)
  oldUniversityId: string;
  oldSubjectId: string;
  oldUnitId: string;
  
  // Suggested PCI mapping (AI-generated)
  suggestedPciSubjectId?: string;
  suggestedPciUnitId?: string;
  suggestedPciTopicId?: string;
  confidence: number;               // 0-100
  
  // Final mapping
  finalPciSubjectId?: string;
  finalPciUnitId?: string;
  finalPciTopicId?: string;
  isUniSpecific: boolean;
  
  status: "pending" | "migrated" | "needs-review" | "skipped";
  
  migratedBy?: string;
  migratedAt?: Date;
}
\`\`\`

---

## 4. API Endpoints

### 4.1 Authentication

\`\`\`
POST   /api/auth/login              - Login with email/password
POST   /api/auth/logout             - Logout
GET    /api/auth/me                 - Get current user
POST   /api/auth/refresh            - Refresh access token
\`\`\`

### 4.2 Users (Admin only)

\`\`\`
GET    /api/users                   - List all users
POST   /api/users                   - Create new user
GET    /api/users/:id               - Get user details
PATCH  /api/users/:id               - Update user
DELETE /api/users/:id               - Delete user
PATCH  /api/users/:id/status        - Activate/deactivate user
\`\`\`

### 4.3 PCI Curriculum

\`\`\`
GET    /api/pci/subjects            - List all PCI subjects
GET    /api/pci/subjects/:id        - Get subject with units and topics
POST   /api/pci/subjects            - Create subject (Admin)
PATCH  /api/pci/subjects/:id        - Update subject
DELETE /api/pci/subjects/:id        - Delete subject

GET    /api/pci/units/:subjectId    - List units for a subject
POST   /api/pci/units               - Create unit
PATCH  /api/pci/units/:id           - Update unit
DELETE /api/pci/units/:id           - Delete unit

GET    /api/pci/topics/:unitId      - List topics for a unit
POST   /api/pci/topics              - Create topic
PATCH  /api/pci/topics/:id          - Update topic
DELETE /api/pci/topics/:id          - Delete topic

POST   /api/pci/import              - Bulk import PCI curriculum from JSON
GET    /api/pci/export              - Export entire PCI curriculum as JSON
GET    /api/pci/stats               - Get curriculum statistics
\`\`\`

### 4.4 Universities

\`\`\`
GET    /api/universities                     - List all universities
POST   /api/universities                     - Create university
GET    /api/universities/:id                 - Get university details
PATCH  /api/universities/:id                 - Update university
DELETE /api/universities/:id                 - Delete university

GET    /api/universities/:id/subjects        - List subjects
POST   /api/universities/:id/import          - Import curriculum JSON
GET    /api/universities/:id/export          - Export curriculum

# University-PCI Mappings
GET    /api/universities/:id/mappings        - Get all mappings
POST   /api/universities/:id/mappings        - Create mapping
PATCH  /api/universities/:id/mappings/:mapId - Update mapping
DELETE /api/universities/:id/mappings/:mapId - Remove mapping
POST   /api/universities/:id/auto-map        - Auto-map by name similarity
\`\`\`

### 4.5 Documents

\`\`\`
GET    /api/documents               - List documents (with filters)
POST   /api/documents               - Upload document(s)
GET    /api/documents/:id           - Get document details
PATCH  /api/documents/:id           - Update document metadata
DELETE /api/documents/:id           - Delete document
POST   /api/documents/:id/reprocess - Re-process document for RAG

# Query params for GET /api/documents:
# - status: pending|processing|processed|failed
# - subjectId: filter by PCI subject
# - unitId: filter by PCI unit
# - year: filter by year (1-4)
# - semester: filter by semester (1-8)
# - search: text search in filename
# - page, limit: pagination
\`\`\`

### 4.6 Videos

\`\`\`
GET    /api/videos                  - List videos (with filters)
POST   /api/videos                  - Add video URL
GET    /api/videos/:id              - Get video details
PATCH  /api/videos/:id              - Update video
DELETE /api/videos/:id              - Delete video

# Similar query params as documents
\`\`\`

### 4.7 Notes

\`\`\`
GET    /api/notes                   - List generated notes
POST   /api/notes/generate          - Generate notes from document
GET    /api/notes/:id               - Get notes content
DELETE /api/notes/:id               - Delete notes

# Request body for POST /api/notes/generate:
{
  "documentId": "string",
  "templateId": "string"       // Optional, uses default if not provided
}
\`\`\`

### 4.8 Predictions

\`\`\`
GET    /api/predictions             - List predictions
POST   /api/predictions             - Create new prediction
GET    /api/predictions/:id         - Get prediction details
DELETE /api/predictions/:id         - Delete prediction
POST   /api/predictions/:id/retry   - Retry failed prediction

# Request body for POST /api/predictions:
{
  "title": "string",
  "universityId": "string",
  "subjectId": "string",
  "documentIds": ["string"]    // Documents to analyze
}
\`\`\`

### 4.9 Prompt Templates

\`\`\`
GET    /api/templates               - List all templates
POST   /api/templates               - Create template
GET    /api/templates/:id           - Get template
PATCH  /api/templates/:id           - Update template
DELETE /api/templates/:id           - Delete template
\`\`\`

### 4.10 University Content

\`\`\`
# Previous Year Papers
GET    /api/universities/:id/pyqs
POST   /api/universities/:id/pyqs
DELETE /api/universities/:id/pyqs/:pyqId

# Exam Patterns
GET    /api/universities/:id/patterns
POST   /api/universities/:id/patterns
DELETE /api/universities/:id/patterns/:patternId

# Notifications
GET    /api/universities/:id/notifications
POST   /api/universities/:id/notifications
DELETE /api/universities/:id/notifications/:notifId

# Extra Materials
GET    /api/universities/:id/materials
POST   /api/universities/:id/materials
DELETE /api/universities/:id/materials/:materialId
\`\`\`

### 4.11 Content Coverage Analytics

\`\`\`
GET    /api/analytics/coverage              - Get overall coverage stats
GET    /api/analytics/coverage/by-year      - Coverage breakdown by year
GET    /api/analytics/coverage/by-subject   - Coverage per subject
GET    /api/analytics/gaps                  - Identify content gaps
GET    /api/analytics/export                - Export gap report (Excel)

# Query params:
# - curriculum: "pci" | universityId
\`\`\`

### 4.12 Content Migration

\`\`\`
GET    /api/migration/items                 - List migration items
GET    /api/migration/stats                 - Get migration progress stats
POST   /api/migration/:id/accept            - Accept AI suggestion
POST   /api/migration/:id/edit              - Save custom mapping
POST   /api/migration/:id/skip              - Skip document
POST   /api/migration/:id/uni-specific      - Mark as university-specific
POST   /api/migration/bulk-accept           - Bulk accept selected
POST   /api/migration/bulk-skip             - Bulk skip selected
\`\`\`

### 4.13 AI Assistant (Chat)

\`\`\`
POST   /api/chat                    - Send message to AI assistant
GET    /api/chat/history            - Get chat history
DELETE /api/chat/history            - Clear chat history

# Request body for POST /api/chat:
{
  "message": "string",
  "documentIds": ["string"],        // Optional: specific docs to query
  "filters": {                       // Optional: filter documents
    "year": number,
    "semester": number,
    "subjectId": "string",
    "unitId": "string",
    "topicId": "string"
  }
}

# Response (streaming):
{
  "message": "string",
  "sources": [                      // Documents used for response
    {
      "documentId": "string",
      "documentName": "string",
      "relevanceScore": number
    }
  ]
}
\`\`\`

### 4.14 Directory/File Browser

\`\`\`
GET    /api/directory               - Get hierarchical content tree
GET    /api/directory/search        - Search content

# Query params for GET /api/directory:
# - view: "pci" | universityId
# - expand: comma-separated IDs to auto-expand
\`\`\`

---

## 5. Authentication & Authorization

### JWT-based Authentication
1. User logs in with email/password
2. Backend validates credentials
3. Returns access token (short-lived, ~15min) and refresh token (long-lived, ~7days)
4. Client stores tokens securely
5. Access token sent in Authorization header: `Bearer <token>`
6. When access token expires, use refresh token to get new access token

### Session Validation
Every authenticated request should:
1. Extract JWT from Authorization header
2. Verify JWT signature
3. Check token expiration
4. Check user status is "active"
5. Attach user object to request context

### Role-Based Access Control
\`\`\`typescript
// Middleware example
function requireRole(allowedRoles: string[]) {
  return (req, res, next) => {
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: "Insufficient permissions" });
    }
    next();
  };
}

// Usage
app.delete("/api/users/:id", requireRole(["admin"]), deleteUser);
\`\`\`

---

## 6. Feature-wise Implementation Guide

### 6.1 Dashboard

**What it shows:**
- Document stats: Total, Processed, Unprocessed counts
- Content stats: Videos, Notes, University Content counts
- Recent Documents list (last 5)
- Recent Videos list (last 5)

**Backend requirements:**
\`\`\`
GET /api/dashboard/stats
Response:
{
  "documents": { "total": 147, "processed": 120, "unprocessed": 27 },
  "videos": 45,
  "notes": 80,
  "universityContent": 156,
  "recentDocuments": [...],
  "recentVideos": [...]
}
\`\`\`

### 6.2 Document Upload Flow

**Step 1: Select Subject**
- Filter subjects by Year and Semester
- User selects a PCI subject from the list

**Step 2: Select Location**
- User selects Unit (dropdown)
- User selects Topic (dropdown) or enters custom topic

**Step 3: Upload**
- User uploads one or more files (drag-drop or browse)
- Supported formats: PDF, DOC, DOCX, images
- Max file size: 50MB per file

**Backend process after upload:**
1. Store file in object storage (S3)
2. Create Document record with status "pending"
3. Queue document for processing
4. Background job:
   - Extract text from document
   - Generate embeddings using AI model
   - Store embeddings in vector database
   - Update status to "processed"

**Universities info display:**
When a document is uploaded to PCI, show which universities will receive this content based on existing mappings.

### 6.3 Video Upload Flow

Same 3-step flow as documents, but:
- User enters video URL (YouTube/Vimeo)
- Backend validates URL and extracts metadata
- No processing required (just store the link)

### 6.4 Notes Generation

**Trigger:** User clicks "Generate Notes" on a processed document

**Process:**
1. Get document content/chunks
2. Apply selected prompt template
3. Send to LLM (OpenAI/Anthropic)
4. Store generated notes
5. Return notes to user

**Prompt template example:**
\`\`\`
Create detailed study notes from the following content. 
Organize them with clear headings, bullet points, and highlight 
important formulas or concepts:

{{document_content}}
\`\`\`

### 6.5 Predictions

**Trigger:** User creates new prediction

**Input:**
- Title for the prediction
- University (required)
- Subject (required)
- Select documents to analyze (optional)

**Process:**
1. Gather all relevant documents for the subject
2. Analyze past PYQs patterns
3. Use LLM to predict likely exam topics
4. Calculate confidence scores
5. Return structured prediction result

### 6.6 AI Assistant (Chat)

**How it works:**
1. User selects filters (Year, Semester, Subject, Unit, Topic)
2. User can select specific documents
3. User sends a question
4. Backend uses RAG (Retrieval Augmented Generation):
   - Convert question to embedding
   - Search vector DB for relevant document chunks
   - Build context from top matches
   - Send to LLM with context
   - Return response with source citations

**Important:** The sidebar filters determine which documents are searchable. If no filters are set, search across all documents.

### 6.7 University Mappings

**Purpose:** Map university subjects/units to PCI curriculum

**Mapping levels:**
1. **Subject-level:** Map university subject to PCI subject
2. **Unit-level:** Map individual units within a subject

**Mapping process:**
1. Display university subjects grouped by Year/Semester
2. For each unmapped subject, show dropdown to select PCI equivalent
3. Option to mark as "University-Specific" (no PCI equivalent)
4. After subject mapping, allow unit-level mapping refinement
5. Auto-map feature: Match subjects by name similarity

**Mapping statuses:**
- **Mapped (Full):** Subject and all units mapped
- **Partial:** Subject mapped but some units unmapped
- **Unmapped:** No PCI mapping yet

### 6.8 Content Migration Tool

**Purpose:** Migrate existing content from old university-based structure to PCI-based structure

**Process:**
1. AI suggests PCI mapping for each document based on:
   - Old location metadata
   - Document content analysis
   - Name similarity
2. Show suggestion with confidence score
3. User can: Accept, Edit, Mark as Uni-Specific, or Skip
4. Bulk actions supported

**AI suggestion logic:**
- Extract keywords from document name and content
- Match against PCI subjects/units/topics
- Return best match with confidence percentage

### 6.9 University-Specific Content

**Types:**
1. **Previous Year Papers (PYQs):** Past exam question papers
2. **Exam Patterns:** Marking schemes, exam structure
3. **Notifications:** University announcements
4. **Predictions:** AI-generated exam predictions (redirects to Predictions page)

**Each type has:**
- Subject filter (university subjects)
- Year filter (for PYQs)
- Upload modal
- Manage modal (search, filter, delete)

### 6.10 Content Coverage Analytics

**Stats calculated:**
- Documents coverage: (topics with docs / total topics) × 100
- Videos coverage: (topics with videos / total topics) × 100
- Notes coverage: (topics with notes / total topics) × 100
- Overall coverage: average or weighted average

**Gap report:**
- Subjects with no content
- Subjects missing videos
- Subjects missing notes
- Low coverage subjects (below 50%)

**Export:** Generate Excel file with multiple sheets (Summary, By Year, All Subjects, Gaps, Recommendations)

### 6.11 Curriculum Manager

**Two views:**

**1. PCI Master View:**
- Expandable tree: Subject → Unit → Topic
- Each topic shows content indicators (doc/video/notes icons)
- Search across subjects, units, topics

**2. University View:**
- Year pills (Year 1-4)
- Semester toggle (Sem 1/2)
- Table of subjects for selected year/semester

**Admin actions:**
- Add University: 3-step wizard (Basic info → Import JSON → Preview)
- Edit University: Update name, regulation, status
- Update Curriculum: Upload new JSON, show diff, apply changes
- Delete University: Confirmation with impact summary

**Curriculum JSON schema:**
\`\`\`json
{
  "university": "JNTUH",
  "regulation": "R20",
  "course": "B.Pharm",
  "years": {
    "Year 1": {
      "Semester 1": [
        {
          "code": "BP101T",
          "name": "Human Anatomy and Physiology I",
          "type": "Theory",
          "credits": 4,
          "units": [
            {
              "number": 1,
              "title": "Introduction to Human Body",
              "topics": ["Definition and scope", "Levels of organization"]
            }
          ]
        }
      ]
    }
  }
}
\`\`\`

### 6.12 Directory Browser

**Purpose:** Browse all content in a hierarchical tree view

**Two view modes:**

**1. PCI View:**
\`\`\`
Subject (BP101T - Human Anatomy...)
  └── Unit 1: Introduction
      └── Topic: Definition and scope
          ├── document.pdf
          ├── lecture.mp4
          └── notes.md
\`\`\`

**2. University View:**
\`\`\`
Year 1
  └── Semester 1
      └── Human Anatomy & Physiology I
          └── Unit 1
              ├── document.pdf
              └── video.mp4
\`\`\`

**File icons:**
- Document: FileText icon (gray)
- Video: Video icon (red)
- Notes: StickyNote icon (blue)

### 6.13 Access Management

**Features:**
- List all users with search
- Add new user (name, email, role)
- Edit user (name, email, role)
- Activate/Deactivate user
- Delete user

**Role permissions displayed:**
- Admin permissions list
- SME permissions list

---

## 7. File Storage Requirements

### Recommended Setup
- **Service:** AWS S3, Google Cloud Storage, or MinIO
- **Structure:**
  \`\`\`
  /documents/{user_id}/{document_id}/{filename}
  /pyqs/{university_id}/{subject_id}/{year}/{filename}
  /patterns/{university_id}/{year}/{filename}
  /notifications/{university_id}/{filename}
  /materials/{university_id}/{filename}
  \`\`\`

### File Processing Pipeline
1. **Upload:** File uploaded to temporary location
2. **Validation:** Check file type, size, virus scan
3. **Storage:** Move to permanent location with UUID
4. **Processing:** Queue for text extraction and embedding generation
5. **Cleanup:** Remove temporary files

### Presigned URLs
Generate presigned URLs for:
- File uploads (PUT)
- File downloads (GET)
- Expiry: 15 minutes for uploads, 1 hour for downloads

---

## 8. AI Integration

### Required AI Capabilities

**1. Text Embeddings**
- Model: OpenAI text-embedding-ada-002 or similar
- Use: Document search, RAG
- Vector DB: Pinecone, Weaviate, or pgvector

**2. Text Generation**
- Model: GPT-4, Claude, or similar
- Use: Notes generation, predictions, chat responses

**3. Document Processing**
- OCR for scanned documents
- PDF text extraction
- Chunking strategy: 500-1000 tokens per chunk with overlap

### RAG Implementation

\`\`\`typescript
async function generateChatResponse(message: string, documentIds: string[]) {
  // 1. Convert message to embedding
  const queryEmbedding = await embeddings.create(message);
  
  // 2. Search vector DB for relevant chunks
  const relevantChunks = await vectorDB.search({
    embedding: queryEmbedding,
    documentIds: documentIds,
    limit: 10
  });
  
  // 3. Build context
  const context = relevantChunks.map(c => c.text).join("\n\n");
  
  // 4. Generate response
  const response = await llm.chat({
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: `Context:\n${context}\n\nQuestion: ${message}` }
    ]
  });
  
  return {
    message: response.content,
    sources: relevantChunks.map(c => ({
      documentId: c.documentId,
      documentName: c.documentName,
      relevanceScore: c.score
    }))
  };
}
\`\`\`

---

## 9. Database Schema (PostgreSQL)

\`\`\`sql
-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'sme',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  last_active_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- PCI Curriculum
CREATE TABLE pci_subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(20) NOT NULL,
  credits INTEGER NOT NULL,
  semester INTEGER NOT NULL,
  year INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pci_units (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id UUID REFERENCES pci_subjects(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  title VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pci_topics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id UUID REFERENCES pci_units(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  "order" INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Universities
CREATE TABLE universities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  regulation VARCHAR(20) NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  course VARCHAR(50) NOT NULL,
  effective_year VARCHAR(10),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(name, regulation)
);

CREATE TABLE university_subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES universities(id) ON DELETE CASCADE,
  code VARCHAR(20) NOT NULL,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(20) NOT NULL,
  year INTEGER NOT NULL,
  semester INTEGER NOT NULL,
  credits INTEGER,
  pci_subject_id UUID REFERENCES pci_subjects(id),
  is_uni_specific BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE university_units (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_subject_id UUID REFERENCES university_subjects(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  title VARCHAR(255) NOT NULL,
  pci_unit_id UUID REFERENCES pci_units(id),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Documents
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename VARCHAR(255) NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  file_url TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  pci_subject_id UUID REFERENCES pci_subjects(id),
  pci_unit_id UUID REFERENCES pci_units(id),
  pci_topic_id UUID REFERENCES pci_topics(id),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  processing_error TEXT,
  embeddings_generated BOOLEAN DEFAULT FALSE,
  chunks_count INTEGER DEFAULT 0,
  coverage_percentage INTEGER,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Videos
CREATE TABLE videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  url TEXT NOT NULL,
  platform VARCHAR(20) NOT NULL,
  duration INTEGER,
  thumbnail_url TEXT,
  pci_subject_id UUID REFERENCES pci_subjects(id),
  pci_unit_id UUID REFERENCES pci_units(id),
  pci_topic_id UUID REFERENCES pci_topics(id),
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated Notes
CREATE TABLE generated_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  model_used VARCHAR(50),
  prompt_template_id UUID,
  tokens_used INTEGER,
  generated_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Predictions
CREATE TABLE predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  university_id UUID REFERENCES universities(id),
  subject_id UUID,
  document_ids UUID[],
  status VARCHAR(20) NOT NULL DEFAULT 'processing',
  confidence INTEGER DEFAULT 0,
  result JSONB,
  error TEXT,
  generated_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Prompt Templates
CREATE TABLE prompt_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  category VARCHAR(50),
  content TEXT NOT NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- University-Specific Content
CREATE TABLE previous_year_papers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES universities(id) ON DELETE CASCADE,
  subject_id UUID,
  exam_year INTEGER NOT NULL,
  exam_type VARCHAR(20) NOT NULL DEFAULT 'regular',
  semester INTEGER,
  filename VARCHAR(255) NOT NULL,
  file_url TEXT NOT NULL,
  file_size INTEGER,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE exam_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES universities(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  description TEXT,
  filename VARCHAR(255) NOT NULL,
  file_url TEXT NOT NULL,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE university_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES universities(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  filename VARCHAR(255),
  file_url TEXT,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE extra_materials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES universities(id) ON DELETE CASCADE,
  subject_id UUID,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  filename VARCHAR(255) NOT NULL,
  file_url TEXT NOT NULL,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Content Migration
CREATE TABLE migration_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES documents(id),
  old_university_id UUID,
  old_subject_id UUID,
  old_unit_id UUID,
  suggested_pci_subject_id UUID REFERENCES pci_subjects(id),
  suggested_pci_unit_id UUID REFERENCES pci_units(id),
  suggested_pci_topic_id UUID REFERENCES pci_topics(id),
  confidence INTEGER DEFAULT 0,
  final_pci_subject_id UUID REFERENCES pci_subjects(id),
  final_pci_unit_id UUID REFERENCES pci_units(id),
  final_pci_topic_id UUID REFERENCES pci_topics(id),
  is_uni_specific BOOLEAN DEFAULT FALSE,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  migrated_by UUID REFERENCES users(id),
  migrated_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Document Embeddings (if using pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),
  tokens_count INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Indexes for common queries
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_pci_subject ON documents(pci_subject_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_videos_pci_subject ON videos(pci_subject_id);
CREATE INDEX idx_university_subjects_university ON university_subjects(university_id);
CREATE INDEX idx_pyqs_university ON previous_year_papers(university_id);
\`\`\`

---

## Summary

This documentation covers all features of the SME Admin Panel frontend and provides the backend developer with:

1. **Complete data models** for all entities
2. **API endpoints** for every feature
3. **Authentication/authorization** requirements
4. **Feature-by-feature implementation guides**
5. **Database schema** ready to use
6. **AI integration** requirements for RAG and generation

The backend should be built to support:
- JWT authentication with role-based access
- File upload/storage with processing pipeline
- AI-powered features (notes, predictions, chat)
- Real-time status updates (optional)
- Excel export for analytics

For any questions about specific frontend behavior or expected responses, refer to the React components in the `/components` directory.
