"""Goals: CRUD, toggle, holiday, reorder, history quick-add."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import DayRecord, Goal, User
from ..schemas import GoalIn, GoalPatch
from ..services.progress import check_achievements, day_dict, goal_dict, notify

router = APIRouter(prefix="/api", tags=["goals"])


def _day_for(db, user, day_id):
    day = db.query(DayRecord).filter_by(id=day_id, user_id=user.id).first()
    if not day:
        raise HTTPException(404, "Day not found")
    return day


def _check_overlap(db, day, start, end, exclude_id=None):
    warnings = []
    for g in day.goals:
        if exclude_id and g.id == exclude_id:
            continue
        if g.on_holiday:
            continue
        if start < g.end_minutes and end > g.start_minutes:
            warnings.append(f"Overlaps with '{g.name}'")
    return warnings


@router.post("/days/{day_id}/goals")
def add_goal(day_id: int, payload: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = _day_for(db, user, day_id)
    if day.status != "open":
        raise HTTPException(400, "Confirmed day is locked — use Undo Confirmation first")
    pos = max([g.position for g in day.goals], default=-1) + 1
    g = Goal(user_id=user.id, day_id=day.id, name=payload.name,
             start_minutes=payload.start_minutes, end_minutes=payload.end_minutes,
             category=payload.category, notes=payload.notes,
             on_holiday=payload.on_holiday, position=pos)
    db.add(g)
    db.flush()
    warnings = _check_overlap(db, day, payload.start_minutes, payload.end_minutes, exclude_id=g.id)
    db.commit()
    return {"goal": goal_dict(g), "overlap_warnings": warnings}


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: int, payload: GoalPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id).first()
    if not g:
        raise HTTPException(404, "Goal not found")
    day = db.query(DayRecord).filter_by(id=g.day_id).first()
    if day and day.status != "open":
        raise HTTPException(400, "Confirmed day is locked — use Undo Confirmation first")
    was_completed = g.completed
    if payload.name is not None:
        g.name = payload.name
    if payload.start_minutes is not None:
        g.start_minutes = payload.start_minutes
    if payload.end_minutes is not None:
        g.end_minutes = payload.end_minutes
    if g.end_minutes <= g.start_minutes:
        raise HTTPException(400, "end must be after start")
    if payload.category is not None:
        g.category = payload.category
    if payload.notes is not None:
        g.notes = payload.notes
    if payload.completed is not None:
        g.completed = payload.completed
    if payload.on_holiday is not None:
        g.on_holiday = payload.on_holiday
        if g.on_holiday:
            g.completed = False
    if payload.completed and not was_completed:
        user.xp += 10
        notify(db, user.id, "Task completed", f"'{g.name}' completed (+10 XP).")
        check_achievements(db, user)
    db.commit()
    return {"goal": goal_dict(g), "xp": user.xp}


@router.post("/goals/{goal_id}/toggle")
def toggle_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id).first()
    if not g:
        raise HTTPException(404, "Goal not found")
    if g.on_holiday:
        raise HTTPException(400, "Goal is on holiday today")
    return patch_goal(goal_id, GoalPatch(completed=not g.completed), user, db)


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id).first()
    if not g:
        raise HTTPException(404, "Goal not found")
    db.delete(g)
    db.commit()
    return {"detail": "Deleted"}


@router.post("/days/{day_id}/goals/reorder")
def reorder(day_id: int, order: list[int], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = _day_for(db, user, day_id)
    for i, gid in enumerate(order):
        g = db.query(Goal).filter_by(id=gid, user_id=user.id, day_id=day.id).first()
        if g:
            g.position = i
    db.commit()
    return {"day": day_dict(day)}


@router.get("/goals/history")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Distinct goals from previous days, most recent first, for one-click re-add."""
    rows = db.query(Goal).filter_by(user_id=user.id).order_by(Goal.created_at.desc()).all()
    seen, out = set(), []
    for g in rows:
        if g.name in seen:
            continue
        seen.add(g.name)
        out.append(goal_dict(g))
    return {"history": out[:50]}


@router.post("/days/{day_id}/goals/quick-add")
def quick_add(day_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = _day_for(db, user, day_id)
    if day.status != "open":
        raise HTTPException(400, "Confirmed day is locked — use Undo Confirmation first")
    src_id = payload.get("source_goal_id")
    src = db.query(Goal).filter_by(id=src_id, user_id=user.id).first() if src_id else None
    if not src:
        raise HTTPException(404, "Source goal not found")
    pos = max([g.position for g in day.goals], default=-1) + 1
    g = Goal(user_id=user.id, day_id=day.id, name=src.name, start_minutes=src.start_minutes,
             end_minutes=src.end_minutes, category=src.category, notes=src.notes,
             completed=False, on_holiday=False, position=pos)
    db.add(g)
    db.commit()
    return {"goal": goal_dict(g)}
