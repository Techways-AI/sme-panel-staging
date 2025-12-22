from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import os
import json
import hashlib
import re
from datetime import datetime
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import logging

from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..models.document import NotesGenerationRequest, NotesGenerationResponse
from ..config.database import get_db
from ..config.settings import (
    DATA_DIR, OPENAI_API_KEY, GOOGLE_API_KEY, 
    CHAT_MODEL, AI_PROVIDER
)
from ..config.notes_config import get_notes_config, get_provider_max_tokens
from ..utils.s3_utils import (
    save_notes_to_s3, load_notes_from_s3, 
    save_notes_metadata_to_s3, load_notes_metadata_from_s3
)
from ..utils.vector_store import (
    get_embeddings, load_vector_store, verify_document_processed
)
from ..utils.db_utils import (
    save_notes_to_db, get_notes_by_document_id, get_notes_by_id,
    get_notes_by_user_id, delete_notes_by_id, check_notes_exist
)
from ..utils.content_library_utils import (
    generate_topic_slug, index_content_library
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, 'notes.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/notes",
    tags=["notes"]
)

# Global documents list (will be loaded from S3)
documents = []

# S3 constants for notes storage
NOTES_CURRICULUM_DEFAULT = "pci"
NOTES_PREFIX = f"generated-notes/{NOTES_CURRICULUM_DEFAULT}/"
NOTES_METADATA_KEY = "metadata/generated_notes.json"

def load_documents():
    """Load documents from the documents service"""
    global documents
    try:
        # For now, we'll use an empty list and let the documents endpoint handle document loading
        # This avoids circular import issues
        documents = []
        logger.info("Documents will be loaded on-demand from the documents endpoint")
    except Exception as e:
        logger.error(f"Failed to initialize documents: {str(e)}")
        documents = []

def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Get document by ID from the documents router"""
    try:
        # Import here to avoid circular imports
        from ..routers.documents import get_document as get_doc_from_documents
        
        # Try to get document from the documents router
        document = get_doc_from_documents(doc_id)
        if document:
            return document
        
        # Fallback: check if we have it in our local list
        for doc in documents:
            if doc.get('id') == doc_id:
                return doc
                
        return None
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {str(e)}")
        # Fallback: check if we have it in our local list
        for doc in documents:
            if doc.get('id') == doc_id:
                return doc
        return None

def save_notes_metadata(notes_list: list) -> bool:
    """Save notes metadata to S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        json_data = json.dumps(notes_list, indent=2)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=NOTES_METADATA_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save notes metadata: {str(e)}")
        return False

def load_notes_metadata() -> list:
    """Load notes metadata from S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        try:
            response = s3_client.get_object(
                Bucket=S3_BUCKET_NAME,
                Key=NOTES_METADATA_KEY
            )
            
            json_data = response['Body'].read().decode('utf-8')
            return json.loads(json_data)
        except s3_client.exceptions.NoSuchKey:
            # File doesn't exist, create it
            logger.info(f"Notes metadata file doesn't exist, creating empty file")
            empty_metadata = []
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=NOTES_METADATA_KEY,
                Body=json.dumps(empty_metadata, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            return empty_metadata
    except Exception as e:
        logger.error(f"Failed to load notes metadata: {str(e)}")
        return []

def save_notes_to_s3(notes_id: str, notes_content: str) -> bool:
    """Save notes content to S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        s3_key = f"{NOTES_PREFIX}{notes_id}.md"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=notes_content.encode('utf-8'),
            ContentType='text/markdown'
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save notes to S3: {str(e)}")
        return False

