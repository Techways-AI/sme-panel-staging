import os
import uuid
import json
import shutil
import logging
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from langchain_community.vectorstores import FAISS
from copy import deepcopy
import time
import asyncio
import signal
from contextlib import asynccontextmanager

from ..models.document import (
    ProcessOptions, DocumentSearchParams, DocumentMetadata,
    DocumentUpdate, QuestionInput, QuestionResponse
)
from ..utils.file_utils import (
    sanitize_filename, ensure_dir, save_json, load_json,
    get_file_size, is_valid_file_type, get_relative_path,
    delete_empty_parents, extract_text_from_pdf_fitz,
    auto_chunk_text, is_heading, is_heading_text, extract_text_from_docx_python_docx,
    validate_content_coverage
)
from ..utils.vector_store import (
    verify_document_processed, get_embeddings, load_vector_store,
    save_vector_store, delete_vector_store, save_chunk_info, save_chunks_debug,
    check_vector_store_compatibility, load_chunk_info, load_chunks_debug
)
from ..config.settings import (
    DATA_DIR, VECTOR_STORES_DIR, ALLOWED_EXTENSIONS,
    OPENAI_API_KEY, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, EMBEDDING_MODEL
)
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.schema import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ..utils.text_utils import looks_like_table, get_chunk_metadata
from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..utils.s3_utils import (
    get_s3_key, upload_file_to_s3, get_file_url,
    file_exists_in_s3, get_file_metadata,
    save_documents_metadata, load_documents_metadata,
    delete_file_from_s3, download_file_from_s3,
    save_videos_metadata, load_videos_metadata, save_video_metadata_s3
)
from .videos import is_valid_video_url, extract_video_id, get_video_platform
from ..utils.content_library_utils import (
    generate_topic_slug, get_file_type_from_filename, index_content_library,
    delete_content_library_by_s3_key
)
from ..config.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, 'documents.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"]
)

# Global documents list (will be loaded from S3)
documents = []

# Global documents list (will be loaded from S3 when needed)
documents = []

@asynccontextmanager
async def timeout_context(seconds: int, operation_name: str):
    """Context manager for timeout handling"""
    try:
        # Set up timeout
        task = asyncio.current_task()
        if task:
            task.set_name(f"{operation_name}_timeout")
        
        yield
        
    except asyncio.TimeoutError:
        logger.error(f"Operation {operation_name} timed out after {seconds} seconds")
        raise HTTPException(
            status_code=408, 
            detail=f"Operation {operation_name} timed out after {seconds} seconds"
        )
    except Exception as e:
        logger.error(f"Operation {operation_name} failed: {str(e)}")
        raise

