from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import os
import json
import shutil

from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..models.folder import (
    SemesterOption, SemesterInfo, UnitInfo, TopicInfo,
    FolderStructure, FolderNode, FolderRename, FolderResponse
)
from ..utils.file_utils import (
    sanitize_filename, ensure_dir, save_json, load_json,
    get_relative_path, delete_empty_parents
)
from ..config.settings import DATA_DIR

router = APIRouter(
    prefix="/api/folders",
    tags=["folders"]
)

# Global folder structure (will be loaded from disk)
folder_structure = {}

def build_folder_tree(path: str, base_path: str) -> FolderNode:
    """Build a tree structure of folders and files"""
    node = {
        "name": os.path.basename(path),
        "type": "folder",
        "children": [],
        "documents": [],
        "videos": []
    }
    
    try:
        # Get documents and videos
        documents = load_json(os.path.join(DATA_DIR, "documents.json")) or []
        videos = load_json(os.path.join(DATA_DIR, "videos.json")) or []
        
        # Filter documents and videos for this folder
        rel_path = get_relative_path(path, base_path)
        node["documents"] = [
            doc for doc in documents 
            if doc.get("folderStructure", {}).get("fullPath", "").startswith(rel_path)
        ]
        node["videos"] = [
            video for video in videos 
            if video.get("folderStructure", {}).get("fullPath", "").startswith(rel_path)
        ]
        
        # Get subfolders
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                child_node = build_folder_tree(item_path, base_path)
                node["children"].append(child_node)
                
    except Exception as e:
        print(f"Error building folder tree for {path}: {str(e)}")
    
    return node

@router.get("/structure")
async def get_folder_structure(auth_result: dict = Depends(get_dual_auth_user)):
    """Get the complete folder structure"""
    try:
        root_node = build_folder_tree(DATA_DIR, DATA_DIR)
        return {"structure": root_node}
    except Exception as e:
        print(f"[ERROR] Failed to get folder structure: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get folder structure")

@router.get("/semesters")
async def get_semesters(auth_result: dict = Depends(get_dual_auth_user)):
    """Get available semesters"""
    try:
        semesters = []
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                # Extract semester info from folder name
                parts = item.split("_")
                if len(parts) >= 2:
                    year = parts[0]
                    sem = parts[1]
                    label = f"Year {year} - Semester {sem}"
                    value = f"{year}_{sem}"
                    semesters.append(SemesterInfo(label=label, value=value))
        
        return {"semesters": semesters}
    except Exception as e:
        print(f"[ERROR] Failed to get semesters: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get semesters")

