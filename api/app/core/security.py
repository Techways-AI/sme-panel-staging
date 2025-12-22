from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
import os
import datetime as dt
from typing import Optional, List

_scheme = HTTPBearer()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    # For development/testing, use a default key if not set
    SECRET_KEY = "dev-secret-key-change-in-production"
    print("Warning: JWT_SECRET_KEY not set, using development key")
ALGO = "HS256"

def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(_scheme)
):
    token = cred.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        if payload.get("sub") is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        # Optionally check for user type/role here
        # Example: allow both SME and student users
        # role = payload.get("role")
        # if role not in ("sme", "student"):
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not permitted")
        return payload  # Pass full payload downstream if you need role/scope
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

def require_roles(allowed_roles: List[str]):
    """Dependency to require specific roles"""
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        
        # Backward compatibility: if no role is present, assume "admin" for existing tokens
        if not user_role:
            # Check if this is the SME user (backward compatibility)
            username = current_user.get("sub")
            if username == "sme@durranis.ai":
                user_role = "admin"
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User role not found in token"
                )
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user_role}' not permitted. Allowed roles: {allowed_roles}"
            )
        return current_user
    return role_checker

# Convenience functions for common role requirements
require_admin = require_roles(["admin"])
require_student = require_roles(["student"])
require_any_user = require_roles(["admin", "student"]) 