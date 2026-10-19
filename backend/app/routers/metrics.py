"""Dashboard numbers: counts, failure Pareto, root causes, aging, time to close."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Defect, Role, Status, User, as_utc, utcnow
from ..schemas import Metrics
from ..security import get_db, require

router = APIRouter(tags=["metrics"])
DONE = {Status.closed, Status.rejected}
AGE_BUCKETS = [("0-7 days", 7), ("8-30 days", 30), ("31-90 days", 90), ("over 90 days", None)]


@router.get("/metrics", response_model=Metrics)
def metrics(db: Session = Depends(get_db), _: User = Depends(require(Role.viewer)), weeks: int = 12):
    defects = db.scalars(select(Defect)).all()
    now = utcnow()
    open_ = [d for d in defects if d.status not in DONE]

    failures = Counter(d.failure_mode for d in defects if d.status != Status.rejected)
    total_failures = sum(failures.values())
    pareto, running = [], 0
    for mode, count in failures.most_common(10):
        running += count
        pareto.append({"failure_mode": mode, "count": count,
                       "cumulative_pct": round(100 * running / total_failures, 1)})

    aging = {label: 0 for label, _ in AGE_BUCKETS}
    for d in open_:
        age = (now - as_utc(d.created_at)).days
        label = next(label for label, limit in AGE_BUCKETS if limit is None or age <= limit)
        aging[label] += 1

    closed = [d for d in defects if d.status == Status.closed and d.closed_at]
    mean_days = (round(sum((as_utc(d.closed_at) - as_utc(d.created_at)).total_seconds() for d in closed)
                       / len(closed) / 86400, 1) if closed else None)

    start = (now - timedelta(weeks=weeks)).date()
    start -= timedelta(days=start.weekday())  # Monday
    weekly = []
    for i in range(weeks + 1):
        week_start = start + timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        weekly.append({
            "week": week_start.isoformat(),
            "opened": sum(week_start <= as_utc(d.created_at).date() < week_end for d in defects),
            "closed": sum(week_start <= as_utc(d.closed_at).date() < week_end for d in closed),
        })

    return Metrics(
        total=len(defects),
        open=len(open_),
        by_status={s.value: sum(d.status == s for d in defects) for s in Status},
        open_by_severity={sev: sum(d.severity.value == sev for d in open_) for sev in ("critical", "major", "minor")},
        pareto=pareto,
        root_causes=dict(Counter(d.root_cause_category.value for d in defects if d.root_cause_category).most_common()),
        aging=aging,
        mean_days_to_close=mean_days,
        weekly=weekly,
    )
