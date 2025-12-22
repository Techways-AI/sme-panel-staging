import json
import os
import types
from datetime import datetime
from typing import Optional, List, Dict

import bcrypt
from pydantic import BaseModel
from passlib.context import CryptContext
import logging

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = types.SimpleNamespace(__version__=getattr(bcrypt, "__version__", ""))

if hasattr(bcrypt, "_bcrypt") and not hasattr(bcrypt._bcrypt, "__about__"):
    bcrypt._bcrypt.__about__ = bcrypt.__about__

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False
)

MAX_PASSWORD_BYTES = 72


def _normalize_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        logger.warning("Password exceeds bcrypt 72-byte limit; truncating")
        return password_bytes[:MAX_PASSWORD_BYTES].decode('utf-8', 'ignore')
    return password

class User:
    def __init__(self, username: str, email: str, password_hash: str, role: str = "user", is_active: bool = True):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active
        self.created_at = datetime.utcnow()
        self.last_login = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class FileBasedUserManager:
    def __init__(self, users_file: str = "users.json"):
        self.users_file = users_file
        self.users: Dict[str, User] = {}
        self.load_users()
    
    def load_users(self):
        """Load users from JSON file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    for user_data in data.values():
                        user = User(
                            username=user_data['username'],
                            email=user_data['email'],
                            password_hash=user_data['password_hash'],
                            role=user_data.get('role', 'user'),
                            is_active=user_data.get('is_active', True)
                        )
                        user.created_at = datetime.fromisoformat(user_data['created_at'])
                        if user_data.get('last_login'):
                            user.last_login = datetime.fromisoformat(user_data['last_login'])
                        self.users[user.username] = user
                logger.info(f"Loaded {len(self.users)} users from {self.users_file}")
            else:
                logger.warning(f"Users file {self.users_file} not found")
        except Exception as e:
            logger.error(f"Error loading users: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.users = {}
    
    def save_users(self):
        """Save users to JSON file"""
        try:
            data = {}
            for username, user in self.users.items():
                data[username] = {
                    'username': user.username,
                    'email': user.email,
                    'password_hash': user.password_hash,
                    'role': user.role,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.users_file) if os.path.dirname(self.users_file) else '.', exist_ok=True)
            
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.users)} users to {self.users_file}")
        except Exception as e:
            logger.error(f"Error saving users: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Users file path: {self.users_file}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def create_user(self, username: str, email: str, password: str, role: str = "user") -> UserResponse:
        """Create a new user"""
        if username in self.users:
            raise ValueError("Username already exists")
        
        normalized_password = _normalize_password(password)
        password_hash = pwd_context.hash(normalized_password)
        
        # Create user
        user = User(username=username, email=email, password_hash=password_hash, role=role)
        self.users[username] = user
        
        # Save to file
        self.save_users()
        
        logger.info(f"Created new user: {username}")
        return UserResponse(
            id=username,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login
        )
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.users.get(username)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def get_all_users(self) -> List[UserResponse]:
        """Get all users"""
        return [
            UserResponse(
                id=user.username,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                role=user.role,
                created_at=user.created_at,
                last_login=user.last_login
            )
            for user in self.users.values()
        ]
    
    def update_user(self, username: str, user_data: UserUpdate) -> UserResponse:
        """Update user information"""
        user = self.get_user_by_username(username)
        if not user:
            raise ValueError("User not found")
        
        # Update fields
        if user_data.username is not None:
            user.username = user_data.username
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        if user_data.role is not None:
            user.role = user_data.role
        
        # Save to file
        self.save_users()
        
        logger.info(f"Updated user: {username}")
        return UserResponse(
            id=user.username,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login
        )
    
    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        if username not in self.users:
            raise ValueError("User not found")
        
        del self.users[username]
        self.save_users()
        
        logger.info(f"Deleted user: {username}")
        return True
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash while respecting bcrypt's 72-byte limit"""
        try:
            password_bytes_len = len(plain_password.encode('utf-8'))
            logger.debug(f"Verifying password for user hash length {len(hashed_password)}; input bytes={password_bytes_len}")
            normalized_password = _normalize_password(plain_password)
            normalized_bytes_len = len(normalized_password.encode('utf-8'))
            if normalized_bytes_len != password_bytes_len:
                logger.debug(f"Password normalized from {password_bytes_len} to {normalized_bytes_len} bytes")
            return pwd_context.verify(normalized_password, hashed_password)
        except ValueError as exc:
            logger.error(f"Password verification failed: {exc}")
            try:
                normalized_bytes = normalized_password.encode('utf-8')
                hashed_bytes = hashed_password.encode('utf-8')
                if bcrypt.checkpw(normalized_bytes, hashed_bytes):
                    logger.info("Password verified via bcrypt fallback after truncation error")
                    return True
            except Exception as fallback_exc:
                logger.error(f"Fallback bcrypt verification failed: {fallback_exc}")
            return False
    
    def update_last_login(self, username: str):
        """Update user's last login time"""
        user = self.get_user_by_username(username)
        if user:
            user.last_login = datetime.utcnow()
            self.save_users()
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        user = self.get_user_by_username(username)
        if not user:
            return None

        normalized_password = _normalize_password(password)
        logger.info(
            f"Authenticating {username} with normalized password length {len(normalized_password.encode('utf-8'))}"
        )

        if not self.verify_password(password, user.password_hash):
            logger.error(f"Password verification failed for {username}")
            return None

        if not user.is_active:
            return None

        
        # Update last login
        self.update_last_login(username)
        
        return user

# Global user manager instance
user_manager = FileBasedUserManager() 