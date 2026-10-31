"""Admin routes for event sources and their API keys.

A key is shown once, when a source is created or its key is rotated. Only a hash
is stored, so a lost key is replaced, never recovered.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import require_user
from src.api.routes import require_admin
from src.db import sources
from src.db.models import Source
from src.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_admin)])

UserDep = Annotated[Any, Depends(require_user)]
DbDep = Annotated[Session, Depends(get_db)]


class SourceCreate(BaseModel):
    name: str = Field(pattern=sources.NAME_PATTERN.pattern)


class SourceOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    status: str
    created_at: datetime
    created_by: str | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    last_event_at: datetime | None


class SourceWithKey(SourceOut):
    key: str


def _out(row: Source) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "status": "revoked" if row.revoked_at else "active",
        "created_at": row.created_at,
        "created_by": row.created_by,
        "revoked_at": row.revoked_at,
        "last_used_at": row.last_used_at,
        "last_event_at": row.last_event_at,
    }


@router.get("", response_model=list[SourceOut])
def list_sources(user: UserDep, db: DbDep) -> list[dict]:
    return [_out(row) for row in sources.list_sources(db, user.account_id)]


@router.post("", status_code=201, response_model=SourceWithKey)
def create_source(body: SourceCreate, response: Response, user: UserDep, db: DbDep) -> dict:
    try:
        row, key = sources.create_source(db, user.account_id, body.name, user.email)
    except sources.SourceNameTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    logger.info("Source '%s' created by %s", row.name, user.email)
    return {**_out(row), "key": key}


@router.post("/{source_id}/rotate", response_model=SourceWithKey)
def rotate_source(source_id: str, response: Response, user: UserDep, db: DbDep) -> dict:
    try:
        key = sources.rotate_key(db, user.account_id, source_id)
    except sources.SourceRevoked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = sources.get_source(db, user.account_id, source_id)
    if key is None or row is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    response.headers["Cache-Control"] = "no-store"
    logger.info("Key of source '%s' rotated by %s", row.name, user.email)
    return {**_out(row), "key": key}


@router.delete("/{source_id}")
def revoke_source(source_id: str, user: UserDep, db: DbDep) -> dict:
    if not sources.revoke_source(db, user.account_id, source_id):
        raise HTTPException(status_code=404, detail="Source not found.")
    logger.info("Source %s revoked by %s", source_id, user.email)
    return {"revoked": True, "id": source_id}
