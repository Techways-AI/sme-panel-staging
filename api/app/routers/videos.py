from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import json
import uuid
from datetime import datetime
import re
import requests
from urllib.parse import urlparse
import shutil
import threading
import logging
import asyncio

# Configure logger
logger = logging.getLogger(__name__)

from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..models.video import (
    VideoUpload, VideoValidation, VideoMetadata,
    VideoUpdate, VideoResponse
)
from ..utils.file_utils import (
    sanitize_filename, ensure_dir, save_json, load_json,
    get_relative_path
)
from ..config.settings import DATA_DIR, VIDEOS_DIR
from ..utils.s3_utils import (
    save_videos_metadata, load_videos_metadata,
    save_video_metadata_s3, load_video_metadata_s3, delete_video_metadata_s3
)
from ..utils.content_library_utils import (
    generate_topic_slug, index_content_library, delete_content_library_by_s3_key
)
from ..config.database import get_db

# Create videos directory if it doesn't exist
ensure_dir(VIDEOS_DIR)

router = APIRouter(
    prefix="/api/videos",
    tags=["videos"]
)

# Global videos list (will be loaded from S3)
videos = []
# Lock for thread-safe access to videos list
videos_lock = threading.Lock()

VIDEOS_JSON_PATH = os.path.join(VIDEOS_DIR, "videos.json")

def load_videos():
    """Load videos from disk with thread safety"""
    global videos
    with videos_lock:
        if os.path.exists(VIDEOS_JSON_PATH):
            try:
                videos = load_json(VIDEOS_JSON_PATH) or []
            except Exception as e:
                print(f"Error loading videos: {e}")
                videos = []
        else:
            videos = []

def save_videos():
    """Save videos to disk with thread safety"""
    with videos_lock:
        try:
            save_json(videos, VIDEOS_JSON_PATH)
        except Exception as e:
            print(f"Error saving videos: {e}")
            raise HTTPException(status_code=500, detail="Failed to save videos")

# Load videos on startup
load_videos()

def is_valid_video_url(url: str) -> bool:
    """Validate YouTube or Vimeo URL format"""
    if not url:
        return False
    
    # YouTube URL patterns
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
    
    # Vimeo URL patterns
    vimeo_regex = r'(https?://)?(www\.)?(vimeo\.com/)(\d+)'
    
    return bool(re.match(youtube_regex, url) or re.match(vimeo_regex, url))

