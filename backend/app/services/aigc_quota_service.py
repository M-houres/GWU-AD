from sqlalchemy import func

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Task, TaskType

settings = get_settings()


def get_aigc_daily_quota(
    db: Session,
    *,
    user_id: int,
    submitted_delta: int = 0,
) -> dict:
    limit = max(int(settings.aigc_daily_free_limit or 0), 0)
    submitted_today = (
        db.query(Task.id)
        .filter(
            Task.user_id == user_id,
            Task.task_type == TaskType.AIGC_DETECT,
            func.date(Task.created_at) == func.date(func.now()),
        )
        .count()
    )
    submitted_today = max(int(submitted_today) + int(submitted_delta or 0), 0)
    free_used_today = min(submitted_today, limit)
    free_remaining_today = max(limit - submitted_today, 0)
    return {
        "daily_free_limit": limit,
        "submitted_today": submitted_today,
        "free_used_today": free_used_today,
        "free_remaining_today": free_remaining_today,
    }
