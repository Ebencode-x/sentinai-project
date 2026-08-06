"""Bootstrap the first Account + admin User on cold start.

Idempotent — safe to call on every startup. Does nothing once at least
one Account already exists.
"""

from __future__ import annotations

import logging
import os

from src.db.models import Account, Role, User
from src.db.session import SessionLocal
from src.security.passwords import hash_password

logger = logging.getLogger(__name__)


def bootstrap_default_account() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Account).first()
        if existing is not None:
            logger.debug("[bootstrap] Account already exists — skipping.")
            return

        admin_email = os.getenv("SENTINAI_ADMIN_EMAIL", "")
        admin_password = os.getenv("SENTINAI_ADMIN_PASSWORD", "")

        if not admin_email or not admin_password:
            logger.warning(
                "[bootstrap] No Account exists and SENTINAI_ADMIN_EMAIL / "
                "SENTINAI_ADMIN_PASSWORD are not set — skipping bootstrap. "
                "No one will be able to log in until an admin is created."
            )
            return

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
    finally:
        db.close()
