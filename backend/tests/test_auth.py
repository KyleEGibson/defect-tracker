"""Authentication, tokens and configuration safety."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import Settings
from app.security import hash_password, verify_password
from conftest import PASSWORD


def test_login_returns_token_and_user(client):
    response = client.post("/api/auth/token", data={"username": "eng", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["user"] == {"username": "eng", "full_name": "Eng", "role": "engineer"}


def test_wrong_password_and_unknown_user_look_identical(client):
    wrong = client.post("/api/auth/token", data={"username": "eng", "password": "nope"})
    unknown = client.post("/api/auth/token", data={"username": "nobody", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration


def test_inactive_user_cannot_log_in(client):
    assert client.post("/api/auth/token", data={"username": "gone", "password": PASSWORD}).status_code == 401


@pytest.mark.parametrize("header", [None, "Bearer not-a-jwt", "Basic abc"])
def test_requests_without_valid_token_rejected(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/api/defects", headers=headers).status_code == 401


def test_token_signed_with_other_secret_rejected(client):
    forged = jwt.encode({"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "attacker-controlled-secret-of-adequate-length", algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(app, client):
    expired = jwt.encode({"sub": "eng", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
                         app.state.settings.jwt_secret, algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_for_deactivated_user_rejected(app, client, as_user):
    api = as_user("eng")
    with app.state.sessionmaker() as db:
        from app.models import User
        db.query(User).filter_by(username="eng").update({"active": False})
        db.commit()
    assert api.get("/users/me").status_code == 401


def test_password_hashing():
    stored = hash_password("correct horse")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("same") != hash_password("same")  # salted
    assert not verify_password("x", "md5$abc")
    assert not verify_password("x", "garbage")


def test_production_refuses_unsafe_settings():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(environment="production").check()
    with pytest.raises(RuntimeError, match="SEED_DEMO"):
        Settings(environment="production", jwt_secret="s" * 40, seed_demo=True).check()
    Settings(environment="production", jwt_secret="s" * 40).check()


def test_health_needs_no_auth(client):
    assert client.get("/api/health").json()["status"] == "ok"
