"""Defects, their workflow, corrective actions and history."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import workflow
from ..models import AuditEvent, CorrectiveAction, Defect, Role, Severity, Status, User, as_utc, utcnow
from ..schemas import (ActionCreate, ActionOut, DefectCreate, DefectOut, DefectPage, DefectSummary,
                       DefectUpdate, EventOut, TransitionIn, TransitionOption)
from ..security import get_db, require

router = APIRouter(prefix="/defects", tags=["defects"])
KEY = re.compile(r"^DEF-(\d{1,9})$")
LOCKED = {Status.closed, Status.rejected}


def _load(db: Session, key: str) -> Defect:
    match = KEY.match(key.upper())
    defect = db.get(Defect, int(match.group(1)),
                    options=[selectinload(Defect.actions), selectinload(Defect.events)]) if match else None
    if defect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{key} not found")
    return defect


def _user(db: Session, username: str | None, field: str) -> User | None:
    if username is None:
        return None
    user = db.scalar(select(User).where(User.username == username, User.active))
    if user is None or user.role.rank < Role.engineer.rank:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field}: no active engineer '{username}'")
    return user


def _audit(db: Session, defect: Defect, actor: User, action: str, **details) -> None:
    db.add(AuditEvent(defect=defect, actor_id=actor.id, action=action,
                      from_status=details.pop("from_status", None), to_status=details.pop("to_status", None),
                      details=json.dumps(details, default=str) if details else ""))


def _out(defect: Defect) -> DefectOut:
    return DefectOut(
        key=defect.key, title=defect.title, description=defect.description, severity=defect.severity,
        status=defect.status, product=defect.product, component=defect.component,
        failure_mode=defect.failure_mode, found_in=defect.found_in, reporter=defect.reporter.username,
        assignee=defect.assignee.username if defect.assignee else None,
        root_cause_category=defect.root_cause_category, root_cause=defect.root_cause,
        verification_notes=defect.verification_notes, created_at=as_utc(defect.created_at),
        updated_at=as_utc(defect.updated_at), closed_at=as_utc(defect.closed_at),
        actions=[_action_out(a) for a in defect.actions],
    )


def _action_out(action: CorrectiveAction) -> ActionOut:
    return ActionOut(id=action.id, description=action.description, owner=action.owner.username,
                     due_date=action.due_date, done=action.done, completed_at=as_utc(action.completed_at))


@router.get("", response_model=DefectPage)
def list_defects(
    db: Session = Depends(get_db),
    _: User = Depends(require(Role.viewer)),
    status_: list[Status] | None = Query(default=None, alias="status"),
    severity: list[Severity] | None = Query(default=None),
    assignee: str | None = None,
    product: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    query = select(Defect)
    if status_:
        query = query.where(Defect.status.in_(status_))
    if severity:
        query = query.where(Defect.severity.in_(severity))
    if assignee:
        query = query.join(User, Defect.assignee_id == User.id).where(User.username == assignee)
    if product:
        query = query.where(Defect.product == product)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Defect.title).like(like), func.lower(Defect.description).like(like),
                                func.lower(Defect.failure_mode).like(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Defect.created_at.desc(), Defect.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    now = utcnow()
    items = [DefectSummary(key=d.key, title=d.title, severity=d.severity, status=d.status, product=d.product,
                           failure_mode=d.failure_mode, assignee=d.assignee.username if d.assignee else None,
                           created_at=as_utc(d.created_at),
                           age_days=((as_utc(d.closed_at) or now) - as_utc(d.created_at)).days)
             for d in rows]
    return DefectPage(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=DefectOut, status_code=status.HTTP_201_CREATED)
def create_defect(body: DefectCreate, db: Session = Depends(get_db), user: User = Depends(require(Role.engineer))):
    defect = Defect(**body.model_dump(exclude={"assignee"}), reporter_id=user.id,
                    assignee=_user(db, body.assignee, "assignee"), status=Status.open)
    db.add(defect)
    db.flush()
    _audit(db, defect, user, "created", to_status=Status.open.value)
    db.commit()
    return _out(_load(db, defect.key))


@router.get("/{key}", response_model=DefectOut)
def get_defect(key: str, db: Session = Depends(get_db), _: User = Depends(require(Role.viewer))):
    return _out(_load(db, key))


@router.patch("/{key}", response_model=DefectOut)
def update_defect(key: str, body: DefectUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require(Role.engineer))):
    defect = _load(db, key)
    if defect.status in LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{defect.key} is {defect.status.value}; reopen it to edit")
    changes = body.model_dump(exclude_unset=True)
    recorded = {}
    if "assignee" in changes:
        new = _user(db, changes.pop("assignee"), "assignee")
        old = defect.assignee.username if defect.assignee else None
        if (new.username if new else None) != old:
            recorded["assignee"] = [old, new.username if new else None]
        defect.assignee = new
    for field, value in changes.items():
        if getattr(defect, field) != value:
            recorded[field] = [getattr(defect, field), value]
            setattr(defect, field, value)
    if recorded:
        _audit(db, defect, user, "updated", **recorded)
    db.commit()
    return _out(_load(db, key))


@router.get("/{key}/transitions", response_model=list[TransitionOption])
def transition_options(key: str, db: Session = Depends(get_db), user: User = Depends(require(Role.viewer))):
    return workflow.options(_load(db, key), user)


@router.post("/{key}/transition", response_model=DefectOut)
def transition(key: str, body: TransitionIn, db: Session = Depends(get_db),
               user: User = Depends(require(Role.engineer))):
    defect = _load(db, key)
    problems = workflow.check(defect, body.to, user, body.reason)
    if problems:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "transition not allowed", "problems": problems})
    previous = defect.status
    defect.status = body.to
    defect.closed_at = utcnow() if body.to == Status.closed else None
    _audit(db, defect, user, "transition", from_status=previous.value, to_status=body.to.value,
           **({"reason": body.reason} if body.reason else {}))
    db.commit()
    return _out(_load(db, key))


@router.post("/{key}/actions", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
def add_action(key: str, body: ActionCreate, db: Session = Depends(get_db),
               user: User = Depends(require(Role.engineer))):
    defect = _load(db, key)
    if defect.status not in (Status.root_cause_identified, Status.corrective_action):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "corrective actions are added once the root cause is identified")
    action = CorrectiveAction(defect=defect, description=body.description,
                              owner=_user(db, body.owner, "owner"), due_date=body.due_date)
    db.add(action)
    db.flush()
    _audit(db, defect, user, "action_added", action_id=action.id, description=body.description)
    db.commit()
    return _action_out(action)


@router.post("/{key}/actions/{action_id}/complete", response_model=ActionOut)
def complete_action(key: str, action_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require(Role.engineer))):
    defect = _load(db, key)
    action = next((a for a in defect.actions if a.id == action_id), None)
    if action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"action {action_id} not found on {defect.key}")
    if defect.status != Status.corrective_action:
        raise HTTPException(status.HTTP_409_CONFLICT, "actions are completed during the corrective_action stage")
    if not action.done:
        action.done, action.completed_at = True, utcnow()
        _audit(db, defect, user, "action_completed", action_id=action.id)
        db.commit()
    return _action_out(action)


@router.get("/{key}/history", response_model=list[EventOut])
def history(key: str, db: Session = Depends(get_db), _: User = Depends(require(Role.viewer))):
    return [EventOut(action=e.action, actor=e.actor.username, from_status=e.from_status, to_status=e.to_status,
                     details=e.details, at=as_utc(e.at)) for e in _load(db, key).events]
