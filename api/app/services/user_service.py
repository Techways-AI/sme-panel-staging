from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from datetime import datetime
from typing import Optional, List
import logging

from ..models.user import User, UserCreate, UserUpdate, UserResponse
from ..config.database import get_db

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user"""
        try:
            # Hash the password
            hashed_password = pwd_context.hash(user_data.password)
            
            # Create user object
            db_user = User(
                username=user_data.username,
                email=user_data.email,
                password_hash=hashed_password,
                role=user_data.role
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            logger.info(f"Created new user: {user_data.username}")
            return UserResponse.from_orm(db_user)
            
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Username or email already exists")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_all_users(self) -> List[UserResponse]:
        """Get all users"""
        users = self.db.query(User).all()
        return [UserResponse.from_orm(user) for user in users]
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> UserResponse:
        """Update user information"""
        user = self.get_user_by_id(user_id)
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
        
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"Updated user: {user.username}")
        return UserResponse.from_orm(user)
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        self.db.delete(user)
        self.db.commit()
        
        logger.info(f"Deleted user: {user.username}")
        return True
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def update_last_login(self, user_id: int):
        """Update user's last login time"""
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        # Update last login
        self.update_last_login(user.id)
        
        return user