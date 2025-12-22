from datetime import datetime, timedelta
import os
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from fastapi import HTTPException, status
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
#  Configuration
# ────────────────────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    logger.warning("JWT_SECRET_KEY not found in environment variables. Using a default key for development only.")
    SECRET_KEY = "supersecretkey"  # Only for development

ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# ────────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────────
def _credentials_exc(detail: str = "Could not validate credentials") -> HTTPException:
    logger.warning(f"Authentication failed: {detail}")
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

# ────────────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────────────
def create_access_token(
    subject: str,
    extra_claims: Optional[Dict] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a new JWT access token.
    
    Args:
        subject: The username/user-id
        extra_claims: Additional payload fields
        expires_delta: Optional custom expiration time
    
    Returns:
        str: The encoded JWT token
        
    Raises:
        HTTPException: If token creation fails
    """
    if not subject:
        raise ValueError("subject must be provided")

    try:
        data = {"sub": subject}
        if extra_claims:
            data.update(extra_claims)

        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        data.update({"exp": expire, "iat": datetime.utcnow()})

        return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create access token",
        )

def verify_token(token: str) -> Dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Dict: The decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Validate required claims
        if not all(key in payload for key in ["sub", "exp", "iat"]):
            raise _credentials_exc("Token missing required claims")
            
        # Validate token hasn't expired
        if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
            raise _credentials_exc("Token has expired")
            
        return payload
        
    except ExpiredSignatureError:
        raise _credentials_exc("Token has expired")
    except JWTError as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise _credentials_exc("Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )

 