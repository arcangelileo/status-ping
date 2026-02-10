from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_current_user_api,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.models.status_page import StatusPage
from app.schemas import LoginResponse, SignupRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=LoginResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Check if slug already exists
    result = await db.execute(select(User).where(User.account_slug == body.account_slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This status page URL is already taken",
        )

    # Create user
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        account_slug=body.account_slug,
        plan="free",
    )
    db.add(user)
    await db.flush()

    # Create default status page
    status_page = StatusPage(
        user_id=user.id,
        title=f"{body.name}'s Service Status",
    )
    db.add(status_page)
    await db.commit()
    await db.refresh(user)

    # Create JWT token
    token = create_access_token(data={"sub": user.id})

    response = JSONResponse(
        status_code=201,
        content=LoginResponse(
            message="Account created successfully",
            user=UserResponse.model_validate(user),
        ).model_dump(mode="json"),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        secure=False,
    )
    return response


@router.post("/login", response_model=LoginResponse)
async def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(data={"sub": user.id})

    response = JSONResponse(
        content=LoginResponse(
            message="Logged in successfully",
            user=UserResponse.model_validate(user),
        ).model_dump(mode="json"),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        secure=False,
    )
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user_api)):
    return UserResponse.model_validate(user)
