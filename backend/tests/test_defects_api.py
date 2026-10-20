"""Defect API: CRUD, validation, workflow over HTTP, roles, corrective actions, audit trail."""

import json

import pytest

from conftest import drive_to


def test_create_and_read(as_user):
    eng = as_user("eng")
    created = eng.create()
    assert created["key"] == "DEF-0001" and created["status"] == "open"
    assert created["reporter"] == "eng" and created["assignee"] == "eng"
    assert eng.get("/defects/DEF-0001").json()["title"] == "Bus voltage out of tolerance"
    assert eng.get("/defects/def-1").json()["key"] == "DEF-0001"  # keys are case- and padding-tolerant


@pytest.mark.parametrize("override, field", [
    ({"title": "x"}, "title"),
    ({"severity": "catastrophic"}, "severity"),
    ({"found_in": "production"}, "found_in"),
    ({"product": ""}, "product"),
])
def test_validation_errors(as_user, override, field):
    body = {"title": "Valid title", "severity": "minor", "product": "P", "component": "c", "failure_mode": "f",
            "found_in": "unit"} | override
    response = as_user("eng").post("/defects", json=body)
    assert response.status_code == 422
    assert field in json.dumps(response.json())


def test_assignee_must_be_an_active_engineer(as_user):
    eng = as_user("eng")
    for bad in ("nobody", "viewer", "gone"):
        response = eng.post("/defects", json={"title": "Valid title", "severity": "minor", "product": "P",
                                              "component": "c", "failure_mode": "f", "found_in": "unit",
                                              "assignee": bad})
        assert response.status_code == 422, bad


def test_unknown_key_is_404(as_user):
    assert as_user("eng").get("/defects/DEF-0999").status_code == 404
    assert as_user("eng").get("/defects/garbage").status_code == 404


def test_viewer_is_read_only(as_user):
    as_user("eng").create()
    viewer = as_user("viewer")
    assert viewer.get("/defects").status_code == 200
    assert viewer.post("/defects", json={}).status_code == 403
    assert viewer.patch("/defects/DEF-0001", json={"title": "Changed title"}).status_code == 403
    assert viewer.move("DEF-0001", "investigating").status_code == 403


