from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
import time
import logging
from datetime import datetime
from fastapi.responses import JSONResponse

from ..auth.jwt_utils import create_access_token, verify_token
from ..models.user import UserLogin, UserLoginResponse, UserResponse, UserCreate, user_manager
from ..core.security import require_any_user
from ..config.database import SessionLocal
from ..models.admin_user import AdminUser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting with in-memory storage (for production, use Redis)
RATE_LIMIT_WINDOW = 300  # 5 minutes
MAX_LOGIN_ATTEMPTS = 5
login_attempts = {}

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Add explicit CORS handling for auth endpoints
@router.options("/login")
async def login_options():
    """Handle CORS preflight for login endpoint"""
    return {"message": "CORS preflight handled"}

@router.options("/register")
async def register_options():
    """Handle CORS preflight for register endpoint"""
    return {"message": "CORS preflight handled"}

@router.options("/verify")
async def verify_options():
    """Handle CORS preflight for verify endpoint"""
    return {"message": "CORS preflight handled"}

@router.get("/test-cors")
async def test_auth_cors():
    """Test endpoint to verify CORS is working for auth router"""
    return {
        "message": "Auth router CORS test successful",
        "timestamp": datetime.now().isoformat(),
        "status": "working"
    }

@router.get("/health")
async def auth_health():
    """Health check endpoint for auth router"""
    try:
        user_count = len(user_manager.users)
        return {
            "status": "healthy",
            "user_count": user_count,
            "timestamp": datetime.now().isoformat(),
            "message": "Auth router is working"
        }
    except Exception as e:
        logger.error(f"Auth health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def check_rate_limit(request: Request) -> None:
    """Check if the client has exceeded rate limits"""
    client_ip = request.client.host
    current_time = time.time()
    
    # Clean up old attempts
    if client_ip in login_attempts:
        login_attempts[client_ip] = {
            timestamp: count for timestamp, count in login_attempts[client_ip].items()
            if current_time - timestamp < RATE_LIMIT_WINDOW
        }
    
    # Count recent attempts
    recent_attempts = sum(login_attempts.get(client_ip, {}).values())
    
    if recent_attempts >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    # Record this attempt
    if client_ip not in login_attempts:
        login_attempts[client_ip] = {}
    login_attempts[client_ip][current_time] = login_attempts[client_ip].get(current_time, 0) + 1

@router.post("/login", response_model=UserLoginResponse)
async def login(request: Request, login_data: UserLogin):
    """Login endpoint - authenticates against admin_users table where panel='sme'"""
    try:
        # Log the received data for debugging
        logger.info(f"Login attempt received: username={login_data.username}")
        logger.info(f"Request origin: {request.headers.get('origin', 'unknown')}")
        
        # Check rate limit
        check_rate_limit(request)
        
        # Authenticate against admin_users table with panel='sme'
        db = SessionLocal()
        try:
            # First check if user exists at all
            any_user = db.query(AdminUser).filter(AdminUser.email == login_data.username).first()
            if any_user:
                logger.info(f"Found user: email={any_user.email}, panel={any_user.panel}, status={any_user.status}")
            else:
                logger.warning(f"No user found with email: {login_data.username}")
            
            admin_user = (
                db.query(AdminUser)
                .filter(AdminUser.email == login_data.username)
                .filter(AdminUser.panel == "sme")
                .filter(AdminUser.status == "active")
                .first()
            )
            
            if not admin_user:
                if any_user and any_user.panel != "sme":
                    logger.warning(f"User {login_data.username} exists but panel={any_user.panel}, not 'sme'")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="You are not authorized to access the SME panel",
                        headers={"WWW-Authenticate": "Bearer"}
                    )
                elif any_user and any_user.status != "active":
                    logger.warning(f"User {login_data.username} is not active, status={any_user.status}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Your account is not active. Please contact administrator.",
                        headers={"WWW-Authenticate": "Bearer"}
                    )
                else:
                    logger.warning(f"User not found: {login_data.username}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password",
                        headers={"WWW-Authenticate": "Bearer"}
                    )
            
            # Check password (plain text comparison as per database structure)
            logger.info(f"Checking password for {login_data.username}: DB password length={len(admin_user.password)}, input length={len(login_data.password)}")
            if admin_user.password != login_data.password:
                logger.warning(f"Password mismatch for user: {login_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Create token
            try:
                access_token = create_access_token(
                    subject=admin_user.email,
                    extra_claims={"user_id": admin_user.email, "role": admin_user.role, "name": admin_user.name}
                )
            except Exception as token_error:
                logger.error(f"Token creation failed: {str(token_error)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create access token"
                )
            
            # Clear rate limit on successful login
            if request.client.host in login_attempts:
                del login_attempts[request.client.host]
            
            # Prepare response data
            response_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "user": UserResponse(
                    id=str(admin_user.id),
                    username=admin_user.email,
                    email=admin_user.email,
                    is_active=admin_user.status == "active",
                    role=admin_user.role,
                    created_at=datetime.combine(admin_user.joined_date, datetime.min.time()),
                    last_login=None
                )
            }
            
            logger.info(f"Successful login for user: {admin_user.email} (panel=sme)")
            return response_data
            
        finally:
            db.close()
        
    except HTTPException as http_exc:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register a new user"""
    try:
        db = SessionLocal()
        try:
            allowed_user = (
                db.query(AdminUser)
                .filter(AdminUser.email.in_([user_data.email, user_data.username]))
                .filter(AdminUser.panel == "sme")
                .first()
            )
        finally:
            db.close()

        if not allowed_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to sign up for this panel",
            )

        new_user = user_manager.create_user(
            user_data.username,
            user_data.email,
            user_data.password,
            user_data.role
        )
        
        logger.info(f"New user registered: {user_data.username}")
        return new_user
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration"
        )

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get the current authenticated user"""
    try:
        payload = verify_token(token)
        username = payload["sub"]
        user_id = payload.get("user_id")
        
        user = user_manager.get_user_by_username(username)
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Return the full payload including user info
        return {
            "user_id": user.username,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "sub": user.username
        }
        
    except HTTPException as http_exc:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error authenticating user"
        )

@router.get("/verify")
async def verify_auth(current_user: dict = Depends(get_current_user)):
    """Verify authentication token"""
    try:
        return JSONResponse(
            content={
                "valid": True,
                "user": {
                    "user_id": current_user.get("user_id"),
                    "username": current_user.get("username"),
                    "role": current_user.get("role")
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.get("/users", response_model=list[UserResponse])
async def get_users(current_user: dict = Depends(get_current_user)):
    """Get all users (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return user_manager.get_all_users()

@router.post("/reset-rate-limit")
async def reset_rate_limit(request: Request):
    """Reset rate limit for testing purposes"""
    if request.client.host in login_attempts:
        del login_attempts[request.client.host]
    return {"message": "Rate limit reset successfully"}

@router.get("/debug-token")
async def debug_token(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check token contents and role"""
    return {
        "message": "Token debug info",
        "user": current_user,
        "has_role": "role" in current_user,
        "role": current_user.get("role"),
        "username": current_user.get("sub")
    }

@router.get("/debug-role-check")
async def debug_role_check(current_user: dict = Depends(require_any_user)):
    """Debug endpoint to test role checking"""
    return {
        "message": "Role check passed",
        "user": current_user,
        "role": current_user.get("role"),
        "username": current_user.get("sub")
    }

 