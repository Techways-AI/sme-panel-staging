import os
import tempfile
import shutil
import pickle
import time
from typing import Dict, List, Optional, Any
import faiss
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.faiss import DistanceStrategy

try:
    # LangChain >= 0.1
    from langchain_core.documents import Document
except Exception:
    # Older LangChain
    from langchain.schema import Document

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
    """Load vector store from S3 with simplified error handling"""
    try:
        print(f"[DEBUG] Loading vector store for doc_id={doc_id}")
        
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
            
            # Load embeddings
            embeddings = get_embeddings()
            
            # Try loading with different strategies (enum for compatibility)
            strategies: List[Any] = []
            try:
                for name in ("COSINE", "EUCLIDEAN", "L2"):
                    if hasattr(DistanceStrategy, name):
                        strategies.append(getattr(DistanceStrategy, name))
            except Exception as strategy_err:
                print(f"[WARNING] Failed to enumerate distance strategies: {strategy_err}")
            strategies.append(None)
            print(f"[DEBUG] Distance strategies to try: {strategies}")
            
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
                        return vector_store
                        
                except Exception as e:
                    print(f"[DEBUG] Strategy {strategy} failed: {e}")
                    
                    # Backward compatibility: handle legacy pydantic/Document pickles
                    if "__fields_set__" in str(e):
                        try:
                            print("[DEBUG] Attempting manual fallback vector store load")
                            fallback_store = _manual_load_vector_store(temp_dir, embeddings)
                            if fallback_store and hasattr(fallback_store, "index") and fallback_store.index.ntotal > 0:
                                print("[DEBUG] Manual fallback vector store load succeeded")
                                return fallback_store
                        except Exception as fallback_error:
                            print(f"[WARNING] Manual fallback vector store load failed: {fallback_error}")
                    continue
            
            # Final fallback try before giving up
            try:
                print("[DEBUG] All enum strategies failed; attempting manual fallback load")
                fallback_store = _manual_load_vector_store(temp_dir, embeddings)
                if fallback_store and hasattr(fallback_store, "index") and fallback_store.index.ntotal > 0:
                    print("[DEBUG] Manual fallback vector store load succeeded")
                    return fallback_store
            except Exception as final_fallback_error:
                print(f"[WARNING] Manual fallback after strategies failed: {final_fallback_error}")
            
            print(f"[ERROR] All loading strategies failed for {doc_id}")
            return None
            
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                print(f"[WARNING] Failed to cleanup temp directory: {cleanup_error}")
                
    except Exception as e:
        print(f"[ERROR] Failed to load vector store: {e}")
        # If a strategy name itself caused the error (e.g., unsupported enum), attempt manual load
        if "EUCLIDEAN" in str(e) or "DistanceStrategy" in str(e):
            try:
                print("[DEBUG] Attempting manual fallback after strategy error")
                temp_dir = tempfile.mkdtemp(prefix=f"vectorstore_fallback_{doc_id}_")
                download_all_vectorstore_files(doc_id, temp_dir)
                embeddings = get_embeddings()
                fallback_store = _manual_load_vector_store(temp_dir, embeddings)
                shutil.rmtree(temp_dir, ignore_errors=True)
                if fallback_store and hasattr(fallback_store, "index") and fallback_store.index.ntotal > 0:
                    print("[DEBUG] Manual fallback after strategy error succeeded")
                    return fallback_store
            except Exception as fallback_error:
                print(f"[WARNING] Manual fallback after strategy error failed: {fallback_error}")
        return None
                        

def _manual_load_vector_store(temp_dir: str, embeddings) -> Optional[FAISS]:
    """Best-effort loader for legacy vector stores serialized with older LangChain/Pydantic versions."""
    faiss_path = os.path.join(temp_dir, "index.faiss")
    pkl_path = os.path.join(temp_dir, "index.pkl")

    if not (os.path.exists(faiss_path) and os.path.exists(pkl_path)):
        print("[ERROR] Manual load failed: index files missing")
        return None

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    index = faiss.read_index(faiss_path)
    raw_docstore = data.get("docstore")
    index_to_docstore_id = data.get("index_to_docstore_id", {})
    normalize_L2 = data.get("normalize_L2", False)
    distance_strategy = data.get("distance_strategy")

    # Extract raw docs from various stored shapes
    if isinstance(raw_docstore, InMemoryDocstore):
        raw_docs = getattr(raw_docstore, "_dict", {}) or {}
    elif isinstance(raw_docstore, dict):
        raw_docs = raw_docstore
    else:
        raw_docs = {}

    cleaned_docs = {}
    for key, value in raw_docs.items():
        if isinstance(value, Document):
            cleaned_docs[key] = value
            continue

        content = getattr(value, "page_content", None)
        metadata = getattr(value, "metadata", None)

        if content is None and isinstance(value, dict):
            content = value.get("page_content") or value.get("content") or ""
            metadata = value.get("metadata", {})

        if content is None:
            continue

        try:
            cleaned_docs[key] = Document(page_content=content, metadata=metadata or {})
        except Exception:
            cleaned_docs[key] = Document(page_content=str(content), metadata=metadata or {})

    docstore = InMemoryDocstore(cleaned_docs)

    # Map distance strategy from stored value (string or enum)
    ds = None
    if distance_strategy:
        try:
            if isinstance(distance_strategy, DistanceStrategy):
                ds = distance_strategy
            elif isinstance(distance_strategy, str) and distance_strategy in DistanceStrategy.__members__:
                ds = DistanceStrategy[distance_strategy]
        except Exception:
            ds = None

    return FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=docstore,
        index_to_docstore_id=index_to_docstore_id,
        normalize_L2=normalize_L2,
        distance_strategy=ds or DistanceStrategy.COSINE
    )


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

def check_vector_store_compatibility(doc_id: str) -> bool:
    """Check if a document's vector store is compatible with current system"""
    try:
        vector_store = load_vector_store(doc_id)
        if vector_store and vector_store.index and vector_store.index.ntotal > 0:
            # Test if we can perform a basic search
            try:
                test_results = vector_store.similarity_search("test", k=1)
                return True
            except Exception:
                return False
        return False
    except Exception:
        return False 