"""
Dual Authentication System

This module provides authentication that supports both JWT tokens (for user sessions)
and API keys (for internal server-to-server communication).
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Union, Dict
import logging

from .security import get_current_user
from .api_keys import validate_api_key_for_endpoint

logger = logging.getLogger(__name__)

# JWT Bearer scheme
_scheme = HTTPBearer(auto_error=False)

async def get_dual_auth_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_scheme)
) -> Dict:
    """
    Authenticate user using either JWT token or API key
    
    This function tries JWT authentication first, then falls back to API key
    if JWT is not provided or invalid.
    
    Returns:
        Dict: User information from either JWT or API key
        
    Raises:
        HTTPException: If neither authentication method is valid
    """
    endpoint = request.url.path
    
    # Try JWT authentication first
    if credentials:
        try:
            jwt_user = get_current_user(credentials)
            logger.info(f"JWT authentication successful for user: {jwt_user.get('sub')}")
            return {
                "auth_type": "jwt",
                "user_data": jwt_user,
                "permissions": ["full_access"]  # JWT users have full access
            }
        except HTTPException as jwt_error:
            logger.debug(f"JWT authentication failed: {jwt_error.detail}")
            # Continue to API key authentication
            pass
    
    # Try API key authentication
    api_key = request.headers.get("X-API-Key")
    if api_key:
        try:
            key_data = validate_api_key_for_endpoint(api_key, endpoint)
            logger.info(f"API key authentication successful for key: {key_data['name']}")
            return {
                "auth_type": "api_key",
                "user_data": {
                    "sub": f"api_key_{key_data['name']}",
                    "role": "api_key",
                    "permissions": key_data["allowed_endpoints"]
                },
                "key_data": key_data,
                "permissions": key_data["allowed_endpoints"]
            }
        except HTTPException as api_error:
            logger.debug(f"API key authentication failed: {api_error.detail}")
            # Continue to final error
    
    # If we get here, neither authentication method worked
    logger.warning(f"Authentication failed for endpoint: {endpoint}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide either a valid JWT token or API key.",
        headers={
            "WWW-Authenticate": "Bearer",
            "X-API-Key-Required": "true"
        }
    )

async def require_jwt_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_scheme)
) -> Dict:
    """
    Require JWT authentication specifically (no API key fallback)
    
    Use this when you specifically need user session authentication
    """
    return await get_current_user(credentials)

async def require_api_key_auth(
    request: Request
) -> Dict:
    """
    Require API key authentication specifically (no JWT fallback)
    
    Use this when you specifically need API key authentication
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required in X-API-Key header",
            headers={"X-API-Key-Required": "true"}
        )
    
    endpoint = request.url.path
    key_data = validate_api_key_for_endpoint(api_key, endpoint)
    
    return {
        "auth_type": "api_key",
        "user_data": {
            "sub": f"api_key_{key_data['name']}",
            "role": "api_key",
            "permissions": key_data["allowed_endpoints"]
        },
        "key_data": key_data,
        "permissions": key_data["allowed_endpoints"]
    }

def get_auth_type(auth_result: Dict) -> str:
    """Get the authentication type from the auth result"""
    return auth_result.get("auth_type", "unknown")

def has_permission(auth_result: Dict, required_permission: str) -> bool:
    """Check if the authenticated entity has a specific permission"""
    permissions = auth_result.get("permissions", [])
    return required_permission in permissions or "full_access" in permissions

