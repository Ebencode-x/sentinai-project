"""Bootstrap the first Account + admin User on cold start.

Idempotent - safe to call on every startup. Does nothing once at least
one Account already exists.

If SENTINAI_ADMIN_EMAIL / SENTINAI_ADMIN_PASSWORD are not set, a first-run
admin is created with a random one-time password that is written to the log
exactly once. There is never a built-in default password.
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Callable

from sqlalchemy.orm import Session

from src.db.models import Account, Role, User
from src.db.session import SessionLocal
from src.security.passwords import hash_password

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = "admin@sentinai.local"
_MIN_PASSWORD_LEN = 8


def bootstrap_default_account(session_factory: Callable[[], Session] = SessionLocal) -> None:
    db = session_factory()
    try:
        existing = db.query(Account).first()
        if existing is not None:
            logger.debug("[bootstrap] Account already exists - skipping.")
            return

        admin_email = os.getenv("SENTINAI_ADMIN_EMAIL", "").strip() or DEFAULT_ADMIN_EMAIL
        admin_password = os.getenv("SENTINAI_ADMIN_PASSWORD", "")
        generated = not admin_password
        if generated:
            admin_password = secrets.token_urlsafe(12)
        elif len(admin_password) < _MIN_PASSWORD_LEN:
            logger.warning(
                "[bootstrap] SENTINAI_ADMIN_PASSWORD is shorter than %d characters - "
                "use a longer one before any public deployment.",
                _MIN_PASSWORD_LEN,
            )

        account = Account(name="default")
        db.add(account)
        db.flush()  # populate account.id

        admin = User(
            account_id=account.id,
            email=admin_email,
            password_hash=hash_password(admin_password),
            role=Role.ADMIN,
        )
        db.add(admin)
        db.commit()
        logger.info("[bootstrap] Created default Account and admin user %r", admin_email)
        if generated:
            logger.warning(
                "[bootstrap] FIRST-RUN ADMIN LOGIN  email=%s  password=%s  "
                "(shown only once - change it, or set SENTINAI_ADMIN_EMAIL and "
                "SENTINAI_ADMIN_PASSWORD before first start)",
                admin_email,
                admin_password,
            )
    finally:
        db.close()
