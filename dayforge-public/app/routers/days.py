"""Day records: dashboard day, Complete Day, Undo, plan/copy next day."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Confirmation, DayRecord, Goal, User
from ..schemas import OnboardingIn, ProfileIn
from ..services.progress import (auto_confirm_overdue, check_achievements,
                                 day_dict, ensure_day, finalize_day, level_of,
                                 notify, streak)

router = APIRouter(prefix="/api", tags=["days"])


def _parse(d: str) -> date:
    try:
        return date.fromisoformat(d)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")


@router.post("/onboarding")
def onboarding(payload: OnboardingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name:
        user.name = payload.name
    if payload.age is not None:
        user.age = payload.age
    user.timezone = payload.timezone or user.timezone
    user.notification_prefs = payload.notification_prefs or {}
    user.auto_confirm = payload.auto_confirm
    today = date.today()
    day = ensure_day(db, user, today)
    db.commit()
    return {"user_id": user.id, "day": day_dict(day)}


@router.get("/dashboard")
def dashboard(date_str: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    auto_confirm_overdue(db, user, today)
    db.commit()
    target = _parse(date_str) if date_str else today
    day = ensure_day(db, user, target)
    db.commit()
    confirmations = db.query(Confirmation).filter_by(user_id=user.id, day_id=day.id)\
        .order_by(Confirmation.created_at).all()
    return {
        "today": today.isoformat(), "date": day.date.isoformat(),
        "weekday": day.date.strftime("%A"), "day_number": day.day_number,
        "day": day_dict(day), "streak": streak(db, user), "xp": user.xp,
        "level": level_of(user.xp),
        "confirmations": [{"action": c.action, "final_percent": c.final_percent,
                           "completed": c.completed_count, "incomplete": c.incomplete_count,
                           "at": c.created_at.isoformat()} for c in confirmations],
    }


@router.post("/days/{day_id}/complete")
def complete_day(day_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = db.query(DayRecord).filter_by(id=day_id, user_id=user.id).first()
    if not day:
        raise HTTPException(404, "Day not found")
    if day.status != "open":
        raise HTTPException(400, "Day is already confirmed")
    pct = finalize_day(db, user, day, status="confirmed")
    check_achievements(db, user)
    db.commit()
    return {"day": day_dict(day), "final_percent": pct, "streak": streak(db, user), "xp": user.xp}


@router.post("/days/{day_id}/undo")
def undo_day(day_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = db.query(DayRecord).filter_by(id=day_id, user_id=user.id).first()
    if not day:
        raise HTTPException(404, "Day not found")
    if day.status == "open":
        raise HTTPException(400, "Day is not confirmed")
    # Recompute XP conservatively: undo removes the +50/+25 day bonus.
    if user.xp >= 50:
        user.xp -= 50
        if day.final_percent == 100 and user.xp >= 25:
            user.xp -= 25
    day.status = "open"
    day.final_percent = None
    db.add(Confirmation(user_id=user.id, day_id=day.id, action="undo",
                        final_percent=None, completed_count=0, incomplete_count=0))
    notify(db, user.id, "Confirmation undone", f"{day.date.isoformat()} reopened for editing.")
    db.commit()
    return {"day": day_dict(day)}


@router.post("/days/{day_id}/copy-to-next")
def copy_to_next(day_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Copy this day's goals to the next day, then return the next day.
    The frontend navigates straight to it — that navigation is the feature."""
    day = db.query(DayRecord).filter_by(id=day_id, user_id=user.id).first()
    if not day:
        raise HTTPException(404, "Day not found")
    nxt = ensure_day(db, user, day.date + timedelta(days=1))
    existing = {(g.name, g.start_minutes) for g in nxt.goals}
    pos = max([g.position for g in nxt.goals], default=-1) + 1
    copied = 0
    for g in sorted(day.goals, key=lambda x: x.position):
        if (g.name, g.start_minutes) in existing:
            continue  # duplicates auto-skip
        db.add(Goal(user_id=user.id, day_id=nxt.id, name=g.name,
                    start_minutes=g.start_minutes, end_minutes=g.end_minutes,
                    category=g.category, notes=g.notes, completed=False,
                    on_holiday=False, position=pos))
        pos += 1
        copied += 1
    db.commit()
    return {"copied": copied, "next_day": day_dict(nxt)}


@router.get("/profile")
def profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import UserAchievement
    from ..services.progress import ACHIEVEMENTS
    earned = db.query(UserAchievement).filter_by(user_id=user.id).all()
    total = db.query(Goal).filter_by(user_id=user.id, completed=True).count()
    return {
        "id": user.id, "email": user.email, "name": user.name, "age": user.age,
        "timezone": user.timezone,
        "journey_start_date": user.journey_start_date.isoformat() if user.journey_start_date else None,
        "day_number": (date.today() - user.journey_start_date).days + 1 if user.journey_start_date else None,
        "level": level_of(user.xp), "xp": user.xp, "streak": streak(db, user),
        "total_completed_tasks": total,
        "achievements": [{"code": a.code, "name": ACHIEVEMENTS.get(a.code, a.code),
                          "awarded_at": a.awarded_at.isoformat()} for a in earned],
        "all_achievements": ACHIEVEMENTS,
    }


@router.patch("/profile")
def update_profile(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name is not None:
        user.name = payload.name
    if payload.age is not None:
        user.age = payload.age
    if payload.timezone is not None:
        user.timezone = payload.timezone
    db.commit()
    return {"detail": "Profile saved"}
