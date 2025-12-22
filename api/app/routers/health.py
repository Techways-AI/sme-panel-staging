from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import platform
import psutil
from datetime import datetime
import sys

from ..utils.file_utils import load_json
from ..config.settings import (
    DATA_DIR, VECTOR_STORES_DIR, VIDEOS_DIR,
    OPENAI_API_KEY, CHAT_MODEL, EMBEDDING_MODEL, LOGS_DIR
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("")
async def health_check():
    """Check system health"""
    try:
        # Get system info
        system_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }
        
        # Get memory info
        memory = psutil.virtual_memory()
        memory_info = {
            "total": f"{memory.total / (1024**3):.2f} GB",
            "available": f"{memory.available / (1024**3):.2f} GB",
            "used": f"{memory.used / (1024**3):.2f} GB",
            "percent": f"{memory.percent}%"
        }
        
        # Get disk info
        disk = psutil.disk_usage(DATA_DIR)
        disk_info = {
            "total": f"{disk.total / (1024**3):.2f} GB",
            "used": f"{disk.used / (1024**3):.2f} GB",
            "free": f"{disk.free / (1024**3):.2f} GB",
            "percent": f"{disk.percent}%"
        }
        
        # Check directories
        directories = {
            "data_dir": {
                "path": DATA_DIR,
                "exists": os.path.exists(DATA_DIR),
                "writable": os.access(DATA_DIR, os.W_OK)
            },
            "vector_stores_dir": {
                "path": VECTOR_STORES_DIR,
                "exists": os.path.exists(VECTOR_STORES_DIR),
                "writable": os.access(VECTOR_STORES_DIR, os.W_OK)
            },
            "videos_dir": {
                "path": VIDEOS_DIR,
                "exists": os.path.exists(VIDEOS_DIR),
                "writable": os.access(VIDEOS_DIR, os.W_OK)
            }
        }
        
        # Check data files
        data_files = {
            "documents": {
                "path": os.path.join(DATA_DIR, "documents.json"),
                "exists": os.path.exists(os.path.join(DATA_DIR, "documents.json")),
                "size": f"{os.path.getsize(os.path.join(DATA_DIR, 'documents.json')) / 1024:.2f} KB" if os.path.exists(os.path.join(DATA_DIR, "documents.json")) else "N/A"
            },
            "videos": {
                "path": os.path.join(DATA_DIR, "videos.json"),
                "exists": os.path.exists(os.path.join(DATA_DIR, "videos.json")),
                "size": f"{os.path.getsize(os.path.join(DATA_DIR, 'videos.json')) / 1024:.2f} KB" if os.path.exists(os.path.join(DATA_DIR, "videos.json")) else "N/A"
            }
        }
        
        # Get document and video counts
        documents = load_json(os.path.join(DATA_DIR, "documents.json")) or []
        videos = load_json(os.path.join(DATA_DIR, "videos.json")) or []
        
        content_stats = {
            "documents": {
                "total": len(documents),
                "processed": len([d for d in documents if d.get("processed", False)]),
                "processing": len([d for d in documents if d.get("processing", False)])
            },
            "videos": {
                "total": len(videos)
            }
        }
        
        # Check OpenAI API key
        openai_status = {
            "configured": bool(OPENAI_API_KEY and OPENAI_API_KEY != "dummy_key_for_testing"),
            "models": {
                "chat": CHAT_MODEL,
                "embedding": EMBEDDING_MODEL
            }
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system": system_info,
            "memory": memory_info,
            "disk": disk_info,
            "directories": directories,
            "data_files": data_files,
            "content_stats": content_stats,
            "openai": openai_status
        }
        
    except Exception as e:
        print(f"Health check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/test")
