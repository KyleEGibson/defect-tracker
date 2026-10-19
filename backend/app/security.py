"""Password hashing, JWT access tokens and role checks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Role, User

# scrypt (memory-hard, standard library): N=2^14, r=8, p=1
_N, _R, _P = 2**14, 8, 1
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                dklen=len(base64.b64decode(digest)))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, base64.b64decode(digest))  # constant time


def create_token(user: User, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": user.username, "role": user.role.value, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def get_db(request: Request):
    db: Session = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


_UNAUTHORIZED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                              headers={"WWW-Authenticate": "Bearer"})


def current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    settings = request.app.state.settings
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise _UNAUTHORIZED from None
    user = db.scalar(select(User).where(User.username == claims["sub"]))
    if user is None or not user.active:
        raise _UNAUTHORIZED
    return user


def require(minimum: Role):
    # viewer < engineer < lead < admin
    def check(user: User = Depends(current_user)) -> User:
        if user.role.rank < minimum.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role {minimum.value} or higher")
        return user

    return check
