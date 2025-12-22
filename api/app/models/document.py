from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class Tag(BaseModel):
    tags: List[str]

class ProcessOptions(BaseModel):
    chunkSize: int = 500
    chunkOverlap: int = 100
    includeMetadata: bool = True

class SourceMetadata(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    source: str
    folder_structure: Optional[str] = None
    topic: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    relevance: Optional[str] = None
    doc_id: Optional[str] = None
    chunk_text: Optional[str] = None
    document: Optional[str] = None
    score: Optional[float] = None

class QuestionResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    answer: str
    sources: List[SourceMetadata]

class QuestionInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    question: str
    document_id: Optional[str] = None
    year: Optional[str] = None
    semester: Optional[str] = None
    unit: Optional[str] = None
    topic: Optional[str] = None
    metadata_filter: Optional[dict] = None

class DocumentSearchParams(BaseModel):
    query: Optional[str] = None
    folder: Optional[str] = None
    semester: Optional[str] = None
    unit: Optional[str] = None
    topic: Optional[str] = None
    processed: Optional[bool] = None

class DocumentMetadata(BaseModel):
    id: str
    fileName: str
    fileSize: str
    uploadDate: str
    path: str
    processed: bool = False
    processing: bool = False
    folderStructure: Dict[str, str]

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folderStructure: Optional[Dict[str, str]] = None

class NotesGenerationRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    document_id: str
    course_name: str
    subject_name: str
    unit_name: str
    topic: str
    user_id: Optional[str] = None
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for notes generation. Higher values prevent truncation.")
    quality: Optional[str] = Field("standard", description="Notes quality level: 'high_quality', 'standard', or 'fast'")

class NotesGenerationResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    notes: str
    document_id: str
    generated_at: str
    metadata: Dict[str, Any] 