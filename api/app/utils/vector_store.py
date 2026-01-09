import os
import tempfile
import shutil
import time
import sys
from typing import Dict, List, Optional, Any, Tuple
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore

try:
    # LangChain >= 0.1
    from langchain_core.documents import Document
except Exception:
    # Older LangChain
    from langchain.schema import Document

# Import pydantic for version checking
try:
    import pydantic
    PYDANTIC_VERSION = pydantic.__version__
    PYDANTIC_MAJOR_VERSION = int(PYDANTIC_VERSION.split('.')[0])
except ImportError:
    PYDANTIC_VERSION = "unknown"
    PYDANTIC_MAJOR_VERSION = 0

from ..config.settings import (
    VECTOR_STORES_DIR, OPENAI_API_KEY, GOOGLE_API_KEY, 
    EMBEDDING_MODEL, AI_PROVIDER, USE_OPENAI_EMBEDDINGS
)

from .s3_utils import (
    upload_all_vectorstore_files,
    download_all_vectorstore_files,
    delete_all_vectorstore_files,
    ESSENTIAL_VECTORSTORE_FILES
)

def get_system_versions() -> Dict[str, str]:
    """Get versions of critical dependencies for compatibility checking"""
    versions = {
        "python": sys.version.split()[0],
        "pydantic": PYDANTIC_VERSION,
        "pydantic_major": str(PYDANTIC_MAJOR_VERSION),
    }
    
    try:
        import langchain
        versions["langchain"] = langchain.__version__
    except:
        versions["langchain"] = "unknown"
    
    try:
        import faiss
        versions["faiss"] = faiss.__version__
    except:
        versions["faiss"] = "unknown"
    
    return versions

def is_pydantic_compatibility_error(error: Exception) -> bool:
    """Check if an error is related to Pydantic v1/v2 compatibility issues"""
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Common Pydantic compatibility error indicators
    pydantic_indicators = [
        '__fields_set__',
        'fields_set',
        'pydantic',
        'validation error',
        'field required',
        'extra fields not permitted',
    ]
    
    # Check error message
    if any(indicator in error_str for indicator in pydantic_indicators):
        return True
    
    # Check error type
    if 'pydantic' in error_type.lower():
        return True
    
    return False

def get_compatibility_error_message(doc_id: str, error: Exception) -> str:
    """Generate a helpful error message for compatibility issues"""
    versions = get_system_versions()
    
    base_msg = (
        f"Vector store compatibility error for document {doc_id}. "
        f"This usually happens when a vector store was created in a different environment "
        f"(different Python/Pydantic versions). "
    )
    
    if is_pydantic_compatibility_error(error):
        base_msg += (
            f"\n\nDetected Pydantic compatibility issue. "
            f"Current Pydantic version: {versions['pydantic']} (v{versions['pydantic_major']}). "
            f"The vector store was likely created with Pydantic v1, but you're running Pydantic v2 (or vice versa)."
        )
    
    base_msg += (
        f"\n\nCurrent system versions:"
        f"\n  Python: {versions['python']}"
        f"\n  Pydantic: {versions['pydantic']}"
        f"\n  LangChain: {versions.get('langchain', 'unknown')}"
        f"\n  FAISS: {versions.get('faiss', 'unknown')}"
    )
    
    base_msg += (
        f"\n\nSOLUTION: Rebuild the vector store in the current environment by reprocessing the document. "
        f"This will create a new vector store compatible with your current dependencies."
    )
    
    return base_msg

def verify_document_processed(doc_id: str, retries: int = 3, delay: float = 2.0) -> bool:
    """Verify if document has been processed by checking essential vector store files in S3, with retries for S3 consistency."""
    for attempt in range(retries):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                download_all_vectorstore_files(doc_id, temp_dir)
                missing = [filename for filename in ESSENTIAL_VECTORSTORE_FILES if not os.path.exists(os.path.join(temp_dir, filename))]
                if not missing:
                    return True
                else:
                    print(f"Attempt {attempt+1}: Missing essential files: {missing}")
        except Exception as e:
            print(f"Attempt {attempt+1}: Error verifying document processing: {str(e)}")
        if attempt < retries - 1:
            time.sleep(delay)
    return False

