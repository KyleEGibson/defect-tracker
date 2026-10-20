"""Test app on in-memory SQLite, or PostgreSQL when TRACKER_TEST_DATABASE_URL is set."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base, Role, User
from app.security import hash_password

PASSWORD = "test-pass-1234"
DATABASE_URL = os.environ.get("TRACKER_TEST_DATABASE_URL", "sqlite://")


@pytest.fixture
def app():
    application = create_app(Settings(database_url=DATABASE_URL, jwt_secret="t" * 40))
    with application.state.sessionmaker() as db:
        for username, role in [("eng", Role.engineer), ("eng2", Role.engineer), ("lead", Role.lead),
                               ("lead2", Role.lead), ("viewer", Role.viewer), ("admin", Role.admin)]:
            db.add(User(username=username, full_name=username.title(), role=role, password_hash=hash_password(PASSWORD)))
        db.add(User(username="gone", full_name="Former", role=Role.engineer, active=False,
                    password_hash=hash_password(PASSWORD)))
        db.commit()
    yield application
    Base.metadata.drop_all(application.state.engine)
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    return TestClient(app)


class Api:
    """Logged-in shortcuts for one user."""

    def __init__(self, client: TestClient, username: str) -> None:
        response = client.post("/api/auth/token", data={"username": username, "password": PASSWORD})
        assert response.status_code == 200, response.text
        self.client = client
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def get(self, path, **kw):
        return self.client.get("/api" + path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post("/api" + path, headers=self.headers, **kw)

    def patch(self, path, **kw):
        return self.client.patch("/api" + path, headers=self.headers, **kw)

    def create(self, **overrides) -> dict:
        body = {"title": "Bus voltage out of tolerance", "severity": "major", "product": "EOS-100",
                "component": "power", "failure_mode": "Bus voltage out of tolerance", "found_in": "acceptance",
                "assignee": "eng"} | overrides
        response = self.post("/defects", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def move(self, key: str, to: str, reason: str = ""):
        return self.post(f"/defects/{key}/transition", json={"to": to, "reason": reason})


@pytest.fixture
def as_user(client):
    return lambda username: Api(client, username)


def drive_to(eng: Api, lead: Api, key: str, target: str) -> None:
    """Walk a defect through the happy path up to ``target``."""
    steps = ["investigating", "root_cause_identified", "corrective_action", "verification", "closed"]
    for step in steps[: steps.index(target) + 1]:
        if step == "root_cause_identified":
            eng.patch(f"/defects/{key}", json={"root_cause_category": "test_equipment",
                                               "root_cause": "Bench 2 voltmeter out of calibration"})
        if step == "corrective_action":
            assert eng.post(f"/defects/{key}/actions", json={"description": "Recalibrate bench 2 meter",
                                                             "owner": "eng"}).status_code == 201
        if step == "verification":
            for action in eng.get(f"/defects/{key}").json()["actions"]:
                eng.post(f"/defects/{key}/actions/{action['id']}/complete")
        if step == "closed":
            eng.patch(f"/defects/{key}", json={"verification_notes": "Retested 3 units on bench 2: all pass"})
        actor = lead if step == "closed" else eng
        response = actor.move(key, step)
        assert response.status_code == 200, response.text
