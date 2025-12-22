import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from typing import List, Set

# Load environment variables
load_dotenv()

# Environment check
ENV = os.getenv("ENV", "development")
IS_PRODUCTION = ENV == "production"

# Configure logging with UTF-8 support
import io
import sys

# Create a UTF-8 compatible stdout handler for Windows
if sys.platform == "win32":
    # Force UTF-8 encoding for stdout on Windows
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO if IS_PRODUCTION else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log", encoding='utf-8')
    ]
)

# Reduce noise from boto3 and other AWS libraries
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)

# Reduce noise from PDF processing libraries
logging.getLogger('pdfplumber').setLevel(logging.WARNING)
logging.getLogger('pdfminer').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfinterp').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfdocument').setLevel(logging.WARNING)
logging.getLogger('pdfminer.psparser').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

# Reduce noise from OpenAI and HTTP libraries
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Reduce noise from multipart and other libraries
logging.getLogger('multipart').setLevel(logging.WARNING)
logging.getLogger('multipart.multipart').setLevel(logging.WARNING)
logging.getLogger('starlette').setLevel(logging.WARNING)
logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('fastapi').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY and IS_PRODUCTION:
    raise ValueError("JWT_SECRET_KEY must be set in production environment")
elif not JWT_SECRET_KEY:
    logger.warning("JWT_SECRET_KEY not found in environment variables. Using a default key for development only.")
    JWT_SECRET_KEY = "supersecretkey"  # Only for development

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Required Environment Variables for Production
REQUIRED_ENV_VARS = [
    "JWT_SECRET_KEY"  # Only JWT_SECRET_KEY is truly required
]

# Optional but recommended for production
RECOMMENDED_ENV_VARS = [
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "AWS_ACCESS_KEY_ID", 
    "AWS_SECRET_ACCESS_KEY",
    "S3_BUCKET_NAME"
]

if IS_PRODUCTION:
    # Check required variables
    missing_required = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_required:
        raise ValueError(f"Missing required environment variables in production: {', '.join(missing_required)}")
    
    # Check recommended variables and warn
    missing_recommended = [var for var in RECOMMENDED_ENV_VARS if not os.getenv(var)]
    if missing_recommended:
        logger.warning(f"Missing recommended environment variables in production: {', '.join(missing_recommended)}")
        logger.warning("Some features may not work properly without these variables")

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Check if at least one API key is available
if not OPENAI_API_KEY and not GOOGLE_API_KEY:
    logger.warning("Neither OPENAI_API_KEY nor GOOGLE_API_KEY found in environment variables. Some features may not work properly.")

# AI Provider Configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "google").lower()  # "openai" or "google"

# Hybrid Mode Configuration
HYBRID_MODE = os.getenv("HYBRID_MODE", "false").lower() == "true"
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "false").lower() == "true" or HYBRID_MODE

if AI_PROVIDER not in ["openai", "google"]:
    logger.warning(f"Invalid AI_PROVIDER: {AI_PROVIDER}. Defaulting to 'google'")
    AI_PROVIDER = "google"

# Log hybrid mode configuration
if HYBRID_MODE:
    logger.info("Hybrid mode enabled: OpenAI embeddings + Google chat")





    
elif USE_OPENAI_EMBEDDINGS and AI_PROVIDER == "google":
    logger.info("Custom hybrid mode: OpenAI embeddings + Google chat")

# Directory Configuration
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
VECTOR_STORES_DIR = os.path.abspath(os.path.join(BASE_DIR, "vectorstores"))
VIDEOS_DIR = os.path.abspath(os.path.join(BASE_DIR, "videos"))
LOGS_DIR = os.path.abspath(os.path.join(BASE_DIR, "logs"))

# Create required directories with proper permissions
# Note: In production (Railway), these operations are handled by the startup event
if not IS_PRODUCTION:
    for directory in [DATA_DIR, VECTOR_STORES_DIR, VIDEOS_DIR, LOGS_DIR]:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create directory {directory}: {e}")

# File Configuration
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB default