def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube or Vimeo URL"""
    if not url:
        return None
    
    # Try YouTube first
    youtube_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if youtube_match:
        return youtube_match.group(1)
    
    # Try Vimeo
    vimeo_match = re.search(r'(?:vimeo\.com/)(\d+)', url)
    if vimeo_match:
        return vimeo_match.group(1)
    
    return None

def get_video_platform(url: str) -> str:
    """Determine if URL is from YouTube or Vimeo"""
    if re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)', url):
        return "youtube"
    elif re.search(r'(?:vimeo\.com/)', url):
        return "vimeo"
    else:
        return "unknown"

def create_video_folder(folder_structure: dict, video_id: str) -> str:
    """Create folder structure for video"""
    course = sanitize_filename(folder_structure["courseName"])
    year_sem = sanitize_filename(folder_structure["yearSemester"])
    subject = sanitize_filename(folder_structure["subjectName"])
    unit = sanitize_filename(folder_structure["unitName"])
    topic = sanitize_filename(folder_structure["topic"])
    
    folder_path = os.path.join(VIDEOS_DIR, course, year_sem, subject, unit, topic, video_id)
    ensure_dir(folder_path)
    return folder_path

def save_video_metadata(video: dict, folder_path: str) -> None:
    """Save video metadata to JSON file"""
    metadata_path = os.path.join(folder_path, "metadata.json")
    save_json(video, metadata_path)

@router.get("")
async def get_videos(auth_result: dict = Depends(get_dual_auth_user)):
    """Get all videos"""
    global videos
    try:
        videos = await asyncio.to_thread(load_videos_metadata)
        return {"videos": videos}
    except Exception as e:
        print(f"[ERROR] Failed to get videos: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get videos")

@router.post("/upload")
async def upload_videos(video_data: VideoUpload, auth_result: dict = Depends(get_dual_auth_user)):
    """Upload videos with folder structure, storing metadata in S3"""
    logger.info(f"Received video upload request: {video_data}")
    try:
        # Validate inputs
        if not video_data.videoUrl and not video_data.videoUrls:
            logger.error("No video URLs provided in request")
            return JSONResponse(
                status_code=400,
                content={"detail": "No video URLs provided"}
            )
        
        # Parse folder structure
        folder = video_data.folderStructure
        logger.info(f"Processing folder structure: {folder}")
        
        if not all([
            folder.get("courseName"),
            folder.get("yearSemester"),
            folder.get("subjectName"),
            folder.get("unitName"),
            folder.get("topic")
        ]):
            missing_fields = [field for field in ["courseName", "yearSemester", "subjectName", "unitName", "topic"] 
                            if not folder.get(field)]
            logger.error(f"Missing required folder structure fields: {missing_fields}")
            return JSONResponse(
                status_code=400,
                content={"detail": f"Missing required folder structure fields: {', '.join(missing_fields)}"}
            )
        
        # Process videos
        urls = [video_data.videoUrl] if video_data.videoUrl else video_data.videoUrls
        logger.info(f"Processing {len(urls)} video URLs: {urls}")
        
        new_videos = []
        video_results = []
        current_time = datetime.now()
        
        # Load latest videos list from S3 without blocking the event loop
        try:
            videos = await asyncio.to_thread(load_videos_metadata)
            logger.info(f"Loaded {len(videos)} existing videos from S3")
        except Exception as e:
            logger.error(f"Error loading videos from S3: {str(e)}")
            videos = []
        
        for url in urls:
            video_status = {"url": url, "status": None, "reason": None}
            try:
                if not url:
                    logger.warning("Empty URL provided, skipping")
                    video_status.update({"status": "skipped", "reason": "Empty URL"})
                    continue
                
                if not is_valid_video_url(url):
                    logger.warning(f"Invalid video URL: {url}")
                    video_status.update({"status": "skipped", "reason": "Invalid video URL"})
                    continue
                
                video_id = extract_video_id(url)
                if not video_id:
                    logger.warning(f"Could not extract video ID from URL: {url}")
                    video_status.update({"status": "skipped", "reason": "Could not extract video ID"})
                    continue
                
                logger.info(f"Processing video {url} with ID {video_id}")
                
                # Check for duplicates
                with videos_lock:
                    duplicate = next((v for v in videos if v["url"] == url and
                        v["folderStructure"]["courseName"] == folder["courseName"] and
                        v["folderStructure"]["yearSemester"] == folder["yearSemester"] and
                        v["folderStructure"]["subjectName"] == folder["subjectName"] and
                        v["folderStructure"]["unitName"] == folder["unitName"] and
                        v["folderStructure"]["topic"] == folder["topic"]), None)
                
                if duplicate:
                    logger.warning(f"Duplicate video found: {url}")
                    video_status.update({"status": "skipped", "reason": "Duplicate video"})
                    continue
                
                # Create unique video ID and S3 folder path
                unique_id = f"vid-{int(current_time.timestamp())}-{uuid.uuid4().hex[:8]}"
                curriculum = folder.get('curriculum', 'pci')
                s3_folder_path = f"videos/{curriculum}/{folder['yearSemester']}/{folder['subjectName']}/{folder['unitName']}/{folder['topic']}/{unique_id}"
                logger.info(f"Created S3 folder path: {s3_folder_path}")
                
                # Create video metadata
                video = {
                    "id": unique_id,
                    "url": url,
                    "videoId": video_id,
                    "platform": get_video_platform(url),
                    "dateAdded": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "folderStructure": {
                        **folder,
                        "fullPath": s3_folder_path
                    },
                    "s3_key": s3_folder_path  # Store S3 key for future operations
                }
                
                # Save video metadata to S3
                try:
                    await asyncio.to_thread(save_video_metadata_s3, video, s3_folder_path)
                    logger.info(f"Saved video metadata to S3 for video {unique_id}")
                except Exception as e:
                    logger.error(f"Failed to save video metadata to S3: {str(e)}")
                    raise
                
                # Index in content library
                # For videos, we use the metadata.json path as the s3_key reference
                # The actual video is stored externally (YouTube/Vimeo), but we index the metadata
                try:
                    topic_name = folder.get("topic", "")
                    unit_name = folder.get("unitName", "")
                    unit_number = folder.get("unitNumber")
                    subject_code = folder.get("subjectCode", "")
                    # Include subject code and unit info in slug to ensure uniqueness and match with topic_mappings
                    # Priority: subject_code + unit_number > subject_code + unit_name > unit_name only
                    topic_slug = generate_topic_slug(
                        topic_name,
                        unit_name=unit_name if not unit_number else None,
                        unit_number=unit_number,
                        subject_code=subject_code if subject_code else None
                    )
                    # Use the metadata.json path as the s3_key for indexing
                    video_s3_key = f"{s3_folder_path}/metadata.json"
                    uploaded_via = folder.get("curriculum", "PCI").upper()
                    
                    # Get database session
                    db = next(get_db())
                    try:
                        index_content_library(
                            db=db,
                            topic_slug=topic_slug,
                            topic_name=topic_name,  # Store human-readable topic name
                            s3_key=video_s3_key,
                            file_type="video",
                            uploaded_via=uploaded_via
                        )
                        logger.info(f"Successfully indexed video in content library: {video_s3_key}")
                    except Exception as db_error:
                        logger.error(f"Failed to index video in content library: {str(db_error)}")
                        # Don't fail the upload if indexing fails
                    finally:
                        db.close()
                except Exception as index_error:
                    logger.error(f"Error indexing video in content library: {str(index_error)}")
                    # Don't fail the upload if indexing fails
                
                # Add to videos list with thread safety
                with videos_lock:
                    videos.append(video)
                    new_videos.append(video)
                    try:
                        save_videos_metadata(videos)
                        logger.info(f"Updated videos metadata in S3, total videos: {len(videos)}")
                    except Exception as e:
                        logger.error(f"Failed to save videos metadata to S3: {str(e)}")
                        raise
                
                video_status.update({
                    "status": "uploaded",
                    "reason": "Success",
                    "video_id": video["id"]
                })
                logger.info(f"Successfully processed video {url}")
                
            except Exception as e:
                logger.error(f"Error processing video {url}: {str(e)}")
                video_status.update({
                    "status": "error",
                    "reason": f"Error processing video: {str(e)}"
                })
            
            video_results.append(video_status)
        
        if not new_videos:
            logger.error("No videos were successfully uploaded")
            return JSONResponse(
                status_code=400,
                content={"detail": "No videos were successfully uploaded", "videoResults": video_results}
            )
        
        return {
            "status": "success",
            "message": f"{len(new_videos)} videos uploaded successfully",
            "videos": new_videos,
            "videoResults": video_results
        }
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

@router.post("/validate")
async def validate_video(video: VideoValidation, auth_result: dict = Depends(get_dual_auth_user)):
    """Validate a video URL"""
    print(f"Validating video URL: {video.url}")
    
    if not video.url:
        print("No URL provided")
        return JSONResponse(
            status_code=400,
            content={"detail": "No URL provided"}
        )
    
    if not is_valid_video_url(video.url):
        print(f"Invalid video URL format: {video.url}")
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid video URL format. Please provide a valid video URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID or https://vimeo.com/VIDEO_ID)"}
        )
    
    video_id = extract_video_id(video.url)
    if not video_id:
        print(f"Could not extract video ID from URL: {video.url}")
        return JSONResponse(
            status_code=400,
            content={"detail": "Could not extract video ID from URL. Please ensure it's a valid video URL."}
        )
    
    print(f"Video validation successful for ID: {video_id}")
    return {
        "status": "success",
        "message": "Valid video URL",
        "videoId": video_id,
        "platform": get_video_platform(video.url)
    }

@router.delete("/{video_id}")
async def delete_video(video_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Delete a video and its metadata from S3"""
    global videos
    try:
        videos = load_videos_metadata()
        video = next((v for v in videos if v["id"] == video_id), None)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        s3_folder_path = video["folderStructure"]["fullPath"]
        video_s3_key = f"{s3_folder_path}/metadata.json"
        
        # Delete video metadata from S3
        delete_video_metadata_s3(s3_folder_path)
        
        # Delete from content_library table
        try:
            db = next(get_db())
            try:
                delete_content_library_by_s3_key(db, video_s3_key)
                logger.info(f"Deleted content library record for video: {video_s3_key}")
            except Exception as db_error:
                logger.error(f"Failed to delete content library record: {str(db_error)}")
                # Don't fail the deletion if content library deletion fails
            finally:
                db.close()
        except Exception as index_error:
            logger.error(f"Error deleting content library record: {str(index_error)}")
            # Don't fail the deletion if content library deletion fails
        
        videos = [v for v in videos if v["id"] != video_id]
        save_videos_metadata(videos)
        return {"status": "success", "message": "Video deleted successfully"}
    except Exception as e:
        print(f"Delete video error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")

