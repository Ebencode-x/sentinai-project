"""Auth dependencies backed by the User/Account/Session model.

Replaces src/api/auth.py (Tenant/API-key) and src/api/security.py
(legacy single API key) — see docs/account-model-design.md.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.db.models import Role, User
from src.db.models import Session as SessionModel
from src.db.session import get_db

_SESSION_HEADER_NAME = "X-Session-Token"
_session_header = APIKeyHeader(name=_SESSION_HEADER_NAME, auto_error=False)


def require_user(
    token: str | None = Security(_session_header),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the request via session token, return the User.

    HTTP 401  token missing or unknown
    HTTP 401  token expired (also deletes the expired row)
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {_SESSION_HEADER_NAME} header.",
        )

    session = db.get(SessionModel, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        )

    if session.is_expired:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )

    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refers to a deleted user.",
        )

    return user


def require_role(role: Role):
    """Dependency factory — require_role(Role.ADMIN) etc.

    Admins implicitly satisfy a viewer requirement; viewers do not
    satisfy an admin requirement.
    """

    def _check(user: User = Depends(require_user)) -> User:
        if user.role == Role.ADMIN:
            return user
        if user.role == role:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role '{role}'.",
        )

    return _check