@router.get("")
async def get_documents(auth_result: dict = Depends(get_dual_auth_user)):
    """Get all documents"""
    global documents
    try:
        # Log user context
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting documents")
        
        # Load documents from S3
        try:
            documents = load_documents_metadata()
            logger.info(f"Found {len(documents)} documents for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to load documents for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load documents: {str(e)}"
            )

        # Return documents with user context
        return {
            "documents": documents,
            "user": {
                "id": user_id,
                "permissions": auth_result.get('user_data', {}).get('permissions', [])
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting documents for user {auth_result.get('user_data', {}).get('sub', 'unknown')}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get documents: {str(e)}"
        )

@router.post("/upload")
async def upload_documents(
    auth_result: dict = Depends(get_dual_auth_user),
    files: List[UploadFile] = File(...),
    folderStructure: str = Form(...),
    videoUrl: Optional[str] = Form(None)
):
    """Upload documents with folder structure to S3"""
    try:
        logger.info(f"Received upload request from user {auth_result.get('user_data', {}).get('sub')} with {len(files)} files")
        logger.info(f"Folder structure: {folderStructure}")
        
        # Parse folder structure
        try:
            folder_data = json.loads(folderStructure)
            logger.info(f"Parsed folder structure: {json.dumps(folder_data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid folder structure JSON: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid folder structure format"
            )

        # Validate folder structure components
        required_fields = {
            'courseName': folder_data.get('courseName'),
            'yearSemester': folder_data.get('yearSemester'),
            'subjectName': folder_data.get('subjectName'),
            'unitName': folder_data.get('unitName'),
            'topic': folder_data.get('topic')
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        # Validate files
        if not files:
            logger.error("No files provided in request")
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate file types and check for duplicates
        valid_extensions = {'.pdf', '.docx', '.txt'}
        seen_filenames = set()
        
        for file in files:
            logger.info(f"Processing file: {file.filename}")
            
            # Check file extension
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in valid_extensions:
                logger.error(f"Invalid file type: {file.filename} (extension: {file_ext})")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file.filename}. Only PDF, DOCX, and TXT files are allowed."
                )

            # Check for duplicates
            if file.filename in seen_filenames:
                logger.error(f"Duplicate file detected: {file.filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate file detected: {file.filename}"
                )
            seen_filenames.add(file.filename)

            # Check if file is empty
            content = await file.read()
            if not content:
                logger.error(f"Empty file detected: {file.filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Empty file detected: {file.filename}"
                )
            await file.seek(0)  # Reset file pointer
            logger.info(f"File {file.filename} passed validation")

        # Process files
        new_documents = []
        file_results = []
        current_time = datetime.now()
        
        # Load latest documents from S3
        try:
            documents = load_documents_metadata()
        except Exception as e:
            logger.error(f"Failed to load documents from S3: {str(e)}")
            documents = []
        
        for file in files:
            file_status = {"filename": file.filename, "status": None, "reason": None}
            try:
                if not file.filename:
                    file_status.update({"status": "skipped", "reason": "No filename"})
                    continue
                    
                ext = os.path.splitext(file.filename)[1].lower()
                if not is_valid_file_type(file.filename, ALLOWED_EXTENSIONS):
                    file_status.update({"status": "skipped", "reason": f"Invalid file type: {ext}"})
                    continue
                    
                content = await file.read()
                if not content:
                    file_status.update({"status": "skipped", "reason": "File is empty"})
                    continue
                    
                safe_filename = sanitize_filename(file.filename.replace(" ", "_"))
                
                # Generate S3 key
                s3_key = get_s3_key(folder_data, safe_filename)
                
                # Check for duplicates in S3
                if file_exists_in_s3(s3_key):
                    file_status.update({"status": "skipped", "reason": "Duplicate document"})
                    continue
                
                # Upload to S3
                await file.seek(0)  # Reset file pointer for upload
                file_url = upload_file_to_s3(
                    file.file,
                    s3_key,
                    content_type=file.content_type
                )
                
                # Get file metadata from S3
                metadata = get_file_metadata(s3_key)
                
                # Create document metadata
                doc = {
                    "id": f"doc-{int(current_time.timestamp())}-{uuid.uuid4().hex[:8]}",
                    "fileName": safe_filename,
                    "fileSize": f"{metadata['size'] / 1024:.1f} KB",
                    "uploadDate": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "path": file_url,  # Store S3 URL instead of local path
                    "s3_key": s3_key,  # Store S3 key for future operations
                    "processed": False,
                    "processing": False,
                    "user_id": auth_result.get("user_data", {}).get("sub", "unknown"),
                    "folderStructure": {
                        "courseName": folder_data["courseName"],
                        "yearSemester": folder_data["yearSemester"],
                        "subjectName": folder_data["subjectName"],
                        "unitName": folder_data["unitName"],
                        "topic": folder_data["topic"],
                        "fullPath": s3_key.rsplit('/', 1)[0]  # Store S3 prefix as fullPath
                    }
                }
                
                documents.append(doc)
                new_documents.append(doc)
                file_status.update({
                    "status": "uploaded",
                    "reason": "Success",
                    "doc_id": doc["id"]
                })
                logger.info(f"Successfully uploaded file to S3: {safe_filename}")
                
                # Index in content library
                try:
                    topic_name = folder_data.get("topic", "")
                    unit_name = folder_data.get("unitName", "")
                    unit_number = folder_data.get("unitNumber")
                    subject_code = folder_data.get("subjectCode", "")
                    # Include subject code and unit info in slug to ensure uniqueness and match with topic_mappings
                    # Priority: subject_code + unit_number > subject_code + unit_name > unit_name only
                    topic_slug = generate_topic_slug(
                        topic_name,
                        unit_name=unit_name if not unit_number else None,
                        unit_number=unit_number,
                        subject_code=subject_code if subject_code else None
                    )
                    file_type = get_file_type_from_filename(safe_filename)
                    uploaded_via = folder_data.get("curriculum", "PCI").upper()
                    
                    # Get database session
                    db = next(get_db())
                    try:
                        index_content_library(
                            db=db,
                            topic_slug=topic_slug,
                            topic_name=topic_name,  # Store human-readable topic name
                            s3_key=s3_key,
                            file_type=file_type,
                            uploaded_via=uploaded_via
                        )
                        logger.info(f"Successfully indexed document in content library: {s3_key}")
                    except Exception as db_error:
                        logger.error(f"Failed to index document in content library: {str(db_error)}")
                        # Don't fail the upload if indexing fails
                    finally:
                        db.close()
                except Exception as index_error:
                    logger.error(f"Error indexing document in content library: {str(index_error)}")
                    # Don't fail the upload if indexing fails
                
                # Save updated documents list to S3
                try:
                    save_documents_metadata(documents)
                    logger.info("Successfully saved documents metadata to S3")
                except Exception as e:
                    logger.error(f"Failed to save documents metadata to S3: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to save document metadata: {str(e)}"
                    )
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                file_status.update({
                    "status": "error",
                    "reason": f"Error processing file: {str(e)}"
                })
                
            file_results.append(file_status)
        
        if not new_documents:
            logger.error("No files were successfully uploaded")
            return JSONResponse(
                status_code=400,
                content={"detail": "No files were successfully uploaded", "fileResults": file_results}
            )
            
        uploaded_videos = []
        # Store video metadata if videoUrl is provided
        if videoUrl:
            if not is_valid_video_url(videoUrl):
                logger.error(f"Invalid video URL provided: {videoUrl}")
                raise HTTPException(status_code=400, detail="Invalid video URL. Only YouTube or Vimeo URLs are allowed.")
            video_id = extract_video_id(videoUrl)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {videoUrl}")
                raise HTTPException(status_code=400, detail="Could not extract video ID from video URL.")
            current_time = datetime.now()
            # Load latest videos list from S3
            try:
                videos = load_videos_metadata()
            except Exception as e:
                logger.error(f"Error loading videos from S3: {str(e)}")
                videos = []
            # Check for duplicates
            duplicate = next((v for v in videos if v["url"] == videoUrl and
                v["folderStructure"]["courseName"] == folder_data["courseName"] and
                v["folderStructure"]["yearSemester"] == folder_data["yearSemester"] and
                v["folderStructure"]["subjectName"] == folder_data["subjectName"] and
                v["folderStructure"]["unitName"] == folder_data["unitName"] and
                v["folderStructure"]["topic"] == folder_data["topic"]), None)
            if not duplicate:
                unique_id = f"vid-{int(current_time.timestamp())}-{uuid.uuid4().hex[:8]}"
                curriculum = folder_data.get('curriculum', 'pci')
                s3_folder_path = f"videos/{curriculum}/{folder_data['yearSemester']}/{folder_data['subjectName']}/{folder_data['unitName']}/{folder_data['topic']}/{unique_id}"
                video = {
                    "id": unique_id,
                    "url": videoUrl,
                    "videoId": video_id,
                    "platform": get_video_platform(videoUrl),
                    "dateAdded": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "folderStructure": {
                        **folder_data,
                        "fullPath": s3_folder_path
                    },
                    "s3_key": s3_folder_path
                }
                try:
                    save_video_metadata_s3(video, s3_folder_path)
                except Exception as e:
                    logger.error(f"Failed to save video metadata to S3: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Failed to save video metadata: {str(e)}")
                videos.append(video)
                uploaded_videos.append(video)
                try:
                    save_videos_metadata(videos)
                except Exception as e:
                    logger.error(f"Failed to save videos metadata to S3: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Failed to save videos metadata: {str(e)}")
        
        # Prepare response message
        if uploaded_videos:
            message = f"{len(new_documents)} document(s) and 1 video uploaded successfully"
        else:
            message = f"{len(new_documents)} document(s) uploaded successfully"
        
        return {
            "status": "success",
            "message": message,
            "documents": new_documents,
            "fileResults": file_results,
            "videos": uploaded_videos if uploaded_videos else None
        }
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a document by ID from the documents list"""
    global documents
    try:
        # Reload documents from S3
        documents = load_documents_metadata()
        doc = next((d for d in documents if str(d.get("id")) == str(doc_id)), None)
        if not doc:
            logger.warning(f"Document not found: {doc_id}")
            return None
        return doc
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {str(e)}")
        return None

@router.post("/{doc_id}/process")
async def process_document(doc_id: str, options: ProcessOptions = None, auth_result: dict = Depends(get_dual_auth_user)):
    """Process a document for RAG with timeout handling"""
    start_time = time.time()
    logger.info(f"Starting document processing for doc_id: {doc_id} at {datetime.now()}")
    logger.info(f"Current user: {auth_result.get('user_data', {}).get('sub', 'unknown')}")
    
    # Set timeout for entire operation (10 minutes)
    timeout_seconds = int(os.getenv("DOCUMENT_PROCESSING_TIMEOUT", "600"))
    
    try:
        async with timeout_context(timeout_seconds, "document_processing"):
            # Get document info
            doc = get_document(doc_id)
            if not doc:
                logger.error(f"Document not found: {doc_id}")
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Convert to dict if it's a Pydantic model
            if hasattr(doc, 'dict'):
                doc = doc.dict()
            
            logger.info(f"Document metadata: {doc.get('fileName', 'unknown')}")
            
            if doc.get("processing"):
                logger.warning(f"Document {doc_id} is already being processed")
                raise HTTPException(status_code=400, detail="Document is already being processed")
            
            # Update status
            doc["processing"] = True
            doc["processing_start_time"] = datetime.now().isoformat()
            save_documents_metadata(documents)
            
            # Get file info from S3
            s3_start_time = time.time()
            s3_key = doc.get("s3_key")
            if not s3_key:
                folder_structure = doc.get("folderStructure", {})
                filename = doc.get("fileName")
                if not filename:
                    logger.error(f"Document filename not found in metadata for doc_id: {doc_id}")
                    raise HTTPException(status_code=404, detail="Document filename not found in metadata")
                s3_key = get_s3_key(folder_structure, filename)
            
            logger.info(f"S3 key for document: {s3_key}")
            
            if not file_exists_in_s3(s3_key):
                logger.error(f"Document file not found in S3: {s3_key}")
                raise HTTPException(status_code=404, detail="Document file not found in S3")
            
            # Download file from S3 to a temporary location
            temp_dir = os.path.join(os.getcwd(), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"{doc_id}{os.path.splitext(s3_key)[1]}")
            
            logger.info(f"Downloading file to temp location: {temp_file}")
            
            # Download and process file
            file_content = download_file_from_s3(s3_key)
            with open(temp_file, 'wb') as f:
                f.write(file_content)
            
            s3_time = time.time() - s3_start_time
            logger.info(f"File downloaded successfully. Size: {len(file_content)} bytes in {s3_time:.2f}s")
            
            file_ext = os.path.splitext(s3_key)[1].lower()
            logger.info(f"File extension: {file_ext}")
            
            # Get folder structure metadata
            folder_structure = doc.get("folderStructure", {})
            
            # Process based on file type
            chunks = []
            if file_ext == ".pdf":
                logger.info("Processing PDF file")
                raw_text = extract_text_from_pdf_fitz(temp_file)
                if not raw_text:
                    logger.error("Failed to extract text from PDF")
                    raise HTTPException(status_code=500, detail="Failed to extract text from PDF")
                
                effective_limit = (options.chunkSize if options else DEFAULT_CHUNK_SIZE)
                if any(line.strip().startswith('|') for line in raw_text.split('\n')):
                    effective_limit = int(effective_limit * 1.2)
                
                raw_chunks = auto_chunk_text(
                    raw_text,
                    max_chunk_size=effective_limit,
                    chunk_overlap=options.chunkOverlap if options else DEFAULT_CHUNK_OVERLAP
                )
                if not raw_chunks:
                    logger.error("Failed to generate chunks from PDF")
                    raise HTTPException(status_code=500, detail="Failed to generate chunks from PDF")
                
                for i, chunk_text in enumerate(raw_chunks):
                    # Get enhanced metadata for PDF chunks
                    metadata = get_chunk_metadata(chunk_text, temp_file)
                    doc_chunk = LangchainDocument(
                        page_content=chunk_text,
                        metadata={
                            "chunk_id": i,
                            "chunk_type": metadata["chunk_type"],
                            "is_semantic": metadata["is_semantic"],
                            "is_table": metadata["is_table"],
                            "chunk_size": len(chunk_text),
                            "has_header": metadata["has_header"],
                            "semantic_header": metadata["semantic_header"],
                            "headers": metadata["headers"],
                            "course": folder_structure.get("courseName"),
                            "year_semester": folder_structure.get("yearSemester"),
                            "subject": folder_structure.get("subjectName"),
                            "unit": folder_structure.get("unitName"),
                            "topic": folder_structure.get("topic"),
                            "folder_path": folder_structure.get("fullPath"),
                            "source_file": doc.get("fileName"),
                            "source_path": temp_file,
                            "processing_timestamp": datetime.now().isoformat()
                        }
                    )
                    chunks.append(doc_chunk)
            elif file_ext == ".docx":
                logger.info(f"Processing DOCX file: {s3_key}")
                raw_text = extract_text_from_docx_python_docx(temp_file)
                if not raw_text:
                    raise HTTPException(status_code=500, detail="Failed to extract content from DOCX file")
                
                effective_limit = (options.chunkSize if options else DEFAULT_CHUNK_SIZE)
                table_lines = [line for line in raw_text.split('\n') if line.strip().startswith('|')]
                if table_lines:
                    effective_limit = int(effective_limit * 1.2)
                
                raw_chunks = auto_chunk_text(
                    raw_text,
                    max_chunk_size=effective_limit,
                    chunk_overlap=options.chunkOverlap if options else DEFAULT_CHUNK_OVERLAP
                )
                
                if not raw_chunks:
                    raise HTTPException(status_code=500, detail="Failed to generate chunks from DOCX")
                
                for i, chunk_text in enumerate(raw_chunks):
                    metadata = get_chunk_metadata(chunk_text, temp_file)
                    doc_chunk = LangchainDocument(
                        page_content=chunk_text,
                        metadata={
                            "chunk_id": i,
                            "chunk_type": metadata["chunk_type"],
                            "is_semantic": metadata["is_semantic"],
                            "is_table": metadata["is_table"],
                            "chunk_size": len(chunk_text),
                            "has_header": metadata["has_header"],
                            "semantic_header": metadata["semantic_header"],
                            "headers": metadata["headers"],
                            "course": folder_structure.get("courseName"),
                            "year_semester": folder_structure.get("yearSemester"),
                            "subject": folder_structure.get("subjectName"),
                            "unit": folder_structure.get("unitName"),
                            "topic": folder_structure.get("topic"),
                            "folder_path": folder_structure.get("fullPath"),
                            "source_file": doc.get("fileName"),
                            "source_path": temp_file,
                            "processing_timestamp": datetime.now().isoformat()
                        }
                    )
                    chunks.append(doc_chunk)
            elif file_ext == ".txt":
                logger.info("Processing TXT file")
                with open(temp_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                effective_limit = (options.chunkSize if options else DEFAULT_CHUNK_SIZE)
                if any('\t' in line or '|' in line for line in content.split('\n')):
                    effective_limit = int(effective_limit * 1.2)
                
                raw_chunks = auto_chunk_text(
                    content,
                    max_chunk_size=effective_limit,
                    chunk_overlap=options.chunkOverlap if options else DEFAULT_CHUNK_OVERLAP
                )
                
                if not raw_chunks:
                    # Fallback to single chunk if auto_chunk_text fails
                    raw_chunks = [content]
                
                for i, chunk_text in enumerate(raw_chunks):
                    # Get enhanced metadata for TXT chunks
                    metadata = get_chunk_metadata(chunk_text, temp_file)
                    doc_chunk = LangchainDocument(
                        page_content=chunk_text,
                        metadata={
                            "chunk_id": i,
                            "chunk_type": metadata["chunk_type"],
                            "is_semantic": metadata["is_semantic"],
                            "is_table": metadata["is_table"],
                            "chunk_size": len(chunk_text),
                            "has_header": metadata["has_header"],
                            "semantic_header": metadata["semantic_header"],
                            "headers": metadata["headers"],
                            "course": folder_structure.get("courseName"),
                            "year_semester": folder_structure.get("yearSemester"),
                            "subject": folder_structure.get("subjectName"),
                            "unit": folder_structure.get("unitName"),
                            "topic": folder_structure.get("topic"),
                            "folder_path": folder_structure.get("fullPath"),
                            "source_file": doc.get("fileName"),
                            "source_path": temp_file,
                            "processing_timestamp": datetime.now().isoformat()
                        }
                    )
                    chunks.append(doc_chunk)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
            
            if not chunks:
                raise HTTPException(status_code=400, detail="No chunks generated from document")
            
            # Create vector store
            embeddings = get_embeddings()
            texts = [chunk.page_content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            vector_store = FAISS.from_texts(
                texts=texts,
                embedding=embeddings,
                metadatas=metadatas,
                distance_strategy="COSINE_DISTANCE"  # Use cosine distance for better similarity scoring
            )
            
            # Save vector store directly to S3
            if not save_vector_store(vector_store, doc_id):
                logger.error("Failed to save vector store to S3")
                raise HTTPException(status_code=500, detail="Failed to save vector store to S3")
            
            # Save chunk metadata for debugging and traceability
            try:
                # Calculate chunk statistics
                semantic_chunks = sum(1 for chunk in chunks if chunk.metadata.get("is_semantic", False))
                table_chunks = sum(1 for chunk in chunks if chunk.metadata.get("is_table", False))
                text_chunks = len(chunks) - semantic_chunks - table_chunks
                
                # Calculate content coverage
                content_coverage = None
                try:
                    # Convert chunks to the format expected by validate_content_coverage
                    chunks_for_coverage = []
                    for chunk in chunks:
                        chunks_for_coverage.append({
                            'text': chunk.page_content,
                            'metadata': chunk.metadata
                        })
                    
                    # Get the original text for coverage calculation
                    if file_ext == ".pdf":
                        original_text = extract_text_from_pdf_fitz(temp_file)
                    elif file_ext == ".docx":
                        original_text = extract_text_from_docx_python_docx(temp_file)
                    elif file_ext == ".txt":
                        with open(temp_file, 'r', encoding='utf-8') as f:
                            original_text = f.read()
                    else:
                        original_text = ""
                    
                    if original_text:
                        coverage_result = validate_content_coverage(original_text, chunks_for_coverage)
                        content_coverage = coverage_result.get("coverage_percent", 0)
                        logger.info(f"Content coverage: {content_coverage}%")
                except Exception as e:
                    logger.warning(f"Failed to calculate content coverage: {str(e)}")
                    content_coverage = None
                
                # Create comprehensive chunk info metadata
                chunk_info = {
                    "doc_id": doc_id,
                    "total_chunks": len(chunks),
                    "chunk_size": options.chunkSize if options else DEFAULT_CHUNK_SIZE,
                    "chunk_overlap": options.chunkOverlap if options else DEFAULT_CHUNK_OVERLAP,
                    "processing_timestamp": datetime.now().isoformat(),
                    "file_name": doc.get("fileName", "unknown"),
                    "file_size": len(file_content),
                    "file_type": file_ext,
                    "embedding_model": EMBEDDING_MODEL,
                    "chunking_stats": {
                        "total_chunks": len(chunks),
                        "semantic_chunks": semantic_chunks,
                        "table_chunks": table_chunks,
                        "text_chunks": text_chunks,
                        "average_chunk_size": sum(chunk.metadata.get("chunk_size", 0) for chunk in chunks) / len(chunks) if chunks else 0,
                        "chunk_types": {
                            chunk_type: sum(1 for c in chunks if c.metadata.get("chunk_type") == chunk_type)
                            for chunk_type in set(c.metadata.get("chunk_type") for c in chunks)
                        },
                        "coverage_percent": content_coverage
                    },
                    "folder_structure": folder_structure,
                    "processing_options": {
                        "chunk_size": options.chunkSize if options else DEFAULT_CHUNK_SIZE,
                        "chunk_overlap": options.chunkOverlap if options else DEFAULT_CHUNK_OVERLAP,
                        "effective_limit": effective_limit if 'effective_limit' in locals() else (options.chunkSize if options else DEFAULT_CHUNK_SIZE)
                    }
                }
                
                # Save chunk info
                if not save_chunk_info(chunk_info, doc_id):
                    logger.warning(f"Failed to save chunk info for document {doc_id}")
                
                # Create detailed chunks debug info
                chunks_debug = []
                for i, chunk in enumerate(chunks):
                    chunk_debug = {
                        "chunk_id": i,
                        "content_preview": chunk.page_content[:300] + "..." if len(chunk.page_content) > 300 else chunk.page_content,
                        "content_length": len(chunk.page_content),
                        "metadata": {
                            **chunk.metadata,
                            "headers": chunk.metadata.get("headers", []),
                            "semantic_header": chunk.metadata.get("semantic_header"),
                            "block_type": chunk.metadata.get("block_type"),
                            "chunk_type": chunk.metadata.get("chunk_type"),
                            "is_semantic": chunk.metadata.get("is_semantic", False),
                            "is_table": chunk.metadata.get("is_table", False),
                            "has_header": chunk.metadata.get("has_header", False),
                            "chunk_size": chunk.metadata.get("chunk_size", 0)
                        },
                        "page_number": extract_page_number(chunk.page_content),
                        "length": len(chunk.page_content)
                    }
                    chunks_debug.append(chunk_debug)
                
                # Save chunks debug info
                if not save_chunks_debug(chunks_debug, doc_id):
                    logger.warning(f"Failed to save chunks debug info for document {doc_id}")
                
                logger.info(f"Successfully saved chunk metadata for document {doc_id}")
                logger.info(f"Chunk statistics: {semantic_chunks} semantic, {table_chunks} table, {text_chunks} text chunks")
                
            except Exception as e:
                logger.warning(f"Failed to save chunk metadata for document {doc_id}: {str(e)}")
                # Don't fail the entire process if metadata saving fails
            
            # Update document status
            doc["processed"] = True
            doc["processing"] = False
            doc["total_chunks"] = len(chunks)
            doc["totalChunks"] = len(chunks)
            
            # Save updated documents list to S3
            save_documents_metadata(documents)
            
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            return {
                "status": "success",
                "message": "Document processed successfully",
                "num_chunks": len(chunks)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Provide more specific error messages
        error_detail = str(e)
        if "No module named" in error_detail:
            error_detail = "Missing required dependency. Please check server logs."
        elif "Permission denied" in error_detail:
            error_detail = "File access permission denied."
        elif "No such file" in error_detail:
            error_detail = "File not found or inaccessible."
        elif "timeout" in error_detail.lower():
            error_detail = "Document processing timed out. Please try again."
        elif "memory" in error_detail.lower():
            error_detail = "Insufficient memory to process document."
        else:
            error_detail = f"Document processing failed: {error_detail}"
        
        # Reset document processing state on error
        try:
            if doc and doc.get("processing"):
                doc["processing"] = False
                doc["processing_start_time"] = None
                save_documents_metadata(documents)
                logger.info(f"Reset processing state for document {doc_id} after error")
        except Exception as reset_error:
            logger.error(f"Failed to reset processing state for document {doc_id}: {str(reset_error)}")
        
        raise HTTPException(status_code=500, detail=error_detail)

def extract_page_number(chunk: str) -> Optional[int]:
    """Extract page number from chunk content if available"""
    if "=== Page " in chunk and " Content ===" in chunk:
        try:
            page_str = chunk.split("=== Page ")[1].split(" Content ===")[0]
            return int(page_str)
        except:
            pass
    return None

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Delete a document and all its associated data"""
    global documents
    
    # Load latest documents from S3
    try:
        documents = load_documents_metadata()
    except Exception as e:
        logger.error(f"Failed to load documents from S3: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load documents: {str(e)}"
        )
    
    # Find document
    doc = next((d for d in documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete from S3
        s3_key = doc.get("s3_key")
        if s3_key:
            delete_file_from_s3(s3_key)
            logger.info(f"Deleted document from S3: {s3_key}")
        
        # Delete vector store files from S3
        try:
            delete_vector_store(doc_id)
            logger.info(f"Deleted vector store files for document: {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to delete vector store files for document {doc_id}: {str(e)}")
            # Continue with deletion even if vector store deletion fails
        
        # Delete from content_library table
        if s3_key:
            try:
                db = next(get_db())
                try:
                    delete_content_library_by_s3_key(db, s3_key)
                    logger.info(f"Deleted content library record for document: {s3_key}")
                except Exception as db_error:
                    logger.error(f"Failed to delete content library record: {str(db_error)}")
                    # Don't fail the deletion if content library deletion fails
                finally:
                    db.close()
            except Exception as index_error:
                logger.error(f"Error deleting content library record: {str(index_error)}")
                # Don't fail the deletion if content library deletion fails
        
        # Remove from documents list
        documents = [d for d in documents if d["id"] != doc_id]
        
        # Save updated documents list to S3
        save_documents_metadata(documents)
        logger.info("Successfully updated documents metadata in S3")
        
        return {
            "status": "success",
            "message": "Document and all associated data deleted successfully",
            "details": {
                "document_id": doc_id,
                "s3_file_deleted": s3_key is not None,
                "vector_store_deleted": True,
                "metadata_updated": True
            }
        }
        
    except Exception as e:
        logger.error(f"Delete document error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )

@router.put("/{doc_id}")
async def edit_document(doc_id: str, update: DocumentUpdate, auth_result: dict = Depends(get_dual_auth_user)):
    """Edit document metadata"""
    global documents
    
    # Find document
    doc = next((d for d in documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        old_path = doc["path"]
        
        # Update filename if provided
        if update.name:
            new_filename = sanitize_filename(update.name)
            new_path = os.path.join(os.path.dirname(old_path), new_filename)
            os.rename(old_path, new_path)
            doc["fileName"] = new_filename
            doc["path"] = new_path
        
        # Update folder structure if provided
        if update.folderStructure:
            folder = update.folderStructure
            new_folder_path = os.path.join(
                DATA_DIR,
                sanitize_filename(folder["courseName"]),
                sanitize_filename(folder["yearSemester"]),
                sanitize_filename(folder["subjectName"]),
                sanitize_filename(folder["unitName"]),
                sanitize_filename(folder["topic"])
            )
            os.makedirs(new_folder_path, exist_ok=True)
            
            new_path = os.path.join(new_folder_path, doc["fileName"])
            os.rename(old_path, new_path)
            
            doc["path"] = new_path
            doc["folderStructure"] = {
                **folder,
                "fullPath": new_folder_path
            }
        
        # Update documents list
        for i, d in enumerate(documents):
            if d["id"] == doc_id:
                documents[i] = doc
                break
        
        # Save updated documents list to S3
        save_documents_metadata(documents)
        
        return {
            "status": "success",
            "message": "Document updated successfully",
            "document": doc
        }
        
    except Exception as e:
        logger.error(f"Edit document error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to edit document: {str(e)}"
        )

@router.get("/{doc_id}/status")
async def get_document_status(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get document processing status with detailed information"""
    global documents
    
    # Reload documents from S3
    documents = load_documents_metadata()
    
    doc = next((d for d in documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user owns this document (handle missing user_id for backward compatibility)
    doc_user_id = doc.get("user_id")
    auth_user_email = auth_result.get("user_data", {}).get("email")
    auth_user_sub = auth_result.get("user_data", {}).get("sub")
    
    # For backward compatibility, if document has no user_id, allow access
    # Otherwise, check if user owns the document
    if doc_user_id and doc_user_id not in [auth_user_email, auth_user_sub]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if document is currently being processed
    is_processing = doc.get("processing", False)
    
    # Check if document has been processed
    is_processed = doc.get("processed", False)
    
    # Check if vector store exists and is compatible
    vector_store_compatible = False
    needs_reprocessing = False
    vector_store_stats = {}
    
    if is_processed:
        try:
            vector_store_compatible = check_vector_store_compatibility(doc_id)
            if not vector_store_compatible:
                needs_reprocessing = True
            else:
                # Get vector store statistics
                vector_store = load_vector_store(doc_id)
                if vector_store and hasattr(vector_store, 'index'):
                    index = vector_store.index
                    vector_store_stats = {
                        "total_vectors": index.ntotal if hasattr(index, 'ntotal') else 0,
                        "dimension": index.d if hasattr(index, 'd') else 0,
                        "metric_type": getattr(index, 'metric_type', 1)
                    }
        except Exception as e:
            logger.warning(f"Error checking vector store compatibility for {doc_id}: {str(e)}")
            needs_reprocessing = True
    
    # Load detailed processing information
    processing_details = {}
    if is_processed:
        try:
            # Load chunk info if available
            chunk_info = load_chunk_info(doc_id)
            if chunk_info:
                processing_details = {
                    "chunking_stats": chunk_info.get("chunking_stats", {}),
                    "processing_timestamp": chunk_info.get("processing_timestamp"),
                    "file_size": chunk_info.get("file_size"),
                    "file_type": chunk_info.get("file_type"),
                    "embedding_model": chunk_info.get("embedding_model"),
                    "chunk_size": chunk_info.get("chunk_size"),
                    "chunk_overlap": chunk_info.get("chunk_overlap"),
                    "average_chunk_size": chunk_info.get("chunking_stats", {}).get("average_chunk_size", 0),
                    "chunk_types": chunk_info.get("chunking_stats", {}).get("chunk_types", {}),
                    "total_chunks": chunk_info.get("total_chunks", doc.get("total_chunks", 0))
                }
            
            # Load chunks debug info if available
            chunks_debug = load_chunks_debug(doc_id)
            if chunks_debug:
                processing_details["chunks_debug"] = {
                    "total_chunks": len(chunks_debug),
                    "sample_chunks": chunks_debug[:3] if len(chunks_debug) > 3 else chunks_debug
                }
                
        except Exception as e:
            logger.warning(f"Error loading processing details for {doc_id}: {str(e)}")
    
    # Calculate content coverage if available
    content_coverage = None
    if processing_details:
        try:
            # First try to get coverage from chunk_info if available
            if "chunking_stats" in processing_details:
                # Check if coverage was calculated during processing
                chunking_stats = processing_details["chunking_stats"]
                if "coverage_percent" in chunking_stats:
                    content_coverage = chunking_stats["coverage_percent"]
                else:
                    # Calculate coverage based on chunk sizes and file size
                    total_chunk_chars = processing_details.get("average_chunk_size", 0) * processing_details.get("total_chunks", 0)
                    file_size = processing_details.get("file_size", 0)
                    if total_chunk_chars > 0 and file_size > 0:
                        # Estimate coverage based on character count vs file size
                        # This is an approximation - actual coverage would need to be calculated during processing
                        estimated_chars_per_byte = 0.1  # Rough estimate for text content
                        estimated_total_chars = file_size * estimated_chars_per_byte
                        if estimated_total_chars > 0:
                            content_coverage = min(100, (total_chunk_chars / estimated_total_chars) * 100)
        except Exception as e:
            logger.warning(f"Error calculating content coverage for {doc_id}: {str(e)}")
    
    return {
        "id": doc_id,
        "processed": doc.get("processed", False),
        "processing": doc.get("processing", False),
        "fileName": doc.get("fileName", ""),
        "uploadDate": doc.get("uploadDate", ""),
        "fileSize": doc.get("fileSize", ""),
        "folderStructure": doc.get("folderStructure", {}),
        "vector_store_compatible": vector_store_compatible,
        "needs_reprocessing": needs_reprocessing,
        "vector_store_stats": vector_store_stats,
        "processing_details": processing_details,
        "content_coverage": content_coverage,
        "total_chunks": doc.get("total_chunks", processing_details.get("total_chunks", 0))
    }

@router.get("/search")
async def search_documents(params: DocumentSearchParams, auth_result: dict = Depends(get_dual_auth_user)):
    """Search and filter documents"""
    filtered_docs = documents
    
    if params.query:
        query = params.query.lower()
        filtered_docs = [
            doc for doc in filtered_docs 
            if query in doc.get("fileName", "").lower() or 
               query in doc.get("folderStructure", {}).get("topic", "").lower() or
               query in doc.get("folderStructure", {}).get("unitName", "").lower()
        ]
    
    if params.folder:
        filtered_docs = [
            doc for doc in filtered_docs 
            if doc.get("folderStructure", {}).get("courseName") == params.folder
        ]
    
    if params.semester:
        filtered_docs = [
            doc for doc in filtered_docs 
            if doc.get("folderStructure", {}).get("yearSemester") == params.semester
        ]
    
    if params.unit:
        filtered_docs = [
            doc for doc in filtered_docs 
            if doc.get("folderStructure", {}).get("unitName") == params.unit
        ]
    
    if params.topic:
        filtered_docs = [
            doc for doc in filtered_docs 
            if doc.get("folderStructure", {}).get("topic") == params.topic
        ]
    
    if params.processed is not None:
        filtered_docs = [
            doc for doc in filtered_docs 
            if doc.get("processed", False) == params.processed
        ]
    
    return {"documents": filtered_docs}

@router.get("/{doc_id}/preview")
async def get_document_preview(doc_id: str, max_lines: int = 100, auth_result: dict = Depends(get_dual_auth_user)):
    """Get document preview"""
    doc = next((d for d in documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = doc.get("path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        preview = ""
        
        if file_ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[:max_lines]
                preview = "".join(lines)
        elif file_ext == ".pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            preview = f"PDF Document\nPages: {len(reader.pages)}\nTitle: {reader.metadata.get('/Title', 'N/A')}"
        elif file_ext == ".docx":
            preview = "Word Document - Preview not available"
        else:
            preview = f"File type {file_ext} - Preview not available"
        
        return {
            "id": doc_id,
            "fileName": doc.get("fileName", ""),
            "preview": preview,
            "fileType": file_ext[1:].upper() if file_ext else "Unknown"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading document: {str(e)}")

@router.get("/{doc_id}/chunk-info")
async def get_chunk_info(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get information about document chunks"""
    doc = next((d for d in documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.get("processed", False):
        raise HTTPException(status_code=400, detail="Document is not processed")
    
    try:
        vector_store = load_vector_store(doc_id)
        if not vector_store:
            raise HTTPException(status_code=404, detail="Vector store not found")
        
        index = vector_store.index
        num_vectors = index.ntotal
        dimension = index.d
        
        # Get sample chunks
        sample_chunks = []
        if num_vectors > 0:
            for i in range(min(3, num_vectors)):
                try:
                    docs_with_scores = vector_store.similarity_search_with_score("", k=2)
                    if docs_with_scores:
                        doc_with_score = docs_with_scores[0]
                        chunk_text = doc_with_score[0].page_content
                        metadata = doc_with_score[0].metadata
                        
                        sample_chunks.append({
                            "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                            "metadata": {
                                "source": metadata.get("source", "Unknown"),
                                "page": metadata.get("page", "N/A"),
                                "section": metadata.get("section", "N/A"),
                                "year": metadata.get("year", "N/A"),
                                "semester": metadata.get("semester", "N/A"),
                                "subject": metadata.get("subject", "N/A"),
                                "unit": metadata.get("unit", "N/A"),
                                "topic": metadata.get("topic", "N/A")
                            }
                        })
                except Exception as e:
                    print(f"Error getting chunk {i}: {str(e)}")
                    continue
        
        return {
            "num_chunks": num_vectors,
            "embedding_dimension": dimension,
            "model": EMBEDDING_MODEL,
            "sample_chunks": sample_chunks,
            "document_info": {
                "fileName": doc.get("fileName"),
                "folderStructure": doc.get("folderStructure"),
                "processed": doc.get("processed", False)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chunk info: {str(e)}")

@router.get("/by-folder/{folder_path:path}")
async def get_documents_by_folder(folder_path: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get documents in a specific folder"""
    abs_folder_path = os.path.join(DATA_DIR, folder_path)
    folder_docs = [
        doc for doc in documents 
        if doc.get("path", "").startswith(abs_folder_path)
    ]
    return {"documents": folder_docs}

@router.get("/by-topic/{topic}")
async def get_documents_by_topic(topic: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get documents for a specific topic"""
    topic_docs = [
        doc for doc in documents 
        if doc.get("folderStructure", {}).get("topic") == topic
    ]
    return {"documents": topic_docs}

@router.post("/validate-processed-documents")
async def validate_processed_documents(auth_result: dict = Depends(get_dual_auth_user)):
    """Validate all processed documents and fix any inconsistencies"""
    global documents
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting validation of processed documents")
        
        # Load latest documents
        documents = load_documents_metadata()
        
        # Find documents marked as processed
        processed_docs = [d for d in documents if d.get("processed", False)]
        
        validation_results = []
        fixed_count = 0
        
        for doc in processed_docs:
            doc_id = doc["id"]
            doc_name = doc.get("fileName", "Unknown")
            
            try:
                # Check if vector store actually exists and is valid
                vector_store_valid = verify_document_processed(doc_id)
                
                if not vector_store_valid:
                    logger.warning(f"Document {doc_id} ({doc_name}) marked as processed but vector store is invalid")
                    
                    # Mark as not processed
                    doc["processed"] = False
                    doc["processing"] = False
                    doc["vector_store"] = None
                    doc["total_chunks"] = 0
                    doc["totalChunks"] = 0
                    doc["semantic_chunks"] = 0
                    doc["table_chunks"] = 0
                    doc["chunking_stats"] = {}
                    
                    validation_results.append({
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "status": "fixed",
                        "issue": "marked_as_processed_but_no_valid_vector_store",
                        "action": "marked_as_unprocessed"
                    })
                    fixed_count += 1
                else:
                    validation_results.append({
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "status": "valid",
                        "issue": None,
                        "action": None
                    })
                    
            except Exception as e:
                logger.error(f"Error validating document {doc_id}: {str(e)}")
                validation_results.append({
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "status": "error",
                    "issue": str(e),
                    "action": None
                })
        
        # Save updated documents if any were fixed
        if fixed_count > 0:
            save_documents_metadata(documents)
            logger.info(f"Fixed {fixed_count} documents with invalid processing status")
        
        return {
            "status": "success",
            "message": f"Validated {len(processed_docs)} processed documents",
            "total_processed": len(processed_docs),
            "fixed_count": fixed_count,
            "validation_results": validation_results
        }
        
    except Exception as e:
        logger.error(f"Error validating processed documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate processed documents: {str(e)}"
        )

@router.post("/{doc_id}/force-reprocess")
async def force_reprocess_document(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Force reprocessing of a document by clearing its processing status"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting force reprocessing for document {doc_id}")
        
        # Load latest documents
        documents = load_documents_metadata()
        
        # Find document
        doc = next((d for d in documents if d["id"] == doc_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_name = doc.get("fileName", "Unknown")
        
        # Check if document is currently being processed
        # If it's been processing for more than 10 minutes, allow force reprocess
        if doc.get("processing", False):
            # Check if this is a stuck processing state (processing for too long)
            processing_start = doc.get("processing_start_time")
            current_time = datetime.now()
            
            if processing_start:
                try:
                    start_time = datetime.fromisoformat(processing_start)
                    time_diff = (current_time - start_time).total_seconds()
                    
                    # If processing for more than 10 minutes, allow force reprocess
                    if time_diff > 600:  # 10 minutes
                        logger.warning(f"Document {doc_id} has been processing for {time_diff/60:.1f} minutes, allowing force reprocess")
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Document {doc_name} is currently being processed. Please wait for completion."
                        )
                except (ValueError, TypeError):
                    # If we can't parse the time, allow force reprocess
                    logger.warning(f"Document {doc_id} has invalid processing start time, allowing force reprocess")
            else:
                # No processing start time, allow force reprocess
                logger.warning(f"Document {doc_id} has no processing start time, allowing force reprocess")
        
        # Clear processing status and metadata
        doc["processed"] = False
        doc["processing"] = False
        doc["processing_start_time"] = None
        doc["vector_store"] = None
        doc["total_chunks"] = 0
        doc["totalChunks"] = 0
        doc["semantic_chunks"] = 0
        doc["table_chunks"] = 0
        doc["chunking_stats"] = {}
        
        # Delete vector store files from S3
        try:
            delete_vector_store(doc_id)
            logger.info(f"Deleted vector store files for document: {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to delete vector store files for document {doc_id}: {str(e)}")
            # Continue even if deletion fails
        
        # Save updated documents
        save_documents_metadata(documents)
        
        return {
            "status": "success",
            "message": f"Document {doc_name} has been reset for reprocessing",
            "document_id": doc_id,
            "document_name": doc_name,
            "action": "reset_for_reprocessing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error force reprocessing document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to force reprocess document: {str(e)}"
        )

@router.post("/cleanup-stuck-documents")
async def cleanup_stuck_documents(auth_result: dict = Depends(get_dual_auth_user)):
    """Automatically cleanup documents that have been stuck in processing for too long"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting cleanup of stuck documents")
        
        # Load latest documents
        documents = load_documents_metadata()
        current_time = datetime.now()
        
        stuck_docs = []
        cleaned_docs = []
        
        for doc in documents:
            if doc.get("processing", False):
                processing_start = doc.get("processing_start_time")
                
                if processing_start:
                    try:
                        start_time = datetime.fromisoformat(processing_start)
                        time_diff = (current_time - start_time).total_seconds()
                        
                        # If processing for more than 15 minutes, consider it stuck
                        if time_diff > 900:  # 15 minutes
                            stuck_docs.append({
                                "id": doc["id"],
                                "fileName": doc.get("fileName", "Unknown"),
                                "processing_time_minutes": time_diff / 60
                            })
                            
                            # Reset the stuck document
                            doc["processed"] = False
                            doc["processing"] = False
                            doc["processing_start_time"] = None
                            doc["vector_store"] = None
                            doc["total_chunks"] = 0
                            doc["totalChunks"] = 0
                            doc["semantic_chunks"] = 0
                            doc["table_chunks"] = 0
                            doc["chunking_stats"] = {}
                            
                            cleaned_docs.append(doc["id"])
                            logger.info(f"Automatically cleaned up stuck document: {doc['id']}")
                    except (ValueError, TypeError):
                        # Invalid time format, reset the document
                        doc["processing"] = False
                        doc["processing_start_time"] = None
                        cleaned_docs.append(doc["id"])
                        logger.info(f"Reset document with invalid processing time: {doc['id']}")
                else:
                    # No processing start time, reset the document
                    doc["processing"] = False
                    doc["processing_start_time"] = None
                    cleaned_docs.append(doc["id"])
                    logger.info(f"Reset document without processing start time: {doc['id']}")
        
        if cleaned_docs:
            # Save updated documents
            save_documents_metadata(documents)
            logger.info(f"Cleaned up {len(cleaned_docs)} stuck documents")
        
        return {
            "status": "success",
            "message": f"Cleaned up {len(cleaned_docs)} stuck documents",
            "stuck_documents": stuck_docs,
            "cleaned_documents": cleaned_docs,
            "total_documents_checked": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up stuck documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup stuck documents: {str(e)}"
        )

@router.post("/{doc_id}/reset-stuck")
async def reset_stuck_document(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Reset a document that is stuck in processing state"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting reset for stuck document {doc_id}")
        
        # Load latest documents
        documents = load_documents_metadata()
        
        # Find document
        doc = next((d for d in documents if d["id"] == doc_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_name = doc.get("fileName", "Unknown")
        
        # Only allow reset if document is stuck in processing
        if not doc.get("processing", False):
            raise HTTPException(
                status_code=400,
                detail=f"Document {doc_name} is not currently processing"
            )
        
        # Clear processing status and metadata
        doc["processed"] = False
        doc["processing"] = False
        doc["processing_start_time"] = None
        doc["vector_store"] = None
        doc["total_chunks"] = 0
        doc["totalChunks"] = 0
        doc["semantic_chunks"] = 0
        doc["table_chunks"] = 0
        doc["chunking_stats"] = {}
        
        # Save updated documents
        save_documents_metadata(documents)
        
        logger.info(f"Successfully reset stuck document: {doc_id}")
        
        return {
            "status": "success",
            "message": f"Document {doc_name} has been reset from stuck processing state",
            "document_id": doc_id,
            "document_name": doc_name,
            "action": "reset_stuck_processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting stuck document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset stuck document: {str(e)}"
        )

@router.get("/{doc_id}/validate")
async def validate_single_document(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Validate a single document's processing status"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting validation for document {doc_id}")
        
        # Load latest documents
        documents = load_documents_metadata()
        
        # Find document
        doc = next((d for d in documents if d["id"] == doc_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_name = doc.get("fileName", "Unknown")
        is_marked_processed = doc.get("processed", False)
        
        try:
            # Check if vector store actually exists and is valid
            vector_store_valid = verify_document_processed(doc_id)
            
            if is_marked_processed and not vector_store_valid:
                logger.warning(f"Document {doc_id} ({doc_name}) marked as processed but vector store is invalid")
                
                # Mark as not processed
                doc["processed"] = False
                doc["processing"] = False
                doc["vector_store"] = None
                doc["total_chunks"] = 0
                doc["totalChunks"] = 0
                doc["semantic_chunks"] = 0
                doc["table_chunks"] = 0
                doc["chunking_stats"] = {}
                
                # Save updated documents
                save_documents_metadata(documents)
                
                return {
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "status": "fixed",
                    "issue": "marked_as_processed_but_no_valid_vector_store",
                    "action": "marked_as_unprocessed",
                    "was_marked_processed": True,
                    "vector_store_valid": False
                }
            elif is_marked_processed and vector_store_valid:
                return {
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "status": "valid",
                    "issue": None,
                    "action": None,
                    "was_marked_processed": True,
                    "vector_store_valid": True
                }
            elif not is_marked_processed and vector_store_valid:
                logger.info(f"Document {doc_id} ({doc_name}) not marked as processed but has valid vector store")
                return {
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "status": "inconsistent",
                    "issue": "not_marked_processed_but_has_valid_vector_store",
                    "action": "should_mark_as_processed",
                    "was_marked_processed": False,
                    "vector_store_valid": True
                }
            else:
                return {
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "status": "valid",
                    "issue": None,
                    "action": None,
                    "was_marked_processed": False,
                    "vector_store_valid": False
                }
                
        except Exception as e:
            logger.error(f"Error validating document {doc_id}: {str(e)}")
            return {
                "document_id": doc_id,
                "document_name": doc_name,
                "status": "error",
                "issue": str(e),
                "action": None,
                "was_marked_processed": is_marked_processed,
                "vector_store_valid": False
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating single document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate document: {str(e)}"
        ) 