@router.put("/{video_id}")
async def edit_video(video_id: str, update: VideoUpdate, auth_result: dict = Depends(get_dual_auth_user)):
    """Edit video metadata"""
    global videos
    
    # Find video
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        # Update URL if provided
        if update.url:
            if not is_valid_video_url(update.url):
                raise HTTPException(status_code=400, detail="Invalid video URL")
            
            video_id = extract_video_id(update.url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Could not extract video ID")
            
            video["url"] = update.url
            video["videoId"] = video_id
            video["platform"] = get_video_platform(update.url)
        
        # Update folder structure if provided
        if update.folderStructure:
            folder = update.folderStructure
            if not all([
                folder.get("courseName"),
                folder.get("yearSemester"),
                folder.get("subjectName"),
                folder.get("unitName"),
                folder.get("topic")
            ]):
                raise HTTPException(status_code=400, detail="All folder structure components are required")
            
            new_folder_path = os.path.join(
                DATA_DIR,
                sanitize_filename(folder["courseName"]),
                sanitize_filename(folder["yearSemester"]),
                sanitize_filename(folder["subjectName"]),
                sanitize_filename(folder["unitName"]),
                sanitize_filename(folder["topic"])
            )
            ensure_dir(new_folder_path)
            
            video["folderStructure"] = {
                **folder,
                "fullPath": get_relative_path(new_folder_path, DATA_DIR)
            }
        
        # Save changes
        save_json(videos, VIDEOS_JSON_PATH)
        
        return {
            "status": "success",
            "message": "Video updated successfully",
            "video": video
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update video: {str(e)}")

@router.get("/by-folder/{folder_path:path}")
async def get_videos_by_folder(folder_path: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get videos in a specific folder"""
    abs_folder_path = os.path.join(DATA_DIR, folder_path)
    folder_videos = [
        video for video in videos 
        if video.get("folderStructure", {}).get("fullPath", "").startswith(folder_path)
    ]
    return {"videos": folder_videos}

@router.get("/by-topic/{topic}")
async def get_videos_by_topic(topic: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get videos for a specific topic"""
    topic_videos = [
        video for video in videos 
        if video.get("folderStructure", {}).get("topic") == topic
    ]
    return {"videos": topic_videos} 