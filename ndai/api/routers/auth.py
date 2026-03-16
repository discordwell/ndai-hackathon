"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import create_access_token
from ndai.api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from ndai.db.repositories import create_user, get_user_by_email
from ndai.db.session import get_db

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if request.role not in ("seller", "buyer"):
        raise HTTPException(status_code=400, detail="Role must be 'seller' or 'buyer'")

    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await create_user(
        db,
        email=request.email,
        password_hash=bcrypt.hash(request.password),
        role=request.role,
        display_name=request.display_name,
    )
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, request.email)
    if not user or not bcrypt.verify(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, role=user.role)
