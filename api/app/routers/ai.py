# Import all required modules cleanly
from fastapi import APIRouter, HTTPException, Body, Depends, UploadFile, File
from fastapi.responses import JSONResponse, Response
from typing import List, Optional, Dict, Any
import os
import json
import shutil
from datetime import datetime
from functools import lru_cache
import hashlib
import time
import logging

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
)
from langchain.chains import ConversationalRetrievalChain
from langchain_community.vectorstores import FAISS

# Pydantic
from pydantic import ConfigDict, BaseModel

# Local imports
from app.core.security import get_current_user
from app.core.dual_auth import get_dual_auth_user
from app.models.document import QuestionInput, QuestionResponse, SourceMetadata
from app.utils.file_utils import load_json
from app.utils.vector_store import (
    get_embeddings, load_vector_store, verify_document_processed
)
from app.config.settings import (
    DATA_DIR, VECTOR_STORES_DIR, OPENAI_API_KEY, GOOGLE_API_KEY,
    CHAT_MODEL, DEFAULT_CHUNK_SIZE, AI_PROVIDER
)
from app.utils.s3_utils import (
    load_documents_metadata, save_response_to_s3, load_response_from_s3,
    save_template_to_s3, load_template_from_s3, list_available_templates,
    get_template_s3_key, list_template_backups, restore_template_from_backup
)

# FastAPI and other imports
from fastapi.middleware.cors import CORSMiddleware
import math
import asyncio



router = APIRouter(
    prefix="/api/ai",
    tags=["ai"]
)

@router.get("/health")
async def health_check(auth_result: dict = Depends(get_dual_auth_user)):
    """Health check endpoint to verify vector store loading capabilities"""
    try:
        print(f"[HEALTH_CHECK] Health check requested at {datetime.now().isoformat()}")
        
        # Test environment variables
        env_status = {
            "AI_PROVIDER": AI_PROVIDER,
            "OPENAI_API_KEY": "configured" if OPENAI_API_KEY and OPENAI_API_KEY != "dummy_key_for_testing" else "not_configured",
            "GOOGLE_API_KEY": "configured" if GOOGLE_API_KEY and GOOGLE_API_KEY != "dummy_key_for_testing" else "not_configured",
            "VECTOR_STORES_DIR": VECTOR_STORES_DIR,
            "DATA_DIR": DATA_DIR
        }
        
        # Test embeddings loading
        try:
            embeddings = get_embeddings()
            embeddings_status = "working"
            print(f"[HEALTH_CHECK] ✓ Embeddings loaded successfully")
        except Exception as e:
            embeddings_status = f"failed: {str(e)}"
            print(f"[HEALTH_CHECK] ✗ Embeddings failed: {str(e)}")
        
        # Test S3 connection (if available)
        try:
            templates = list_available_templates()
            s3_status = "working"
            print(f"[HEALTH_CHECK] ✓ S3 connection successful")
        except Exception as e:
            s3_status = f"failed: {str(e)}"
            print(f"[HEALTH_CHECK] ✗ S3 connection failed: {str(e)}")
        
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": env_status,
            "embeddings": embeddings_status,
            "s3": s3_status,
            "vector_store_cache_size": len(vector_store_cache)
        }
        
        print(f"[HEALTH_CHECK] Health check completed successfully")
        return result
        
    except Exception as e:
        print(f"[HEALTH_CHECK] ✗ Health check failed: {str(e)}")
        
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/test-basic", dependencies=[])
async def test_basic_functionality(auth_result: dict = Depends(get_dual_auth_user)):
    """Basic test endpoint to check if the service is running"""
    try:
        print(f"[BASIC_TEST] Basic test requested at {datetime.now().isoformat()}")
        
        # Test basic Python functionality
        test_result = {
            "status": "basic_test_passed",
            "timestamp": datetime.now().isoformat(),
            "python_version": "working",
            "basic_imports": "working",
            "ai_provider": AI_PROVIDER,
            "env_access": "working"
        }
        
        print(f"[BASIC_TEST] Basic test completed successfully")
        return test_result
        
    except Exception as e:
        print(f"[BASIC_TEST] ✗ Basic test failed: {str(e)}")
        
        return {
            "status": "basic_test_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/test-vectorstore/{doc_id}")