def get_embeddings():
    """Get embeddings model based on configured AI provider and hybrid mode settings"""
    from ..config.settings import USE_OPENAI_EMBEDDINGS, AI_PROVIDER, OPENAI_API_KEY, GOOGLE_API_KEY, EMBEDDING_MODEL
    
    if USE_OPENAI_EMBEDDINGS:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when USE_OPENAI_EMBEDDINGS is enabled")
        return OpenAIEmbeddings(
            openai_api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL
        )
    elif AI_PROVIDER == "google":
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when AI_PROVIDER is set to 'google'")
        # Ensure Google embedding model name has the correct format (models/ prefix)
        model_name = EMBEDDING_MODEL
        
        # Detect and reject OpenAI model names - they're not compatible with Google API
        # Check if model name contains OpenAI-specific patterns (with or without models/ prefix)
        openai_patterns = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002", "text-embedding-ada"]
        is_openai_model = any(pattern in model_name for pattern in openai_patterns)
        
        if is_openai_model:
            # OpenAI model detected - replace with valid Google model
            model_name = "models/text-embedding-004"
        elif not model_name.startswith("models/"):
            # Auto-fix common old format Google model names
            if model_name == "text-embedding-gecko-002":
                model_name = "models/text-embedding-004"
            elif model_name in ["text-embedding-004", "text-embedding-003"]:
                # Valid Google model names - add prefix
                model_name = f"models/{model_name}"
            elif model_name == "embedding-001":
                # Valid Google model name - add prefix
                model_name = f"models/{model_name}"
            else:
                # Unknown format - default to valid Google model
                model_name = "models/text-embedding-004"
        
        # Final validation: ensure it's a valid Google model format
        if not model_name.startswith("models/"):
            model_name = "models/text-embedding-004"
            
        return GoogleGenerativeAIEmbeddings(
            google_api_key=GOOGLE_API_KEY,
            model=model_name
        )
    else:  # OpenAI
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER is set to 'openai'")
        return OpenAIEmbeddings(
            openai_api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL
        )

def load_vector_store(doc_id: str) -> Optional[FAISS]:
    """
    Load vector store from S3 with improved error handling and compatibility detection.
    
    Returns:
        FAISS vector store if successful, None otherwise
        
    Raises:
        ValueError: If a compatibility issue is detected (with helpful message)
    """
    try:
        print(f"[DEBUG] Loading vector store for doc_id={doc_id}")
        print(f"[DEBUG] System versions: {get_system_versions()}")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"vectorstore_{doc_id}_")
        
        try:
            # Download files
            download_all_vectorstore_files(doc_id, temp_dir)
            
            # Check essential files
            faiss_path = os.path.join(temp_dir, "index.faiss")
            pkl_path = os.path.join(temp_dir, "index.pkl")
            
            if not (os.path.exists(faiss_path) and os.path.exists(pkl_path)):
                print(f"[ERROR] Essential vector store files missing")
                return None
            
            # Check file sizes
            faiss_size = os.path.getsize(faiss_path)
            pkl_size = os.path.getsize(pkl_path)
            
            if faiss_size == 0 or pkl_size == 0:
                print(f"[ERROR] Vector store files are empty")
                return None
            
            print(f"[DEBUG] Vector store files found: index.faiss={faiss_size} bytes, index.pkl={pkl_size} bytes")
            
            # Load embeddings
            embeddings = get_embeddings()
            
            # Try loading with different strategies
            strategies = ["COSINE_DISTANCE", "EUCLIDEAN_DISTANCE", None]
            last_error = None
            compatibility_error = None
            
            for strategy in strategies:
                try:
                    if strategy:
                        vector_store = FAISS.load_local(
                            temp_dir, 
                            embeddings, 
                            allow_dangerous_deserialization=True,
                            distance_strategy=strategy
                        )
                    else:
                        vector_store = FAISS.load_local(
                            temp_dir, 
                            embeddings, 
                            allow_dangerous_deserialization=True
                        )
                    
                    # Verify it's usable
                    if vector_store and hasattr(vector_store, 'index') and vector_store.index.ntotal > 0:
                        print(f"[DEBUG] Vector store loaded successfully with {strategy or 'default'} strategy")
                        print(f"[DEBUG] Vector store index size: {vector_store.index.ntotal}, dimension: {vector_store.index.d}")
                        return vector_store
                        
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    error_type = type(e).__name__
                    
                    print(f"[DEBUG] Strategy {strategy} failed: {error_type}: {error_str}")
                    
                    # Check if this is a compatibility error
                    if is_pydantic_compatibility_error(e):
                        compatibility_error = e
                        print(f"[ERROR] Pydantic compatibility issue detected: {error_str}")
                        # Continue trying other strategies, but remember this error
                    
                    continue
            
            # If we get here, all strategies failed
            print(f"[ERROR] All loading strategies failed for {doc_id}")
            
            # If we detected a compatibility error, raise a more helpful exception
            if compatibility_error:
                error_msg = get_compatibility_error_message(doc_id, compatibility_error)
                print(f"[ERROR] {error_msg}")
                # Store the error message in a way that can be caught and handled
                raise ValueError(error_msg) from compatibility_error
            
            # Otherwise, log the last error for debugging
            if last_error:
                print(f"[ERROR] Last error was: {type(last_error).__name__}: {str(last_error)}")
            
            return None
            
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                print(f"[WARNING] Failed to cleanup temp directory: {cleanup_error}")
                
    except ValueError as ve:
        # Re-raise compatibility errors
        raise
    except Exception as e:
        print(f"[ERROR] Failed to load vector store: {type(e).__name__}: {str(e)}")
        # Check if this might be a compatibility issue we didn't catch earlier
        if is_pydantic_compatibility_error(e):
            error_msg = get_compatibility_error_message(doc_id, e)
            print(f"[ERROR] {error_msg}")
            raise ValueError(error_msg) from e
        return None
                        


