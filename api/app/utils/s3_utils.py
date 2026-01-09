import boto3
import os
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO, Dict, Any, List
from ..config.settings import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_REGION, S3_BUCKET_NAME, S3_BASE_URL
)
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize S3 client with validation
def _create_s3_client():
    """Create S3 client with proper validation"""
    try:
        # Check if all required S3 configuration is present
        if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME]):
            missing_vars = []
            if not AWS_ACCESS_KEY_ID:
                missing_vars.append("AWS_ACCESS_KEY_ID")
            if not AWS_SECRET_ACCESS_KEY:
                missing_vars.append("AWS_SECRET_ACCESS_KEY")
            if not AWS_REGION:
                missing_vars.append("AWS_REGION")
            if not S3_BUCKET_NAME:
                missing_vars.append("S3_BUCKET_NAME")
            
            logger.error(f"S3 configuration incomplete. Missing: {', '.join(missing_vars)}")
            return None
        
        # Validate AWS_REGION is not empty
        if not AWS_REGION or AWS_REGION.strip() == "":
            logger.error("AWS_REGION is empty or not set")
            return None
        
        # Create S3 client
        client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        logger.info(f"S3 client initialized successfully for region: {AWS_REGION}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create S3 client: {str(e)}")
        return None

# Initialize S3 client
s3_client = _create_s3_client()

# Check if S3 is available
S3_AVAILABLE = s3_client is not None

if not S3_AVAILABLE:
    logger.warning("S3 client not available. S3 operations will be disabled.")
else:
    logger.info("S3 client available and ready for use.")

# Constants for metadata files
DOCUMENTS_JSON_KEY = "metadata/documents.json"
VECTOR_STORES_PREFIX = "vectorstores/"
# Essential files required for vector store functionality
ESSENTIAL_VECTORSTORE_FILES = ["index.faiss", "index.pkl"]
# Additional metadata files (optional)
METADATA_VECTORSTORE_FILES = ["chunk_info.json", "chunks_debug.json"]
VECTORSTORE_FILES = ESSENTIAL_VECTORSTORE_FILES + METADATA_VECTORSTORE_FILES
VIDEOS_JSON_KEY = "metadata/videos.json"
TEMPLATE_KEY = "templates/pharmacy_prompt.txt"

# Constants for template management
TEMPLATES_PREFIX = "templates/"
TEMPLATE_BACKUPS_PREFIX = "templates/backups/"

def _check_s3_available():
    """Check if S3 is available and provide helpful error message"""
    if not S3_AVAILABLE:
        missing_vars = []
        if not AWS_ACCESS_KEY_ID:
            missing_vars.append("AWS_ACCESS_KEY_ID")
        if not AWS_SECRET_ACCESS_KEY:
            missing_vars.append("AWS_SECRET_ACCESS_KEY")
        if not AWS_REGION:
            missing_vars.append("AWS_REGION")
        if not S3_BUCKET_NAME:
            missing_vars.append("S3_BUCKET_NAME")
        
        error_msg = f"S3 is not available. Missing environment variables: {', '.join(missing_vars)}"
        if not AWS_REGION or AWS_REGION.strip() == "":
            error_msg += ". AWS_REGION is required and cannot be empty."
        
        raise Exception(error_msg)

def get_s3_key(folder_structure: Dict[str, str], filename: str) -> str:
    """Generate S3 key from folder structure and filename
    
    Structure: bpharma/pci/{year}_{semester}/{subject}/{unit}/{topic}/{filename}
    """
    curriculum = folder_structure.get('curriculum', 'pci')
    year_sem = folder_structure.get('yearSemester', '')
    subject = folder_structure.get('subjectName', '')
    unit = folder_structure.get('unitName', '')
    topic = folder_structure.get('topic', '')
    
    # Construct the S3 key: bpharma/pci/{year_sem}/{subject}/{unit}/{topic}/{filename}
    return f"bpharma/{curriculum}/{year_sem}/{subject}/{unit}/{topic}/{filename}"

