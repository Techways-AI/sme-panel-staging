from typing import List, Optional, Dict
from pydantic import BaseModel

class SemesterOption(BaseModel):
    label: str
    value: str

class SemesterInfo(BaseModel):
    label: str
    value: str

class UnitInfo(BaseModel):
    name: str
    value: str

class TopicInfo(BaseModel):
    name: str
    value: str

class FolderStructure(BaseModel):
    courseName: str
    yearSemester: str
    subjectName: str
    unitName: str
    topic: str
    fullPath: Optional[str] = None

class FolderNode(BaseModel):
    name: str
    type: str = "folder"
    children: List['FolderNode'] = []
    documents: List[Dict] = []
    videos: List[Dict] = []

class FolderRename(BaseModel):
    old_path: str
    new_path: str

class FolderResponse(BaseModel):
    status: str
    message: str
    documents_updated: Optional[bool] = None 