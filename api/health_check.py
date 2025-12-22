#!/usr/bin/env python3
"""
Deployment Health Check
Checks if the deployment environment is ready for document processing
"""

import os
import sys
import logging
import importlib
import psutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_environment():
    """Check deployment environment"""
    issues = []
    
    # Check required packages
    required_packages = [
        "fastapi", "uvicorn", "boto3", "openai", "pdfplumber", 
        "PyPDF2", "PyMuPDF", "python-docx", "nltk", "faiss"
    ]
    
    for package in required_packages:
        try:
            importlib.import_module(package.replace("-", "_"))
        except ImportError:
            issues.append(f"Missing package: {package}")
    
    # Check environment variables
    required_env_vars = [
        "OPENAI_API_KEY", "AWS_ACCESS_KEY_ID", 
        "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME"
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            issues.append(f"Missing environment variable: {var}")
    
    # Check memory
    memory = psutil.virtual_memory()
    if memory.percent > 95:
        issues.append(f"Critical memory usage: {memory.percent:.1f}%")
    elif memory.percent > 90:
        issues.append(f"High memory usage: {memory.percent:.1f}%")
    
    # Check disk space
    disk = psutil.disk_usage('/')
    if disk.percent > 95:
        issues.append(f"Critical disk usage: {disk.percent:.1f}%")
    
    return issues

def main():
    """Main function"""
    issues = check_environment()
    
    if issues:
        logger.error("Health check failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        sys.exit(1)
    else:
        logger.info("Health check passed")
        sys.exit(0)

if __name__ == "__main__":
    main()