def load_notes_from_s3(notes_id: str) -> Optional[str]:
    """Load notes content from S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        s3_key = f"{NOTES_PREFIX}{notes_id}.md"
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to load notes from S3: {str(e)}")
        return None

def get_existing_notes(document_id: str) -> Optional[Dict[str, Any]]:
    """Check if notes already exist for a document"""
    try:
        notes_list = load_notes_metadata()
        for note in notes_list:
            if note.get('document_id') == document_id:
                return note
        return None
    except Exception as e:
        logger.error(f"Error checking existing notes: {str(e)}")
        return None

def extract_document_content(doc_id: str) -> str:
    """Extract content from a processed document"""
    try:
        # Verify document is processed
        if not verify_document_processed(doc_id):
            raise HTTPException(
                status_code=400,
                detail=f"Document {doc_id} is not processed. Please process the document first."
            )
        
        # Load vector store for the document
        vector_store = load_vector_store(doc_id)
        if not vector_store:
            raise HTTPException(
                status_code=404,
                detail=f"Vector store not found for document {doc_id}"
            )
        
        # Get all documents from the vector store
        docs = vector_store.docstore._dict
        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"No content found in document {doc_id}"
            )
        
        # Extract and combine all text content
        content_parts = []
        for doc_id_internal, doc in docs.items():
            if hasattr(doc, 'page_content'):
                content_parts.append(doc.page_content)
        
        if not content_parts:
            raise HTTPException(
                status_code=404,
                detail=f"No readable content found in document {doc_id}"
            )
        
        # Combine all content with proper spacing
        full_content = "\n\n".join(content_parts)
        logger.info(f"Extracted {len(full_content)} characters from document {doc_id}")
        
        return full_content
        
    except Exception as e:
        logger.error(f"Error extracting content from document {doc_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract document content: {str(e)}"
        )

def extract_section_content(document_content: str, section_number: int = 5) -> str:
    import re

    if not document_content:
        return ""

    lines = document_content.splitlines()
    capture = False
    captured_lines = []

    section_patterns = [
        re.compile(rf"^(?:#+\s*)?section\s+{section_number}\b", re.IGNORECASE),
        re.compile(rf"^{section_number}\s*[\.)-]"),
        re.compile(rf"^(?:#+\s*)?{section_number}\s*[:\-]", re.IGNORECASE)
    ]
    next_section_pattern = re.compile(r"^(?:#+\s*)?section\s+(\d+)\b", re.IGNORECASE)
    next_number_pattern = re.compile(r"^(\d+)\s*[\.)-]")

    for line in lines:
        stripped = line.strip()
        if not capture:
            if stripped and any(pattern.match(stripped) for pattern in section_patterns):
                capture = True
                captured_lines.append(line)
            continue

        if stripped:
            next_section_match = next_section_pattern.match(stripped)
            if next_section_match:
                next_number = int(next_section_match.group(1))
                if next_number != section_number:
                    break

            next_number_match = next_number_pattern.match(stripped)
            if next_number_match:
                next_number = int(next_number_match.group(1))
                if next_number != section_number:
                    break

        captured_lines.append(line)

    return "\n".join(captured_lines).strip()

def clean_placeholder_text(notes: str) -> str:
    """Clean up any remaining placeholder text in the generated notes"""
    import re
    
    # Remove "Molecular Structure:" placeholders and similar
    notes = re.sub(r'Molecular Structure:\s*', '', notes, flags=re.IGNORECASE)
    notes = re.sub(r'Molecular Structure\s*', '', notes, flags=re.IGNORECASE)
    
    # Remove other common placeholders
    notes = re.sub(r'Structure:\s*', '', notes, flags=re.IGNORECASE)
    notes = re.sub(r'Formula:\s*', '', notes, flags=re.IGNORECASE)
    
    # Clean up any double spaces or formatting issues
    notes = re.sub(r'\n\s*\n\s*\n', '\n\n', notes)  # Remove excessive blank lines
    notes = re.sub(r'^\s+', '', notes, flags=re.MULTILINE)  # Remove leading spaces
    
    return notes

def get_chat_model_for_notes(temperature: float = 0.3, max_tokens: Optional[int] = None):
    """Get chat model for notes generation based on configured AI provider"""
    # Use higher token limits for comprehensive notes generation
    if max_tokens is None:
        max_tokens = get_provider_max_tokens(AI_PROVIDER, CHAT_MODEL)
    
    logger.info(f"Initializing chat model - Provider: {AI_PROVIDER}, Model: {CHAT_MODEL}, Max Tokens: {max_tokens}, Temperature: {temperature}")
    
    if AI_PROVIDER == "google":
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when AI_PROVIDER is set to 'google'")
        model = ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            temperature=temperature,
            google_api_key=GOOGLE_API_KEY,
            max_output_tokens=max_tokens
        )
        logger.info(f"Initialized Google Gemini model: {CHAT_MODEL}")
        return model
    else:  # OpenAI
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER is set to 'openai'")
        model = ChatOpenAI(
            model=CHAT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=OPENAI_API_KEY
        )
        logger.info(f"Initialized OpenAI model: {CHAT_MODEL}")
        return model

def generate_notes_with_openai(document_content: str, course_name: str, subject_name: str, 
                              unit_name: str, topic: str, max_tokens: Optional[int] = None, 
                              temperature: float = 0.3) -> str:
    """Generate notes using AI API with the specified prompt"""
    try:
        # Load the notes prompt template
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'notes_prompt.txt')
        if not os.path.exists(template_path):
            logger.error(f"Notes prompt template not found at {template_path}")
            raise FileNotFoundError(f"Notes prompt template not found at {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Create the notes generation prompt
        notes_prompt = ChatPromptTemplate.from_template(template_content)
        
        # Initialize AI model with quality-specific settings
        model = get_chat_model_for_notes(max_tokens=max_tokens, temperature=temperature)
        
        # Create the chain with the simplified prompt
        chain = notes_prompt | model
        
        logger.info(f"Generating notes for course: {course_name}, subject: {subject_name}, unit: {unit_name}, topic: {topic}")
        logger.info(f"Using max_tokens: {max_tokens}, temperature: {temperature}")
        
        # Generate notes
        logger.info(f"Invoking AI chain with document content length: {len(document_content)}")
        response = chain.invoke({
            "course_name": course_name,
            "subject_name": subject_name,
            "unit_name": unit_name,
            "topic": topic,
            "document_content": document_content
        })
        
        notes = response.content
        # Log notes preview safely (handle Unicode characters)
        try:
            preview = notes[:200]
            # Replace problematic Unicode characters for logging
            safe_preview = preview.encode('ascii', 'replace').decode('ascii')
            logger.info(f"Notes preview (first 200 chars): {safe_preview}...")
        except Exception as e:
            logger.info(f"Notes preview unavailable due to encoding issues: {str(e)}")
        
        try:
            ending = notes[-200:]
            safe_ending = ending.encode('ascii', 'replace').decode('ascii')
            logger.info(f"Notes ending (last 200 chars): ...{safe_ending}")
        except Exception as e:
            logger.info(f"Notes ending unavailable due to encoding issues: {str(e)}")
        
        # Post-process to remove any remaining placeholder text
        notes = clean_placeholder_text(notes)
        
        # Validate notes completeness
        if not notes or len(notes.strip()) < 100:
            logger.error("Generated notes are too short or empty")
            raise HTTPException(
                status_code=500,
                detail="Generated notes are incomplete. Please try again."
            )
        
        # Check for common truncation indicators
        if notes.count('(') != notes.count(')'):
            logger.warning(f"Potential truncation detected in notes - mismatched parentheses")
        if notes.count('**') % 2 != 0:
            logger.warning(f"Potential truncation detected in notes - mismatched bold markers")
        if notes.count('|') > 0 and notes.count('|') % 2 != 0:
            logger.warning(f"Potential table truncation detected - odd number of pipe characters")
        
        # Ensure notes end properly (not mid-sentence)
        # More comprehensive check for notes completeness
        notes_stripped = notes.strip()
        if len(notes_stripped) > 1000:  # Only check long notes
            if notes_stripped.endswith(('.', '!', '?', ':', ';', '```', '---', '##', '#')):
                logger.info("Notes appear to be complete")
            else:
                # Check if it ends with common markdown patterns or is very long
                if (notes_stripped.endswith(('**', '*', '>', '-', '•')) or 
                    len(notes_stripped) > 50000):  # Very long notes are likely complete
                    logger.info("Notes appear to be complete (long content or markdown formatting)")
                else:
                    logger.warning("Notes may be incomplete - not ending with proper punctuation")
        else:
            logger.info("Notes appear to be complete (short content)")
        
        return notes
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error generating notes with AI: {error_str}")
        
        # Check for rate limit errors (429)
        if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
            # Extract retry delay if available
            import re
            retry_match = re.search(r'retry.*?(\d+)\s*seconds?', error_str, re.IGNORECASE)
            retry_seconds = retry_match.group(1) if retry_match else None
            
            error_message = "API rate limit exceeded. "
            if retry_seconds:
                error_message += f"Please wait {retry_seconds} seconds before trying again. "
            else:
                error_message += "Please wait a minute before trying again. "
            
            error_message += "The free tier has a limit of 5 requests per minute. Consider upgrading your API plan or reducing request frequency."
            
            raise HTTPException(
                status_code=429,
                detail=error_message
            )
        
        # Check for other API errors
        if "api" in error_str.lower() or "authentication" in error_str.lower() or "invalid" in error_str.lower():
            raise HTTPException(
                status_code=500,
                detail=f"API error: {error_str}. Please check your API configuration and credentials."
            )
        
        # Generic error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate notes: {error_str}"
        )

@router.post("/generate", response_model=NotesGenerationResponse)
async def generate_notes(
    request: NotesGenerationRequest,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive academic notes from a processed document
    """
    try:
        # Get user context
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting notes generation for document {request.document_id}")
        
        # Verify document exists by getting it from the documents service
        document = get_document(request.document_id)
        if not document:
            # Try to get documents from the documents service to see if it exists
            try:
                from ..routers.documents import get_documents
                mock_auth = {'user_data': {'sub': user_id}}
                documents_response = await get_documents(mock_auth)
                
                if documents_response and 'documents' in documents_response:
                    all_documents = documents_response['documents']
                    document = next((doc for doc in all_documents if str(doc.get('id')) == str(request.document_id)), None)
                    
                    if not document:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Document {request.document_id} not found. Please check if the document exists."
                        )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Document {request.document_id} not found. Please check if the document exists."
                    )
            except Exception as e:
                logger.error(f"Error checking document existence: {str(e)}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Document {request.document_id} not found. Please check if the document exists."
                )
        
        # Check if document is processed
        if not document.get('processed', False):
            raise HTTPException(
                status_code=400,
                detail=f"Document {request.document_id} is not processed. Please process the document first before generating notes."
            )
        
        # Check if document is currently being processed
        if document.get('processing', False):
            raise HTTPException(
                status_code=400,
                detail=f"Document {request.document_id} is currently being processed. Please wait for processing to complete before generating notes."
            )
        
        # Check if notes already exist for this document (check both S3 and PostgreSQL)
        existing_notes = get_existing_notes(request.document_id)
        existing_db_notes = None
        
        try:
            existing_db_notes = get_notes_by_document_id(db, request.document_id)
        except Exception as db_error:
            logger.warning(f"Database query failed, falling back to S3: {str(db_error)}")
            # Continue with S3 fallback
        
        if existing_notes or existing_db_notes:
            logger.info(f"Found existing notes for document {request.document_id}, loading from storage")
            
            # Try to load from PostgreSQL first (primary storage)
            if existing_db_notes:
                return NotesGenerationResponse(
                    notes=existing_db_notes.notes_content,
                    document_id=request.document_id,
                    generated_at=existing_db_notes.created_at.isoformat(),
                    metadata={
                        "course_name": existing_db_notes.course_name,
                        "subject_name": existing_db_notes.subject_name,
                        "unit_name": existing_db_notes.unit_name,
                        "topic": existing_db_notes.topic,
                        "document_name": existing_db_notes.document_name,
                        "user_id": existing_db_notes.user_id,
                        "content_length": existing_db_notes.content_length,
                        "notes_length": existing_db_notes.notes_length,
                        "notes_id": existing_db_notes.id,
                        "s3_key": existing_db_notes.s3_key,
                        "additional_metadata": existing_db_notes.notes_metadata
                    }
                )
            
            # Fallback to S3 if not in PostgreSQL
            if existing_notes:
                notes_content = load_notes_from_s3(existing_notes['notes_id'])
                if notes_content:
                    return NotesGenerationResponse(
                        notes=notes_content,
                        document_id=request.document_id,
                        generated_at=existing_notes['generated_at'],
                        metadata=existing_notes['metadata']
                    )
                else:
                    logger.warning(f"Failed to load existing notes from S3, will regenerate")
        
        # Extract document content
        try:
            document_content = extract_document_content(request.document_id)
        except HTTPException as he:
            # Provide more specific error messages
            if "not processed" in str(he.detail):
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {request.document_id} processing verification failed. Please try processing the document again."
                )
            elif "Vector store not found" in str(he.detail):
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {request.document_id} vector store is missing or corrupted. Please process the document again to recreate the vector store."
                )
            elif "No content found" in str(he.detail):
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {request.document_id} has no readable content. Please check if the document contains text."
                )
            else:
                raise he
        except Exception as e:
            # Handle vector store loading errors gracefully
            logger.error(f"Vector store loading error for document {request.document_id}: {str(e)}")
            
            # Check if this is a FAISS compatibility issue
            if "'__fields_set__'" in str(e) or "pydantic" in str(e).lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {request.document_id} vector store has compatibility issues. This is likely due to a FAISS version mismatch. Please process the document again to recreate the vector store with the current version."
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {request.document_id} vector store is corrupted. Please process the document again to fix the issue."
                )
        
        section_number = 5
        section_content = extract_section_content(document_content, section_number=section_number)

        if not section_content:
            logger.error(f"Section {section_number} not found in document {request.document_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Section {section_number} content not found in document. Please verify the document formatting or update the section identifier."
            )

        logger.info(
            f"Section {section_number} content extracted for document {request.document_id}: "
            f"section length={len(section_content)}, full length={len(document_content)}"
        )

        # Get notes configuration based on quality level
        quality = request.quality or "standard"
        notes_config = get_notes_config(quality, AI_PROVIDER)
        
        # Get quality-specific configuration
        max_tokens = notes_config.get("max_tokens")
        temperature = notes_config.get("temperature", 0.3)
        
        logger.info(f"Notes generation request - Quality: {quality}, Provider: {AI_PROVIDER}, Model: {CHAT_MODEL}")
        logger.info(f"Configuration - max_tokens: {max_tokens}, temperature: {temperature}")
        logger.info(f"Notes config: {notes_config}")

        # Generate notes using AI with quality-specific settings
        logger.info(f"Calling generate_notes_with_openai with max_tokens={max_tokens}, temperature={temperature}")
        notes = generate_notes_with_openai(
            document_content=section_content,
            course_name=request.course_name,
            subject_name=request.subject_name,
            unit_name=request.unit_name,
            topic=request.topic,
            max_tokens=max_tokens,
            temperature=temperature
        )
        logger.info(f"Notes generation completed, length: {len(notes) if notes else 0}")
        
        # Generate unique ID for the notes
        import uuid
        notes_id = f"notes-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}"
        
        # Prepare metadata
        metadata = {
            "course_name": request.course_name,
            "subject_name": request.subject_name,
            "unit_name": request.unit_name,
            "topic": request.topic,
            "document_name": document.get('fileName', 'Unknown'),
            "user_id": user_id,
            "content_length": len(document_content),
            "notes_length": len(notes),
            "notes_id": notes_id,
            "s3_key": f"{NOTES_PREFIX}{notes_id}.md"
        }
        metadata["section_number"] = section_number

        # Save to PostgreSQL (primary storage)
        db_notes = None
        try:
            db_notes = save_notes_to_db(
                db=db,
                notes_id=notes_id,
                document_id=request.document_id,
                user_id=user_id,
                notes_content=notes,
                metadata=metadata
            )
            logger.info(f"Successfully saved notes to PostgreSQL: {notes_id}")
        except Exception as e:
            logger.error(f"Failed to save notes to PostgreSQL: {str(e)}")
            logger.warning("Continuing with S3 storage only")
            # Don't fail the request, continue with S3 storage
        
        # Also save to S3 as backup
        try:
            if not save_notes_to_s3(notes_id, notes):
                logger.warning(f"Failed to save notes to S3 backup: {notes_id}")
            
            # Save notes metadata to S3
            notes_list = load_notes_metadata()
            notes_entry = {
                "notes_id": notes_id,
                "document_id": request.document_id,
                "generated_at": datetime.now().isoformat(),
                "metadata": metadata,
                "s3_key": f"{NOTES_PREFIX}{notes_id}.md"
            }
            notes_list.append(notes_entry)
            
            if not save_notes_metadata(notes_list):
                logger.warning(f"Failed to save notes metadata to S3: {notes_id}")
        except Exception as e:
            logger.warning(f"Failed to save notes to S3 backup: {str(e)}")
            # Don't fail the request if S3 backup fails, since PostgreSQL is primary
        
        # Index notes in content_library table
        try:
            # Extract subject_code from document metadata if available
            folder_structure = document.get('folderStructure', {})
            subject_code = folder_structure.get('subjectCode', '')
            
            # Extract unit number from unit_name if possible
            unit_number = None
            if request.unit_name:
                unit_name_lower = request.unit_name.lower().strip()
                num_match = re.search(r'unit\s*(\d+)', unit_name_lower)
                if num_match:
                    unit_number = int(num_match.group(1))
                else:
                    num_match = re.search(r'^(\d+)[:\s]', unit_name_lower)
                    if num_match:
                        unit_number = int(num_match.group(1))
            
            # Generate topic slug
            topic_slug = generate_topic_slug(
                topic_name=request.topic,
                unit_name=request.unit_name if not unit_number else None,
                unit_number=unit_number,
                subject_code=subject_code if subject_code else None
            )
            
            # Get S3 key (already generated in metadata)
            s3_key = metadata.get('s3_key', f"{NOTES_PREFIX}{notes_id}.md")
            
            # Determine uploaded_via from document metadata or default to 'PCI'
            uploaded_via = folder_structure.get('curriculum', 'PCI').upper()
            
            # Index in content library
            content_lib_record = index_content_library(
                db=db,
                topic_slug=topic_slug,
                topic_name=request.topic,  # Human-readable topic name
                s3_key=s3_key,
                file_type='notes',
                uploaded_via=uploaded_via
            )
            
            if content_lib_record:
                logger.info(f"Successfully indexed notes in content library: topic_slug={topic_slug}, s3_key={s3_key}")
            else:
                logger.warning(f"Failed to index notes in content library: topic_slug={topic_slug}, s3_key={s3_key}")
        except Exception as e:
            logger.error(f"Error indexing notes in content library: {str(e)}")
            # Don't fail the request if content library indexing fails
            # This is a non-critical operation
        
        # Prepare response
        response = NotesGenerationResponse(
            notes=notes,
            document_id=request.document_id,
            generated_at=datetime.now().isoformat(),
            metadata=metadata
        )
        
        logger.info(f"Successfully generated and stored notes for user {user_id}, document {request.document_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in notes generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/documents")