def upload_file_to_s3(file_content: BinaryIO, s3_key: str, content_type: Optional[str] = None) -> str:
    """Upload a file to S3 and return its URL"""
    _check_s3_available()
    
    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
            
        s3_client.upload_fileobj(
            file_content,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args
        )
        
        return f"{S3_BASE_URL}/{s3_key}"
    except ClientError as e:
        raise Exception(f"Failed to upload file to S3: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error uploading to S3: {str(e)}")

def download_file_from_s3(s3_key: str) -> bytes:
    """Download a file from S3"""
    _check_s3_available()
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        raise Exception(f"Failed to download file from S3: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error downloading from S3: {str(e)}")

def get_file_from_s3(s3_key: str) -> bytes:
    """Get a file from S3 (alias for download_file_from_s3)"""
    return download_file_from_s3(s3_key)

def delete_file_from_s3(s3_key: str) -> bool:
    """Delete a file from S3"""
    _check_s3_available()
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        raise Exception(f"Failed to delete file from S3: {str(e)}")

def get_file_url(s3_key: str) -> str:
    """Get the public URL for a file in S3"""
    return f"{S3_BASE_URL}/{s3_key}"

def list_files_in_folder(prefix: str) -> list:
    """List all files in a folder (prefix) in S3"""
    _check_s3_available()
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )
        return [item['Key'] for item in response.get('Contents', [])]
    except ClientError as e:
        raise Exception(f"Failed to list files in S3: {str(e)}")

def file_exists_in_s3(s3_key: str) -> bool:
    """Check if a file exists in S3"""
    _check_s3_available()
    try:
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise Exception(f"Failed to check file existence in S3: {str(e)}")

def get_file_metadata(s3_key: str) -> Dict[str, Any]:
    """Get metadata for a file in S3"""
    _check_s3_available()
    try:
        response = s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return {
            'size': response['ContentLength'],
            'last_modified': response['LastModified'],
            'content_type': response.get('ContentType'),
            'metadata': response.get('Metadata', {})
        }
    except ClientError as e:
        raise Exception(f"Failed to get file metadata from S3: {str(e)}")

def save_documents_metadata(documents: list) -> bool:
    """Save documents metadata to S3"""
    _check_s3_available()
    try:
        # Convert documents to JSON string
        json_data = json.dumps(documents, indent=2)
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=DOCUMENTS_JSON_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save documents metadata to S3: {str(e)}")

def load_documents_metadata() -> list:
    """Load documents metadata from S3"""
    _check_s3_available()
    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=DOCUMENTS_JSON_KEY
        )
        json_data = response['Body'].read().decode('utf-8')
        return json.loads(json_data)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            # If documents.json doesn't exist yet, return empty list
            return []
        raise Exception(f"Failed to load documents metadata from S3: {str(e)}")

def save_vector_store_to_s3(vector_store_data: bytes, doc_id: str) -> bool:
    """Save vector store data to S3"""
    _check_s3_available()
    try:
        # Save the vector store files to S3
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/index.faiss"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=vector_store_data,
            ContentType='application/octet-stream'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save vector store to S3: {str(e)}")

def load_vector_store_from_s3(doc_id: str) -> Optional[bytes]:
    """Load vector store data from S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/index.faiss"
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise Exception(f"Failed to load vector store from S3: {str(e)}")

def delete_vector_store_from_s3(doc_id: str) -> bool:
    """Delete vector store data from S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/index.faiss"
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return True  # Already deleted
        raise Exception(f"Failed to delete vector store from S3: {str(e)}")

def save_chunk_info_to_s3(chunk_info: dict, doc_id: str) -> bool:
    """Save chunk information to S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/chunk_info.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(chunk_info, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save chunk info to S3: {str(e)}")

def load_chunk_info_from_s3(doc_id: str) -> Optional[dict]:
    """Load chunk information from S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/chunk_info.json"
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise Exception(f"Failed to load chunk info from S3: {str(e)}")