@router.get("/units/{semester}")
async def get_units(semester: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get available units for a semester"""
    try:
        units = []
        semester_path = os.path.join(DATA_DIR, semester)
        if not os.path.exists(semester_path):
            return {"units": []}
        
        for subject in os.listdir(semester_path):
            subject_path = os.path.join(semester_path, subject)
            if os.path.isdir(subject_path):
                for unit in os.listdir(subject_path):
                    unit_path = os.path.join(subject_path, unit)
                    if os.path.isdir(unit_path):
                        units.append(UnitInfo(name=unit, value=unit))
        
        return {"units": units}
    except Exception as e:
        print(f"[ERROR] Failed to get units: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get units")

@router.get("/topics/{semester}/{unit}")
async def get_topics(semester: str, unit: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get available topics for a unit"""
    try:
        topics = []
        unit_path = os.path.join(DATA_DIR, semester, unit)
        if not os.path.exists(unit_path):
            return {"topics": []}
        
        for topic in os.listdir(unit_path):
            topic_path = os.path.join(unit_path, topic)
            if os.path.isdir(topic_path):
                topics.append(TopicInfo(name=topic, value=topic))
        
        return {"topics": topics}
    except Exception as e:
        print(f"[ERROR] Failed to get topics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get topics")

@router.post("/create")
async def create_folder(folder: FolderStructure, auth_result: dict = Depends(get_dual_auth_user)):
    """Create a new folder"""
    try:
        # Validate inputs
        if not all([
            folder.courseName,
            folder.yearSemester,
            folder.subjectName,
            folder.unitName,
            folder.topic
        ]):
            return JSONResponse(
                status_code=400,
                content={"detail": "All folder components are required"}
            )
        
        # Build folder path
        folder_path = os.path.join(
            DATA_DIR,
            sanitize_filename(folder.courseName),
            sanitize_filename(folder.yearSemester),
            sanitize_filename(folder.subjectName),
            sanitize_filename(folder.unitName),
            sanitize_filename(folder.topic)
        )
        
        # Check if folder exists
        if os.path.exists(folder_path):
            return JSONResponse(
                status_code=400,
                content={"detail": "Folder already exists"}
            )
        
        # Create folder
        os.makedirs(folder_path, exist_ok=True)
        
        return {
            "status": "success",
            "message": "Folder created successfully",
            "path": get_relative_path(folder_path, DATA_DIR)
        }
        
    except Exception as e:
        print(f"Create folder error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")

@router.post("/rename")
async def rename_folder(rename: FolderRename, auth_result: dict = Depends(get_dual_auth_user)):
    """Rename a folder"""
    try:
        old_path = os.path.join(DATA_DIR, rename.old_path)
        new_path = os.path.join(DATA_DIR, rename.new_path)
        
        # Validate paths
        if not os.path.exists(old_path):
            raise HTTPException(status_code=404, detail="Source folder not found")
        
        if os.path.exists(new_path):
            raise HTTPException(status_code=400, detail="Destination folder already exists")
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        
        # Move folder
        shutil.move(old_path, new_path)
        
        # Update document and video paths
        documents = load_json(os.path.join(DATA_DIR, "documents.json")) or []
        videos = load_json(os.path.join(DATA_DIR, "videos.json")) or []
        
        documents_updated = 0
        for doc in documents:
            if doc.get("path", "").startswith(old_path):
                doc["path"] = doc["path"].replace(old_path, new_path)
                doc["folderStructure"]["fullPath"] = get_relative_path(new_path, DATA_DIR)
                documents_updated += 1
        
        for video in videos:
            if video.get("folderStructure", {}).get("fullPath", "").startswith(rename.old_path):
                video["folderStructure"]["fullPath"] = video["folderStructure"]["fullPath"].replace(
                    rename.old_path, rename.new_path
                )
        
        # Save updated lists
        save_json(documents, os.path.join(DATA_DIR, "documents.json"))
        save_json(videos, os.path.join(DATA_DIR, "videos.json"))
        
        return {
            "status": "success",
            "message": "Folder renamed successfully",
            "documents_updated": documents_updated
        }
        
    except Exception as e:
        print(f"Rename folder error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rename folder: {str(e)}")

@router.delete("/{folder_path:path}")
async def delete_folder(folder_path: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Delete a folder"""
    try:
        abs_path = os.path.join(DATA_DIR, folder_path)
        
        # Validate path
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Check if folder is empty
        if os.listdir(abs_path):
            raise HTTPException(status_code=400, detail="Folder is not empty")
        
        # Delete folder
        os.rmdir(abs_path)
        delete_empty_parents(abs_path, DATA_DIR)
        
        return {
            "status": "success",
            "message": "Folder deleted successfully"
        }
        
    except Exception as e:
        print(f"Delete folder error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete folder: {str(e)}")

@router.get("/{folder_path:path}/contents")
async def get_folder_contents(folder_path: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get contents of a folder"""
    try:
        abs_path = os.path.join(DATA_DIR, folder_path)
        
        # Validate path
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Get documents and videos
        documents = load_json(os.path.join(DATA_DIR, "documents.json")) or []
        videos = load_json(os.path.join(DATA_DIR, "videos.json")) or []
        
        # Filter for this folder
        folder_docs = [
            doc for doc in documents 
            if doc.get("folderStructure", {}).get("fullPath", "") == folder_path
        ]
        folder_videos = [
            video for video in videos 
            if video.get("folderStructure", {}).get("fullPath", "") == folder_path
        ]
        
        # Get subfolders
        subfolders = []
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                subfolders.append({
                    "name": item,
                    "path": os.path.join(folder_path, item)
                })
        
        return {
            "documents": folder_docs,
            "videos": folder_videos,
            "subfolders": subfolders
        }
        
    except Exception as e:
        print(f"Get folder contents error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get folder contents: {str(e)}") 