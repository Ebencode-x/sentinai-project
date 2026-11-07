"""Activity API: GET /api/activity/daily feeds the overview charts and heatmap.

Any signed-in user can read it. It returns counts and source names only, never keys.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import require_user
from src.db import activity
from src.db.session import get_db

router = APIRouter(prefix="/activity", tags=["activity"], dependencies=[Depends(require_user)])

UserDep = Annotated[Any, Depends(require_user)]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/daily")
def daily(
    user: UserDep,
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=activity.MAX_DAYS)] = 182,
) -> dict[str, Any]:
    """One entry per UTC day for the last `days` days, plus totals and per source counts."""
    return activity.daily_activity(db, user.account_id, days=days)