# API Settings
API_TITLE = "AI Tutor with File Upload"
API_VERSION = "1.0.0"
API_DESCRIPTION = "An AI-powered tutoring system with document and video management"

# CORS Configuration
CORS_ORIGINS = [
    "http://localhost:3001",
    "http://localhost:3001",
    "http://127.0.0.1:8001"
]

# Function to clean and validate CORS origins
def clean_cors_origins(origins):
    """Clean and validate CORS origins, removing semicolons and invalid characters"""
    cleaned_origins = []
    for origin in origins:
        if isinstance(origin, str):
            # Remove semicolons, commas, and other invalid characters more aggressively
            cleaned = origin.strip()
            # Remove all semicolons and commas from anywhere in the string
            cleaned = cleaned.replace(';', '').replace(',', '').strip()
            
            if cleaned and (cleaned.startswith('http://') or cleaned.startswith('https://')):
                cleaned_origins.append(cleaned)
                if cleaned != origin:
                    logger.info(f"Cleaned CORS origin: '{origin}' -> '{cleaned}'")
            else:
                logger.warning(f"Invalid CORS origin format: '{origin}' -> cleaned: '{cleaned}'")
        elif isinstance(origin, (list, tuple)):
            # Handle nested lists
            cleaned_origins.extend(clean_cors_origins(origin))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_origins = []
    for origin in cleaned_origins:
        if origin not in seen:
            seen.add(origin)
            unique_origins.append(origin)
    
    logger.info(f"Final cleaned CORS origins: {unique_origins}")
    return unique_origins

# Clean the CORS origins
ALLOWED_ORIGINS = clean_cors_origins(CORS_ORIGINS)

# Check for environment variable override for CORS origins
ENV_CORS_ORIGINS = os.getenv("CORS_ORIGINS")
if ENV_CORS_ORIGINS:
    try:
        # Parse environment variable (comma or semicolon separated)
        # Handle both comma and semicolon separators, and clean up any extra whitespace
        env_origins_raw = ENV_CORS_ORIGINS.replace(';', ',').replace(' ', '')
        env_origins = [origin.strip() for origin in env_origins_raw.split(',') if origin.strip()]
        env_origins = clean_cors_origins(env_origins)
        if env_origins:
            ALLOWED_ORIGINS = env_origins
            logger.info(f"CORS origins overridden from environment: {ALLOWED_ORIGINS}")
        else:
            logger.warning("Environment CORS_ORIGINS parsed but no valid origins found, using defaults")
    except Exception as e:
        logger.warning(f"Failed to parse CORS_ORIGINS environment variable: {e}")
        logger.info(f"Using default CORS origins: {ALLOWED_ORIGINS}")

# Add development-specific origins if not in production
if not IS_PRODUCTION:
    # Add any additional development origins here if needed
    pass

# Allow all origins for testing (can be overridden with CORS_ALLOW_ALL env var)
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

# Set CORS_ORIGINS first
if CORS_ALLOW_ALL:
    logger.warning("CORS_ALLOW_ALL is enabled - allowing all origins (NOT RECOMMENDED FOR PRODUCTION)")
    CORS_ORIGINS = ["*"]
    logger.info("CORS_ALLOW_ALL enabled - this will allow all origins")
else:
    CORS_ORIGINS = ALLOWED_ORIGINS
    logger.info(f"CORS_ALLOW_ALL disabled - using specific origins: {CORS_ORIGINS}")

# Validate CORS origins at startup
def validate_cors_origins():
    """Validate CORS origins and log any issues"""
    logger.info(f"Validating CORS origins: {CORS_ORIGINS}")
    for i, origin in enumerate(CORS_ORIGINS):
        if ';' in origin or ',' in origin:
            logger.error(f"CORS origin {i+1} contains invalid characters: '{origin}'")
        elif not (origin.startswith('http://') or origin.startswith('https://')):
            logger.error(f"CORS origin {i+1} has invalid protocol: '{origin}'")
        else:
            logger.info(f"CORS origin {i+1} is valid: '{origin}'")

