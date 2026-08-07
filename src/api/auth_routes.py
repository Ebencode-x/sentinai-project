"""/auth/* endpoints — login, logout, current user.

Session tokens are opaque (see src/db/models.Session), stored server-side,
and revoked instantly on logout by deleting the row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from src.api.deps import require_user
from src.db.models import Session as SessionModel
from src.db.models import User
from src.db.session import get_db
from src.security.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_SESSION_LIFETIME = timedelta(hours=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str
    role: str
    expires_at: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DBSession = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == body.email).first()

    # Same error for "no such user" and "wrong password" — don't leak
    # which one it was.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    now = datetime.now(UTC)
    session = SessionModel(user_id=user.id, expires_at=now + _SESSION_LIFETIME)
    db.add(session)
    user.last_login_at = now
    db.commit()

    return LoginResponse(
        token=session.token,
        email=user.email,
        role=user.role,
        expires_at=session.expires_at.isoformat(),
    )


@router.post("/logout")
def logout(
    user: User = Depends(require_user),
    db: DBSession = Depends(get_db),
) -> dict:
    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
    db.commit()
    return {"logged_out": True}


@router.get("/me")
def me(user: User = Depends(require_user)) -> dict:
    return {
        "email": user.email,
        "role": user.role,
        "account_id": user.account_id,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