def test_full_lifecycle_and_audit_trail(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    key = eng.create()["key"]
    drive_to(eng, lead, key, "closed")
    defect = eng.get(f"/defects/{key}").json()
    assert defect["status"] == "closed" and defect["closed_at"]
    history = eng.get(f"/defects/{key}/history").json()
    transitions = [(e["from_status"], e["to_status"], e["actor"]) for e in history if e["action"] == "transition"]
    assert transitions == [("open", "investigating", "eng"), ("investigating", "root_cause_identified", "eng"),
                           ("root_cause_identified", "corrective_action", "eng"),
                           ("corrective_action", "verification", "eng"), ("verification", "closed", "lead")]
    assert [e["action"] for e in history].count("action_completed") == 1


def test_blocked_transition_explains_why(as_user):
    eng = as_user("eng")
    key = eng.create()["key"]
    eng.move(key, "investigating")
    response = eng.move(key, "root_cause_identified")
    assert response.status_code == 409
    assert response.json()["detail"]["problems"] == ["record the root cause category and description"]
    options = eng.get(f"/defects/{key}/transitions").json()
    assert {o["to"]: o["allowed"] for o in options} == {"root_cause_identified": False, "rejected": False}


def test_engineer_cannot_close_and_assignee_cannot_self_verify(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    key = eng.create(assignee="lead")["key"]   # the lead is also the assignee
    lead.move(key, "investigating")
    lead.patch(f"/defects/{key}", json={"root_cause_category": "design", "root_cause": "Undersized motor"})
    lead.move(key, "root_cause_identified")
    lead.post(f"/defects/{key}/actions", json={"description": "Specify larger motor", "owner": "eng"})
    lead.move(key, "corrective_action")
    action_id = lead.get(f"/defects/{key}").json()["actions"][0]["id"]
    lead.post(f"/defects/{key}/actions/{action_id}/complete")
    lead.move(key, "verification")
    lead.patch(f"/defects/{key}", json={"verification_notes": "Slew 1.4 s on 3 units"})
    assert "requires a lead or admin" in eng.move(key, "closed").json()["detail"]["problems"]
    assert "someone other than the assignee" in lead.move(key, "closed").json()["detail"]["problems"][0]
    assert as_user("lead2").move(key, "closed").status_code == 200


def test_closed_defect_is_locked_until_reopened(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    key = eng.create()["key"]
    drive_to(eng, lead, key, "closed")
    assert eng.patch(f"/defects/{key}", json={"title": "Edited after closure"}).status_code == 409
    assert lead.move(key, "investigating").status_code == 409            # reason required
    reopened = lead.move(key, "investigating", reason="Failure recurred on unit 31")
    assert reopened.status_code == 200 and reopened.json()["closed_at"] is None
    assert eng.patch(f"/defects/{key}", json={"title": "Edited after reopen"}).status_code == 200


def test_reject_and_reinstate(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    key = eng.create()["key"]
    assert eng.move(key, "rejected", reason="dup").status_code == 409    # needs a lead
    assert lead.move(key, "rejected", reason="Duplicate of DEF-0002").status_code == 200
    events = eng.get(f"/defects/{key}/history").json()
    assert json.loads(events[-1]["details"]) == {"reason": "Duplicate of DEF-0002"}
    assert lead.move(key, "open", reason="Not a duplicate after all").status_code == 200


def test_actions_only_in_the_right_stages(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    key = eng.create()["key"]
    response = eng.post(f"/defects/{key}/actions", json={"description": "Too early action", "owner": "eng"})
    assert response.status_code == 409
    drive_to(eng, lead, key, "corrective_action")
    action = eng.get(f"/defects/{key}").json()["actions"][0]
    first = eng.post(f"/defects/{key}/actions/{action['id']}/complete").json()
    again = eng.post(f"/defects/{key}/actions/{action['id']}/complete").json()
    assert first["done"] and first["completed_at"] == again["completed_at"]  # idempotent
    assert eng.post(f"/defects/{key}/actions/999/complete").status_code == 404


def test_updates_are_audited_with_old_and_new_values(as_user):
    eng = as_user("eng")
    key = eng.create()["key"]
    eng.patch(f"/defects/{key}", json={"severity": "critical", "assignee": "eng2"})
    eng.patch(f"/defects/{key}", json={"severity": "critical"})  # no change -> no event
    updates = [e for e in eng.get(f"/defects/{key}/history").json() if e["action"] == "updated"]
    assert len(updates) == 1
    assert json.loads(updates[0]["details"]) == {"severity": ["major", "critical"], "assignee": ["eng", "eng2"]}


def test_list_filters_search_and_pagination(as_user):
    eng, lead = as_user("eng"), as_user("lead")
    for i in range(30):
        eng.create(title=f"Defect number {i}", severity="critical" if i % 3 == 0 else "minor",
                   failure_mode="CRC mismatch" if i % 5 == 0 else "Slew time", assignee="eng2" if i % 2 else "eng")
    lead.move("DEF-0001", "rejected", reason="test")
    page = eng.get("/defects", params={"page_size": 10, "page": 2}).json()
    assert page["total"] == 30 and len(page["items"]) == 10
    assert page["items"][0]["key"] == "DEF-0020"   # newest first
    assert eng.get("/defects", params={"severity": "critical"}).json()["total"] == 10
    assert eng.get("/defects", params={"q": "crc"}).json()["total"] == 6
    assert eng.get("/defects", params={"assignee": "eng2"}).json()["total"] == 15
    assert eng.get("/defects", params={"status": ["rejected"]}).json()["total"] == 1
    assert eng.get("/defects", params={"status": ["open", "rejected"]}).json()["total"] == 30
    assert eng.get("/defects", params={"page_size": 500}).status_code == 422


def test_search_is_parameterized_not_injectable(as_user):
    eng = as_user("eng")
    eng.create()
    for probe in ("' OR 1=1 --", "%", "_", "\\"):
        response = eng.get("/defects", params={"q": probe})
        assert response.status_code == 200
    assert eng.get("/defects", params={"q": "' OR 1=1 --"}).json()["total"] == 0
