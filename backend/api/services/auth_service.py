# api/services/auth_service.py
# Core authentication logic (Signup, Login, OAuth, Phone OTP, Refresh, Logout, Invite, Audit Logging)

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.core.config import settings
from api.core.redis_client import blacklist_token
from api.core.security import (
    create_access_token,
    create_invite_token,
    create_refresh_token,
    decode_invite_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from api.schemas.auth import (
    InviteCreateRequest,
    InviteResponse,
    LoginRequest,
    SignupRequest,
    TokenResponse,
)


def log_auth_audit(
    db: Session, user_id: Optional[uuid.UUID], action: str, reasoning: str
):
    """Log authentication events to audit_log table."""
    try:
        dummy_txn_id = user_id or uuid.uuid4()
        query = text("""
            INSERT INTO audit_log (audit_id, txn_id, action, triggered_by, reasoning, created_at)
            VALUES (:audit_id, :txn_id, :action, :triggered_by, :reasoning, NOW())
        """)
        db.execute(
            query,
            {
                "audit_id": uuid.uuid4(),
                "txn_id": dummy_txn_id,
                "action": action,
                "triggered_by": "auth_service",
                "reasoning": reasoning,
            },
        )
        db.commit()
    except Exception:
        db.rollback()


def signup_email(db: Session, req: SignupRequest) -> TokenResponse:
    merchant_id = None
    role = "Merchant Owner"

    if req.invite_token:
        try:
            invite_payload = decode_invite_token(req.invite_token)
            merchant_id = uuid.UUID(invite_payload["merchant_id"])
            role = invite_payload.get("role", "Risk Analyst")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or expired invite token: {str(e)}",
            )

    # Check for existing email/phone
    if req.email:
        existing = db.execute(
            text("SELECT user_id FROM users WHERE email = :email"), {"email": req.email}
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered."
            )

    if req.phone:
        existing = db.execute(
            text("SELECT user_id FROM users WHERE phone = :phone"), {"phone": req.phone}
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered.",
            )

    # Create new merchant if not joining via invite
    if not merchant_id:
        merchant_id = uuid.uuid4()
        m_name = req.merchant_name or f"{req.full_name}'s Merchant Account"
        db.execute(
            text(
                "INSERT INTO merchants (merchant_id, name, status) VALUES (:m_id, :name, 'active')"
            ),
            {"m_id": merchant_id, "name": m_name},
        )

    # Create user
    user_id = uuid.uuid4()
    pwd_hash = hash_password(req.password)
    db.execute(
        text("""
            INSERT INTO users (user_id, merchant_id, email, phone, password_hash, full_name, role)
            VALUES (:user_id, :merchant_id, :email, :phone, :password_hash, :full_name, :role)
        """),
        {
            "user_id": user_id,
            "merchant_id": merchant_id,
            "email": req.email,
            "phone": req.phone,
            "password_hash": pwd_hash,
            "full_name": req.full_name,
            "role": role,
        },
    )

    # Create auth_provider row
    db.execute(
        text("""
            INSERT INTO auth_providers (provider_id, user_id, provider_name, provider_user_id)
            VALUES (:p_id, :user_id, 'email', :provider_user_id)
        """),
        {
            "p_id": uuid.uuid4(),
            "user_id": user_id,
            "provider_user_id": req.email or req.phone,
        },
    )

    # Generate tokens
    access_token = create_access_token(
        {"sub": str(user_id), "merchant_id": str(merchant_id), "role": role}
    )
    refresh_token = create_refresh_token({"sub": str(user_id)})

    # Save session
    rf_hash = hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    db.execute(
        text("""
            INSERT INTO sessions (session_id, user_id, refresh_token_hash, expires_at)
            VALUES (:session_id, :user_id, :rf_hash, :expires_at)
        """),
        {
            "session_id": uuid.uuid4(),
            "user_id": user_id,
            "rf_hash": rf_hash,
            "expires_at": expires_at,
        },
    )

    db.commit()

    log_auth_audit(
        db, user_id, "auth.signup", f"New user signed up successfully with role {role}."
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def login_email(db: Session, req: LoginRequest) -> TokenResponse:
    if not req.email and not req.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email or phone required."
        )

    query = text("""
        SELECT user_id, merchant_id, password_hash, role, failed_login_attempts, locked_until 
        FROM users WHERE email = :identifier OR phone = :identifier
    """)
    identifier = req.email or req.phone
    user = db.execute(query, {"identifier": identifier}).mappings().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Check account lockout status
    now = datetime.now(timezone.utc)
    if user["locked_until"]:
        locked_until = user["locked_until"]
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until:
            minutes_left = int((locked_until - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to multiple failed login attempts. Try again in {minutes_left} minutes.",
            )

    # Verify password
    if not verify_password(req.password, user["password_hash"]):
        new_attempts = user["failed_login_attempts"] + 1
        locked_until_val = None
        if new_attempts >= 5:
            locked_until_val = now + timedelta(minutes=15)
            log_auth_audit(
                db,
                user["user_id"],
                "auth.lockout",
                "Account locked after 5 failed attempts.",
            )

        db.execute(
            text("""
                UPDATE users SET failed_login_attempts = :attempts, locked_until = :locked_until
                WHERE user_id = :user_id
            """),
            {
                "attempts": new_attempts,
                "locked_until": locked_until_val,
                "user_id": user["user_id"],
            },
        )
        db.commit()
        log_auth_audit(
            db,
            user["user_id"],
            "auth.login_failure",
            f"Failed password attempt ({new_attempts}/5).",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Password correct -> reset lockout counters
    db.execute(
        text(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE user_id = :user_id"
        ),
        {"user_id": user["user_id"]},
    )

    # Issue tokens
    access_token = create_access_token(
        {
            "sub": str(user["user_id"]),
            "merchant_id": str(user["merchant_id"]) if user["merchant_id"] else None,
            "role": user["role"],
        }
    )
    refresh_token = create_refresh_token({"sub": str(user["user_id"])})

    # Save session
    rf_hash = hash_token(refresh_token)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.execute(
        text("""
            INSERT INTO sessions (session_id, user_id, refresh_token_hash, expires_at)
            VALUES (:session_id, :user_id, :rf_hash, :expires_at)
        """),
        {
            "session_id": uuid.uuid4(),
            "user_id": user["user_id"],
            "rf_hash": rf_hash,
            "expires_at": expires_at,
        },
    )

    db.commit()
    log_auth_audit(
        db, user["user_id"], "auth.login_success", "User logged in successfully."
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token type.",
            )
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    rf_hash = hash_token(refresh_token)

    # Look up session in DB
    session = (
        db.execute(
            text(
                "SELECT session_id, user_id, expires_at FROM sessions WHERE refresh_token_hash = :rf_hash"
            ),
            {"rf_hash": rf_hash},
        )
        .mappings()
        .first()
    )

    now = datetime.now(timezone.utc)

    if (
        not session
        or (
            session["expires_at"].replace(tzinfo=timezone.utc)
            if session["expires_at"].tzinfo is None
            else session["expires_at"]
        )
        < now
    ):
        # THEFT DETECTION: If token is valid JWT but session not in DB, revoke ALL sessions for this user!
        db.execute(
            text("DELETE FROM sessions WHERE user_id = :user_id"), {"user_id": user_id}
        )
        db.commit()
        log_auth_audit(
            db,
            user_id,
            "auth.token_theft_detected",
            "Reuse of invalidated refresh token. Revoked all sessions.",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security breach detected: invalid refresh token reused. All sessions revoked.",
        )

    # Rotate refresh token: Delete old session
    db.execute(
        text("DELETE FROM sessions WHERE session_id = :session_id"),
        {"session_id": session["session_id"]},
    )

    # Fetch user info
    user = (
        db.execute(
            text("SELECT merchant_id, role FROM users WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )

    # Issue new pair
    new_access = create_access_token(
        {
            "sub": str(user_id),
            "merchant_id": str(user["merchant_id"]) if user["merchant_id"] else None,
            "role": user["role"],
        }
    )
    new_refresh = create_refresh_token({"sub": str(user_id)})

    # Insert new session
    new_rf_hash = hash_token(new_refresh)
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.execute(
        text("""
            INSERT INTO sessions (session_id, user_id, refresh_token_hash, expires_at)
            VALUES (:session_id, :user_id, :rf_hash, :expires_at)
        """),
        {
            "session_id": uuid.uuid4(),
            "user_id": user_id,
            "rf_hash": new_rf_hash,
            "expires_at": new_expires_at,
        },
    )

    db.commit()
    log_auth_audit(
        db, user_id, "auth.token_refresh", "Tokens refreshed and rotated successfully."
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def logout(db: Session, access_token: str, refresh_token: Optional[str] = None):
    try:
        payload = decode_token(access_token)
        user_id = uuid.UUID(payload["sub"])
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            ttl = max(1, exp - now_ts)
            blacklist_token(jti, ttl)

        if refresh_token:
            rf_hash = hash_token(refresh_token)
            db.execute(
                text("DELETE FROM sessions WHERE refresh_token_hash = :rf_hash"),
                {"rf_hash": rf_hash},
            )
            db.commit()

        log_auth_audit(db, user_id, "auth.logout", "User logged out.")
    except Exception:
        pass


def create_invite(
    db: Session, current_user, req: InviteCreateRequest
) -> InviteResponse:
    if current_user["role"] != "Merchant Owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Merchant Owners can create invite tokens.",
        )

    token = create_invite_token(str(current_user["merchant_id"]), req.role)
    log_auth_audit(
        db,
        current_user["user_id"],
        "auth.create_invite",
        f"Invite created for {req.invitee_email}.",
    )
    return InviteResponse(invite_token=token, expires_in_hours=48)
