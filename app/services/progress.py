"""Shared progress / XP / streak / achievement logic."""
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import Confirmation, DayRecord, Goal, Notification, User, UserAchievement

ACHIEVEMENTS = {
    "first_task": "First Task Completed",
    "first_day": "First Day Completed",
    "7_day": "7-Day Consistency",
    "30_day": "30-Day Journey",
    "100_tasks": "100 Tasks Completed",
    "perfect_day": "Perfect Day",
}


def counted_goals(db, day):
    """Goals that count toward %: on-holiday goals are excluded."""
    return [g for g in day.goals if not g.on_holiday]


def day_percent(day) -> int:
    goals = counted_goals(None, day) if False else [g for g in day.goals if not g.on_holiday]
    if not goals:
        return 0
    done = sum(1 for g in goals if g.completed)
    return round(done * 100 / len(goals))


def day_counts(day):
    goals = [g for g in day.goals if not g.on_holiday]
    done = sum(1 for g in goals if g.completed)
    return done, len(goals) - done, len(goals)


def award(db, user, code):
    if db.query(UserAchievement).filter_by(user_id=user.id, code=code).first():
        return False
    db.add(UserAchievement(user_id=user.id, code=code))
    return True


def notify(db, user_id, title, body=""):
    db.add(Notification(user_id=user_id, title=title, body=body))


def check_achievements(db, user):
    """Award achievements from real data only. Call after task/day events."""
    awarded = []
    total_tasks = db.query(Goal).filter_by(user_id=user.id, completed=True).count()
    confirmed_days = db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.status.in_(["confirmed", "auto_confirmed"])
    ).count()
    if total_tasks >= 1 and award(db, user, "first_task"):
        awarded.append("first_task")
    if confirmed_days >= 1 and award(db, user, "first_day"):
        awarded.append("first_day")
    if streak(db, user) >= 7 and award(db, user, "7_day"):
        awarded.append("7_day")
    if user.journey_start_date and (date.today() - user.journey_start_date).days + 1 >= 30 \
            and confirmed_days >= 1 and award(db, user, "30_day"):
        awarded.append("30_day")
    if total_tasks >= 100 and award(db, user, "100_tasks"):
        awarded.append("100_tasks")
    perfect = db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.final_percent == 100
    ).first()
    if perfect and award(db, user, "perfect_day"):
        awarded.append("perfect_day")
    return awarded


def streak(db, user) -> int:
    """Consecutive confirmed days ending at the most recent confirmed day."""
    rows = db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.status.in_(["confirmed", "auto_confirmed"])
    ).order_by(DayRecord.date.desc()).all()
    if not rows:
        return 0
    count, expected = 0, rows[0].date
    for r in rows:
        if r.date == expected:
            count += 1
            expected = expected - timedelta(days=1)
        else:
            break
    return count


def level_of(xp: int) -> int:
    return xp // 100 + 1


def ensure_day(db, user, target: date) -> DayRecord:
    """Get-or-create a day record. Day 1 = journey_start_date."""
    day = db.query(DayRecord).filter_by(user_id=user.id, date=target).first()
    if day:
        return day
    if not user.journey_start_date:
        user.journey_start_date = target
        db.flush()
    number = (target - user.journey_start_date).days + 1
    day = DayRecord(user_id=user.id, date=target, day_number=number)
    db.add(day)
    db.flush()
    return day


def finalize_day(db, user, day, status="confirmed"):
    """Lock a day at its real final %. Unfinished counts as incomplete — never
    falsely marked completed. Appends to confirmation history."""
    done, missed, total = day_counts(day)
    pct = day_percent(day)
    day.status = status
    day.final_percent = pct
    action = "auto_confirm" if status == "auto_confirmed" else "confirm"
    db.add(Confirmation(user_id=user.id, day_id=day.id, action=action,
                        final_percent=pct, completed_count=done, incomplete_count=missed))
    # XP: +50 per completed day, +25 perfect-day bonus, task XP is awarded on toggle.
    user.xp += 50
    if total > 0 and pct == 100:
        user.xp += 25
    notify(db, user.id, "Day completed",
           f"{day.date.isoformat()}: {pct}% ({done}/{total} goals).")
    check_achievements(db, user)
    db.flush()
    return pct


def auto_confirm_overdue(db, user, today: date):
    """If auto_confirm is on, finalize forgotten open days before today."""
    if not user.auto_confirm:
        return []
    done_days = []
    rows = db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.status == "open", DayRecord.date < today
    ).all()
    for day in rows:
        finalize_day(db, user, day, status="auto_confirmed")
        done_days.append(day.date.isoformat())
    return done_days


def goal_dict(g):
    return {
        "id": g.id, "name": g.name, "start_minutes": g.start_minutes,
        "end_minutes": g.end_minutes, "category": g.category, "notes": g.notes,
        "completed": g.completed, "on_holiday": g.on_holiday, "position": g.position,
    }


def day_dict(day):
    goals = sorted(day.goals, key=lambda g: (g.position, g.id))
    done, missed, total = day_counts(day)
    holiday = sum(1 for g in day.goals if g.on_holiday)
    return {
        "id": day.id, "date": day.date.isoformat(), "day_number": day.day_number,
        "status": day.status, "final_percent": day.final_percent,
        "percent": day.final_percent if day.status != "open" else day_percent(day),
        "completed": done, "missed": missed, "total": total, "on_holiday": holiday,
        "goals": [goal_dict(g) for g in goals],
    }
