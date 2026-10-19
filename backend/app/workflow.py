"""Defect lifecycle rules: which status changes are allowed and what each needs.

    open -> investigating -> root_cause_identified -> corrective_action -> verification -> closed

No DB or FastAPI imports here so the rules can be unit tested on their own.
"""

from __future__ import annotations

from .models import Role, Status

S = Status

TRANSITIONS: dict[Status, set[Status]] = {
    S.open: {S.investigating, S.rejected},
    S.investigating: {S.root_cause_identified, S.rejected},
    S.root_cause_identified: {S.corrective_action, S.investigating},
    S.corrective_action: {S.verification, S.root_cause_identified},
    S.verification: {S.closed, S.corrective_action},
    S.closed: {S.investigating},   # reopen
    S.rejected: {S.open},          # reinstate
}

# Decisions that need a lead: closing, rejecting, and undoing either.
LEAD_DECISIONS = {(S.verification, S.closed), (S.open, S.rejected), (S.investigating, S.rejected),
                  (S.closed, S.investigating), (S.rejected, S.open)}
ORDER = list(Status)


def is_backward(current: Status, to: Status) -> bool:
    # rejecting, failed verification, reopen, reinstate
    return to == S.rejected or ORDER.index(to) < ORDER.index(current)


def check(defect, to: Status, actor, reason: str = "") -> list[str]:
    """Returns every reason the move is blocked; empty means it's allowed."""
    current = Status(defect.status)
    if to not in TRANSITIONS[current]:
        return [f"cannot move from {current.value} to {to.value}"]

    problems = []
    if actor.role.rank < Role.engineer.rank:
        problems.append("viewers cannot change defects")
    if (current, to) in LEAD_DECISIONS and actor.role.rank < Role.lead.rank:
        problems.append("requires a lead or admin")
    if is_backward(current, to) and not reason.strip():
        problems.append("a reason is required")

    if to == S.investigating and current == S.open and defect.assignee_id is None:
        problems.append("assign an engineer before investigating")
    if to == S.root_cause_identified and (not defect.root_cause_category or not defect.root_cause.strip()):
        problems.append("record the root cause category and description")
    if to == S.corrective_action and not defect.actions:
        problems.append("add at least one corrective action")
    if to == S.verification and any(not a.done for a in defect.actions):
        problems.append("complete every corrective action")
    if to == S.closed:
        if not defect.verification_notes.strip():
            problems.append("record verification evidence")
        if defect.assignee_id == actor.id:
            problems.append("must be verified and closed by someone other than the assignee")
    return problems


def options(defect, actor) -> list[dict]:
    """Each move out of the current status and what's blocking it (for the UI)."""
    result = []
    for to in sorted(TRANSITIONS[Status(defect.status)], key=ORDER.index):
        problems = check(defect, to, actor, reason="(preview)")
        result.append({"to": to, "allowed": not problems, "problems": problems})
    return result
