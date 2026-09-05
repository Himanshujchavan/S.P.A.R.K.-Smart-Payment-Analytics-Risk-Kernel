# tests/test_auth.py
# Comprehensive security test suite for Phase 2 Auth System

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.main import app
from api.core.db import SessionLocal
from api.schemas.auth import validate_password_complexity

client = TestClient(app)


def is_db_available() -> bool:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception:
        return False


db_required = pytest.mark.skipif(
    not is_db_available(), reason="Postgres DB container not active on localhost:5432"
)


def test_password_complexity_validator():
    with pytest.raises(ValueError, match="at least 8 characters"):
        validate_password_complexity("Short1")

    with pytest.raises(ValueError, match="at least one digit"):
        validate_password_complexity("NoDigitsPass")

    with pytest.raises(ValueError, match="at least one uppercase"):
        validate_password_complexity("lowercase123")

    with pytest.raises(ValueError, match="too common"):
        validate_password_complexity("Password123")

    assert validate_password_complexity("ValidSecurePass123!") == "ValidSecurePass123!"


@db_required
def test_signup_new_merchant_and_login():
    test_email = f"user_{uuid.uuid4().hex[:8]}@merchant.com"
    password = "StrongPassword123!"

    # 1. Signup
    res = client.post(
        "/api/v1/auth/signup",
        json={
            "email": test_email,
            "password": password,
            "full_name": "Test Owner",
            "merchant_name": "Test Merchant Co",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Get Me
    me_res = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == test_email
    assert me_data["role"] == "Merchant Owner"
    assert me_data["merchant_id"] is not None

    # 3. Create Invite Token for Analyst
    invite_res = client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"invitee_email": "analyst@test.com", "role": "Risk Analyst"},
    )
    assert invite_res.status_code == 200
    invite_token = invite_res.json()["invite_token"]

    # 4. Signup Analyst with Invite Token
    analyst_email = f"analyst_{uuid.uuid4().hex[:8]}@merchant.com"
    analyst_signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "Test Analyst",
            "invite_token": invite_token,
        },
    )
    assert analyst_signup.status_code == 201
    analyst_tokens = analyst_signup.json()

    analyst_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {analyst_tokens['access_token']}"},
    )
    assert analyst_me.status_code == 200
    assert analyst_me.json()["role"] == "Risk Analyst"
    assert analyst_me.json()["merchant_id"] == me_data["merchant_id"]

    # 5. Role requirement check (Analyst cannot invite)
    analyst_invite = client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {analyst_tokens['access_token']}"},
        json={"invitee_email": "another@test.com", "role": "Risk Analyst"},
    )
    assert analyst_invite.status_code == 403

    # 6. Test Refresh Token Rotation
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_res.status_code == 200
    new_tokens = ref_res.json()
    new_refresh = new_tokens["refresh_token"]
    assert new_refresh != refresh_token

    # 7. Test Theft Detection (Reusing old refresh token revokes session family)
    theft_res = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert theft_res.status_code == 401
    assert "Security breach" in theft_res.json()["detail"]

    # 8. Test Logout & Token Blacklist
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        json={"refresh_token": new_refresh},
    )
    assert logout_res.status_code == 204

    # Using logged-out token fails
    me_after_logout = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_after_logout.status_code == 401


@db_required
def test_account_lockout():
    db = SessionLocal()
    test_email = f"lockout_{uuid.uuid4().hex[:8]}@merchant.com"
    correct_pass = "ValidPass123!"

    client.post(
        "/api/v1/auth/signup",
        json={
            "email": test_email,
            "password": correct_pass,
            "full_name": "Lockout Test User",
        },
    )

    # Fail 5 times
    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword1!"},
        )
        assert res.status_code in [401, 423]

    # 6th attempt should be locked (HTTP 423)
    locked_res = client.post(
        "/api/v1/auth/login", json={"email": test_email, "password": correct_pass}
    )
    assert locked_res.status_code == 423
    assert "Account locked" in locked_res.json()["detail"]

    db.close()


@db_required
def test_audit_logs_populated():
    db = SessionLocal()
    audit_rows = db.execute(
        text("SELECT action, reasoning FROM audit_log WHERE action LIKE 'auth.%'")
    ).fetchall()
    assert len(audit_rows) > 0
    print(f"\n[✓] Audit log verified with {len(audit_rows)} auth event entries.")
    db.close()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
