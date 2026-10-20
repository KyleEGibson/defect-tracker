"""Demo users and ~12 weeks of defects (TRACKER_SEED_DEMO=true, never in production).

Each defect is pushed through workflow.check() so the audit trail is one the
API could actually have produced.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import workflow
from .models import (AuditEvent, CorrectiveAction, Defect, Role, RootCause, Severity, Status, TestStage, User,
                     utcnow)
from .security import hash_password

DEMO_PASSWORD = "demo-pass-1234"
USERS = [
    ("admin", "Avery Admin", Role.admin),
    ("mlopez", "Maria Lopez", Role.lead),
    ("kgibson", "Kyle Gibson", Role.engineer),
    ("achen", "Alex Chen", Role.engineer),
    ("rpatel", "Riya Patel", Role.engineer),
    ("viewer", "Program Viewer", Role.viewer),
]

# (product, component, failure mode, test stage, usual root cause)
FAILURES = [
    ("EOS-100", "power", "Bus voltage out of tolerance", TestStage.acceptance, RootCause.test_equipment),
    ("EOS-100", "gimbal", "Slew time exceeds 2.0 s", TestStage.acceptance, RootCause.material),
    ("EOS-100", "thermal", "Cooldown time exceeds 15 s", TestStage.system, RootCause.environment),
    ("EOS-100", "imager", "Dead pixel count above limit", TestStage.acceptance, RootCause.material),
    ("EOS-100", "interface", "Telemetry CRC mismatch", TestStage.integration, RootCause.software),
    ("EOS-100", "firmware", "Boot fallback after update", TestStage.integration, RootCause.software),
    ("GC-200", "servo", "Pointing error above 0.1 deg", TestStage.system, RootCause.design),
    ("GC-200", "harness", "Intermittent comm timeout", TestStage.integration, RootCause.workmanship),
    ("GC-200", "firmware", "Config drift after power cycle", TestStage.system, RootCause.process),
    ("EOS-100", "docs", "Test procedure step out of order", TestStage.acceptance, RootCause.documentation),
]
WEIGHTS = [9, 7, 5, 4, 4, 3, 3, 3, 2, 1]


def seed_if_empty(db: Session, defects: int = 60, seed: int = 7) -> bool:
    if db.scalar(select(func.count()).select_from(User)):
        return False
    rng = random.Random(seed)
    users = {}
    for username, name, role in USERS:
        users[username] = User(username=username, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
        db.add(users[username])
    db.flush()
    engineers = [users[u] for u in ("kgibson", "achen", "rpatel")]
    lead = users["mlopez"]
    now = utcnow()

    for _ in range(defects):
        product, component, mode, stage, cause = rng.choices(FAILURES, weights=WEIGHTS)[0]
        created = now - timedelta(days=rng.uniform(1, 84), hours=rng.uniform(0, 8))
        reporter, assignee = rng.choice(engineers), rng.choice(engineers)
        severity = rng.choices([Severity.critical, Severity.major, Severity.minor], weights=[1, 4, 5])[0]
        d = Defect(title=f"{mode} on {product} {component}", severity=severity, product=product,
                   component=component, failure_mode=mode, found_in=stage, reporter_id=reporter.id,
                   assignee_id=assignee.id, status=Status.open, created_at=created, updated_at=created,
                   root_cause="", verification_notes="",
                   description=f"Observed during {stage.value} test. Measurement outside its requirement limit; "
                               f"see attached test report.")
        db.add(d)
        db.flush()
        db.add(AuditEvent(defect_id=d.id, actor_id=reporter.id, action="created", to_status="open", at=created))

        # older defects get further through the lifecycle
        age_days = (now - created).days
        stages = [Status.investigating, Status.root_cause_identified, Status.corrective_action,
                  Status.verification, Status.closed]
        reach = min(len(stages), max(0, int(age_days / 9 + rng.uniform(-1.5, 1.5))))
        if rng.random() < 0.06:
            stages, reach = [Status.rejected], 1
        clock = created
        for target in stages[:reach]:
            clock += timedelta(days=rng.uniform(0.5, 3.0))
            if clock >= now:
                break
            if target == Status.root_cause_identified:
                d.root_cause_category = cause if rng.random() < 0.85 else rng.choice(list(RootCause))
                d.root_cause = f"Investigation traced the failure to a {d.root_cause_category.value.replace('_', ' ')} issue."
            if target == Status.corrective_action:
                owner = rng.choice(engineers)
                d.actions.append(CorrectiveAction(description=f"Corrective action for {mode.lower()}",
                                                  owner_id=owner.id, due_date=(clock + timedelta(days=14)).date()))
            if target == Status.verification:
                for a in d.actions:
                    a.done, a.completed_at = True, clock
            if target == Status.closed:
                d.verification_notes = "Re-ran the failing test on three units; all within limits."
            actor = lead if target in (Status.closed, Status.rejected) else assignee
            reason = "Duplicate of an existing defect" if target == Status.rejected else ""
            problems = workflow.check(d, target, actor, reason)
            if problems:
                raise RuntimeError(f"seed data violates the workflow: {problems}")
            db.add(AuditEvent(defect_id=d.id, actor_id=actor.id, action="transition", from_status=d.status.value,
                              to_status=target.value, at=clock,
                              details='{"reason": "%s"}' % reason if reason else ""))
            d.status, d.updated_at = target, clock
            if target == Status.closed:
                d.closed_at = clock
    db.commit()
    return True
