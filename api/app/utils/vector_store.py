import os
import tempfile
import shutil
from typing import Dict, List, Optional, Any
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
        return GoogleGenerativeAIEmbeddings(
            google_api_key=GOOGLE_API_KEY,
            model=EMBEDDING_MODEL
        )
    else:  # OpenAI
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER is set to 'openai'")
        return OpenAIEmbeddings(
            openai_api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL
        )

def load_vector_store(doc_id: str) -> Optional[FAISS]:
    """Load vector store from S3 with improved error handling and logging"""
    import logging
    logger = logging.getLogger(__name__)
    
    temp_dir = None
    try:
        logger.info(f"Loading vector store for doc_id={doc_id}")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"vectorstore_{doc_id}_")
        logger.debug(f"Created temporary directory: {temp_dir}")
        
        # Download files - this will now raise exceptions on failure
        try:
            download_all_vectorstore_files(doc_id, temp_dir)
            logger.info(f"Successfully downloaded all vector store files for doc_id={doc_id}")
        except Exception as download_error:
            error_msg = f"Failed to download vector store files from S3 for doc_id={doc_id}: {str(download_error)}"
            logger.error(error_msg, exc_info=True)
            # Re-raise with more context
            raise Exception(error_msg) from download_error
        
        # Check essential files
        faiss_path = os.path.join(temp_dir, "index.faiss")
        pkl_path = os.path.join(temp_dir, "index.pkl")
        
        if not (os.path.exists(faiss_path) and os.path.exists(pkl_path)):
            error_msg = f"Essential vector store files missing after download for doc_id={doc_id}. faiss exists: {os.path.exists(faiss_path)}, pkl exists: {os.path.exists(pkl_path)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Check file sizes
        faiss_size = os.path.getsize(faiss_path)
        pkl_size = os.path.getsize(pkl_path)
        logger.debug(f"File sizes - faiss: {faiss_size} bytes, pkl: {pkl_size} bytes")
        
        if faiss_size == 0 or pkl_size == 0:
            error_msg = f"Vector store files are empty for doc_id={doc_id}. faiss size: {faiss_size}, pkl size: {pkl_size}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Load embeddings
        try:
            embeddings = get_embeddings()
            logger.debug("Embeddings model loaded successfully")
        except Exception as emb_error:
            error_msg = f"Failed to load embeddings model: {str(emb_error)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from emb_error
        
        # Try loading with different strategies
        strategies = ["COSINE_DISTANCE", "EUCLIDEAN_DISTANCE", None]
        last_error = None
        
        for strategy in strategies:
            try:
                logger.debug(f"Attempting to load vector store with strategy: {strategy or 'default'}")
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
                    logger.info(f"Vector store loaded successfully with {strategy or 'default'} strategy. Index size: {vector_store.index.ntotal}")
                    return vector_store
                else:
                    logger.warning(f"Vector store loaded but appears invalid. Has index: {hasattr(vector_store, 'index') if vector_store else False}")
                    
            except Exception as e:
                last_error = e
                logger.debug(f"Strategy {strategy} failed: {str(e)}")
                continue
        
        # If all strategies failed, raise an exception with details
        error_msg = f"All loading strategies failed for doc_id={doc_id}. Last error: {str(last_error) if last_error else 'Unknown'}"
        logger.error(error_msg, exc_info=last_error is not None)
        if last_error:
            raise Exception(error_msg) from last_error
        else:
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to load vector store for doc_id={doc_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Re-raise to allow caller to handle
        raise Exception(error_msg) from e
    finally:
        # Clean up temp directory
        if temp_dir:
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp directory {temp_dir}: {cleanup_error}")
                        


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