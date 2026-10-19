"""Lifecycle rules, tested directly (no database or HTTP)."""

from types import SimpleNamespace

import pytest

from app import workflow
from app.models import Role, Status

ENG = SimpleNamespace(id=1, role=Role.engineer)
LEAD = SimpleNamespace(id=2, role=Role.lead)
VIEWER = SimpleNamespace(id=3, role=Role.viewer)


def defect(status, **kw):
    base = dict(status=status, assignee_id=1, root_cause_category=None, root_cause="", verification_notes="",
                actions=[])
    return SimpleNamespace(**(base | kw))


def done(flag=True):
    return SimpleNamespace(done=flag)


@pytest.mark.parametrize("current, to", [
    (Status.open, Status.closed),
    (Status.open, Status.verification),
    (Status.investigating, Status.corrective_action),
    (Status.closed, Status.open),
])
def test_skipping_stages_is_impossible(current, to):
    assert workflow.check(defect(current), to, LEAD, "r")[0].startswith("cannot move")


def test_every_status_has_a_way_out():
    assert set(workflow.TRANSITIONS) == set(Status)
    assert all(workflow.TRANSITIONS.values())


def test_investigation_needs_an_assignee():
    assert "assign an engineer" in workflow.check(defect(Status.open, assignee_id=None), Status.investigating, ENG)[0]


def test_root_cause_needs_category_and_text():
    d = defect(Status.investigating, root_cause_category="design", root_cause="   ")
    assert workflow.check(d, Status.root_cause_identified, ENG) == ["record the root cause category and description"]
    d.root_cause = "Timing margin too small"
    assert workflow.check(d, Status.root_cause_identified, ENG) == []


def test_corrective_action_stage_needs_actions_and_they_must_be_done_before_verification():
    assert workflow.check(defect(Status.root_cause_identified), Status.corrective_action, ENG) == [
        "add at least one corrective action"]
    d = defect(Status.corrective_action, actions=[done(True), done(False)])
    assert workflow.check(d, Status.verification, ENG) == ["complete every corrective action"]


def test_closing_needs_lead_evidence_and_independent_verifier():
    d = defect(Status.verification, assignee_id=LEAD.id)
    problems = workflow.check(d, Status.closed, ENG)
    assert "requires a lead or admin" in problems and "record verification evidence" in problems
    d.verification_notes = "Retested"
    assert workflow.check(d, Status.closed, LEAD) == [
        "must be verified and closed by someone other than the assignee"]
    d.assignee_id = ENG.id
    assert workflow.check(d, Status.closed, LEAD) == []


@pytest.mark.parametrize("current, to", [
    (Status.open, Status.rejected),
    (Status.verification, Status.corrective_action),
    (Status.closed, Status.investigating),
    (Status.rejected, Status.open),
])
def test_backward_moves_need_a_reason(current, to):
    d = defect(current, actions=[done()], verification_notes="x")
    assert "a reason is required" in workflow.check(d, to, LEAD, "")
    assert "a reason is required" not in workflow.check(d, to, LEAD, "Duplicate of DEF-0003")


def test_viewers_cannot_change_anything():
    assert "viewers cannot change defects" in workflow.check(defect(Status.open), Status.investigating, VIEWER)


def test_options_explain_what_is_missing():
    options = {o["to"]: o for o in workflow.options(defect(Status.investigating), ENG)}
    assert set(options) == {Status.root_cause_identified, Status.rejected}
    assert not options[Status.root_cause_identified]["allowed"]
    assert options[Status.rejected]["problems"] == ["requires a lead or admin"]