def save_vector_store(vector_store: FAISS, doc_id: str) -> bool:
    """Save vector store directly to S3 without local storage"""
    try:
        print(f"[DEBUG] Saving vector store for doc_id={doc_id} directly to S3...")
        
        # Create a temporary directory just for serialization
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save to temp directory first (required by FAISS)
            vector_store.save_local(temp_dir)
            
            # Upload all files directly to S3
            upload_all_vectorstore_files(doc_id, temp_dir)
            
            # Clean up temp directory immediately
            import shutil
            shutil.rmtree(temp_dir)
            
        print(f"[DEBUG] Vector store saved successfully to S3 for doc_id={doc_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save vector store for doc_id={doc_id}: {str(e)}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Exception details: {str(e)}")
        
        # Clean up temp directory on error
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
        except Exception as cleanup_error:
            print(f"[WARNING] Failed to cleanup temp directory on error: {str(cleanup_error)}")
            
        return False

def delete_vector_store(doc_id: str) -> bool:
    """Delete all vector store files from S3"""
    try:
        delete_all_vectorstore_files(doc_id)
        return True
    except Exception as e:
        print(f"Error deleting vector store: {str(e)}")
        return False

def save_chunk_info(chunk_info: dict, doc_id: str) -> bool:
    """Save chunk_info.json to S3"""
    try:
        from .s3_utils import save_chunk_info_to_s3
        return save_chunk_info_to_s3(chunk_info, doc_id)
    except Exception as e:
        print(f"Error saving chunk info: {str(e)}")
        return False

def load_chunk_info(doc_id: str) -> Optional[dict]:
    """Load chunk_info.json from S3"""
    try:
        from .s3_utils import load_chunk_info_from_s3
        return load_chunk_info_from_s3(doc_id)
    except Exception as e:
        print(f"Error loading chunk info: {str(e)}")
        return None

def save_chunks_debug(chunks_debug: list, doc_id: str) -> bool:
    """Save chunks_debug.json to S3"""
    try:
        from .s3_utils import save_chunks_debug_to_s3
        return save_chunks_debug_to_s3(chunks_debug, doc_id)
    except Exception as e:
        print(f"Error saving chunks debug: {str(e)}")
        return False

def load_chunks_debug(doc_id: str) -> Optional[list]:
    """Load chunks_debug.json from S3"""
    try:
        from .s3_utils import load_chunks_debug_from_s3
        return load_chunks_debug_from_s3(doc_id)
    except Exception as e:
        print(f"Error loading chunks debug: {str(e)}")
        return None

def check_vector_store_compatibility(doc_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a document's vector store is compatible with current system.
    
    Returns:
        Tuple of (is_compatible: bool, error_message: Optional[str])
        If compatible, error_message is None.
        If incompatible, error_message contains a helpful explanation.
    """
    try:
        vector_store = load_vector_store(doc_id)
        if vector_store and vector_store.index and vector_store.index.ntotal > 0:
            # Test if we can perform a basic search
            try:
                test_results = vector_store.similarity_search("test", k=1)
                return (True, None)
            except Exception as e:
                error_msg = f"Vector store loaded but search failed: {type(e).__name__}: {str(e)}"
                if is_pydantic_compatibility_error(e):
                    error_msg = get_compatibility_error_message(doc_id, e)
                return (False, error_msg)
        return (False, "Vector store could not be loaded or is empty")
    except ValueError as ve:
        # Compatibility error with helpful message
        return (False, str(ve))
    except Exception as e:
        error_msg = f"Error checking compatibility: {type(e).__name__}: {str(e)}"
        if is_pydantic_compatibility_error(e):
            error_msg = get_compatibility_error_message(doc_id, e)
        return (False, error_msg) 