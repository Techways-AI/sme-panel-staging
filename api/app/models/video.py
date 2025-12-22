from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class VideoUpload(BaseModel):
    videoUrl: Optional[str] = None
    videoUrls: Optional[List[str]] = None
    folderStructure: Dict[str, str]

class VideoValidation(BaseModel):
    url: str

class VideoMetadata(BaseModel):
    id: str
    url: str
    dateAdded: str
    folderStructure: Dict[str, str]

class VideoUpdate(BaseModel):
    url: Optional[str] = None
    folderStructure: Optional[Dict[str, str]] = None

class VideoResponse(BaseModel):
    status: str
    message: str
    videos: Optional[List[VideoMetadata]] = None 