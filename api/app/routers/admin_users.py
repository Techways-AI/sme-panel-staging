from datetime import date
from typing import List
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..core.dual_auth import get_dual_auth_user
from ..models.admin_user import (
    AdminUser,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
)
from ..models.user import user_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin-users", tags=["admin-users"])


@router.get("", response_model=List[AdminUserResponse])
async def list_admin_users(
    db: Session = Depends(get_db),
    auth_result: dict = Depends(get_dual_auth_user),
):
    """Return all admin users where panel='sme'.

    Authentication is required (JWT or API key via dual_auth).
    """
    users = db.query(AdminUser).filter(AdminUser.panel == "sme").order_by(AdminUser.id).all()
    return users


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    auth_result: dict = Depends(get_dual_auth_user),
):
    """Create a new admin user row in admin_users.

    - Maps directly from the Access Management UI fields.
    - joined_date defaults to today.
    """
    # Normalize defaults on the server side as well
    status_value = payload.status or "active"
    panel_value = payload.panel or "sme"

    user = AdminUser(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        status=status_value,
        joined_date=date.today(),
        panel=panel_value,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Also create login credentials in users.json so the user can log in immediately
    try:
        login_role = "admin" if "admin" in payload.role.lower() else "sme"
        user_manager.create_user(
            username=payload.email,
            email=payload.email,
            password=payload.password,
            role=login_role,
        )
        logger.info(f"Created login credentials for user: {payload.email}")
    except ValueError as e:
        # User already exists in users.json, that's okay
        logger.warning(f"Login user already exists for {payload.email}: {e}")
    except Exception as e:
        logger.error(f"Failed to create login credentials for {payload.email}: {e}")

    return user


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    auth_result: dict = Depends(get_dual_auth_user),
):
    """Update an existing admin user.

    Any provided field will overwrite the existing value.
    """
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.password is not None and payload.password != "":
        user.password = payload.password
    if payload.role is not None:
        user.role = payload.role
    if payload.status is not None:
        user.status = payload.status
    if payload.panel is not None:
        user.panel = payload.panel

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_admin_user(
    user_id: int,
    db: Session = Depends(get_db),
    auth_result: dict = Depends(get_dual_auth_user),
):
    """Delete an admin user from the table."""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
