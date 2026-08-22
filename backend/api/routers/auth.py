# api/routers/auth.py
# FastAPI router for authentication endpoints (/api/v1/auth)

from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.core.deps import get_current_user, require_role
from api.core.redis_client import limiter
from api.schemas.auth import (
    InviteCreateRequest,
    InviteResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from api.services.auth_service import (
    create_invite,
    login_email,
    logout,
    refresh_tokens,
    signup_email,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/hour")
def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)):
    return signup_email(db, body)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    return login_email(db, body)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/hour")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    return refresh_tokens(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/hour")
def logout_user(
    request: Request,
    body: Optional[RefreshRequest] = None,
    authorization: str = Header(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = authorization.replace("Bearer ", "")
    refresh_tok = body.refresh_token if body else None
    logout(db, token, refresh_tok)
    return None


@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
def get_me(request: Request, current_user=Depends(get_current_user)):
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        phone=current_user["phone"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        merchant_id=current_user["merchant_id"],
    )


@router.post("/invite", response_model=InviteResponse)
@limiter.limit("10/hour")
def create_user_invite(
    request: Request,
    body: InviteCreateRequest,
    current_user=Depends(require_role("Merchant Owner")),
    db: Session = Depends(get_db),
):
    return create_invite(db, current_user, body)
