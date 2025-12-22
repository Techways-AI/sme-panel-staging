"""
Admin Router for System Administration

This router provides endpoints for managing API keys and other administrative functions.
Access is restricted to admin users only.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging

from ..core.security import require_admin
from ..core.api_keys import get_api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Pydantic models for API key management
class APIKeyCreate(BaseModel):
    name: str
    description: str
    allowed_endpoints: List[str]

class APIKeyResponse(BaseModel):
    name: str
    description: str
    allowed_endpoints: List[str]
    created_at: str
    last_used: Optional[str]
    usage_count: int
    is_active: bool

class APIKeyGenerateResponse(BaseModel):
    api_key: str
    name: str
    description: str
    allowed_endpoints: List[str]
    created_at: str
    message: str

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(current_user: Dict = Depends(require_admin)):
    """
    List all API keys (admin only)
    
    Returns metadata about all API keys without exposing the actual keys
    """
    try:
        api_key_manager = get_api_key_manager()
        keys = api_key_manager.list_keys()
        logger.info(f"Admin {current_user.get('sub')} listed {len(keys)} API keys")
        return keys
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )

@router.post("/api-keys/generate", response_model=APIKeyGenerateResponse)
async def generate_api_key(
    key_data: APIKeyCreate,
    current_user: Dict = Depends(require_admin)
):
    """
    Generate a new API key (admin only)
    
    Creates a new API key with the specified permissions.
    The actual key is only returned once upon creation.
    """
    try:
        api_key_manager = get_api_key_manager()
        
        # Validate endpoints
        valid_endpoints = [
            "/api/ai/ask",
            "/api/documents",
            "/api/health/test"
        ]
        
        invalid_endpoints = [ep for ep in key_data.allowed_endpoints if ep not in valid_endpoints]
        if invalid_endpoints:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid endpoints: {invalid_endpoints}. Valid endpoints: {valid_endpoints}"
            )
        
        # Generate the API key
        api_key = api_key_manager.generate_api_key(
            name=key_data.name,
            description=key_data.description,
            allowed_endpoints=key_data.allowed_endpoints
        )
        
        # Get the key metadata
        key_hash = api_key_manager.keys[list(api_key_manager.keys.keys())[-1]]
        
        logger.info(f"Admin {current_user.get('sub')} generated new API key: {key_data.name}")
        
        return APIKeyGenerateResponse(
            api_key=api_key,
            name=key_data.name,
            description=key_data.description,
            allowed_endpoints=key_data.allowed_endpoints,
            created_at=key_hash["created_at"],
            message="API key generated successfully. Store this key securely as it cannot be retrieved again."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        )

@router.post("/api-keys/{key_hash}/deactivate")
async def deactivate_api_key(
    key_hash: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Deactivate an API key (admin only)
    
    Deactivated keys cannot be used for authentication
    """
    try:
        api_key_manager = get_api_key_manager()
        success = api_key_manager.deactivate_key(key_hash)
        
        if success:
            logger.info(f"Admin {current_user.get('sub')} deactivated API key: {key_hash}")
            return {"message": "API key deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate API key"
        )

@router.delete("/api-keys/{key_hash}")
async def delete_api_key(
    key_hash: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Delete an API key permanently (admin only)
    
    This action cannot be undone
    """
    try:
        api_key_manager = get_api_key_manager()
        success = api_key_manager.delete_key(key_hash)
        
        if success:
            logger.info(f"Admin {current_user.get('sub')} deleted API key: {key_hash}")
            return {"message": "API key deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key"
        )

@router.get("/system-info")
async def get_system_info(current_user: Dict = Depends(require_admin)):
    """
    Get system information (admin only)
    """
    try:
        api_key_manager = get_api_key_manager()
        
        return {
            "total_api_keys": len(api_key_manager.keys),
            "active_api_keys": len([k for k in api_key_manager.keys.values() if k.get("is_active", True)]),
            "system_status": "healthy",
            "admin_user": current_user.get("sub")
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system information"
        )