# Call validation at startup
validate_cors_origins()

CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_HEADERS = ["*"]
CORS_MAX_AGE = int(os.getenv("CORS_MAX_AGE", "600"))

# Security Settings
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "300"))
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))

# Vector Store Settings
if USE_OPENAI_EMBEDDINGS:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION = 1536
else:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-gecko-002" if AI_PROVIDER == "google" else "text-embedding-3-small")
    EMBEDDING_DIMENSION = 768 if AI_PROVIDER == "google" else 1536

OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-3.5-turbo")
CHAT_MODEL = os.getenv(
    "CHAT_MODEL",
    "models/gemini-2.5-flash" if AI_PROVIDER == "google" else OPENAI_FALLBACK_MODEL
)
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "1000"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "200"))

# PDF Extraction Settings
PDF_EXTRACTION_CONFIG = {
    "primary_extractor": os.getenv("PDF_PRIMARY_EXTRACTOR", "pdfplumber"),  # "pdfplumber" or "pypdf2"
    "fallback_threshold": int(os.getenv("PDF_FALLBACK_THRESHOLD", "50")),  # chars per page
    "enable_table_extraction": os.getenv("PDF_ENABLE_TABLES", "true").lower() == "true",
    "enable_ocr_fallback": os.getenv("PDF_ENABLE_OCR", "false").lower() == "true",
    "log_extraction_details": os.getenv("PDF_LOG_DETAILS", "true").lower() == "true",
    "max_file_size_mb": int(os.getenv("PDF_MAX_SIZE_MB", "50")),  # MB
    "extraction_timeout": int(os.getenv("PDF_EXTRACTION_TIMEOUT", "300"))  # seconds
}

# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Validate AWS_REGION is not empty
if not AWS_REGION or AWS_REGION.strip() == "":
    logger.error("AWS_REGION is empty or not set. Please set AWS_REGION environment variable.")
    if IS_PRODUCTION:
        raise ValueError("AWS_REGION must be set in production environment")
    else:
        logger.warning("Using default AWS_REGION: ap-south-1")
        AWS_REGION = "ap-south-1"

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Construct S3_BASE_URL with validation
if S3_BUCKET_NAME and AWS_REGION:
    S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"
    logger.info(f"S3 Base URL configured: {S3_BASE_URL}")
else:
    S3_BASE_URL = None
    if IS_PRODUCTION:
        logger.warning("S3_BASE_URL not configured - S3 functionality will be limited")
    else:
        logger.info("S3_BASE_URL not configured - using local storage")

# Validate S3 settings
if IS_PRODUCTION and not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME, AWS_REGION]):
    missing_s3_vars = []
    if not AWS_ACCESS_KEY_ID:
        missing_s3_vars.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY:
        missing_s3_vars.append("AWS_SECRET_ACCESS_KEY")
    if not S3_BUCKET_NAME:
        missing_s3_vars.append("S3_BUCKET_NAME")
    if not AWS_REGION:
        missing_s3_vars.append("AWS_REGION")
    
    raise ValueError(f"S3 configuration is required in production. Missing: {', '.join(missing_s3_vars)}")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(LOGS_DIR, "app.log")

# Configure file handler with rotation
if IS_PRODUCTION:
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
else:
    file_handler = logging.FileHandler(LOG_FILE)

file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(file_handler)

# Print startup configuration
logger.info(f"Starting application in {ENV} mode")
logger.info(f"API Version: {API_VERSION}")
logger.info(f"Data Directory: {DATA_DIR}")
logger.info(f"Vector Stores Directory: {VECTOR_STORES_DIR}")
logger.info(f"Videos Directory: {VIDEOS_DIR}")
logger.info(f"Logs Directory: {LOGS_DIR}")
logger.info(f"CORS Origins: {CORS_ORIGINS}")
logger.info(f"Rate Limit Window: {RATE_LIMIT_WINDOW}s")
logger.info(f"Max Login Attempts: {MAX_LOGIN_ATTEMPTS}") 