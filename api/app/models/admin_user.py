from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Date, Integer, String

from ..config.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    joined_date = Column(Date, nullable=False, default=date.today)
    panel = Column(String, nullable=True)


class AdminUserBase(BaseModel):
    name: str
    email: str
    password: str
    role: str
    status: Optional[str] = "active"
    panel: Optional[str] = "sme"


class AdminUserCreate(AdminUserBase):
    pass


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    panel: Optional[str] = None


class AdminUserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str
    joined_date: date
    panel: Optional[str] = None

    class Config:
        from_attributes = True
