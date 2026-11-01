"""Templates, categories, settings, notifications, export/import, search, delete."""
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (Category, DayRecord, Goal, Notification, Template, User)
from ..schemas import CategoryIn, ImportIn, SettingsIn, TemplateIn
from ..services.progress import day_dict, ensure_day, goal_dict

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/settings")
def get_settings(user: User = Depends(get_current_user)):
    return {"theme": user.theme, "auto_confirm": user.auto_confirm,
            "notification_prefs": user.notification_prefs}


@router.patch("/settings")
def patch_settings(payload: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.theme is not None:
        user.theme = payload.theme
    if payload.auto_confirm is not None:
        user.auto_confirm = payload.auto_confirm
    if payload.notification_prefs is not None:
        user.notification_prefs = payload.notification_prefs
    db.commit()
    return {"theme": user.theme, "auto_confirm": user.auto_confirm,
            "notification_prefs": user.notification_prefs}


@router.get("/templates")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"templates": [{"id": t.id, "name": t.name, "goals_json": t.goals_json}
                          for t in db.query(Template).filter_by(user_id=user.id).all()]}


@router.post("/templates")
def create_template(payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = Template(user_id=user.id, name=payload.name, goals_json=payload.goals_json)
    db.add(t)
    db.commit()
    return {"id": t.id, "name": t.name}


@router.post("/templates/{tid}/apply")
def apply_template(tid: int, day_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Template).filter_by(id=tid, user_id=user.id).first()
    day = db.query(DayRecord).filter_by(id=day_id, user_id=user.id).first()
    if not t or not day:
        raise HTTPException(404, "Template or day not found")
    if day.status != "open":
        raise HTTPException(400, "Confirmed day is locked")
    pos = max([g.position for g in day.goals], default=-1) + 1
    for item in t.goals_json:
        db.add(Goal(user_id=user.id, day_id=day.id, name=item.get("name", "Goal"),
                    start_minutes=int(item.get("start_minutes", 540)),
                    end_minutes=int(item.get("end_minutes", 600)),
                    category=item.get("category", "Other"), notes=item.get("notes", ""),
                    completed=False, position=pos))
        pos += 1
    db.commit()
    return {"day": day_dict(day)}


@router.get("/categories")
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"categories": [c.name for c in db.query(Category).filter_by(user_id=user.id).all()]}


@router.post("/categories")
def add_category(payload: CategoryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Category).filter_by(user_id=user.id, name=payload.name).first():
        raise HTTPException(400, "Category already exists")
    db.add(Category(user_id=user.id, name=payload.name))
    db.commit()
    return {"name": payload.name}


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return {"notifications": [{"id": n.id, "title": n.title, "body": n.body,
                               "is_read": n.is_read, "at": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/{nid}/read")
def read_notification(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter_by(id=nid, user_id=user.id).first()
    if n:
        n.is_read = True
        db.commit()
    return {"detail": "ok"}


@router.get("/search")
def search(q: str = "", category: str = "", status: str = "",
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Goal).filter_by(user_id=user.id)
    if q:
        query = query.filter(Goal.name.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)
    if status == "completed":
        query = query.filter_by(completed=True)
    elif status == "pending":
        query = query.filter_by(completed=False)
    rows = query.order_by(Goal.created_at.desc()).limit(200).all()
    return {"results": [goal_dict(g) for g in rows]}


@router.get("/export/csv", response_class=PlainTextResponse)
def export_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "day_number", "goal", "category", "start", "end", "completed", "on_holiday"])
    for g in db.query(Goal).filter_by(user_id=user.id).order_by(Goal.created_at).all():
        day = db.query(DayRecord).filter_by(id=g.day_id).first()
        w.writerow([day.date.isoformat() if day else "", day.day_number if day else "",
                    g.name, g.category,
                    f"{g.start_minutes // 60}:{g.start_minutes % 60:02d}",
                    f"{g.end_minutes // 60}:{g.end_minutes % 60:02d}",
                    g.completed, g.on_holiday])
    return buf.getvalue()


@router.get("/export/json")
def export_json(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    days = db.query(DayRecord).filter_by(user_id=user.id).order_by(DayRecord.date).all()
    return {"user": {"name": user.name, "age": user.age, "timezone": user.timezone,
                     "journey_start_date": user.journey_start_date.isoformat() if user.journey_start_date else None},
            "days": [day_dict(d) for d in days]}


@router.post("/import/json")
def import_json(payload: ImportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = payload.data
    restored = 0
    for d in data.get("days", []):
        from datetime import date as _date
        try:
            target = _date.fromisoformat(d["date"])
        except Exception:
            continue
        day = ensure_day(db, user, target)
        for item in d.get("goals", []):
            db.add(Goal(user_id=user.id, day_id=day.id, name=item.get("name", "Goal"),
                        start_minutes=int(item.get("start_minutes", 540)),
                        end_minutes=int(item.get("end_minutes", 600)),
                        category=item.get("category", "Other"),
                        notes=item.get("notes", ""), completed=bool(item.get("completed", False)),
                        on_holiday=bool(item.get("on_holiday", False)), position=restored))
            restored += 1
    db.commit()
    return {"restored_goals": restored}


@router.delete("/account")
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(user)
    db.commit()
    return {"detail": "Account and all data deleted"}
