"""
Authentication API routes.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from database import get_db
from models.user import UserCreate, UserLogin, UserResponse, TokenResponse
from services.auth_service import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Register a new user."""
    # Check if username already exists
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (user.username,))
    if await cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    password_hash = hash_password(user.password)
    cursor = await db.execute(
        """INSERT INTO users (username, full_name, role, password_hash)
           VALUES (?, ?, ?, ?)""",
        (user.username, user.full_name, user.role, password_hash),
    )
    await db.commit()

    user_id = cursor.lastrowid
    access_token = create_access_token(data={"sub": user.username})

    logger.info(f"User registered: {user.username} ({user.role})")

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user_id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(user_login: UserLogin, db: aiosqlite.Connection = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = await authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(data={"sub": user["username"]})
    logger.info(f"User logged in: {user['username']}")

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            full_name=user["full_name"],
            role=user["role"],
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        created_at=current_user.get("created_at"),
    )
