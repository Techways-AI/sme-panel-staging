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
        
        # Proactively fix Pydantic compatibility issues in pickle file BEFORE loading
        # This handles the case where pickles were created with Pydantic v1 but loaded with v2 (or vice versa)
        pkl_path = os.path.join(temp_dir, "index.pkl")
        
        try:
            import pickle
            logger.debug("Checking pickle file for Pydantic compatibility issues...")
            
            # Read and check the pickle file
            with open(pkl_path, 'rb') as f:
                pickle_data = pickle.load(f)
            
            # Recursively fix dicts that look like Pydantic model states
            fixed_count = [0]  # Use list to allow modification in nested function
            
            def fix_pydantic_dict(obj, path=""):
                if isinstance(obj, dict):
                    # Check if this looks like a Pydantic model state
                    # Pydantic v1 models have __fields_set__ but v2 might not when unpickling v1 pickles
                    has_underscore_fields = any(k.startswith('__') and k != '__fields_set__' for k in obj.keys())
                    missing_fields_set = '__fields_set__' not in obj
                    
                    if has_underscore_fields and missing_fields_set:
                        # Add __fields_set__ with all non-private keys (this is what Pydantic v1 expects)
                        obj['__fields_set__'] = set(k for k in obj.keys() if not k.startswith('__'))
                        fixed_count[0] += 1
                        logger.debug(f"Fixed __fields_set__ at path: {path}")
                    
                    # Recursively fix nested dicts
                    for k, v in obj.items():
                        if isinstance(v, (dict, list)):
                            fix_pydantic_dict(v, f"{path}.{k}" if path else k)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if isinstance(item, (dict, list)):
                            fix_pydantic_dict(item, f"{path}[{i}]" if path else f"[{i}]")
            
            fix_pydantic_dict(pickle_data)
            
            if fixed_count[0] > 0:
                # Save the fixed pickle
                with open(pkl_path, 'wb') as f:
                    pickle.dump(pickle_data, f)
                logger.info(f"Proactively fixed {fixed_count[0]} Pydantic compatibility issues in pickle file")
            else:
                logger.debug("No Pydantic compatibility issues found in pickle file")
        except Exception as fix_error:
            logger.warning(f"Could not proactively fix pickle file: {str(fix_error)}")
            # Continue anyway - we'll try to fix on error
        
        # Apply Pydantic monkey-patch as additional safety
        try:
            import pydantic
            if hasattr(pydantic, 'v1'):
                logger.debug("Pydantic v1 and v2 both available, applying compatibility patch")
                
                # Monkey-patch pydantic.v1 to handle missing __fields_set__
                if hasattr(pydantic.v1.main, 'BaseModel'):
                    original_setstate = pydantic.v1.main.BaseModel.__setstate__
                    
                    def patched_setstate(self, state):
                        # If __fields_set__ is missing, create an empty set
                        if isinstance(state, dict) and '__fields_set__' not in state:
                            state['__fields_set__'] = set()
                        return original_setstate(self, state)
                    
                    pydantic.v1.main.BaseModel.__setstate__ = patched_setstate
                    logger.debug("Applied Pydantic v1 compatibility patch")
        except Exception as patch_error:
            logger.debug(f"Could not apply Pydantic compatibility patch: {str(patch_error)}")
        
        # Try loading with different strategies
        strategies = [None, "COSINE_DISTANCE", "EUCLIDEAN_DISTANCE"]  # Try None first (no strategy)
        last_error = None
        vector_store = None
        retry_after_fix = False
        
        for strategy in strategies:
            try:
                logger.debug(f"Attempting to load vector store with strategy: {strategy or 'default'}")
                
                # Try loading with FAISS
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
                    
            except (KeyError, AttributeError) as e:
                error_str = str(e)
                error_type = type(e).__name__
                
                # Check if this is a Pydantic compatibility issue
                if "__fields_set__" in error_str or (error_type == "KeyError" and "__fields_set__" in str(e)):
                    logger.warning(f"Pydantic compatibility issue detected during load: {error_str}")
                    last_error = e
                    # This should not happen if proactive fix worked, but try reactive fix
                    logger.info("Attempting reactive fix for Pydantic compatibility...")
                    try:
                        import pickle
                        
                        # Read the pickle again
                        with open(pkl_path, 'rb') as f:
                            pickle_data = pickle.load(f)
                        
                        # Recursively fix dicts
                        fixed_count = [0]
                        
                        def fix_pydantic_dict(obj, path=""):
                            if isinstance(obj, dict):
                                has_underscore_fields = any(k.startswith('__') and k != '__fields_set__' for k in obj.keys())
                                missing_fields_set = '__fields_set__' not in obj
                                
                                if has_underscore_fields and missing_fields_set:
                                    obj['__fields_set__'] = set(k for k in obj.keys() if not k.startswith('__'))
                                    fixed_count[0] += 1
                                    logger.debug(f"Fixed __fields_set__ at path: {path}")
                                
                                for k, v in obj.items():
                                    if isinstance(v, (dict, list)):
                                        fix_pydantic_dict(v, f"{path}.{k}" if path else k)
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    if isinstance(item, (dict, list)):
                                        fix_pydantic_dict(item, f"{path}[{i}]" if path else f"[{i}]")
                        
                        fix_pydantic_dict(pickle_data)
                        
                        if fixed_count[0] > 0:
                            with open(pkl_path, 'wb') as f:
                                pickle.dump(pickle_data, f)
                            logger.info(f"Reactive fix applied ({fixed_count[0]} fixes), will retry from first strategy")
                            # Set flag to retry from beginning
                            retry_after_fix = True
                            break
                    except Exception as fix_error:
                        logger.warning(f"Reactive fix failed: {str(fix_error)}")
                        last_error = e
                        continue
                else:
                    last_error = e
                    logger.debug(f"Strategy {strategy} failed: {str(e)}")
                    continue
            except Exception as e:
                last_error = e
                error_str = str(e)
                # Check if the underlying error is Pydantic-related
                if "__fields_set__" in error_str:
                    logger.warning(f"Pydantic compatibility issue in exception chain: {error_str}")
                    last_error = e
                    continue
                logger.debug(f"Strategy {strategy} failed: {str(e)}")
                continue
        
        # If we fixed the pickle and need to retry, do it now
        if retry_after_fix:
            logger.info("Retrying load after Pydantic fix...")
            for strategy in strategies:
                try:
                    logger.debug(f"Retry: Attempting to load vector store with strategy: {strategy or 'default'}")
                    
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
                    
                    if vector_store and hasattr(vector_store, 'index') and vector_store.index.ntotal > 0:
                        logger.info(f"Vector store loaded successfully after fix with {strategy or 'default'} strategy. Index size: {vector_store.index.ntotal}")
                        return vector_store
                except Exception as retry_error:
                    logger.debug(f"Retry with strategy {strategy} failed: {str(retry_error)}")
                    if strategy == strategies[-1]:
                        last_error = retry_error
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