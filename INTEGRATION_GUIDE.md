# Frontend-Backend Integration Guide

## Overview

This document provides a comprehensive guide for integrating the new frontend UI (`web/`) with the existing backend (`api/`).

## What Was Done

### 1. Created API Service Layer (`web/lib/api.ts`)

A complete API service layer was created with:
- **Authentication helpers**: `getToken()`, `setToken()`, `removeToken()`, `isAuthenticated()`
- **API request wrapper**: Handles auth headers, JSON/FormData, error handling
- **Typed API modules**:
  - `authApi` - Login, register, verify, logout
  - `documentsApi` - CRUD operations, upload, process
  - `videosApi` - CRUD operations, upload, validate
  - `foldersApi` - Folder structure management
  - `aiApi` - AI chat, templates
  - `notesApi` - Notes generation and management
  - `modelPapersApi` - Model paper management
  - `predictionsApi` - Prediction management
  - `healthApi` - Health checks

### 2. Updated Components

| Component | Changes Made |
|-----------|-------------|
| `login-form.tsx` | Changed from mock localStorage to actual `authApi.login()` call |
| `documents-view.tsx` | Fetches from `documentsApi.getAll()`, real delete/process |
| `upload-modal.tsx` | Calls `documentsApi.upload()` with proper folder structure |
| `videos-view.tsx` | Fetches from `videosApi.getAll()`, real delete |
| `upload-video-modal.tsx` | Calls `videosApi.upload()` with proper structure |
| `ai-chat-view.tsx` | Fetches processed docs, calls `aiApi.ask()` |
| `notes-view.tsx` | Fetches docs/notes, calls `notesApi.generate()` |
| `predictions-view.tsx` | Fetches from `predictionsApi.getAll()` |

### 3. Environment Configuration

Created `.env.local` with:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Safe Integration Plan

### Phase 1: Backend Verification (Before Frontend Changes)

1. **Start the backend server**:
   ```bash
   cd api
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. **Verify endpoints work**:
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Auth test
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "test", "password": "test123"}'
   ```

### Phase 2: Frontend Setup

1. **Install dependencies** (if not already):
   ```bash
   cd web
   npm install
   ```

2. **Configure environment**:
   - Copy `.env.local.example` to `.env.local`
   - Update `NEXT_PUBLIC_API_URL` if backend is not on localhost:8000

3. **Start frontend**:
   ```bash
   npm run dev
   ```

### Phase 3: Testing Checklist

| Feature | Test Steps | Expected Result |
|---------|------------|-----------------|
| **Login** | Enter username/password, click Sign In | Redirects to /dashboard, token stored |
| **Documents List** | Navigate to /documents | Shows documents from backend |
| **Document Upload** | Click Upload, select file, complete wizard | File uploaded, appears in list |
| **Document Delete** | Click delete on a document | Document removed from list |
| **Videos List** | Navigate to /videos | Shows videos from backend |
| **Video Upload** | Click Upload, enter URL, complete wizard | Video added to list |
| **AI Chat** | Navigate to /ai-assistant, ask question | Gets response from AI |
| **Notes** | Navigate to /notes, click Generate | Notes generated for document |
| **Predictions** | Navigate to /predictions | Shows predictions list |

### Phase 4: CORS Configuration

If you encounter CORS errors, ensure the backend has proper CORS settings in `api/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.durranis.ai"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## API Endpoint Mapping

| Frontend Action | Backend Endpoint | Method |
|-----------------|------------------|--------|
| Login | `/api/auth/login` | POST |
| Get Documents | `/api/documents` | GET |
| Upload Document | `/api/documents/upload` | POST |
| Process Document | `/api/documents/{id}/process` | POST |
| Delete Document | `/api/documents/{id}` | DELETE |
| Get Videos | `/api/videos` | GET |
| Upload Video | `/api/videos/upload` | POST |
| Delete Video | `/api/videos/{id}` | DELETE |
| AI Ask | `/api/ai/ask` | POST |
| Generate Notes | `/api/notes/generate` | POST |
| Get Notes | `/api/notes` | GET |
| Get Predictions | `/api/model-paper-predictions` | GET |

## Request/Response Formats

### Login
```typescript
// Request
POST /api/auth/login
{ "username": "string", "password": "string" }

// Response
{
  "access_token": "string",
  "token_type": "bearer",
  "user": { "id": "string", "username": "string", ... }
}
```

### Document Upload
```typescript
// Request (FormData)
POST /api/documents/upload
- files: File[]
- folderStructure: JSON string {
    "courseName": "B.Pharm",
    "yearSemester": "1_1",
    "subjectName": "Subject Name",
    "unitName": "Unit 1",
    "topic": "Topic Name"
  }
```

### AI Ask
```typescript
// Request
POST /api/ai/ask
{
  "question": "string",
  "document_id": "optional string",
  "filter": {
    "subject": "optional string",
    "unit": "optional string",
    "topic": "optional string"
  }
}

// Response
{
  "answer": "string",
  "sources": [{ "content": "string", "metadata": {} }]
}
```

## Troubleshooting

### "Failed to fetch" errors
- Check if backend is running on the correct port
- Verify CORS is configured correctly
- Check browser console for detailed error

### "Unauthorized" errors
- Token may have expired - try logging in again
- Check if token is being sent in Authorization header

### "Not Found" errors
- Verify the endpoint exists in the backend
- Check for typos in the API URL

## Files Modified

1. `web/lib/api.ts` - NEW: Complete API service layer
2. `web/.env.local` - NEW: Environment configuration
3. `web/.env.local.example` - NEW: Example env file
4. `web/components/auth/login-form.tsx` - Updated for API
5. `web/components/documents/documents-view.tsx` - Updated for API
6. `web/components/documents/upload-modal.tsx` - Updated for API
7. `web/components/documents/document-card.tsx` - Added "processing" status
8. `web/components/videos/videos-view.tsx` - Updated for API
9. `web/components/videos/upload-video-modal.tsx` - Updated for API
10. `web/components/ai-assistant/ai-chat-view.tsx` - Updated for API
11. `web/components/notes/notes-view.tsx` - Updated for API
12. `web/components/predictions/predictions-view.tsx` - Updated for API

## Next Steps

1. **Test all endpoints** with the backend running
2. **Add error boundaries** for better error handling
3. **Implement token refresh** if needed
4. **Add loading skeletons** for better UX
5. **Implement proper logout** that clears all state