def save_chunks_debug_to_s3(chunks_debug: list, doc_id: str) -> bool:
    """Save detailed chunks debug information to S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/chunks_debug.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(chunks_debug, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save chunks debug info to S3: {str(e)}")

def load_chunks_debug_from_s3(doc_id: str) -> Optional[list]:
    """Load detailed chunks debug information from S3"""
    _check_s3_available()
    try:
        s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/chunks_debug.json"
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise Exception(f"Failed to load chunks debug info from S3: {str(e)}")

def upload_vectorstore_file(doc_id: str, filename: str, data: bytes, content_type: str) -> bool:
    _check_s3_available()
    s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/{filename}"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=data,
            ContentType=content_type
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to upload {filename} to S3: {str(e)}")

def download_vectorstore_file(doc_id: str, filename: str) -> bytes:
    _check_s3_available()
    s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/{filename}"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise Exception(f"Failed to download {filename} from S3: {str(e)}")

def delete_vectorstore_file(doc_id: str, filename: str) -> bool:
    _check_s3_available()
    s3_key = f"{VECTOR_STORES_PREFIX}{doc_id}/{filename}"
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return True
        raise Exception(f"Failed to delete {filename} from S3: {str(e)}")

def upload_all_vectorstore_files(doc_id: str, local_dir: str) -> None:
    logger = logging.getLogger(__name__)
    for filename in VECTORSTORE_FILES:
        local_path = os.path.join(local_dir, filename)
        if os.path.exists(local_path):
            logger.info(f"Uploading {filename} for doc_id={doc_id} from {local_path} to S3...")
            try:
                with open(local_path, 'rb') as f:
                    data = f.read()
                content_type = 'application/octet-stream' if filename.endswith('.faiss') or filename.endswith('.pkl') else 'application/json'
                upload_success = upload_vectorstore_file(doc_id, filename, data, content_type)
                if upload_success:
                    logger.info(f"Successfully uploaded {filename} for doc_id={doc_id} to S3.")
                else:
                    logger.error(f"Upload function returned False for {filename} (doc_id={doc_id}).")
            except Exception as e:
                logger.error(f"Error uploading {filename} for doc_id={doc_id}: {e}")
        else:
            logger.warning(f"File {filename} for doc_id={doc_id} is missing locally at {local_path}, skipping upload.")

def download_all_vectorstore_files(doc_id: str, target_dir: str) -> None:
    import os
    os.makedirs(target_dir, exist_ok=True)
    print(f"\n[DEBUG] Starting download of vector store files for doc_id={doc_id} to {target_dir}")
    
    # First, check if the vector store directory exists in S3
    prefix = f"{VECTOR_STORES_PREFIX}{doc_id}/"
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )
        if 'Contents' not in response:
            print(f"[DEBUG] No vector store files found in S3 for doc_id={doc_id}")
            return
        
        available_files = [obj['Key'].split('/')[-1] for obj in response['Contents']]
        print(f"[DEBUG] Found files in S3: {available_files}")
    except Exception as e:
        print(f"[DEBUG] Error listing vector store files in S3: {str(e)}")
        return
    
    for filename in VECTORSTORE_FILES:
        print(f"[DEBUG] Attempting to download {filename} for doc_id={doc_id}")
        try:
            data = download_vectorstore_file(doc_id, filename)
            if data is not None:
                file_path = os.path.join(target_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(data)
                print(f"[DEBUG] Downloaded and wrote {filename} ({len(data)} bytes)")
                
                # Verify the file was written correctly
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    print(f"[DEBUG] Verified {filename} exists on disk with size {size} bytes")
                else:
                    print(f"[DEBUG] Warning: {filename} was not written to disk properly")
            else:
                print(f"[DEBUG] {filename} not found in S3 for doc_id={doc_id}")
        except Exception as e:
            print(f"[DEBUG] Error downloading {filename}: {str(e)}")
            # Continue with other files even if one fails

def delete_all_vectorstore_files(doc_id: str) -> None:
    _check_s3_available()
    for filename in VECTORSTORE_FILES:
        delete_vectorstore_file(doc_id, filename)

def save_videos_metadata(videos: list) -> bool:
    """Save videos metadata to S3 (videos.json)"""
    _check_s3_available()
    try:
        json_data = json.dumps(videos, indent=2)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=VIDEOS_JSON_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save videos metadata to S3: {str(e)}")

def load_videos_metadata() -> list:
    """Load videos metadata from S3 (videos.json)"""
    _check_s3_available()
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=VIDEOS_JSON_KEY)
        json_data = response['Body'].read().decode('utf-8')
        return json.loads(json_data)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []
        raise Exception(f"Failed to load videos metadata from S3: {str(e)}")

def save_video_metadata_s3(video: dict, folder_path: str) -> bool:
    """Save per-video metadata.json to S3"""
    _check_s3_available()
    try:
        s3_key = f"{folder_path}/metadata.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(video, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to save video metadata to S3: {str(e)}")

def load_video_metadata_s3(folder_path: str) -> dict:
    """Load per-video metadata.json from S3"""
    _check_s3_available()
    try:
        s3_key = f"{folder_path}/metadata.json"
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise Exception(f"Failed to load video metadata from S3: {str(e)}")

def delete_video_metadata_s3(folder_path: str) -> bool:
    """Delete per-video metadata.json from S3"""
    _check_s3_available()
    try:
        s3_key = f"{folder_path}/metadata.json"
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return True
        raise Exception(f"Failed to delete video metadata from S3: {str(e)}")

def save_response_to_s3(response: dict, response_id: str) -> bool:
    _check_s3_available()
    s3_key = f"responses/{response_id}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(response).encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        print(f"Failed to save response to S3: {e}")
        return False

def load_response_from_s3(response_id: str) -> Optional[dict]:
    _check_s3_available()
    s3_key = f"responses/{response_id}.json"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"Failed to load response from S3: {e}")
        return None

def get_template_s3_key(template_name: str, is_backup: bool = False) -> str:
    """Generate S3 key for a template file"""
    if is_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{TEMPLATE_BACKUPS_PREFIX}{template_name}_{timestamp}.txt"
    return f"{TEMPLATES_PREFIX}{template_name}.txt"

def save_template_to_s3(template_text: str, template_name: str = "pharmacy_prompt") -> bool:
    """
    Save a template to S3 with backup (maintaining only 3 most recent backups)
    Args:
        template_text: The template content
        template_name: Name of the template (default: pharmacy_prompt)
    Returns:
        bool: Success status
    """
    _check_s3_available()
    try:
        # First, create a backup of the existing template if it exists
        try:
            existing_template = load_template_from_s3(template_name)
            if existing_template:
                # Get list of existing backups
                response = s3_client.list_objects_v2(
                    Bucket=S3_BUCKET_NAME,
                    Prefix=f"{TEMPLATE_BACKUPS_PREFIX}{template_name}_"
                )
                existing_backups = response.get('Contents', [])
                
                # Sort backups by timestamp (newest first)
                existing_backups.sort(key=lambda x: x['LastModified'], reverse=True)
                
                # If we already have 3 backups, delete the oldest one
                if len(existing_backups) >= 3:
                    oldest_backup = existing_backups[-1]
                    try:
                        s3_client.delete_object(
                            Bucket=S3_BUCKET_NAME,
                            Key=oldest_backup['Key']
                        )
                        logging.info(f"Deleted oldest backup: {oldest_backup['Key']}")
                    except Exception as e:
                        logging.warning(f"Failed to delete oldest backup: {str(e)}")
                
                # Create new backup with timestamp
                backup_key = get_template_s3_key(template_name, is_backup=True)
                s3_client.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=backup_key,
                    Body=existing_template.encode('utf-8'),
                    ContentType='text/plain'
                )
                logging.info(f"Created backup of template {template_name} at {backup_key}")
        except Exception as e:
            logging.warning(f"Failed to create backup of template {template_name}: {str(e)}")

        # Save the new template content
        template_key = get_template_s3_key(template_name)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=template_key,
            Body=template_text.encode('utf-8'),
            ContentType='text/plain'
        )
        return True
    except Exception as e:
        logging.error(f"Failed to save template to S3: {str(e)}")
        return False

def load_template_from_s3(template_name: str = "pharmacy_prompt") -> Optional[str]:
    """
    Load a template from S3
    Args:
        template_name: Name of the template to load (default: pharmacy_prompt)
    Returns:
        Optional[str]: Template content if successful, None otherwise
    """
    _check_s3_available()
    try:
        template_key = get_template_s3_key(template_name)
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=template_key)
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logging.warning(f"Template {template_name} not found in S3")
            return None
        logging.error(f"Error loading template from S3: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error loading template from S3: {str(e)}")
        return None

def list_available_templates() -> List[str]:
    """List all available templates in S3"""
    _check_s3_available()
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=TEMPLATES_PREFIX
        )
        templates = []
        for item in response.get('Contents', []):
            key = item['Key']
            if key.endswith('.txt') and not key.startswith(TEMPLATE_BACKUPS_PREFIX):
                # Extract template name from key (remove prefix and .txt)
                template_name = key[len(TEMPLATES_PREFIX):-4]
                templates.append(template_name)
        return templates
    except Exception as e:
        logging.error(f"Error listing templates: {str(e)}")
        return []

def list_template_backups(template_name: str = "pharmacy_prompt") -> List[Dict[str, Any]]:
    """
    List all backups for a template (returns up to 3 most recent backups)
    Args:
        template_name: Name of the template
    Returns:
        List of backup metadata including timestamp and size
    """
    _check_s3_available()
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=f"{TEMPLATE_BACKUPS_PREFIX}{template_name}_"
        )
        backups = []
        for item in response.get('Contents', []):
            key = item['Key']
            # Extract timestamp from filename
            timestamp_str = key.split('_')[-1].replace('.txt', '')
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                backups.append({
                    "key": key,
                    "timestamp": timestamp.isoformat(),
                    "size": item['Size'],
                    "last_modified": item['LastModified'].isoformat()
                })
            except ValueError:
                logging.warning(f"Invalid timestamp format in backup file: {key}")
        
        # Sort by timestamp (newest first) and return only the 3 most recent
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)[:3]
    except Exception as e:
        logging.error(f"Failed to list template backups: {str(e)}")
        return []

def restore_template_from_backup(template_name: str, backup_key: str) -> bool:
    """
    Restore a template from a backup
    Args:
        template_name: Name of the template
        backup_key: S3 key of the backup to restore from
    Returns:
        bool: Success status
    """
    _check_s3_available()
    try:
        # Load the backup content
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=backup_key)
        backup_content = response['Body'].read().decode('utf-8')
        
        # Save it as the current template
        return save_template_to_s3(backup_content, template_name)
    except Exception as e:
        logging.error(f"Failed to restore template from backup: {str(e)}")
        return False

# Notes-related S3 functions
NOTES_CURRICULUM_DEFAULT = "pci"
NOTES_PREFIX = f"generated-notes/{NOTES_CURRICULUM_DEFAULT}/"
NOTES_METADATA_KEY = "metadata/generated_notes.json"

def save_notes_to_s3(notes_id: str, notes_content: str) -> bool:
    """Save notes content to S3"""
    _check_s3_available()
    try:
        s3_key = f"{NOTES_PREFIX}{notes_id}.txt"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=notes_content.encode('utf-8'),
            ContentType='text/plain'
        )
        return True
    except Exception as e:
        logging.error(f"Failed to save notes to S3: {str(e)}")
        return False

def load_notes_from_s3(notes_id: str) -> Optional[str]:
    """Load notes content from S3"""
    _check_s3_available()
    try:
        s3_key = f"{NOTES_PREFIX}{notes_id}.txt"
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        logging.error(f"Failed to load notes from S3: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Failed to load notes from S3: {str(e)}")
        return None

def save_notes_metadata_to_s3(notes_list: list) -> bool:
    """Save notes metadata to S3"""
    _check_s3_available()
    try:
        json_data = json.dumps(notes_list, indent=2)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=NOTES_METADATA_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        logging.error(f"Failed to save notes metadata to S3: {str(e)}")
        return False

def load_notes_metadata_from_s3() -> list:
    """Load notes metadata from S3"""
    _check_s3_available()
    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=NOTES_METADATA_KEY
        )
        json_data = response['Body'].read().decode('utf-8')
        return json.loads(json_data)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []
        logging.error(f"Failed to load notes metadata from S3: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Failed to load notes metadata from S3: {str(e)}")
        return [] 