async def test_vectorstore_loading(doc_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Test endpoint to verify vector store loading for a specific document"""
    try:
        print(f"[DEBUG] Testing vector store loading for document {doc_id}")
        
        # Test vector store loading
        vector_store = get_cached_vector_store(doc_id)
        
        if not vector_store:
            return {
                "status": "failed",
                "error": "Vector store could not be loaded",
                "doc_id": doc_id,
                "timestamp": datetime.now().isoformat()
            }
        
        # Test basic operations
        try:
            # Test index access
            index_size = vector_store.index.ntotal if hasattr(vector_store, 'index') and vector_store.index else 0
            index_dimension = vector_store.index.d if hasattr(vector_store, 'index') and vector_store.index else 0
            
            # Test basic search
            test_results = vector_store.similarity_search("test", k=1)
            search_working = len(test_results) > 0
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "index_size": index_size,
                "index_dimension": index_dimension,
                "search_working": search_working,
                "test_results_count": len(test_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as test_error:
            return {
                "status": "partial_success",
                "doc_id": doc_id,
                "error": f"Vector store loaded but operations failed: {str(test_error)}",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"[ERROR] Test vector store loading failed: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "doc_id": doc_id,
            "timestamp": datetime.now().isoformat()
        }

# Global documents list (will be loaded from disk)
documents = []

# Cache for frequently asked questions
question_cache: Dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour cache TTL

# Add a response cache to store recent responses
response_cache = {}
RESPONSE_CACHE_TTL = 3600  # 1 hour

# Vector store cache with proper cleanup
vector_store_cache: Dict[str, Any] = {}
VECTOR_STORE_CACHE_TTL = 1800  # 30 minutes cache TTL
vector_store_timestamps: Dict[str, float] = {}

# Update the memory configuration with proper Pydantic settings
class MemoryConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

# User session management for conversation memory
user_sessions: Dict[str, ConversationBufferWindowMemory] = {}
USER_SESSION_TTL = 3600  # 1 hour
user_session_timestamps: Dict[str, float] = {}

def get_user_memory(user_id: str) -> ConversationBufferWindowMemory:
    """Get or create conversation memory for a user"""
    current_time = time.time()
    
    # Clean up expired sessions
    expired_users = [uid for uid, timestamp in user_session_timestamps.items() 
                    if current_time - timestamp > USER_SESSION_TTL]
    for uid in expired_users:
        if uid in user_sessions:
            del user_sessions[uid]
        if uid in user_session_timestamps:
            del user_session_timestamps[uid]
    
    # Create new session if doesn't exist
    if user_id not in user_sessions:
        user_sessions[user_id] = ConversationBufferWindowMemory(
            k=3,  # Keep last 3 exchanges
            return_messages=True,
            memory_key="chat_history",
            output_key="answer"
        )
        user_session_timestamps[user_id] = current_time
    
    # Update timestamp
    user_session_timestamps[user_id] = current_time
    
    return user_sessions[user_id]

def cleanup_expired_user_sessions():
    """Clean up expired user sessions"""
    current_time = time.time()
    expired_users = [uid for uid, timestamp in user_session_timestamps.items() 
                    if current_time - timestamp > USER_SESSION_TTL]
    for uid in expired_users:
        if uid in user_sessions:
            del user_sessions[uid]
        if uid in user_session_timestamps:
            del user_session_timestamps[uid]

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    output_key="answer",
    model_config=MemoryConfig.model_config
)

def get_chat_model(temperature: float = 0.3, max_tokens: Optional[int] = None, request_timeout: int = 30, max_retries: int = 2):
    """Get chat model based on configured AI provider"""
    # Use higher token limits for comprehensive responses
    if max_tokens is None:
        if AI_PROVIDER == "google":
            max_tokens = 8192  # Gemini 2.5 Flash supports up to 8192 tokens
        else:
            max_tokens = 4096  # GPT-3.5-turbo supports up to 4096 tokens
    
    if AI_PROVIDER == "google":
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when AI_PROVIDER is set to 'google'")
        return ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            temperature=temperature,
            google_api_key=GOOGLE_API_KEY,
            max_output_tokens=max_tokens,
            request_timeout=request_timeout,
            max_retries=max_retries,
            convert_system_message_to_human=True
        )
    else:  # OpenAI
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER is set to 'openai'")
        return ChatOpenAI(
            model_name=CHAT_MODEL,
            temperature=temperature,
            openai_api_key=OPENAI_API_KEY,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            max_retries=max_retries
        )

def get_cache_key(question: str, document_id: Optional[str] = None, filter_dict: Optional[dict] = None) -> str:
    """Generate a cache key for a question"""
    key_parts = [question, str(document_id) if document_id else "all"]
    if filter_dict:
        key_parts.append(json.dumps(filter_dict, sort_keys=True))
    return hashlib.md5("|".join(key_parts).encode()).hexdigest()

def cleanup_expired_caches():
    """Clean up expired caches to prevent memory leaks"""
    current_time = time.time()
    
    # Clean up question cache
    expired_keys = []
    for key, value in question_cache.items():
        if (current_time - value["timestamp"]) > CACHE_TTL:
            expired_keys.append(key)
    
    for key in expired_keys:
        del question_cache[key]
    
    # Clean up response cache
    expired_response_keys = []
    for key, value in response_cache.items():
        if (current_time - value["timestamp"]) > RESPONSE_CACHE_TTL:
            expired_response_keys.append(key)
    
    for key in expired_response_keys:
        del response_cache[key]
    
    # Clean up vector store cache
    expired_vector_keys = []
    for key, timestamp in vector_store_timestamps.items():
        if (current_time - timestamp) > VECTOR_STORE_CACHE_TTL:
            expired_vector_keys.append(key)
    
    for key in expired_vector_keys:
        if key in vector_store_cache:
            del vector_store_cache[key]
        del vector_store_timestamps[key]
    
    # Clean up user sessions
    cleanup_expired_user_sessions()
    
    if expired_keys or expired_response_keys or expired_vector_keys:
        print(f"[CACHE_CLEANUP] Cleaned up {len(expired_keys)} question cache entries, {len(expired_response_keys)} response cache entries, {len(expired_vector_keys)} vector store cache entries")

def ensure_document_metadata(doc_obj, document_id: str, filename: str = "Unknown"):
    """Ensure Document object has proper metadata for newer LangChain versions"""
    if not hasattr(doc_obj, 'metadata') or not doc_obj.metadata:
        doc_obj.metadata = {}
    
    # Add document ID to metadata if not present
    if 'source' not in doc_obj.metadata:
        doc_obj.metadata['source'] = str(document_id)
    if 'document_id' not in doc_obj.metadata:
        doc_obj.metadata['document_id'] = str(document_id)
    if 'filename' not in doc_obj.metadata:
        doc_obj.metadata['filename'] = filename
    
    return doc_obj

def load_pharmacy_template():
    """Load the pharmacy prompt template from S3 (preferred) or local file (fallback)"""
    try:
        # Try to load from S3 first
        template = load_template_from_s3("pharmacy_prompt")
        if template:
            return template
    except Exception as e:
        logging.error(f"Error loading template from S3: {str(e)}")
    
    # Fallback to local file
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(base_dir, '..', 'templates')
        template_path = os.path.join(templates_dir, 'pharmacy_prompt.txt')
        os.makedirs(templates_dir, exist_ok=True)
        
        if not os.path.exists(template_path):
            default_template = """You are a helpful AI assistant specialized in academic and educational content. Use the following context to answer the question comprehensively.

IMPORTANT INSTRUCTIONS:
1. Use ONLY the information provided in the context to answer the question
2. If the context contains relevant information, provide a detailed and comprehensive answer
3. If the context doesn't contain enough information to answer the question, clearly state what information is missing
4. Do NOT use external knowledge or make assumptions beyond what's in the context
5. If the question asks for specific examples, concepts, or details, focus on what's mentioned in the context
6. Structure your answer logically and clearly
7. If the context mentions worked examples, exercises, or specific content, reference them in your answer

Context: {context}
Question: {question}
Document Context: {doc_context}

Answer:"""
            # Save default template both locally and to S3
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(default_template)
            save_template_to_s3(default_template, "pharmacy_prompt")
            return default_template
            
        with open(template_path, encoding='utf-8') as f:
            template_content = f.read()
            # Try to sync local template to S3 if it's not there
            try:
                s3_template = load_template_from_s3("pharmacy_prompt")
                if not s3_template:
                    save_template_to_s3(template_content, "pharmacy_prompt")
            except Exception as e:
                logging.error(f"Failed to sync template to S3: {str(e)}")
            return template_content
    except Exception as e:
        logging.error(f"Error loading pharmacy template locally: {str(e)}")
        return "You are a helpful AI assistant specialized in academic and educational content. Use the following context to answer the question comprehensively.\n\nIMPORTANT INSTRUCTIONS:\n1. Use ONLY the information provided in the context to answer the question\n2. If the context contains relevant information, provide a detailed and comprehensive answer\n3. If the context doesn't contain enough information to answer the question, clearly state what information is missing\n4. Do NOT use external knowledge or make assumptions beyond what's in the context\n5. If the question asks for specific examples, concepts, or details, focus on what's mentioned in the context\n6. Structure your answer logically and clearly\n7. If the context mentions worked examples, exercises, or specific content, reference them in your answer\n\nContext: {context}\nQuestion: {question}\nDocument Context: {doc_context}\n\nAnswer:"

def load_model_paper_prediction_template():
    """Load the model paper prediction template from S3 (preferred) or local file (fallback)"""
    try:
        # Try to load from S3 first
        template = load_template_from_s3("model_paper_prediction")
        if template:
            return template
    except Exception as e:
        logging.error(f"Error loading model paper prediction template from S3: {str(e)}")
    
    # Fallback to local file
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(base_dir, '..', 'templates')
        template_path = os.path.join(templates_dir, 'model_paper_prediction.txt')
        os.makedirs(templates_dir, exist_ok=True)
        
        if not os.path.exists(template_path):
            logging.error("Model paper prediction template not found locally")
            return None
            
        with open(template_path, encoding='utf-8') as f:
            template_content = f.read()
            # Try to sync local template to S3 if it's not there
            try:
                s3_template = load_template_from_s3("model_paper_prediction")
                if not s3_template:
                    save_template_to_s3(template_content, "model_paper_prediction")
            except Exception as e:
                logging.error(f"Failed to sync template to S3: {str(e)}")
            return template_content
    except Exception as e:
        logging.error(f"Error loading model paper prediction template locally: {str(e)}")
        return None

def load_notes_template():
    """Load the notes prompt template from S3 (preferred) or local file (fallback)"""
    try:
        # Try to load from S3 first
        template = load_template_from_s3("notes_prompt")
        if template:
            return template
    except Exception as e:
        logging.error(f"Error loading notes template from S3: {str(e)}")
    
    # Fallback to local file
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(base_dir, '..', 'templates')
        template_path = os.path.join(templates_dir, 'notes_prompt.txt')
        os.makedirs(templates_dir, exist_ok=True)
        
        if not os.path.exists(template_path):
            default_template = """You are an expert academic assistant. Create professional, structured academic notes in **Markdown format** using the input below.

Requirements:
1. Use proper Markdown headers: `#`, `##`, `###`, `####`
2. Use bullet points (`-`) and numbered lists
3. Use LaTeX for math:
   - Inline math in `$...$`
   - Block math in `$$...$$`
4. Use GitHub-Flavored Markdown tables with proper formatting:
   - Use pipe `|` to separate columns
   - Include header row with column names
   - Add separator row with at least 3 dashes per column: `|---|---|---|`
   - Ensure consistent number of columns in all rows
   - No leading/trailing spaces before or after pipes
   - ALWAYS include the separator row after headers
5. Wrap SMILES with `<mol>...</mol>`
6. Wrap chemical formulas with `<chem>...</chem>`
7. Emphasize key points using `**bold**` or `*italic*`
8. Do **NOT** include metadata like course, subject, unit, or topic headings in the output
9. Do **NOT** use HTML tags — use only Markdown and the special tags mentioned above

---

Document Info:
- Course: {course_name}
- Subject: {subject_name}
- Unit: {unit_name}
- Topic: {topic}

Document Content:
{document_content}

---

Ensure:
- Start directly with the topic content
- Tables are well-formatted with aligned pipes and proper separators
- All tables follow GitHub-Flavored Markdown syntax exactly
- For "Official Data" tables, use proper headers like "Property" and "Value"
- Final output is fully compatible with `remark-gfm` and `react-markdown`
- No malformed or misaligned tables
- No raw pipe characters in the output

Return only the formatted notes in Markdown. No explanations."""
            # Save default template both locally and to S3
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(default_template)
            save_template_to_s3(default_template, "notes_prompt")
            return default_template
            
        with open(template_path, encoding='utf-8') as f:
            template_content = f.read()
            # Try to sync local template to S3 if it's not there
            try:
                s3_template = load_template_from_s3("notes_prompt")
                if not s3_template:
                    save_template_to_s3(template_content, "notes_prompt")
            except Exception as e:
                logging.error(f"Failed to sync template to S3: {str(e)}")
            return template_content
    except Exception as e:
        logging.error(f"Error loading notes template locally: {str(e)}")
        return """You are an expert academic assistant. Create professional, structured academic notes in **Markdown format** using the input below.

Requirements:
1. Use proper Markdown headers: `#`, `##`, `###`, `####`
2. Use bullet points (`-`) and numbered lists
3. Use LaTeX for math:
   - Inline math in `$...$`
   - Block math in `$$...$$`
4. Use GitHub-Flavored Markdown tables with proper formatting:
   - Use pipe `|` to separate columns
   - Include header row with column names
   - Add separator row with at least 3 dashes per column: `|---|---|---|`
   - Ensure consistent number of columns in all rows
   - No leading/trailing spaces before or after pipes
   - ALWAYS include the separator row after headers
5. Wrap SMILES with `<mol>...</mol>`
6. Wrap chemical formulas with `<chem>...</chem>`
7. Emphasize key points using `**bold**` or `*italic*`
8. Do **NOT** include metadata like course, subject, unit, or topic headings in the output
9. Do **NOT** use HTML tags — use only Markdown and the special tags mentioned above

---

Document Info:
- Course: {course_name}
- Subject: {subject_name}
- Unit: {unit_name}
- Topic: {topic}

Document Content:
{document_content}

---

Ensure:
- Start directly with the topic content
- Tables are well-formatted with aligned pipes and proper separators
- All tables follow GitHub-Flavored Markdown syntax exactly
- For "Official Data" tables, use proper headers like "Property" and "Value"
- Final output is fully compatible with `remark-gfm` and `react-markdown`
- No malformed or misaligned tables
- No raw pipe characters in the output

Return only the formatted notes in Markdown. No explanations."""

@router.get("/ask/{response_id}")
async def get_response(response_id: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get a cached response by ID and format it using the pharmacy prompt template"""
    try:
        print(f"Attempting to retrieve response for ID: {response_id}")
        print(f"Current cache keys: {list(response_cache.keys())}")
        
        if response_id in response_cache:
            cached_data = response_cache[response_id]
            current_time = datetime.now().timestamp()
            cache_age = current_time - cached_data["timestamp"]
            
            print(f"Found cached response, age: {cache_age}s")
            
            if cache_age < RESPONSE_CACHE_TTL:
                print(f"Retrieved valid cached response for ID: {response_id}")
                
                # Load the pharmacy prompt template
                try:
                    template = load_pharmacy_template()
                except Exception as e:
                    print(f"Error loading template: {str(e)}")
                    # If template loading fails, return the original response
                    return cached_data["response"]
                
                # Format the response using the template
                try:
                    # Initialize chat model
                    chat_model = get_chat_model()
                    
                    # Get the original response data
                    original_response = cached_data["response"]
                    context = "\n".join([source.get("chunk_text", "") for source in original_response.get("sources", [])])
                    
                    # Format the prompt using the template
                    #template_text = load_pharmacy_template()
                    system_prompt = load_pharmacy_template()
                    chat_prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("human", """Context:
                    {context}
 
                    Question:
                    {question}
 
                    Instructions:
                    - Use ONLY the context above to answer the question.
                    - Do NOT use external knowledge or inference.
                    - Include only sections mentioned in the context.
                    - Use <chem>, <mol>, <calc> tags only if present in the context.
                    - Omit empty sections from your answer.
                    """)
                    ])

 
                    messages = chat_prompt.format_messages(context=context, question=original_response.get('question', ''))
                    result = chat_model.invoke(messages)
                    
                    # Add logging for context and question
                    print(f"[DEBUG] Context being sent to AI: {context}")
                    print(f"[DEBUG] Question: {original_response.get('question', '')}")
                    
                    # Get formatted response from AI
                    result = chat_model.invoke(messages)
                    
                    # Create new formatted response
                    formatted_response = {
                        "answer": result.content.strip(),
                        "sources": original_response.get("sources", []),
                        "timestamp": datetime.now().isoformat(),
                        "original_answer": original_response.get("answer", "")  # Keep original for reference
                    }
                    
                    print(f"Formatted response using template for ID: {response_id}")
                    # PATCH: Ensure answer is always a string
                    if not isinstance(formatted_response.get("answer", ""), str):
                        formatted_response["answer"] = "Sorry, the AI could not generate a valid answer for your question."
                    return formatted_response
                    
                except Exception as e:
                    print(f"Error formatting response with template: {str(e)}")
                    # If formatting fails, return the original response
                    response_to_return = cached_data["response"]
                    if not isinstance(response_to_return.get("answer", ""), str):
                        response_to_return["answer"] = "Sorry, the AI could not generate a valid answer for your question."
                    return response_to_return
            else:
                print(f"Cache expired for ID: {response_id}")
                del response_cache[response_id]
        # Try to load from S3 if not in cache
        print(f"[DEBUG] Response not found in cache, trying S3 for ID: {response_id}")
        s3_response = load_response_from_s3(response_id)
        if s3_response:
            print(f"[DEBUG] Loaded response from S3 for ID: {response_id}")
            return s3_response
        print(f"Response not found in cache or S3 for ID: {response_id}")
        raise HTTPException(status_code=404, detail="Response not found or expired")
    except HTTPException as http_exc:
        raise
    except Exception as e:
        print(f"Error retrieving response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving response: {str(e)}")

