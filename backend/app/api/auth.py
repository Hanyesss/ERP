from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, UserResponse
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.login == body.login, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
