from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Role, User
from ..schemas import TokenOut, UserOut
from ..security import create_token, current_user, get_db, require, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/token", response_model=TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    # same message whether the user exists or not: no account enumeration
    if user is None or not user.active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    return TokenOut(access_token=create_token(user, settings.jwt_secret, settings.token_minutes), user=user)


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db), _: User = Depends(require(Role.viewer))):
    return db.scalars(select(User).where(User.active).order_by(User.full_name)).all()