@router.post("/ask")
async def ask_question(question: QuestionInput, auth_result: dict = Depends(get_dual_auth_user)):
    """Ask a question about documents with performance monitoring"""
    start_time = time.time()
    global documents
    
    # Immediate debugging for deployment issues
    print(f"[DEPLOYMENT_DEBUG] ===== ASK QUESTION REQUEST START =====")
    print(f"[DEPLOYMENT_DEBUG] Request received at: {datetime.now().isoformat()}")
    print(f"[DEPLOYMENT_DEBUG] Question: {question.question}")
    print(f"[DEPLOYMENT_DEBUG] Document ID: {question.document_id}")
    print(f"[DEPLOYMENT_DEBUG] Auth type: {auth_result.get('auth_type', 'unknown')}")
    print(f"[DEPLOYMENT_DEBUG] Authenticated user: {auth_result.get('user_data', {}).get('sub', 'unknown')}")
    print(f"[DEPLOYMENT_DEBUG] User role: {auth_result.get('user_data', {}).get('role', 'unknown')}")
    
    # Check environment variables immediately
    print(f"[DEPLOYMENT_DEBUG] Environment check:")
    print(f"[DEPLOYMENT_DEBUG] - AI_PROVIDER: {AI_PROVIDER}")
    print(f"[DEPLOYMENT_DEBUG] - OPENAI_API_KEY: {'SET' if OPENAI_API_KEY and OPENAI_API_KEY != 'dummy_key_for_testing' else 'NOT_SET'}")
    print(f"[DEPLOYMENT_DEBUG] - GOOGLE_API_KEY: {'SET' if GOOGLE_API_KEY and GOOGLE_API_KEY != 'dummy_key_for_testing' else 'NOT_SET'}")
    print(f"[DEPLOYMENT_DEBUG] - VECTOR_STORES_DIR: {VECTOR_STORES_DIR}")
    print(f"[DEPLOYMENT_DEBUG] - DATA_DIR: {DATA_DIR}")
    
    # Check if we can import required modules
    try:
        from langchain_community.vectorstores import FAISS
        print(f"[DEPLOYMENT_DEBUG] ✓ FAISS import successful")
    except Exception as e:
        print(f"[DEPLOYMENT_DEBUG] ✗ FAISS import failed: {str(e)}")
    
    try:
        from langchain_openai import OpenAIEmbeddings
        print(f"[DEPLOYMENT_DEBUG] ✓ OpenAIEmbeddings import successful")
    except Exception as e:
        print(f"[DEPLOYMENT_DEBUG] ✗ OpenAIEmbeddings import failed: {str(e)}")
    
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        print(f"[DEPLOYMENT_DEBUG] ✓ GoogleGenerativeAIEmbeddings import successful")
    except Exception as e:
        print(f"[DEPLOYMENT_DEBUG] ✗ GoogleGenerativeAIEmbeddings import failed: {str(e)}")
    
    try:
        from ..utils.s3_utils import load_documents_metadata
        print(f"[DEPLOYMENT_DEBUG] ✓ S3 utils import successful")
    except Exception as e:
        print(f"[DEPLOYMENT_DEBUG] ✗ S3 utils import failed: {str(e)}")
    
    print(f"[DEPLOYMENT_DEBUG] ===== ENVIRONMENT CHECK COMPLETE =====")
    
    try:
        # Validate input
        if not question.question or not question.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        # Validate API keys based on provider
        if AI_PROVIDER == "google":
            if not GOOGLE_API_KEY or GOOGLE_API_KEY == "dummy_key_for_testing":
                raise HTTPException(
                    status_code=400,
                    detail="Google API key not configured"
                )
        else:  # OpenAI
            if not OPENAI_API_KEY or OPENAI_API_KEY == "dummy_key_for_testing":
                raise HTTPException(
                    status_code=400,
                    detail="OpenAI API key not configured"
                )
        
        print(f"[DEBUG] API keys validated. Provider: {AI_PROVIDER}")
        
        # Load documents from S3 to ensure we have latest data
        try:
            documents = load_documents_metadata() or []
            print(f"[DEBUG] Loaded {len(documents)} documents from S3 metadata.")
        except Exception as e:
            print(f"[ERROR] Failed to load documents from S3: {str(e)}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception details: {str(e)}")
            documents = []
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load documents from S3: {str(e)}"
            )
        
        # Check if there are any processed documents
        processed_docs = [d for d in documents if d.get("processed", False)]
        if not processed_docs:
            raise HTTPException(
                status_code=400,
                detail="No processed documents available. Please process some documents first."
            )
        
        print(f"[DEBUG] Found {len(processed_docs)} processed documents")
        
        # Validate document_id if provided
        if question.document_id:
            doc = next((d for d in documents if str(d.get("id")) == str(question.document_id)), None)
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found with ID: {question.document_id}"
                )
            
            # Check if document is processed
            if not doc.get("processed", False):
                if doc.get("processing", False):
                    raise HTTPException(
                        status_code=400,
                        detail="Document is currently being processed. Please try again in a few moments."
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Document is not processed. Please process the document first."
                    )
            
            print(f"[DEBUG] Document {question.document_id} validated successfully")
        
        try:
            # Initialize chat model with increased timeout
            chat_model = get_chat_model(request_timeout=120)  # Increased timeout to 2 minutes
            print(f"[DEBUG] Chat model initialized successfully with provider: {AI_PROVIDER}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize chat model: {str(e)}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception details: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize AI model: {str(e)}"
            )

        # Generate cache key and response ID first
        filter_dict = {}
        for key in ["year", "semester", "subject", "unit", "topic"]:
            value = getattr(question, key, None)
            if value:
                filter_dict[key] = value
        
        if question.metadata_filter:
            for key, value in question.metadata_filter.items():
                if value and key in ["year", "semester", "subject", "unit", "topic"]:
                    filter_dict[key] = value
        
        if not filter_dict:
            filter_dict = None

        # Clean up expired caches before processing
        cleanup_expired_caches()

        # Get user ID for conversation-aware caching
        user_id = auth_result.get('user_data', {}).get('sub', 'anonymous')
        user_memory = get_user_memory(user_id)
        
        # Check if this is a follow-up question by looking at conversation history
        memory_vars = user_memory.load_memory_variables({})
        chat_history = memory_vars.get("chat_history", [])
        
        # Create conversation-aware cache key
        conversation_context_hash = ""
        if chat_history:
            # Create a hash of the conversation context for cache key
            conversation_text = " ".join([msg.content for msg in chat_history[-4:]])  # Last 4 messages
            conversation_context_hash = hashlib.md5(conversation_text.encode()).hexdigest()[:8]
        
        cache_key = get_cache_key(question.question, question.document_id, filter_dict)
        if conversation_context_hash:
            cache_key += f"_conv_{conversation_context_hash}"
        
        response_id = hashlib.md5(cache_key.encode()).hexdigest()
        
        # Check cache first (but only if no conversation context)
        if not conversation_context_hash and cache_key in question_cache:
            cached_result = question_cache[cache_key]
            if (datetime.now().timestamp() - cached_result["timestamp"]) < CACHE_TTL:
                print(f"Found cached response for key: {cache_key}")
                # Update response cache
                response_cache[response_id] = {
                    "response": cached_result["response"],
                    "timestamp": datetime.now().timestamp()
                }
                return cached_result["response"]
        elif conversation_context_hash:
            print(f"[DEBUG] Bypassing cache due to conversation context: {conversation_context_hash}")

        # Get relevant documents
        if question.document_id:
            print(f"[DEBUG] Processing question for specific document: {question.document_id}")
            
            try:
                vector_store = get_cached_vector_store(question.document_id)
                print(f"[DEBUG] Vector store loading attempt completed for document {question.document_id}")
            except Exception as vs_error:
                print(f"[ERROR] Exception during vector store loading: {str(vs_error)}")
                print(f"[ERROR] Exception type: {type(vs_error).__name__}")
                print(f"[ERROR] Exception details: {str(vs_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load vector store: {str(vs_error)}"
                )
            
            if not vector_store:
                print(f"[DEBUG] Vector store not found for document {question.document_id}")
                # Try to provide a helpful error message
                doc = next((d for d in documents if d["id"] == question.document_id), None)
                if doc:
                    if not doc.get("processed", False):
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Document '{doc.get('fileName', 'Unknown')}' is not processed. Please process it first."
                        )
                    else:
                        # Check if this might be a compatibility issue
                        error_msg = f"Vector store for document '{doc.get('fileName', 'Unknown')}' could not be loaded."
                        error_msg += " This may be due to a compatibility issue with the vector store format."
                        error_msg += " Please try reprocessing the document to recreate the vector store."
                        raise HTTPException(
                            status_code=404, 
                            detail=error_msg
                        )
                else:
                    raise HTTPException(status_code=404, detail="Document not found")
            
            print(f"[DEBUG] Vector store loaded successfully for document {question.document_id}")
            
            # Add debugging information about the vector store
            try:
                print(f"[DEBUG] Vector store index size: {vector_store.index.ntotal}")
                print(f"[DEBUG] Vector store dimension: {vector_store.index.d}")
                print(f"[DEBUG] Question being searched: '{question.question}'")
                print(f"[DEBUG] Filter dict: {filter_dict}")
            except Exception as debug_error:
                print(f"[WARNING] Could not get vector store debug info: {str(debug_error)}")
            
            # Test if vector store can find any documents at all
            try:
                test_results = vector_store.similarity_search("test", k=1)
                print(f"[DEBUG] Vector store test search successful, found {len(test_results)} results")
                
                # Additional test: try to get any documents at all
                if test_results:
                    print(f"[DEBUG] Test query successful - vector store is working")
                else:
                    print(f"[DEBUG] Test query returned no results - vector store may be empty")
                    
            except Exception as e:
                print(f"[ERROR] Vector store test search failed: {str(e)}")
                print(f"[ERROR] Exception type: {type(e).__name__}")
                print(f"[ERROR] Exception details: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Vector store test failed: {str(e)}"
                )
            
            # Get relevant chunks
            try:
                print(f"[DEBUG] Attempting similarity search with question: '{question.question}'")
                docs_with_scores = vector_store.similarity_search_with_score(
                    question.question,
                    k=12,  # Increased from 8 to 12 for better coverage
                    filter=filter_dict,
                    fetch_k=25,  # Increased from 15 to 25
                    score_threshold=0.05   # Reduced from 0.1 to 0.05 for better coverage
                )
                print(f"[DEBUG] Primary similarity search successful, found {len(docs_with_scores)} results")
            except Exception as search_error:
                print(f"[ERROR] Primary similarity search failed: {str(search_error)}")
                print(f"[ERROR] Exception type: {type(search_error).__name__}")
                print(f"[ERROR] Exception details: {str(search_error)}")
                
                # Try alternative search method
                try:
                    print(f"[DEBUG] Trying alternative search method...")
                    docs_with_scores = vector_store.similarity_search(
                        question.question,
                        k=5  # Increased from 3 to 5
                    )
                    # Convert to format expected by the rest of the code
                    docs_with_scores = [(doc, 0.5) for doc in docs_with_scores]  # Default score of 0.5
                    print(f"[DEBUG] Alternative search method successful, found {len(docs_with_scores)} results")
                except Exception as alt_search_error:
                    print(f"[ERROR] Alternative search also failed: {str(alt_search_error)}")
                    print(f"[ERROR] Exception type: {type(alt_search_error).__name__}")
                    print(f"[ERROR] Exception details: {str(alt_search_error)}")
                    
                    # Try to get any documents from the vector store as last resort
                    try:
                        print(f"[DEBUG] Trying empty search as last resort...")
                        total_docs = vector_store.index.ntotal
                        if total_docs > 0:
                            # Get the first few documents regardless of relevance
                            docs_with_scores = vector_store.similarity_search_with_score(
                                "",
                                k=min(5, total_docs),  # Increased from 3 to 5
                                fetch_k=total_docs
                            )
                            print(f"[DEBUG] Empty search successful, found {len(docs_with_scores)} chunks")
                        else:
                            raise Exception("Vector store is empty")
                    except Exception as empty_search_error:
                        print(f"[ERROR] Empty search also failed: {str(empty_search_error)}")
                        print(f"[ERROR] Exception type: {type(empty_search_error).__name__}")
                        print(f"[ERROR] Exception details: {str(empty_search_error)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"All search methods failed. Last error: {str(empty_search_error)}"
                        )
            
            print(f"[DEBUG] Found {len(docs_with_scores)} relevant chunks for question: {question.question}")
            
            # If no results with current threshold, try without threshold
            if not docs_with_scores:
                print("[DEBUG] No results with score_threshold=0.1, trying without threshold...")
                try:
                    docs_with_scores = vector_store.similarity_search_with_score(
                        question.question,
                        k=8,  # Increased from 5 to 8 for better coverage
                        filter=filter_dict,
                        fetch_k=15  # Increased from 10 to 15
                    )
                    print(f"[DEBUG] Found {len(docs_with_scores)} chunks without threshold")
                except Exception as e:
                    print(f"[DEBUG] Error in search without threshold: {str(e)}")
                    docs_with_scores = []
            
            # If still no results, try with even more lenient parameters
            if not docs_with_scores:
                print("[DEBUG] Still no results, trying with k=10 and no filter...")
                try:
                    docs_with_scores = vector_store.similarity_search_with_score(
                        question.question,
                        k=10,  # Increased from 8 to 10
                        fetch_k=25  # Increased from 20 to 25
                    )
                    print(f"[DEBUG] Found {len(docs_with_scores)} chunks with lenient search")
                except Exception as e:
                    print(f"[DEBUG] Error in lenient search: {str(e)}")
                    docs_with_scores = []
            
            # If still no results, try getting any content from the document
            if not docs_with_scores:
                print("[DEBUG] No relevant results found, trying to get any content from the document...")
                try:
                    # Get any content from the vector store, regardless of relevance
                    total_docs = vector_store.index.ntotal
                    if total_docs > 0:
                        # Get a few random chunks to provide some context
                        docs_with_scores = vector_store.similarity_search_with_score(
                            "",  # Empty query to get any content
                            k=min(3, total_docs),
                            fetch_k=total_docs
                        )
                        print(f"[DEBUG] Found {len(docs_with_scores)} chunks using empty search as fallback")
                        
                        # If we still get no results, try the most basic search
                        if not docs_with_scores:
                            docs_with_scores = vector_store.similarity_search(
                                "",
                                k=min(3, total_docs)
                            )
                            # Convert to expected format
                            docs_with_scores = [(doc, 0.3) for doc in docs_with_scores]  # Low relevance score
                            print(f"[DEBUG] Found {len(docs_with_scores)} chunks using basic search")
                    else:
                        print("[DEBUG] Vector store is completely empty")
                        raise Exception("Vector store is empty")
                except Exception as e:
                    print(f"[DEBUG] Fallback search also failed: {str(e)}")
                    docs_with_scores = []
            
            # If we still have no results, provide a helpful error message
            if not docs_with_scores:
                print("[DEBUG] No content found in document, providing helpful error message")
                doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
                doc_name = doc_info.get("fileName", "Unknown") if doc_info else "Unknown"
                
                # Return a helpful response instead of an error
                response = {
                    "answer": f"I apologize, but I couldn't find any relevant content in the document '{doc_name}' that matches your question: '{question.question}'. This could be because:\n\n1. The document content doesn't contain information related to your question\n2. The document may need to be reprocessed to improve content extraction\n3. The question may be too specific for the available content\n\nPlease try:\n- Rephrasing your question in simpler terms\n- Asking about general topics covered in the document\n- Reprocessing the document if it was recently uploaded",
                    "sources": [],
                    "timestamp": datetime.now().isoformat(),
                    "metadata_summary": [{"course": "", "semester": "", "unit": "", "topic": ""}],
                    "warning": "No relevant content found in document"
                }
                
                # Cache this response to avoid repeated failures
                question_cache[cache_key] = {
                    "response": {
                        **response,
                        "question": question.question
                    },
                    "timestamp": datetime.now().timestamp()
                }
                
                return response
            
            # Build context and sources
            context_chunks = []
            sources = []
            
            for doc_obj, score in docs_with_scores:
                metadata = doc_obj.metadata
                context_chunks.append(doc_obj.page_content)
                
                # Calculate enhanced relevance score
                enhanced_score = calculate_enhanced_relevance_score(question.question, doc_obj.page_content, score)
                relevance = round(enhanced_score * 100)
                
                # Get document info by id
                doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
                # Get the best available source name from metadata
                source_name = (
                    metadata.get("source") or
                    metadata.get("fileName") or
                    metadata.get("source_file") or
                    metadata.get("document") or
                    "Unknown"
                )
                doc_name = doc_info.get("fileName", source_name) if doc_info else source_name
                doc_topic = doc_info.get("topic", "General") if doc_info else "General"
                # Build folder structure from metadata
                folder_structure = "/".join([
                    metadata.get("course") or metadata.get("courseName") or "",
                    metadata.get("year_semester") or metadata.get("yearSemester") or "",
                    metadata.get("subject") or metadata.get("subjectName") or "",
                    metadata.get("unit") or metadata.get("unitName") or "",
                    metadata.get("topic") or ""
                ]).strip("/")
                sources.append({
                    "source": folder_structure,
                    "folder_structure": folder_structure,
                    "topic": doc_topic,
                    "page": metadata.get("page", "N/A"),
                    "section": metadata.get("section", "N/A"),
                    "relevance": f"{relevance}%",
                    "doc_id": question.document_id,
                    "chunk_text": doc_obj.page_content[:150] + "..." if len(doc_obj.page_content) > 150 else doc_obj.page_content
                })
            
            # Ensure each source has 'document' and 'score' fields
            for source in sources:
                if 'source' in source:
                    source['document'] = source['source']
                source['score'] = float(source['relevance'].rstrip('%')) / 100
            
            # Build context text
            context_text = "\n\n".join(context_chunks)
            print(f"[DEBUG] Generated context with {len(context_chunks)} chunks")
            print(f"[DEBUG] Context preview: {context_text[:200]}...")
            
            # Get document context
            doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
            doc_context = f"Document: {doc_info.get('fileName', 'Unknown')}" if doc_info else "Unknown document"
            
            # Load template and generate response
            try:
                template = load_pharmacy_template()
                print(f"[DEBUG] Template loaded successfully")
            except Exception as template_error:
                print(f"[ERROR] Failed to load template: {str(template_error)}")
                print(f"[ERROR] Exception type: {type(template_error).__name__}")
                print(f"[ERROR] Exception details: {str(template_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load response template: {str(template_error)}"
                )
            
            try:
                chat_prompt = ChatPromptTemplate.from_template(template)
                print(f"[DEBUG] Chat prompt template created successfully")
            except Exception as prompt_error:
                print(f"[ERROR] Failed to create chat prompt: {str(prompt_error)}")
                print(f"[ERROR] Exception type: {type(prompt_error).__name__}")
                print(f"[ERROR] Exception details: {str(prompt_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create chat prompt: {str(prompt_error)}"
                )
            
            try:
                messages = chat_prompt.format_messages(
                    context=context_text,
                    question=question.question,
                    doc_context=doc_context
                )
                print(f"[DEBUG] Messages formatted successfully")
            except Exception as format_error:
                print(f"[ERROR] Failed to format messages: {str(format_error)}")
                print(f"[ERROR] Exception type: {type(format_error).__name__}")
                print(f"[ERROR] Exception details: {str(format_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to format messages: {str(format_error)}"
                )
            
            try:
                print(f"[DEBUG] Setting up conversational context...")
                
                # Get conversation history (already retrieved above)
                memory_vars = user_memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", [])
                
                print(f"[DEBUG] Conversation history length: {len(chat_history)}")
                
                # Build conversation context for the prompt
                conversation_context = ""
                if chat_history:
                    conversation_context = "\n\nPrevious conversation:\n"
                    for i, msg in enumerate(chat_history):
                        role = "User" if msg.__class__.__name__ == "HumanMessage" else "Assistant"
                        conversation_context += f"{role}: {msg.content}\n"
                    conversation_context += "\nCurrent question: " + question.question
                    print(f"[DEBUG] Built conversation context: {conversation_context[:200]}...")
                else:
                    print(f"[DEBUG] No conversation history found")
                
                # Instead of modifying template, modify the question to include conversation context
                enhanced_question = question.question
                if conversation_context:
                    enhanced_question = f"{conversation_context}\n\nQuestion: {question.question}"
                    print(f"[DEBUG] Enhanced question with conversation context")
                    print(f"[DEBUG] Enhanced question preview: {enhanced_question[:300]}...")
                else:
                    print(f"[DEBUG] No conversation context, using original question")
                
                # Use original template but with enhanced question
                chat_prompt = ChatPromptTemplate.from_template(template)
                
                # Format messages with enhanced question
                enhanced_messages = chat_prompt.format_messages(
                    context=context_text,
                    question=enhanced_question,
                    doc_context=doc_context
                )
                
                print(f"[DEBUG] Enhanced messages created, calling AI...")
                print(f"[DEBUG] Original question: {question.question}")
                print(f"[DEBUG] Enhanced question: {enhanced_question[:200]}...")
                print(f"[DEBUG] Context length: {len(context_text)} characters")
                
                print(f"[DEBUG] Invoking chat model with conversation context...")
                result = chat_model.invoke(enhanced_messages)
                answer = result.content
                
                print(f"[DEBUG] AI response received: {answer[:200]}...")
                
                # Save the conversation to memory
                user_memory.chat_memory.add_user_message(question.question)
                user_memory.chat_memory.add_ai_message(answer)
                
                print(f"[DEBUG] Conversational response received and saved to memory")
                
            except Exception as chat_error:
                print(f"[ERROR] Failed to get response with conversation context: {str(chat_error)}")
                print(f"[ERROR] Exception type: {type(chat_error).__name__}")
                print(f"[ERROR] Exception details: {str(chat_error)}")
                
                # Fallback to original method if conversational approach fails
                try:
                    print(f"[DEBUG] Falling back to direct chat model...")
                    result = chat_model.invoke(messages)
                    answer = result.content
                    
                    # Still save to memory even in fallback
                    user_memory.chat_memory.add_user_message(question.question)
                    user_memory.chat_memory.add_ai_message(answer)
                    
                    print(f"[DEBUG] Fallback successful and saved to memory")
                except Exception as fallback_error:
                    print(f"[ERROR] Fallback also failed: {str(fallback_error)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to get AI response: {str(chat_error)}"
                    )
            
            response = {
                "answer": answer.strip(),
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "metadata_summary": [{"course": "", "semester": "", "unit": "", "topic": ""}]
            }
            
            print(f"Generated response for question: {question.question}")
            print(f"Response: {response}")
            
            # Cache the result immediately
            question_cache[cache_key] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Cache the response
            response_cache[response_id] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Save response to S3 for persistence
            try:
                save_response_to_s3({**response, "question": question.question}, response_id)
                print(f"[DEBUG] Response saved to S3 with ID: {response_id}")
            except Exception as s3_error:
                print(f"[WARNING] Failed to save response to S3: {str(s3_error)}")
                print(f"[WARNING] Exception type: {type(s3_error).__name__}")
                print(f"[WARNING] Exception details: {str(s3_error)}")
                # Don't fail the request if S3 save fails
                print(f"[WARNING] Continuing without S3 persistence")
            
            print(f"[DEBUG] Cached response with ID: {response_id}")
            
            # Log performance metrics
            total_time = time.time() - start_time
            print(f"[PERFORMANCE] Single document search completed in {total_time:.2f} seconds")
            
            return response
            
        else:
            # Multi-document handling for general questions
            processed_docs = [d for d in documents if d.get("processed", False)]
            if not processed_docs:
                raise HTTPException(status_code=400, detail="No processed documents available")
            
            # Apply smart filtering for performance
            if len(processed_docs) > 10:
                print(f"[DEBUG] Filtering {len(processed_docs)} documents to improve performance")
                processed_docs = filter_relevant_documents(question.question, processed_docs, max_docs=10)
                print(f"[DEBUG] Selected {len(processed_docs)} most relevant documents")
            
            print(f"Processing general question across {len(processed_docs)} documents")
            
            # Initialize variables for multi-document processing
            combined_store = None
            all_docs = []
            docs_with_scores = []  # Initialize docs_with_scores variable
            filter_dict = None  # Initialize filter_dict for multi-document queries
            
            # Load and combine vector stores from all processed documents
            for doc in processed_docs:
                try:
                    print(f"[DEBUG] Loading vector store for document {doc.get('id')} ({doc.get('fileName', 'Unknown')})")
                    vector_store = get_cached_vector_store(doc["id"])
                    if vector_store:
                        # Instead of merging, collect all documents and create a new combined store
                        try:
                            # Get all documents from this vector store
                            total_docs = vector_store.index.ntotal
                            print(f"[DEBUG] Vector store {doc.get('id')} has {total_docs} documents")
                            
                            if total_docs > 0:
                                docs_from_store = vector_store.similarity_search("", k=total_docs)
                                # Fix: Add metadata to Document objects for newer LangChain versions
                                for doc_obj in docs_from_store:
                                    ensure_document_metadata(doc_obj, str(doc.get('id')), doc.get('fileName', 'Unknown'))
                                
                                all_docs.extend(docs_from_store)
                                print(f"[DEBUG] Added {len(docs_from_store)} chunks from document: {doc.get('fileName', 'Unknown')}")
                            else:
                                print(f"[DEBUG] Vector store {doc.get('id')} is empty")
                        except Exception as e:
                            print(f"[ERROR] Error extracting documents from vector store {doc.get('id')}: {str(e)}")
                            print(f"[ERROR] Exception type: {type(e).__name__}")
                            print(f"[ERROR] Exception details: {str(e)}")
                            # Try alternative approach - search with a generic term
                            try:
                                print(f"[DEBUG] Trying alternative extraction method for {doc.get('id')}")
                                docs_from_store = vector_store.similarity_search("the", k=10)
                                
                                # Fix: Add metadata to Document objects for newer LangChain versions
                                for doc_obj in docs_from_store:
                                    ensure_document_metadata(doc_obj, str(doc.get('id')), doc.get('fileName', 'Unknown'))
                                
                                all_docs.extend(docs_from_store)
                                print(f"[DEBUG] Added {len(docs_from_store)} chunks using alternative method from: {doc.get('fileName', 'Unknown')}")
                            except Exception as alt_e:
                                print(f"[ERROR] Alternative extraction also failed for {doc.get('id')}: {str(alt_e)}")
                                print(f"[ERROR] Exception type: {type(alt_e).__name__}")
                                print(f"[ERROR] Exception details: {str(alt_e)}")
                                continue
                    else:
                        print(f"[WARNING] Vector store not found for document {doc.get('id')}")
                except Exception as e:
                    print(f"[ERROR] Error loading vector store for document {doc.get('id')}: {str(e)}")
                    print(f"[ERROR] Exception type: {type(e).__name__}")
                    print(f"[ERROR] Exception details: {str(e)}")
                    continue
            
            if not all_docs:
                raise HTTPException(status_code=404, detail="No documents found in any vector stores")
            
            print(f"[DEBUG] Total documents collected: {len(all_docs)}")
            
            # Create a new combined vector store with all documents
            try:
                print(f"[DEBUG] Creating combined vector store with {len(all_docs)} documents")
                
                # Additional validation: ensure all documents have proper metadata
                for i, doc_obj in enumerate(all_docs):
                    if not hasattr(doc_obj, 'page_content') or not doc_obj.page_content:
                        print(f"[WARNING] Document {i} missing page_content, skipping")
                        continue
                    if not hasattr(doc_obj, 'metadata'):
                        doc_obj.metadata = {}
                
                embeddings = get_embeddings()
                print(f"[DEBUG] Embeddings model loaded successfully")
                
                # Try to create the combined store
                combined_store = FAISS.from_documents(all_docs, embeddings, distance_strategy="COSINE_DISTANCE")
                print(f"[DEBUG] Created combined vector store with {combined_store.index.ntotal} total documents")
            except Exception as e:
                print(f"[ERROR] Error creating combined vector store: {str(e)}")
                print(f"[ERROR] Exception type: {type(e).__name__}")
                print(f"[ERROR] Exception details: {str(e)}")
                
                # Try to provide more specific error information
                if "id" in str(e).lower():
                    print(f"[ERROR] This appears to be a Document object metadata issue")
                    print(f"[ERROR] Document objects may be missing required attributes")
                
                print(f"[ERROR] Combined vector store creation failed, falling back to individual stores")
                # Fallback: try to use individual vector stores instead
                combined_store = None
                docs_with_scores = []
                
                # Try searching individual vector stores
                for doc in processed_docs:
                    try:
                        vector_store = get_cached_vector_store(doc["id"])
                        if vector_store:
                            # Try to get at least one result from each store
                            try:
                                single_result = vector_store.similarity_search_with_score(
                                    question.question,
                                    k=1,
                                    fetch_k=3
                                )
                                if single_result:
                                    docs_with_scores.extend(single_result)
                                    print(f"Found {len(single_result)} results from {doc.get('fileName', 'Unknown')}")
                            except Exception as e:
                                print(f"Error searching individual store {doc.get('id')}: {str(e)}")
                                continue
                    except Exception as e:
                        print(f"Error loading individual vector store {doc.get('id')}: {str(e)}")
                        continue
                
                if docs_with_scores:
                    print(f"[INFO] Fallback successful: found {len(docs_with_scores)} results from individual stores")
                    # Sort by score and take the best ones
                    docs_with_scores.sort(key=lambda x: x[1], reverse=True)
                    docs_with_scores = docs_with_scores[:5]  # Take top 5
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to create combined vector store and fallback also failed: {str(e)}")
            
            if not combined_store:
                print(f"[ERROR] Combined vector store creation failed")
                raise HTTPException(status_code=404, detail="No vector stores found")
            
            # Only perform combined search if we have a combined store and no fallback results
            if combined_store and not docs_with_scores:
                # Optimize search parameters for multi-doc
                try:
                    print(f"[DEBUG] Attempting multi-document similarity search with question: '{question.question}'")
                    
                    # Add timeout protection for vector store search
                    try:
                        docs_with_scores = await asyncio.wait_for(
                            asyncio.to_thread(
                                combined_store.similarity_search_with_score,
                                question.question,
                                k=12,  # Increased from 8 to 12 for better coverage
                                filter=filter_dict,
                                fetch_k=30,  # Increased from 20 to 30
                                score_threshold=0.05   # Reduced from 0.1 to 0.05 for better coverage
                            ),
                            timeout=30.0  # 30 second timeout for vector search
                        )
                        print(f"[DEBUG] Primary multi-doc search successful, found {len(docs_with_scores)} results")
                    except asyncio.TimeoutError:
                        print(f"[ERROR] Vector store search timed out after 30 seconds")
                        docs_with_scores = []
                    except Exception as search_error:
                        print(f"[ERROR] Primary multi-doc search failed: {str(search_error)}")
                        print(f"[ERROR] Exception type: {type(search_error).__name__}")
                        print(f"[ERROR] Exception details: {str(search_error)}")
                        docs_with_scores = []
                except Exception as search_error:
                    print(f"[ERROR] Primary multi-doc search failed: {str(search_error)}")
                    print(f"[ERROR] Exception type: {type(search_error).__name__}")
                    print(f"[ERROR] Exception details: {str(search_error)}")
                    docs_with_scores = []
            
            # If no results with current threshold, try without threshold
            if not docs_with_scores:
                print("[DEBUG] No results with score_threshold=0.05, trying without threshold...")
                try:
                    docs_with_scores = combined_store.similarity_search_with_score(
                        question.question,
                        k=8,  # Increased from 5 to 8 for better coverage
                        filter=filter_dict,
                        fetch_k=20  # Increased from 15 to 20
                    )
                    print(f"[DEBUG] Search without threshold successful, found {len(docs_with_scores)} chunks")
                except Exception as e:
                    print(f"[ERROR] Search without threshold failed: {str(e)}")
                    docs_with_scores = []
            
            # If still no results, try with even more lenient parameters
            if not docs_with_scores:
                print("[DEBUG] Still no results, trying with k=10 and no filter...")
                try:
                    docs_with_scores = combined_store.similarity_search_with_score(
                        question.question,
                        k=10,  # Increased from 8 to 10
                        fetch_k=25  # Increased from 20 to 25
                    )
                    print(f"[DEBUG] Lenient search successful, found {len(docs_with_scores)} chunks")
                except Exception as e:
                    print(f"[ERROR] Lenient search failed: {str(e)}")
                    docs_with_scores = []
            elif docs_with_scores:
                print(f"[DEBUG] Using fallback results: {len(docs_with_scores)} documents found")
            
            # If still no results, try searching individual vector stores as fallback
            if not docs_with_scores:
                print("[DEBUG] Combined search failed, trying individual vector stores...")
                individual_results = []
                
                for i, doc in enumerate(processed_docs):
                    print(f"[DEBUG] Processing individual store {i+1}/{len(processed_docs)}: {doc.get('fileName', 'Unknown')}")
                    try:
                        vector_store = get_cached_vector_store(doc["id"])
                        if vector_store:
                            # Try to get at least one result from each store
                            try:
                                print(f"[DEBUG] Searching in {doc.get('fileName', 'Unknown')}...")
                                
                                # Add timeout protection for individual vector store search
                                try:
                                    single_result = await asyncio.wait_for(
                                        asyncio.to_thread(
                                            vector_store.similarity_search_with_score,
                                            question.question,
                                            k=1,
                                            fetch_k=3
                                        ),
                                        timeout=15.0  # 15 second timeout for individual search
                                    )
                                    if single_result:
                                        individual_results.extend(single_result)
                                        print(f"[DEBUG] Found {len(single_result)} results from {doc.get('fileName', 'Unknown')}")
                                    else:
                                        print(f"[DEBUG] No results found in {doc.get('fileName', 'Unknown')}")
                                except asyncio.TimeoutError:
                                    print(f"[ERROR] Individual search timed out for {doc.get('fileName', 'Unknown')}")
                                    continue
                                except Exception as e:
                                    print(f"[ERROR] Error searching individual store {doc.get('id')}: {str(e)}")
                                    continue
                            except Exception as e:
                                print(f"[ERROR] Error searching individual store {doc.get('id')}: {str(e)}")
                                continue
                        else:
                            print(f"[DEBUG] Vector store not available for {doc.get('fileName', 'Unknown')}")
                    except Exception as e:
                        print(f"[ERROR] Error loading individual vector store {doc.get('id')}: {str(e)}")
                        continue
                
                if individual_results:
                    # Sort by score and take the best ones
                    individual_results.sort(key=lambda x: x[1], reverse=True)
                    docs_with_scores = individual_results[:3]  # Take top 3
                    print(f"[DEBUG] Found {len(docs_with_scores)} results from individual searches")
                else:
                    print("[DEBUG] No results found from any individual vector stores")
            
            # Build context and sources with document metadata
            context_chunks = []
            sources = []
            seen_docs = set()  # Track unique documents
            
            for doc_obj, score in docs_with_scores:
                metadata = doc_obj.metadata
                doc_id = metadata.get("source", "").split("/")[-2] if "/" in metadata.get("source", "") else ""
                # Skip if we've seen too many chunks from the same document
                if doc_id and doc_id in seen_docs and len([s for s in sources if s.get("doc_id") == doc_id]) >= 2:
                    continue
                if doc_id:
                    seen_docs.add(doc_id)
                context_chunks.append(doc_obj.page_content)
                
                # Calculate enhanced relevance score
                enhanced_score = calculate_enhanced_relevance_score(question.question, doc_obj.page_content, score)
                relevance = round(enhanced_score * 100)
                
                # Get document info by id
                doc_info = next((d for d in processed_docs if str(d.get("id")) == doc_id), None)
                # If doc_info is not found by id, try matching by file name
                if not doc_info:
                    file_name = os.path.basename(metadata.get("source", ""))
                    doc_info = next((d for d in processed_docs if d.get("fileName") == file_name), None)
                # Get the best available source name from metadata, now including 'source_file'
                source_name = (
                    metadata.get("source") or
                    metadata.get("fileName") or
                    metadata.get("source_file") or
                    metadata.get("document") or
                    "Unknown"
                )
                doc_name = doc_info.get("fileName", source_name) if doc_info else source_name
                doc_topic = doc_info.get("topic", "General") if doc_info else "General"
                # Build folder structure from metadata
                folder_structure = "/".join([
                    metadata.get("course") or metadata.get("courseName") or "",
                    metadata.get("year_semester") or metadata.get("yearSemester") or "",
                    metadata.get("subject") or metadata.get("subjectName") or "",
                    metadata.get("unit") or metadata.get("unitName") or "",
                    metadata.get("topic") or ""
                ]).strip("/")
                sources.append({
                    "source": folder_structure,
                    "folder_structure": folder_structure,
                    "topic": doc_topic,
                    "page": metadata.get("page", "N/A"),
                    "section": metadata.get("section", "N/A"),
                    "relevance": f"{relevance}%",
                    "doc_id": doc_id,
                    "chunk_text": doc_obj.page_content[:1000] + "..." if len(doc_obj.page_content) > 1000 else doc_obj.page_content
                })
            
            # Ensure each source has 'document' and 'score' fields
            for source in sources:
                if 'source' in source:
                    source['document'] = source['source']
                source['score'] = float(source['relevance'].rstrip('%')) / 100
            
            # Build context text with better formatting
            context_parts = []
            for i, chunk in enumerate(context_chunks):
                context_parts.append(f"=== CHUNK {i+1} ===\n{chunk}\n")
            
            context_text = "\n".join(context_parts)
            print(f"[DEBUG] Generated context with {len(context_chunks)} chunks")
            print(f"[DEBUG] Context preview: {context_text[:200]}...")
            
            # Get document context
            doc_context = f"Multiple documents: {len(processed_docs)} documents searched"
            
            # Load template and generate response
            print(f"[DEBUG] Loading pharmacy template...")
            template = load_pharmacy_template()
            print(f"[DEBUG] Template loaded, length: {len(template)}")
            
            print(f"[DEBUG] Creating chat prompt...")
            chat_prompt = ChatPromptTemplate.from_template(template)
            
            print(f"[DEBUG] Formatting messages...")
            messages = chat_prompt.format_messages(
                context=context_text,
                question=question.question,
                doc_context=doc_context
            )
            print(f"[DEBUG] Messages formatted, calling LLM...")
            
            print(f"[DEBUG] Invoking chat model with provider: {AI_PROVIDER}...")
            
            # Add timeout protection for LLM call
            try:
                # Run LLM call with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    asyncio.to_thread(chat_model.invoke, messages),
                    timeout=90.0  # 90 second timeout
                )
                print(f"[DEBUG] LLM response received, length: {len(result.content)}")
            except asyncio.TimeoutError:
                print(f"[ERROR] LLM call timed out after 90 seconds")
                raise HTTPException(
                    status_code=500,
                    detail="AI model response timed out. Please try again with a simpler question."
                )
            except Exception as llm_error:
                print(f"[ERROR] LLM call failed: {str(llm_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"AI model call failed: {str(llm_error)}"
                )
            
            answer = result.content
            
            response = {
                "answer": answer.strip(),
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "question": question.question,
                "is_general": True,
                "metadata_summary": [{"course": "", "semester": "", "unit": "", "topic": ""}]
            }
            
            print(f"Generated general response for question: {question.question}")
            print(f"Response: {response}")
            
            # Cache the result immediately
            question_cache[cache_key] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Cache the response
            response_cache[response_id] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Save response to S3 for persistence
            save_response_to_s3({**response, "question": question.question}, response_id)
            print(f"Cached and saved general response with ID: {response_id}")
            
            # Log performance metrics
            total_time = time.time() - start_time
            print(f"[PERFORMANCE] Multi-document search completed in {total_time:.2f} seconds")
            
            return response
            
    except HTTPException as http_exc:
        print(f"[DEPLOYMENT_DEBUG] HTTPException raised: {str(http_exc)}")
        raise
    except Exception as e:
        print(f"[DEPLOYMENT_DEBUG] ===== UNEXPECTED ERROR IN ASK_QUESTION =====")
        print(f"[DEPLOYMENT_DEBUG] Error: {str(e)}")
        print(f"[DEPLOYMENT_DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEPLOYMENT_DEBUG] Exception details: {str(e)}")
        
        # Import traceback for detailed error information
        import traceback
        print(f"[DEPLOYMENT_DEBUG] Full traceback:")
        traceback.print_exc()
        
        print(f"[DEPLOYMENT_DEBUG] ===== ERROR DETAILS END =====")
        
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/ask/public", dependencies=[])  # Override router-level auth dependency
async def ask_question_public(question: QuestionInput):
    """Public endpoint for other applications to ask questions without authentication"""
    start_time = time.time()
    global documents
    
    try:
        # Validate input
        if not question.question or not question.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        # Validate OpenAI API key
        if not OPENAI_API_KEY or OPENAI_API_KEY == "dummy_key_for_testing":
            raise HTTPException(
                status_code=400,
                detail="OpenAI API key not configured"
            )
        
        # Load documents from S3 to ensure we have latest data
        try:
            documents = load_documents_metadata() or []
            print(f"[DEBUG] Public endpoint: Loaded {len(documents)} documents from S3 metadata.")
        except Exception as e:
            print(f"Error loading documents from S3: {str(e)}")
            documents = []
            raise HTTPException(
                status_code=500,
                detail="Failed to load documents from S3. Please try again."
            )
        
        # Check if there are any processed documents
        processed_docs = [d for d in documents if d.get("processed", False)]
        if not processed_docs:
            raise HTTPException(
                status_code=400,
                detail="No processed documents available. Please process some documents first."
            )
        
        # Validate document_id if provided
        if question.document_id:
            doc = next((d for d in documents if str(d.get("id")) == str(question.document_id)), None)
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found with ID: {question.document_id}"
                )
            
            # Check if document is processed
            if not doc.get("processed", False):
                if doc.get("processing", False):
                    raise HTTPException(
                        status_code=400,
                        detail="Document is currently being processed. Please try again in a few moments."
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Document is not processed. Please process the document first."
                    )
        
        try:
            # Initialize chat model
            chat_model = get_chat_model()
        except Exception as e:
            print(f"Error initializing chat model: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize AI model. Please try again."
            )

        # Generate cache key and response ID first
        filter_dict = {}
        for key in ["year", "semester", "subject", "unit", "topic"]:
            value = getattr(question, key, None)
            if value:
                filter_dict[key] = value
        
        if question.metadata_filter:
            for key, value in question.metadata_filter.items():
                if value and key in ["year", "semester", "subject", "unit", "topic"]:
                    filter_dict[key] = value
        
        if not filter_dict:
            filter_dict = None

        cache_key = get_cache_key(question.question, question.document_id, filter_dict)
        response_id = hashlib.md5(cache_key.encode()).hexdigest()
        
        # Check cache first
        if cache_key in question_cache:
            cached_result = question_cache[cache_key]
            if (datetime.now().timestamp() - cached_result["timestamp"]) < CACHE_TTL:
                print(f"Found cached response for key: {cache_key}")
                # Update response cache
                response_cache[response_id] = {
                    "response": cached_result["response"],
                    "timestamp": datetime.now().timestamp()
                }
                return cached_result["response"]

        # Get relevant documents
        if question.document_id:
            print(f"[DEBUG] Public endpoint: Processing question for specific document: {question.document_id}")
            vector_store = get_cached_vector_store(question.document_id)
            if not vector_store:
                print(f"[DEBUG] Vector store not found for document {question.document_id}")
                # Try to provide a helpful error message
                doc = next((d for d in documents if d["id"] == question.document_id), None)
                if doc:
                    if not doc.get("processed", False):
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Document '{doc.get('fileName', 'Unknown')}' is not processed. Please process it first."
                        )
                    else:
                        # Check if this might be a compatibility issue
                        error_msg = f"Vector store for document '{doc.get('fileName', 'Unknown')}' could not be loaded."
                        error_msg += " This may be due to a compatibility issue with the vector store format."
                        error_msg += " Please try reprocessing the document to recreate the vector store."
                        raise HTTPException(
                            status_code=404, 
                            detail=error_msg
                        )
                else:
                    raise HTTPException(status_code=404, detail="Document not found")
            
            print(f"[DEBUG] Public endpoint: Vector store loaded successfully for document {question.document_id}")
            
            # Add debugging information about the vector store
            print(f"[DEBUG] Vector store index size: {vector_store.index.ntotal}")
            print(f"[DEBUG] Vector store dimension: {vector_store.index.d}")
            print(f"[DEBUG] Question being searched: '{question.question}'")
            print(f"[DEBUG] Filter dict: {filter_dict}")
            
            # Test if vector store can find any documents at all
            try:
                test_results = vector_store.similarity_search("test", k=1)
                print(f"[DEBUG] Vector store test search successful, found {len(test_results)} results")
            except Exception as e:
                print(f"[DEBUG] Vector store test search failed: {str(e)}")
            
            # Get relevant chunks
            try:
                docs_with_scores = vector_store.similarity_search_with_score(
                    question.question,
                    k=12,  # Increased from 8 to 12 for better coverage
                    filter=filter_dict,
                    fetch_k=25,  # Increased from 15 to 25
                    score_threshold=0.05   # Reduced from 0.1 to 0.05 for better coverage
                )
            except Exception as search_error:
                print(f"[DEBUG] Error in similarity search: {str(search_error)}")
                # Try alternative search method
                try:
                    docs_with_scores = vector_store.similarity_search(
                        question.question,
                        k=5  # Increased from 3 to 5
                    )
                    # Convert to format expected by the rest of the code
                    docs_with_scores = [(doc, 0.5) for doc in docs_with_scores]  # Default score of 0.5
                    print(f"[DEBUG] Used alternative search method successfully")
                except Exception as alt_search_error:
                    print(f"[DEBUG] Alternative search also failed: {str(alt_search_error)}")
                    
                    # Try to get any documents from the vector store as last resort
                    try:
                        total_docs = vector_store.index.ntotal
                        if total_docs > 0:
                            # Get the first few documents regardless of relevance
                            docs_with_scores = vector_store.similarity_search_with_score(
                                "",
                                k=min(5, total_docs),  # Increased from 3 to 5
                                fetch_k=total_docs
                            )
                            print(f"[DEBUG] Found {len(docs_with_scores)} chunks using empty search")
                        else:
                            raise Exception("Vector store is empty")
                    except Exception as empty_search_error:
                        print(f"[DEBUG] Empty search also failed: {str(empty_search_error)}")
                        raise HTTPException(
                            status_code=404,
                            detail="Unable to search document content. Please try reprocessing the document."
                        )
            
            print(f"[DEBUG] Found {len(docs_with_scores)} relevant chunks for question: {question.question}")
            
            # If no results with current threshold, try without threshold
            if not docs_with_scores:
                print("[DEBUG] No results with score_threshold=0.1, trying without threshold...")
                try:
                    docs_with_scores = vector_store.similarity_search_with_score(
                        question.question,
                        k=8,  # Increased from 5 to 8 for better coverage
                        filter=filter_dict,
                        fetch_k=15  # Increased from 10 to 15
                    )
                    print(f"[DEBUG] Found {len(docs_with_scores)} chunks without threshold")
                except Exception as e:
                    print(f"[DEBUG] Error in search without threshold: {str(e)}")
                    docs_with_scores = []
            
            # If still no results, try with even more lenient parameters
            if not docs_with_scores:
                print("[DEBUG] Still no results, trying with k=10 and no filter...")
                try:
                    docs_with_scores = vector_store.similarity_search_with_score(
                        question.question,
                        k=10,  # Increased from 8 to 10
                        fetch_k=25  # Increased from 20 to 25
                    )
                    print(f"[DEBUG] Found {len(docs_with_scores)} chunks with lenient search")
                except Exception as e:
                    print(f"[DEBUG] Error in lenient search: {str(e)}")
                    docs_with_scores = []
            
            # If still no results, try getting any content from the document
            if not docs_with_scores:
                print("[DEBUG] No relevant results found, trying to get any content from the document...")
                try:
                    # Get any content from the vector store, regardless of relevance
                    total_docs = vector_store.index.ntotal
                    if total_docs > 0:
                        # Get a few random chunks to provide some context
                        docs_with_scores = vector_store.similarity_search_with_score(
                            "",  # Empty query to get any content
                            k=min(3, total_docs),
                            fetch_k=total_docs
                        )
                        print(f"[DEBUG] Found {len(docs_with_scores)} chunks using empty search as fallback")
                        
                        # If we still get no results, try the most basic search
                        if not docs_with_scores:
                            docs_with_scores = vector_store.similarity_search(
                                "",
                                k=min(3, total_docs)
                            )
                            # Convert to expected format
                            docs_with_scores = [(doc, 0.3) for doc in docs_with_scores]  # Low relevance score
                            print(f"[DEBUG] Found {len(docs_with_scores)} chunks using basic search")
                    else:
                        print("[DEBUG] Vector store is completely empty")
                        raise Exception("Vector store is empty")
                except Exception as e:
                    print(f"[DEBUG] Fallback search also failed: {str(e)}")
                    docs_with_scores = []
            
            # If we still have no results, provide a helpful error message
            if not docs_with_scores:
                print("[DEBUG] No content found in document, providing helpful error message")
                doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
                doc_name = doc_info.get("fileName", "Unknown") if doc_info else "Unknown"
                
                # Return a helpful response instead of an error
                response = {
                    "answer": f"I apologize, but I couldn't find any relevant content in the document '{doc_name}' that matches your question: '{question.question}'. This could be because:\n\n1. The document content doesn't contain information related to your question\n2. The document may need to be reprocessed to improve content extraction\n3. The question may be too specific for the available content\n\nPlease try:\n- Rephrasing your question in simpler terms\n- Asking about general topics covered in the document\n- Reprocessing the document if it was recently uploaded",
                    "sources": [],
                    "timestamp": datetime.now().isoformat(),
                    "metadata_summary": [{"course": "", "semester": "", "unit": "", "topic": ""}],
                    "warning": "No relevant content found in document"
                }
                
                # Cache this response to avoid repeated failures
                question_cache[cache_key] = {
                    "response": {
                        **response,
                        "question": question.question
                    },
                    "timestamp": datetime.now().timestamp()
                }
                
                return response
            
            # Build context and sources
            context_chunks = []
            sources = []
            
            for doc_obj, score in docs_with_scores:
                metadata = doc_obj.metadata
                context_chunks.append(doc_obj.page_content)
                
                # Calculate enhanced relevance score
                enhanced_score = calculate_enhanced_relevance_score(question.question, doc_obj.page_content, score)
                relevance = round(enhanced_score * 100)
                
                # Get document info by id
                doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
                # Get the best available source name from metadata
                source_name = (
                    metadata.get("source") or
                    metadata.get("fileName") or
                    metadata.get("source_file") or
                    metadata.get("document") or
                    "Unknown"
                )
                doc_name = doc_info.get("fileName", source_name) if doc_info else source_name
                doc_topic = doc_info.get("topic", "General") if doc_info else "General"
                # Build folder structure from metadata
                folder_structure = "/".join([
                    metadata.get("course") or metadata.get("courseName") or "",
                    metadata.get("year_semester") or metadata.get("yearSemester") or "",
                    metadata.get("subject") or metadata.get("subjectName") or "",
                    metadata.get("unit") or metadata.get("unitName") or "",
                    metadata.get("topic") or ""
                ]).strip("/")
                sources.append({
                    "source": folder_structure,
                    "folder_structure": folder_structure,
                    "topic": doc_topic,
                    "page": metadata.get("page", "N/A"),
                    "section": metadata.get("section", "N/A"),
                    "relevance": f"{relevance}%",
                    "doc_id": question.document_id,
                    "chunk_text": doc_obj.page_content[:150] + "..." if len(doc_obj.page_content) > 150 else doc_obj.page_content
                })
            
            # Ensure each source has 'document' and 'score' fields
            for source in sources:
                if 'source' in source:
                    source['document'] = source['source']
                source['score'] = float(source['relevance'].rstrip('%')) / 100
            
            # Build context text
            context_text = "\n\n".join(context_chunks)
            print(f"[DEBUG] Generated context with {len(context_chunks)} chunks")
            print(f"[DEBUG] Context preview: {context_text[:200]}...")
            
            # Get document context
            doc_info = next((d for d in documents if str(d.get("id")) == question.document_id), None)
            doc_context = f"Document: {doc_info.get('fileName', 'Unknown')}" if doc_info else "Unknown document"
            
            # Load template and generate response
            template = load_pharmacy_template()
            chat_prompt = ChatPromptTemplate.from_template(template)
            
            messages = chat_prompt.format_messages(
                context=context_text,
                question=question.question,
                doc_context=doc_context
            )
            
            try:
                print(f"[DEBUG] Setting up conversational context for public endpoint...")
                
                # Use anonymous user for public endpoint
                user_id = "anonymous_public"
                print(f"[DEBUG] Public User ID: {user_id}")
                
                # Get user's conversation memory
                user_memory = get_user_memory(user_id)
                
                # Get conversation history
                memory_vars = user_memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", [])
                
                print(f"[DEBUG] Public conversation history length: {len(chat_history)}")
                
                # Build conversation context for the prompt
                conversation_context = ""
                if chat_history:
                    conversation_context = "\n\nPrevious conversation:\n"
                    for i, msg in enumerate(chat_history):
                        role = "User" if msg.__class__.__name__ == "HumanMessage" else "Assistant"
                        conversation_context += f"{role}: {msg.content}\n"
                    conversation_context += "\nCurrent question: " + question.question
                
                # Instead of modifying template, modify the question to include conversation context
                enhanced_question = question.question
                if conversation_context:
                    enhanced_question = f"{conversation_context}\n\nQuestion: {question.question}"
                    print(f"[DEBUG] Enhanced question with conversation context for public endpoint")
                    print(f"[DEBUG] Enhanced question preview: {enhanced_question[:300]}...")
                else:
                    print(f"[DEBUG] No conversation context, using original question for public endpoint")
                
                # Use original template but with enhanced question
                chat_prompt = ChatPromptTemplate.from_template(template)
                
                # Format messages with enhanced question
                enhanced_messages = chat_prompt.format_messages(
                    context=context_text,
                    question=enhanced_question,
                    doc_context=doc_context
                )
                
                print(f"[DEBUG] Invoking chat model with conversation context for public endpoint...")
                result = chat_model.invoke(enhanced_messages)
                answer = result.content
                
                # Save the conversation to memory
                user_memory.chat_memory.add_user_message(question.question)
                user_memory.chat_memory.add_ai_message(answer)
                
                print(f"[DEBUG] Conversational response received and saved to memory for public endpoint")
                
            except Exception as chat_error:
                print(f"[ERROR] Failed to get response with conversation context (public): {str(chat_error)}")
                print(f"[ERROR] Exception type: {type(chat_error).__name__}")
                print(f"[ERROR] Exception details: {str(chat_error)}")
                
                # Fallback to original method if conversational approach fails
                try:
                    print(f"[DEBUG] Falling back to direct chat model for public endpoint...")
                    result = chat_model.invoke(messages)
                    answer = result.content
                    
                    # Still save to memory even in fallback
                    user_id = "anonymous_public"
                    user_memory = get_user_memory(user_id)
                    user_memory.chat_memory.add_user_message(question.question)
                    user_memory.chat_memory.add_ai_message(answer)
                    
                    print(f"[DEBUG] Fallback successful and saved to memory for public endpoint")
                except Exception as fallback_error:
                    print(f"[ERROR] Fallback also failed for public endpoint: {str(fallback_error)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to get AI response: {str(chat_error)}"
                    )
            
            response = {
                "answer": answer.strip(),
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "metadata_summary": [{"course": "", "semester": "", "unit": "", "topic": ""}]
            }
            
            print(f"Generated response for question: {question.question}")
            print(f"Response: {response}")
            
            # Cache the result immediately
            question_cache[cache_key] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Cache the response
            response_cache[response_id] = {
                "response": {
                    **response,
                    "question": question.question  # Store the question in the response
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # Save response to S3 for persistence
            save_response_to_s3({**response, "question": question.question}, response_id)
            print(f"Cached and saved general response with ID: {response_id}")
            
            # Log performance metrics
            total_time = time.time() - start_time
            print(f"[PERFORMANCE] Multi-document search completed in {total_time:.2f} seconds")
            
            return response
            
    except HTTPException as http_exc:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Prompt suggestion error: {error_msg}")
        if "OpenAI" in error_msg:
            raise HTTPException(status_code=500, detail="Error communicating with OpenAI. Please check your API key and try again.")
        elif "vector store" in error_msg.lower():
            raise HTTPException(status_code=500, detail="Error accessing document data. Please try processing the document again.")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to generate prompts: {error_msg}")

@router.post("/suggest-prompts")
async def suggest_prompts(topic: str = Body(...), fileName: str = Body(...), document_id: str = Body(None), auth_result: dict = Depends(get_dual_auth_user)):
    print(f"[DEBUG] suggest_prompts called with topic={topic}, fileName={fileName}, document_id={document_id}")
    # Validate OpenAI API key
    if not OPENAI_API_KEY or OPENAI_API_KEY == "dummy_key_for_testing":
        return JSONResponse(
            status_code=400,
            content={"detail": "OpenAI API key not configured"}
        )
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain_community.vectorstores import FAISS
        
        # Validate inputs
        if not topic or not isinstance(topic, str):
            raise HTTPException(status_code=400, detail="Topic must be a non-empty string")
        if not fileName or not isinstance(fileName, str):
            raise HTTPException(status_code=400, detail="FileName must be a non-empty string")
        
        # If document_id is provided, verify document is processed
        if document_id:
            try:
                # Load documents list to check processing status (from S3)
                documents = load_documents_metadata() or []
                print(f"[DEBUG] Loaded {len(documents)} documents from S3 metadata.")
                doc = next((d for d in documents if str(d.get("id")) == str(document_id)), None)
                print(f"[DEBUG] doc found: {doc is not None}")
                
                if not doc:
                    raise HTTPException(status_code=404, detail=f"Document not found with ID: {document_id}")
                
                if not doc.get("processed", False):
                    print("[DEBUG] Document is not processed.")
                    raise HTTPException(
                        status_code=400,
                        detail="Document is not processed. Please process the document first."
                    )
                
                # Verify vector store exists
                if not verify_document_processed(document_id):
                    raise HTTPException(
                        status_code=400,
                        detail="Document vector store not found. Please process the document again."
                    )
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error checking document status: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error checking document status: {str(e)}")
        
        # Initialize chat model
        try:
            chat_model = get_chat_model()
        except Exception as e:
            print(f"Error initializing chat model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize AI model: {str(e)}")

        # If document_id is provided, use RAG to generate context-aware prompts
        if document_id:
            try:
                # Load vector store for the document
                vector_store = get_cached_vector_store(document_id)
                if not vector_store:
                    print(f"[DEBUG] Vector store not found for document {document_id}, falling back to topic-based prompts")
                    # Fall back to topic-based prompts instead of failing
                    context = ""
                else:
                    # Get relevant chunks from the document
                    try:
                        docs = vector_store.similarity_search(
                            f"key concepts and important information about {topic}",
                            k=1  # Only the top chunk
                        )
                        
                        if not docs:
                            # If no relevant chunks found, fall back to topic-based prompts
                            print(f"No relevant chunks found for topic: {topic}, using topic-based prompts")
                            context = ""
                        else:
                            # Extract key content from chunks
                            context = docs[0].page_content if docs else ""
                    except Exception as search_error:
                        print(f"Error performing similarity search: {str(search_error)}")
                        
                        # Try alternative search method
                        try:
                            docs = vector_store.similarity_search_with_score(
                                f"key concepts and important information about {topic}",
                                k=1
                            )
                            if docs:
                                context = docs[0][0].page_content if docs else ""
                            else:
                                context = ""
                        except Exception as alt_search_error:
                            print(f"Alternative search also failed: {str(alt_search_error)}")
                            context = ""
            except Exception as e:
                print(f"Error loading document context: {str(e)}")
                # Instead of failing, fall back to topic-based prompts
                context = ""

            # Create a prompt that uses the actual document content
            if context:
                prompt = f"""Based on the following document content and information, generate exactly 3 relevant and specific questions that a student might ask about this topic.
                
                Document Topic: {topic}
                Document Name: {fileName}
                
                Document Content:
                {context}
                
                Generate questions that:
                1. Are directly related to the key concepts in the document
                2. Would help understand the most important information
                3. Are specific and focused on the actual content
                4. Start with words like "What", "How", "Why", "Explain", "Describe"
                5. Are clear and concise
                
                Return only the questions as a JSON array of strings, no additional text."""
            else:
                # Fallback to topic-based prompts when no context is available
                prompt = f"""Based on the following document information, generate exactly 3 relevant questions that a student might ask about this topic.
                
                Document Topic: {topic}
                Document Name: {fileName}
                
                Generate questions that:
                1. Are specific to the topic
                2. Would help understand key concepts
                3. Are clear and concise
                4. Start with words like "What", "How", "Why", "Explain", "Describe"
                
                Return only the questions as a JSON array of strings, no additional text."""
        else:
            # Fallback to topic-based prompts if no document_id
            prompt = f"""Based on the following document information, generate exactly 3 relevant questions that a student might ask about this topic.
            
            Document Topic: {topic}
            Document Name: {fileName}
            
            Generate questions that:
            1. Are specific to the topic
            2. Would help understand key concepts
            3. Are clear and concise
            4. Start with words like "What", "How", "Why", "Explain", "Describe"
            
            Return only the questions as a JSON array of strings, no additional text."""
        
        # Get response from AI
        response = chat_model.invoke(prompt)
        
        try:
            # Try to parse the response as JSON
            import json
            prompts = json.loads(response.content)
            if not isinstance(prompts, list):
                prompts = [prompts]
        except json.JSONDecodeError:
            # If parsing fails, split by newlines and clean up
            prompts = [
                line.strip().strip('"').strip("'")
                for line in response.content.split('\n')
                if line.strip() and not line.strip().startswith(('{', '[', ']', '}'))
            ]
        
        # Filter out any empty or invalid prompts
        prompts = [p for p in prompts if p and isinstance(p, str) and len(p) > 10]
        
        # Ensure we have exactly 3 prompts
        if len(prompts) > 3:
            prompts = prompts[:3]
        elif len(prompts) < 3:
            # Generate additional prompts if needed
            additional_prompt = f"""Generate {3 - len(prompts)} more specific questions about {topic} that would help understand the key concepts.
            The questions should be different from: {', '.join(prompts)}
            Return only the questions as a JSON array of strings."""
            
            try:
                additional_response = chat_model.invoke(additional_prompt)
                additional_prompts = json.loads(additional_response.content)
                if isinstance(additional_prompts, list):
                    prompts.extend(additional_prompts[:3 - len(prompts)])
            except:
                # If additional prompt generation fails, use fallback prompts
                fallback_prompts = [
                    f"What are the key concepts in {topic}?",
                    f"How does {topic} relate to other topics in the course?",
                    f"Can you explain the main principles of {topic}?"
                ]
                prompts.extend(fallback_prompts[:3 - len(prompts)])
        
        print("[DEBUG] About to call load_vector_store")
        return {"prompts": prompts[:3]}  # Return exactly 3 prompts
        
    except HTTPException as http_exc:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Prompt suggestion error: {error_msg}")
        if "OpenAI" in error_msg:
            raise HTTPException(status_code=500, detail="Error communicating with OpenAI. Please check your API key and try again.")
        elif "vector store" in error_msg.lower():
            raise HTTPException(status_code=500, detail="Error accessing document data. Please try processing the document again.")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to generate prompts: {error_msg}")

@router.get("/templates")
async def list_templates(auth_result: dict = Depends(get_dual_auth_user)):
    """List all available templates"""
    try:
        templates = list_available_templates()
        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")

@router.get("/template/{template_name}")
async def get_template(template_name: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get a specific template by name"""
    try:
        # Try to load from S3 first
        template = load_template_from_s3(template_name)
        if template:
            return Response(content=template, media_type="text/plain")
        
        # Fallback to local file if not found in S3
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            templates_dir = os.path.join(base_dir, '..', 'templates')
            template_path = os.path.join(templates_dir, f'{template_name}.txt')
            
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # Try to sync local template to S3 if it's not there
                try:
                    if not load_template_from_s3(template_name):
                        save_template_to_s3(template_content, template_name)
                except Exception as e:
                    logging.error(f"Failed to sync template to S3: {str(e)}")
                
                return Response(content=template_content, media_type="text/plain")
        except Exception as e:
            logging.error(f"Error loading template from local file: {str(e)}")
        
        raise HTTPException(status_code=404, detail=f"Template {template_name} not found")
    except HTTPException as http_exc:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read template: {str(e)}")

@router.post("/template/{template_name}")
async def update_template(
    template_name: str,
    template: str = Body(..., embed=False),
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Update a specific template (save to both S3 and local)"""
    try:
        logging.info(f"[POST /template/{template_name}] User {auth_result.get('user_data', {}).get('sub', 'unknown')} updating template")
        
        # Validate template content based on template type
        if template_name == "pharmacy_prompt":
            required_placeholders = ["{context}", "{question}", "{doc_context}"]
        elif template_name == "notes_prompt":
            required_placeholders = ["{course_name}", "{subject_name}", "{unit_name}", "{topic}", "{document_content}"]
        elif template_name == "model_paper_prediction":
            required_placeholders = ["{model_paper_content}"]
        else:
            # For unknown templates, require at least one placeholder
            if "{" not in template or "}" not in template:
                raise HTTPException(
                    status_code=400,
                    detail="Template must contain at least one placeholder (e.g., {variable})"
                )
            required_placeholders = []
        
        # Validate required placeholders
        for placeholder in required_placeholders:
            if placeholder not in template:
                raise HTTPException(
                    status_code=400,
                    detail=f"Template must contain {placeholder} placeholder"
                )
        
        # Save to S3
        if not save_template_to_s3(template, template_name):
            raise HTTPException(status_code=500, detail="Failed to save template to S3")
        
        # Also save to local file for backup/legacy
        base_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.normpath(os.path.join(base_dir, '..', 'templates'))
        backup_dir = os.path.join(templates_dir, 'backups')
        os.makedirs(templates_dir, exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)
        template_path = os.path.join(templates_dir, f'{template_name}.txt')
        
        # Create backup if file exists
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists(template_path):
            shutil.copy2(template_path, os.path.join(backup_dir, f"{template_name}_{timestamp}.txt"))
        
        # Save new template
        with open(template_path, "w", encoding='utf-8') as f:
            f.write(template)
            
        logging.info(f"[POST /template/{template_name}] Template updated successfully (S3 and local)")
        return {"message": f"Template {template_name} updated successfully (S3 and local)"}
    except HTTPException as http_exc:
        raise
    except Exception as e:
        logging.error(f"[POST /template/{template_name}] Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")

# Keep the existing /template/pharmacy endpoints for backward compatibility
@router.get("/template/pharmacy")
async def get_pharmacy_template(auth_result: dict = Depends(get_dual_auth_user)):
    """Get the pharmacy prompt template (legacy endpoint)"""
    return await get_template("pharmacy_prompt", auth_result)

@router.post("/template/pharmacy")
async def update_pharmacy_template(
    template: str = Body(..., embed=False),
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Update the pharmacy prompt template (legacy endpoint)"""
    return await update_template("pharmacy_prompt", template, auth_result)

@router.get("/template/{template_name}/backups")
async def get_template_backups(template_name: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Get list of backups for a template"""
    try:
        backups = list_template_backups(template_name)
        return {"backups": backups}
    except Exception as e:
        logging.error(f"Error getting template backups: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/template/{template_name}/restore/{backup_key:path}")
async def restore_template(template_name: str, backup_key: str, auth_result: dict = Depends(get_dual_auth_user)):
    """Restore a template from a backup"""
    try:
        if restore_template_from_backup(template_name, backup_key):
            return {"message": "Template restored successfully"}
        raise HTTPException(status_code=500, detail="Failed to restore template")
    except Exception as e:
        logging.error(f"Error restoring template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper to clamp and round similarity to 0-100%
def pct(similarity: float, decimals: int = 0) -> float | int:
    """Convert similarity/distance score to percentage, clipped to 0-100."""
    # FAISS returns distance scores (lower = better) for both EUCLIDEAN_DISTANCE and COSINE_DISTANCE
    # We need to convert this to a similarity score (higher = better)
    
    # Handle edge cases
    if similarity <= 0:
        normalized_similarity = 1.0  # Perfect match
    elif similarity >= 2.0:  # Distance can be > 1 for very different vectors
        normalized_similarity = 0.0  # No match
    else:
        # Convert distance to similarity using a more sophisticated approach
        # This provides better differentiation between scores and handles both distance types
        
        # Use a more aggressive transformation for better score distribution
        # This will give higher scores for more relevant content
        if similarity <= 0.1:
            # Very close matches get high scores (95-100%)
            normalized_similarity = 1.0 - (similarity * 5.0)
        elif similarity <= 0.3:
            # Close matches get good scores (70-95%)
            normalized_similarity = 0.95 - (similarity - 0.1) * 1.25
        elif similarity <= 0.6:
            # Medium matches get moderate scores (40-70%)
            normalized_similarity = 0.7 - (similarity - 0.3) * 1.0
        else:
            # Distant matches get lower scores (0-40%)
            normalized_similarity = max(0.0, 0.4 - (similarity - 0.6) * 1.0)
        
        # Ensure the score is within bounds
        normalized_similarity = max(0.0, min(1.0, normalized_similarity))
    
    value = round(normalized_similarity * 100, decimals)  # round
    return int(value) if decimals == 0 else value

def calculate_enhanced_relevance_score(question: str, content: str, vector_score: float) -> float:
    """Calculate enhanced relevance score considering both vector similarity and content relevance"""
    # Base score from vector similarity
    base_score = pct(vector_score) / 100.0
    
    # Content relevance bonus
    content_bonus = 0.0
    
    # Convert to lowercase for case-insensitive matching
    question_lower = question.lower()
    content_lower = content.lower()
    
    # Split into words
    question_words = set(question_lower.split())
    content_words = set(content_lower.split())
    
    # Calculate word overlap
    if question_words:
        overlap_ratio = len(question_words.intersection(content_words)) / len(question_words)
        content_bonus = overlap_ratio * 0.3  # Up to 30% bonus for word overlap
    
    # Check for exact phrase matches
    for word in question_words:
        if len(word) > 3 and word in content_lower:  # Only consider words longer than 3 characters
            content_bonus += 0.1  # 10% bonus for each significant word match
    
    # Cap the content bonus
    content_bonus = min(content_bonus, 0.4)  # Maximum 40% bonus
    
    # Combine scores
    enhanced_score = min(1.0, base_score + content_bonus)
    
    return enhanced_score

def filter_relevant_documents(question: str, documents: list, max_docs: int = 10) -> list:
    """Filter documents by relevance to improve search performance"""
    if len(documents) <= max_docs:
        return documents
    
    # Extract keywords from question
    question_lower = question.lower()
    keywords = question_lower.split()
    
    # Score documents by relevance
    scored_docs = []
    for doc in documents:
        score = 0
        folder_structure = doc.get("folderStructure", {})
        
        # Check topic relevance
        topic = folder_structure.get("topic", "").lower()
        if any(keyword in topic for keyword in keywords):
            score += 3
        
        # Check subject relevance
        subject = folder_structure.get("subjectName", "").lower()
        if any(keyword in subject for keyword in keywords):
            score += 2
        
        # Check unit relevance
        unit = folder_structure.get("unitName", "").lower()
        if any(keyword in unit for keyword in keywords):
            score += 1
        
        # Check filename relevance
        filename = doc.get("fileName", "").lower()
        if any(keyword in filename for keyword in keywords):
            score += 2
        
        scored_docs.append((doc, score))
    
    # Sort by score and return top documents
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, score in scored_docs[:max_docs]] 

# Add caching for vector stores
# Note: vector_store_cache and VECTOR_STORE_CACHE_TTL are defined above

def get_cached_vector_store(doc_id: str) -> Optional[FAISS]:
    """Get vector store from cache or load it with improved error handling"""
    try:
        # Clean up expired caches first
        cleanup_expired_caches()
        
        current_time = time.time()
        
        # Check cache first using the new structure
        if doc_id in vector_store_cache and doc_id in vector_store_timestamps:
            cache_age = current_time - vector_store_timestamps[doc_id]
            if cache_age < VECTOR_STORE_CACHE_TTL:
                print(f"[CACHE_HIT] Using cached vector store for {doc_id} (age: {cache_age:.1f}s)")
                return vector_store_cache[doc_id]
            else:
                # Remove expired cache
                del vector_store_cache[doc_id]
                del vector_store_timestamps[doc_id]
                print(f"[CACHE_EXPIRED] Removed expired cache for {doc_id}")
        
        # Load vector store from scratch
        print(f"[CACHE_MISS] Loading vector store for {doc_id} from S3...")
        vector_store = load_vector_store(doc_id)
        
        if vector_store:
            # Cache the vector store using the new structure
            vector_store_cache[doc_id] = vector_store
            vector_store_timestamps[doc_id] = current_time
            print(f"[CACHE_STORED] Successfully cached vector store for {doc_id}")
            
            # Verify the vector store is usable
            if hasattr(vector_store, 'index') and vector_store.index:
                print(f"[DEBUG] Vector store {doc_id} verified - index size: {vector_store.index.ntotal}")
            else:
                print(f"[WARNING] Vector store {doc_id} has no valid index")
        else:
            print(f"[WARNING] Failed to load vector store for {doc_id}")
        
        return vector_store
        
    except Exception as e:
        print(f"[ERROR] Exception in get_cached_vector_store for {doc_id}: {str(e)}")
        
        # Clear any corrupted cache entry
        if doc_id in vector_store_cache:
            del vector_store_cache[doc_id]
        if doc_id in vector_store_timestamps:
            del vector_store_timestamps[doc_id]
        print(f"[DEBUG] Cleared corrupted cache entry for {doc_id}")
        
        return None

def cleanup_vector_store_cache():
    """Clean up expired vector store cache entries"""
    global vector_store_cache
    current_time = datetime.now().timestamp()
    
    expired_keys = []
    for doc_id, cached_data in vector_store_cache.items():
        if (current_time - cached_data["timestamp"]) >= VECTOR_STORE_CACHE_TTL:
            expired_keys.append(doc_id)
    
    for key in expired_keys:
        del vector_store_cache[key]
        print(f"[DEBUG] Cleaned up expired cache entry for {key}")
    
    print(f"[DEBUG] Cleaned up {len(expired_keys)} expired cache entries")

# Clean up cache periodically
import atexit
atexit.register(cleanup_vector_store_cache)                                                                                  