async def test_endpoint():
    """Simple health check for load balancers"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/dependencies")
async def check_dependencies():
    """Check if all required dependencies are available"""
    dependencies = {
        "python_packages": {},
        "system_dependencies": {},
        "optional_dependencies": {}
    }
    
    # Check Python packages
    try:
        import pdfplumber
        dependencies["python_packages"]["pdfplumber"] = {"available": True, "version": pdfplumber.__version__}
    except ImportError:
        dependencies["python_packages"]["pdfplumber"] = {"available": False, "error": "Not installed"}
    
    try:
        import fitz  # PyMuPDF
        dependencies["python_packages"]["PyMuPDF"] = {"available": True, "version": fitz.version}
    except ImportError:
        dependencies["python_packages"]["PyMuPDF"] = {"available": False, "error": "Not installed"}
    
    try:
        from PyPDF2 import PdfReader
        dependencies["python_packages"]["PyPDF2"] = {"available": True, "version": "3.0.1"}
    except ImportError:
        dependencies["python_packages"]["PyPDF2"] = {"available": False, "error": "Not installed"}
    
    try:
        import tabula.io as tabula
        dependencies["python_packages"]["tabula-py"] = {"available": True, "version": "2.9.0"}
    except ImportError:
        dependencies["python_packages"]["tabula-py"] = {"available": False, "error": "Not installed"}
    
    try:
        import camelot
        dependencies["python_packages"]["camelot-py"] = {"available": True, "version": camelot.__version__}
    except ImportError:
        dependencies["python_packages"]["camelot-py"] = {"available": False, "error": "Not installed"}
    
    try:
        import pytesseract
        dependencies["python_packages"]["pytesseract"] = {"available": True, "version": pytesseract.get_tesseract_version()}
    except ImportError:
        dependencies["python_packages"]["pytesseract"] = {"available": False, "error": "Not installed"}
    
    try:
        import cv2
        dependencies["python_packages"]["opencv-python"] = {"available": True, "version": cv2.__version__}
    except ImportError:
        dependencies["python_packages"]["opencv-python"] = {"available": False, "error": "Not installed"}
    
    try:
        import nltk
        dependencies["python_packages"]["nltk"] = {"available": True, "version": nltk.__version__}
    except ImportError:
        dependencies["python_packages"]["nltk"] = {"available": False, "error": "Not installed"}
    
    # Check system dependencies
    try:
        import subprocess
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            dependencies["system_dependencies"]["java"] = {"available": True, "version": result.stderr.split('\n')[0]}
        else:
            dependencies["system_dependencies"]["java"] = {"available": False, "error": "Not found or not working"}
    except Exception as e:
        dependencies["system_dependencies"]["java"] = {"available": False, "error": str(e)}
    
    try:
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            dependencies["system_dependencies"]["tesseract"] = {"available": True, "version": result.stdout.split('\n')[0]}
        else:
            dependencies["system_dependencies"]["tesseract"] = {"available": False, "error": "Not found or not working"}
    except Exception as e:
        dependencies["system_dependencies"]["tesseract"] = {"available": False, "error": str(e)}
    
    # Check optional dependencies
    try:
        import faiss
        dependencies["optional_dependencies"]["faiss"] = {"available": True, "version": faiss.__version__}
    except ImportError:
        dependencies["optional_dependencies"]["faiss"] = {"available": False, "error": "Not installed"}
    
    try:
        import boto3
        dependencies["optional_dependencies"]["boto3"] = {"available": True, "version": boto3.__version__}
    except ImportError:
        dependencies["optional_dependencies"]["boto3"] = {"available": False, "error": "Not installed"}
    
    # Calculate overall status
    critical_deps = ["pdfplumber", "PyMuPDF", "PyPDF2"]
    optional_deps = ["tabula-py", "camelot-py", "pytesseract", "opencv-python", "nltk"]
    system_deps = ["java", "tesseract"]
    
    critical_available = all(dependencies["python_packages"].get(dep, {}).get("available", False) for dep in critical_deps)
    system_available = all(dependencies["system_dependencies"].get(dep, {}).get("available", False) for dep in system_deps)
    
    overall_status = "healthy" if critical_available else "degraded"
    
    return {
        "status": overall_status,
        "critical_dependencies_available": critical_available,
        "system_dependencies_available": system_available,
        "dependencies": dependencies,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/test-file-operations")
async def test_file_operations():
    """Test file operations"""
    try:
        test_file = os.path.join(DATA_DIR, "test.txt")
        test_content = f"Test file created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Test write
        with open(test_file, "w") as f:
            f.write(test_content)
        
        # Test read
        with open(test_file, "r") as f:
            content = f.read()
        
        # Test delete
        os.remove(test_file)
        
        return {
            "status": "success",
            "message": "File operations test passed",
            "test_content": content
        }
        
    except Exception as e:
        print(f"File operations test error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"File operations test failed: {str(e)}"
        )

@router.get("/test-json-operations")
async def test_json_operations():
    """Test JSON operations"""
    try:
        test_file = os.path.join(DATA_DIR, "test.json")
        test_data = {
            "test": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "numbers": [1, 2, 3],
            "nested": {
                "key": "value"
            }
        }
        
        # Test write
        with open(test_file, "w") as f:
            json.dump(test_data, f, indent=2)
        
        # Test read
        with open(test_file, "r") as f:
            data = json.load(f)
        
        # Test delete
        os.remove(test_file)
        
        return {
            "status": "success",
            "message": "JSON operations test passed",
            "test_data": data
        }
        
    except Exception as e:
        print(f"JSON operations test error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"JSON operations test failed: {str(e)}"
        ) 

@router.get("/deployment-status")
async def get_deployment_status():
    """Get comprehensive deployment status for debugging performance issues"""
    try:
        status = {
            "environment": os.getenv("ENV", "development"),
            "is_production": os.getenv("ENV") == "production",
            "working_directory": os.getcwd(),
            "python_executable": sys.executable,
            "system_resources": {},
            "environment_variables": {},
            "file_system": {},
            "s3_connection": {},
            "openai_connection": {},
            "processing_status": {}
        }
        
        # Check system resources
        status["system_resources"] = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3), 2)
        }
        
        # Check environment variables
        env_vars = [
            "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME",
            "OPENAI_API_KEY", "JWT_SECRET_KEY", "AWS_REGION"
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                status["environment_variables"][var] = "SET"
            else:
                status["environment_variables"][var] = "NOT_SET"
        
        # Check file system
        directories = ["data", "vectorstores", "videos", "logs", "temp"]
        for dir_name in directories:
            dir_path = os.path.join(os.getcwd(), dir_name)
            if os.path.exists(dir_path):
                status["file_system"][dir_name] = {
                    "exists": True,
                    "writable": os.access(dir_path, os.W_OK),
                    "path": dir_path,
                    "size_mb": round(sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                     for dirpath, dirnames, filenames in os.walk(dir_path) 
                                     for filename in filenames) / (1024**2), 2)
                }
            else:
                status["file_system"][dir_name] = {
                    "exists": False,
                    "writable": False,
                    "path": dir_path,
                    "size_mb": 0
                }
        
        # Check S3 connection
        try:
            from ..utils.s3_utils import s3_client
            s3_client.list_buckets()
            status["s3_connection"]["status"] = "CONNECTED"
        except Exception as e:
            status["s3_connection"]["status"] = "ERROR"
            status["s3_connection"]["error"] = str(e)
        
        # Check OpenAI connection
        try:
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY")
            if openai.api_key:
                # Try a simple API call
                response = openai.models.list()
                status["openai_connection"]["status"] = "CONNECTED"
            else:
                status["openai_connection"]["status"] = "NO_API_KEY"
        except Exception as e:
            status["openai_connection"]["status"] = "ERROR"
            status["openai_connection"]["error"] = str(e)
        
        # Check processing status
        try:
            documents_file = os.path.join(DATA_DIR, "documents.json")
            if os.path.exists(documents_file):
                with open(documents_file, 'r') as f:
                    documents = json.load(f)
                
                processing_docs = [doc for doc in documents if doc.get("processing")]
                status["processing_status"] = {
                    "total_documents": len(documents),
                    "processing_count": len(processing_docs),
                    "processing_docs": [{"id": doc.get("id"), "fileName": doc.get("fileName")} 
                                      for doc in processing_docs]
                }
            else:
                status["processing_status"] = {"error": "documents.json not found"}
        except Exception as e:
            status["processing_status"] = {"error": str(e)}
        
        return status
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "ERROR"
        } 