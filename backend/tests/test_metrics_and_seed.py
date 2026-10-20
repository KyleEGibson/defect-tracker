"""Metrics calculations and demo data consistency."""

from datetime import timedelta

from conftest import drive_to

from app.models import Defect, Status, utcnow
from app.seed import seed_if_empty


def test_metrics_counts_pareto_and_time_to_close(app, as_user):
    eng, lead = as_user("eng"), as_user("lead")
    for _ in range(3):
        eng.create(failure_mode="Slew time")
    eng.create(failure_mode="CRC mismatch")
    drive_to(eng, lead, "DEF-0001", "closed")
    lead.move("DEF-0004", "rejected", reason="Not reproducible")

    with app.state.sessionmaker() as db:  # backdate to make ages and durations deterministic
        now = utcnow()
        d1 = db.get(Defect, 1)
        d1.created_at, d1.closed_at = now - timedelta(days=10), now - timedelta(days=4)
        db.get(Defect, 2).created_at = now - timedelta(days=45)
        db.commit()

    m = eng.get("/metrics").json()
    assert m["total"] == 4 and m["open"] == 2
    assert m["by_status"]["closed"] == 1 and m["by_status"]["rejected"] == 1
    assert m["pareto"] == [{"failure_mode": "Slew time", "count": 3, "cumulative_pct": 100.0}]  # rejected excluded
    assert m["mean_days_to_close"] == 6.0
    assert m["aging"] == {"0-7 days": 1, "8-30 days": 0, "31-90 days": 1, "over 90 days": 0}
    assert m["root_causes"] == {"test_equipment": 1}
    assert sum(w["opened"] for w in m["weekly"]) == 4


def test_seed_walks_every_defect_through_the_real_rules(app):
    with app.state.sessionmaker() as db:
        db.query(Defect).delete()
        from app.models import User
        db.query(User).delete()
        db.commit()
        assert seed_if_empty(db, defects=80)
        assert not seed_if_empty(db)  # idempotent
        defects = db.query(Defect).all()
        assert len(defects) == 80
        statuses = {d.status for d in defects}
        assert {Status.open, Status.closed} <= statuses
        for d in defects:
            if d.status == Status.closed:
                assert d.verification_notes and d.closed_at and all(a.done for a in d.actions)
                closer = [e for e in d.events if e.to_status == "closed"][0].actor_id
                assert closer != d.assignee_id
            if d.status in (Status.root_cause_identified, Status.corrective_action, Status.verification):
                assert d.root_cause_category and d.root_cause