async def get_available_documents(auth_result: dict = Depends(get_dual_auth_user)):
    """
    Get list of processed documents available for notes generation
    """
    try:
        # Get user context
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting available documents for notes generation")
        
        # Import here to avoid circular imports
        from ..routers.documents import get_documents
        
        # Get documents from the documents service
        try:
            # Create a mock auth_result for the documents service
            mock_auth = {'user_data': {'sub': user_id}}
            documents_response = await get_documents(mock_auth)
            
            if documents_response and 'documents' in documents_response:
                all_documents = documents_response['documents']
                
                # Filter only processed documents
                processed_docs = [
                    {
                        "id": doc.get('id'),
                        "fileName": doc.get('fileName'),
                        "uploadDate": doc.get('uploadDate'),
                        "folderStructure": doc.get('folderStructure', {}),
                        "processed": doc.get('processed', False)
                    }
                    for doc in all_documents
                    if doc.get('processed', False)
                ]
                
                logger.info(f"Found {len(processed_docs)} processed documents for user {user_id}")
                
                return {
                    "documents": processed_docs,
                    "count": len(processed_docs)
                }
            else:
                logger.warning("No documents found in response")
                return {
                    "documents": [],
                    "count": 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get documents from documents service: {str(e)}")
            # Return empty list if documents service fails
            return {
                "documents": [],
                "count": 0
            }
        
    except Exception as e:
        logger.error(f"Error getting available documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available documents: {str(e)}"
        )

@router.get("/list")
async def list_generated_notes(
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    List all generated notes for the current user
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        
        # Get notes from PostgreSQL (primary source)
        db_notes = get_notes_by_user_id(db, user_id)
        
        user_notes = [
            {
                "notes_id": note.id,
                "document_id": note.document_id,
                "generated_at": note.created_at.isoformat(),
                "metadata": {
                    "course_name": note.course_name,
                    "subject_name": note.subject_name,
                    "unit_name": note.unit_name,
                    "topic": note.topic,
                    "document_name": note.document_name,
                    "user_id": note.user_id,
                    "content_length": note.content_length,
                    "notes_length": note.notes_length,
                    "s3_key": note.s3_key
                },
                "document_name": note.document_name or 'Unknown'
            }
            for note in db_notes
        ]
        
        return {
            "notes": user_notes,
            "count": len(user_notes)
        }
        
    except Exception as e:
        logger.error(f"Error listing generated notes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list generated notes: {str(e)}"
        )

@router.get("")
async def list_generated_notes_root(
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    base_result = await list_generated_notes(auth_result=auth_result, db=db)
    notes = base_result.get("notes", [])
    adapted_notes = []
    for note in notes:
        adapted_note = dict(note)
        if "notes_id" in adapted_note and "id" not in adapted_note:
            adapted_note["id"] = adapted_note["notes_id"]
        adapted_notes.append(adapted_note)
    return {
        "notes": adapted_notes,
        "count": base_result.get("count", len(adapted_notes))
    }

@router.get("/document/{document_id}/notes")
async def get_notes_by_document_id_endpoint(
    document_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Get notes for a specific document by document ID
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting notes for document {document_id}")
        
        # Get notes from PostgreSQL (primary source)
        notes_entry = get_notes_by_document_id(db, document_id)
        
        if not notes_entry:
            raise HTTPException(
                status_code=404,
                detail="Notes not found for this document"
            )

        # Check if user owns these notes (security check)
        if notes_entry.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        return {
            "notes_id": notes_entry.id,
            "notes": notes_entry.notes_content,
            "metadata": {
                "course_name": notes_entry.course_name,
                "subject_name": notes_entry.subject_name,
                "unit_name": notes_entry.unit_name,
                "topic": notes_entry.topic,
                "document_name": notes_entry.document_name,
                "user_id": notes_entry.user_id,
                "content_length": notes_entry.content_length,
                "notes_length": notes_entry.notes_length,
                "s3_key": notes_entry.s3_key
            },
            "generated_at": notes_entry.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notes by document ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get notes: {str(e)}"
        )

@router.delete("/document/{document_id}/notes")
async def delete_notes_by_document_id(
    document_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Delete notes by document ID
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        
        # Get notes from PostgreSQL to find the notes ID
        notes_entry = get_notes_by_document_id(db, document_id)
        
        if not notes_entry:
            raise HTTPException(
                status_code=404,
                detail="Notes not found for this document"
            )
        
        # Check if user owns these notes (security check)
        if notes_entry.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        
        notes_id = notes_entry.id
        
        # Delete from PostgreSQL (primary storage)
        deleted = delete_notes_by_id(db, notes_id, user_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Notes not found or access denied"
            )
        
        # Also delete from S3 backup
        try:
            import boto3
            from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION
            )
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=f"{NOTES_PREFIX}{notes_id}.md"
            )
            logger.info(f"Successfully deleted notes from S3 backup: {notes_id}")
        except Exception as e:
            logger.warning(f"Failed to delete notes from S3 backup: {str(e)}")
            # Don't fail the request if S3 deletion fails
        
        # Clean up S3 metadata - remove the notes entry from the metadata file
        try:
            notes_list = load_notes_metadata()
            # Remove the deleted notes from the metadata list
            notes_list = [note for note in notes_list if note.get('notes_id') != notes_id]
            save_notes_metadata(notes_list)
            logger.info(f"Successfully cleaned up S3 metadata for notes: {notes_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up S3 metadata for notes {notes_id}: {str(e)}")
            # Don't fail the request if metadata cleanup fails
        
        return {"message": "Notes deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notes by document ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete notes: {str(e)}"
        )

@router.get("/{notes_id}")
async def get_generated_notes(
    notes_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Get specific generated notes by ID
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        
        # Get notes from PostgreSQL (primary source)
        notes_entry = get_notes_by_id(db, notes_id)
        
        if not notes_entry:
            raise HTTPException(
                status_code=404,
                detail="Notes not found"
            )
        
        # Check if user owns these notes (security check)
        if notes_entry.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        
        return {
            "notes_id": notes_id,
            "notes": notes_entry.notes_content,
            "metadata": {
                "course_name": notes_entry.course_name,
                "subject_name": notes_entry.subject_name,
                "unit_name": notes_entry.unit_name,
                "topic": notes_entry.topic,
                "document_name": notes_entry.document_name,
                "user_id": notes_entry.user_id,
                "content_length": notes_entry.content_length,
                "notes_length": notes_entry.notes_length,
                "s3_key": notes_entry.s3_key
            },
            "generated_at": notes_entry.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generated notes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get generated notes: {str(e)}"
        )

@router.delete("/{notes_id}")
async def delete_generated_notes(
    notes_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Delete generated notes by ID
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        
        # Delete from PostgreSQL (primary storage)
        deleted = delete_notes_by_id(db, notes_id, user_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Notes not found or access denied"
            )
        
        # Also delete from S3 backup
        try:
            import boto3
            from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION
            )
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=f"{NOTES_PREFIX}{notes_id}.md"
            )
            logger.info(f"Successfully deleted notes from S3 backup: {notes_id}")
        except Exception as e:
            logger.warning(f"Failed to delete notes from S3 backup: {str(e)}")
            # Don't fail the request if S3 deletion fails
        
        # Clean up S3 metadata - remove the notes entry from the metadata file
        try:
            notes_list = load_notes_metadata()
            # Remove the deleted notes from the metadata list
            notes_list = [note for note in notes_list if note.get('notes_id') != notes_id]
            save_notes_metadata(notes_list)
            logger.info(f"Successfully cleaned up S3 metadata for notes: {notes_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up S3 metadata for notes {notes_id}: {str(e)}")
            # Don't fail the request if metadata cleanup fails
        
        return {"message": "Notes deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting generated notes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete generated notes: {str(e)}"
        )

@router.get("/health")
async def notes_health_check(auth_result: dict = Depends(get_dual_auth_user)):
    """
    Health check endpoint for notes service
    """
    return {
        "status": "healthy",
        "service": "notes-generation",
        "timestamp": datetime.now().isoformat(),
        "openai_configured": bool(OPENAI_API_KEY),
        "database_available": True,  # Will be updated based on actual DB status
        "s3_available": True  # Will be updated based on actual S3 status
    }

@router.post("/reprocess-document/{document_id}")
async def reprocess_document_for_notes(
    document_id: str,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """
    Trigger reprocessing of a document to fix vector store issues
    """
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting reprocessing for document {document_id}")
        
        # Verify document exists
        document = get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        # Check if document is already being processed
        if document.get('processing', False):
            raise HTTPException(
                status_code=400,
                detail=f"Document {document_id} is already being processed. Please wait for completion."
            )
        
        # Here you would typically trigger the document processing
        # For now, we'll return a message indicating the user should use the documents endpoint
        return {
            "message": f"Document {document_id} needs to be reprocessed to fix vector store issues.",
            "action_required": "Please use the documents endpoint to reprocess this document.",
            "document_id": document_id,
            "document_name": document.get('fileName', 'Unknown')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reprocess document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@router.get("/document/{document_id}/status")
async def check_document_status(
    document_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Check if a document is ready for notes generation
    """
    try:
        # Load documents
        load_documents()
        
        # Get user context
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} checking status for document {document_id}")
        
        # Verify document exists
        document = get_document(document_id)
        if not document:
            return {
                "document_id": document_id,
                "exists": False,
                "ready_for_notes": False,
                "message": "Document not found"
            }
        
        # Check processing status
        is_processed = document.get('processed', False)
        is_processing = document.get('processing', False)
        
        if is_processing:
            return {
                "document_id": document_id,
                "exists": True,
                "ready_for_notes": False,
                "message": "Document is currently being processed"
            }
        
        if not is_processed:
            return {
                "document_id": document_id,
                "exists": True,
                "ready_for_notes": False,
                "message": "Document is not processed"
            }
        
        # Check if notes already exist (check PostgreSQL first - faster)
        existing_db_notes = False
        try:
            existing_db_notes = check_notes_exist(db, document_id)
        except Exception as db_error:
            logger.warning(f"Database check failed: {str(db_error)}")
        
        # Only check vector store if no notes exist (optimization)
        if not existing_db_notes:
            try:
                # Use fast check without loading for better performance
                vector_store_exists = verify_document_processed(document_id)
                if not vector_store_exists:
                    return {
                        "document_id": document_id,
                        "exists": True,
                        "ready_for_notes": False,
                        "message": "Vector store not found - document needs to be reprocessed"
                    }
            except Exception as e:
                logger.error(f"Error checking vector store for document {document_id}: {str(e)}")
                return {
                    "document_id": document_id,
                    "exists": True,
                    "ready_for_notes": False,
                    "message": f"Error checking vector store: {str(e)}"
                }
        
        # Check S3 notes only if not found in database
        existing_notes = None
        if not existing_db_notes:
            existing_notes = get_existing_notes(document_id)
            
        has_existing_notes = existing_notes is not None or existing_db_notes
        
        return {
            "document_id": document_id,
            "exists": True,
            "ready_for_notes": True,
            "message": "Document is ready for notes generation",
            "document_name": document.get('fileName', 'Unknown'),
            "processed": True,
            "has_existing_notes": has_existing_notes
        }
        
    except Exception as e:
        logger.error(f"Error checking document status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error checking document status: {str(e)}"
        )

@router.post("/documents/status/batch")
async def check_documents_status_batch(
    document_ids: List[str],
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """
    Check status for multiple documents efficiently
    """
    try:
        # Load documents
        load_documents()
        
        # Get user context
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} checking batch status for {len(document_ids)} documents")
        
        results = {}
        
        # First, check all documents exist and are processed
        for doc_id in document_ids:
            document = get_document(doc_id)
            if not document:
                results[doc_id] = {
                    "exists": False,
                    "ready_for_notes": False,
                    "has_existing_notes": False,
                    "message": "Document not found"
                }
                continue
                
            is_processed = document.get('processed', False)
            is_processing = document.get('processing', False)
            
            if is_processing:
                results[doc_id] = {
                    "exists": True,
                    "ready_for_notes": False,
                    "has_existing_notes": False,
                    "message": "Document is currently being processed"
                }
                continue
                
            if not is_processed:
                results[doc_id] = {
                    "exists": True,
                    "ready_for_notes": False,
                    "has_existing_notes": False,
                    "message": "Document is not processed"
                }
                continue
                
            # Mark as ready initially
            results[doc_id] = {
                "exists": True,
                "ready_for_notes": True,
                "has_existing_notes": False,
                "message": "Document is ready for notes generation"
            }
        
        # Batch check for existing notes in database (much faster)
        try:
            # Get all notes for the user
            user_notes = get_notes_by_user_id(db, user_id)
            user_notes_dict = {note.document_id: note for note in user_notes}
            
            # Update results with existing notes
            for doc_id in document_ids:
                if doc_id in user_notes_dict:
                    results[doc_id]["has_existing_notes"] = True
                    
        except Exception as db_error:
            logger.warning(f"Batch database check failed: {str(db_error)}")
        
        # Only check vector stores for documents without notes (optimization)
        docs_to_check_vectorstore = [
            doc_id for doc_id in document_ids 
            if results[doc_id]["ready_for_notes"] and not results[doc_id]["has_existing_notes"]
        ]
        
        # Batch check vector stores (if needed) - use fast check without loading
        for doc_id in docs_to_check_vectorstore:
            try:
                vector_store_exists = verify_document_processed(doc_id)
                if not vector_store_exists:
                    results[doc_id]["ready_for_notes"] = False
                    results[doc_id]["message"] = "Vector store not found - document needs to be reprocessed"
            except Exception as e:
                logger.error(f"Error checking vector store for document {doc_id}: {str(e)}")
                results[doc_id]["ready_for_notes"] = False
                results[doc_id]["message"] = f"Error checking vector store: {str(e)}"
        
        return {
            "results": results,
            "total_checked": len(document_ids),
            "with_notes": sum(1 for r in results.values() if r.get("has_existing_notes", False)),
            "ready_for_notes": sum(1 for r in results.values() if r.get("ready_for_notes", False))
        }
        
    except Exception as e:
        logger.error(f"Error in batch status check: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch status check: {str(e)}"
        ) 