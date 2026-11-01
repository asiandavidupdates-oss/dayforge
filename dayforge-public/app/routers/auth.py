"""Auth router: register / login / logout / password recovery."""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import Category, PasswordResetToken, User
from ..schemas import ForgotIn, LoginIn, RegisterIn, ResetIn
from ..services.progress import notify

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

DEFAULT_CATEGORIES = ["Prayer", "Fitness", "Work", "Study", "Personal", "Business", "Learning", "Other"]


@router.post("/register")
@limiter.limit("20/minute")
def register(request: Request, payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(400, "Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password), name=payload.name)
    db.add(user)
    db.flush()
    for name in DEFAULT_CATEGORIES:
        db.add(Category(user_id=user.id, name=name))
    db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/login")
@limiter.limit("20/minute")
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # JWT is stateless: the client discards the token. This endpoint exists
    # so the frontend has an explicit logout action (and a server-side
    # session/revocation list can be added here later).
    return {"detail": "Logged out — discard the token on the client."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "age": user.age,
            "timezone": user.timezone, "journey_start_date":
            user.journey_start_date.isoformat() if user.journey_start_date else None,
            "theme": user.theme, "auto_confirm": user.auto_confirm,
            "notification_prefs": user.notification_prefs, "xp": user.xp}


@router.post("/forgot-password")
@limiter.limit("10/minute")
def forgot(request: Request, payload: ForgotIn, db: Session = Depends(get_db)):
    # Always return the same message so account existence is not leaked.
    user = db.query(User).filter_by(email=payload.email.strip().lower()).first()
    resp = {"detail": "If that email is registered, a reset token has been created. "
                       "Email sending is NOT configured unless SMTP env vars are set (see API.md)."}
    if user:
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(user_id=user.id, token=token,
                                  expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.commit()
        if os.environ.get("ALLOW_RESET_TOKEN_IN_RESPONSE") == "true":
            resp["reset_token"] = token
    return resp


@router.post("/reset-password")
def reset(payload: ResetIn, db: Session = Depends(get_db)):
    row = db.query(PasswordResetToken).filter_by(token=payload.token, used=False).first()
    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired reset token")
    user = db.query(User).filter_by(id=row.user_id).first()
    if not user:
        raise HTTPException(400, "Invalid reset token")
    user.password_hash = hash_password(payload.new_password)
    row.used = True
    notify(db, user.id, "Password changed", "Your password was reset.")
    db.commit()
    return {"detail": "Password reset successful"}
