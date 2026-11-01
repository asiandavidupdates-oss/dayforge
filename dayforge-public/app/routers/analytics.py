"""Weekly / monthly analytics, calendar, improvement engine."""
from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import DayRecord, Goal, User
from ..services.progress import day_counts, day_percent

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _days(db, user, start, end):
    return db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.date >= start, DayRecord.date <= end
    ).order_by(DayRecord.date).all()


def _summary(days):
    total = completed = missed = 0
    per_task, per_cat = Counter(), Counter()
    best = lowest = None
    for d in days:
        goals = [g for g in d.goals if not g.on_holiday]
        done, miss, tot = day_counts(d)
        total += tot
        completed += done
        missed += miss
        pct = d.final_percent if d.status != "open" else day_percent(d)
        if tot:
            if best is None or pct > best[1]:
                best = (d.date.isoformat(), pct)
            if lowest is None or pct < lowest[1]:
                lowest = (d.date.isoformat(), pct)
        for g in goals:
            per_task[(g.name, g.completed)] += 1
            per_cat[(g.category, g.completed)] += 1
    pct = round(completed * 100 / total) if total else 0
    return {
        "total_scheduled": total, "total_completed": completed, "total_missed": missed,
        "percent": pct, "best_day": best, "lowest_day": lowest,
        "per_task": [{"name": k[0], "completed": k[1]} for k, v in
                     sorted(per_task.items()) for _ in [0]][:0] or _per_task(per_task),
        "per_category": _per_cat(per_cat),
    }


def _per_task(counter):
    agg = defaultdict(lambda: {"completed": 0, "missed": 0})
    for (name, done), n in counter.items():
        agg[name]["completed" if done else "missed"] += n
    return [{"name": k, **v} for k, v in sorted(agg.items())]


def _per_cat(counter):
    agg = defaultdict(lambda: {"completed": 0, "missed": 0})
    for (name, done), n in counter.items():
        agg[name]["completed" if done else "missed"] += n
    return [{"category": k, **v} for k, v in sorted(agg.items())]


@router.get("/weekly")
def weekly(date_str: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = date.fromisoformat(date_str) if date_str else date.today()
    monday = target - timedelta(days=target.weekday())  # Monday-start week
    sunday = monday + timedelta(days=6)
    days = _days(db, user, monday, sunday)
    by_date = {d.date: d for d in days}
    daily = []
    for i in range(7):
        d = monday + timedelta(days=i)
        rec = by_date.get(d)
        daily.append({"date": d.isoformat(), "weekday": d.strftime("%a"),
                      "percent": (rec.final_percent if rec and rec.status != "open" else day_percent(rec)) if rec else 0,
                      "status": rec.status if rec else "open",
                      "total": day_counts(rec)[2] if rec else 0})
    s = _summary(days)
    confirmed = sum(1 for d in days if d.status == "confirmed")
    auto = sum(1 for d in days if d.status == "auto_confirmed")
    open_n = sum(1 for d in days if d.status == "open")
    return {"week_start": monday.isoformat(), "week_end": sunday.isoformat(),
            "daily": daily, "confirmed_days": confirmed, "auto_confirmed_days": auto,
            "open_days": open_n, **s}


@router.get("/monthly")
def monthly(year: int | None = None, month: int | None = None,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    days = _days(db, user, start, end)
    s = _summary(days)
    # week comparison: group by Monday
    weeks = defaultdict(list)
    for d in days:
        weeks[d.date - timedelta(days=d.date.weekday())].append(d)
    week_cmp = []
    for w_start in sorted(weeks):
        ws = _summary(weeks[w_start])
        week_cmp.append({"week_start": w_start.isoformat(), "percent": ws["percent"],
                         "completed": ws["total_completed"], "total": ws["total_scheduled"]})
    day_pcts = [day_percent(d) if d.status == "open" else (d.final_percent or 0)
                for d in days if [g for g in d.goals if not g.on_holiday]]
    avg = round(sum(day_pcts) / len(day_pcts)) if day_pcts else 0
    consistency = round(len([p for p in day_pcts if p >= 80]) * 100 / len(day_pcts)) if day_pcts else 0
    review = _monthly_review(s, week_cmp, avg, consistency)
    return {"month": f"{year}-{month:02d}", "average_daily_percent": avg,
            "consistency_score": consistency, "week_comparison": week_cmp,
            "review": review, **s}


def _monthly_review(s, weeks, avg, consistency):
    did_well, struggled, improve = [], [], []
    for t in s["per_task"]:
        tot = t["completed"] + t["missed"]
        if tot and t["completed"] / tot >= 0.8:
            did_well.append(t["name"])
        if tot and t["missed"] >= 2:
            struggled.append(t["name"])
            improve.append(f"Try moving or shortening '{t['name']}' — it was missed {t['missed']} times.")
    return {
        "did_well": did_well, "struggled_with": struggled,
        "habits_to_improve": improve,
        "summary": f"Monthly completion {s['percent']}% ({s['total_completed']}/{s['total_scheduled']} goals). "
                   f"Average daily {avg}%, consistency {consistency}%.",
    }


@router.get("/improvements")
def improvements(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rule-based engine over REAL confirmed days only."""
    days = db.query(DayRecord).filter(
        DayRecord.user_id == user.id, DayRecord.status.in_(["confirmed", "auto_confirmed"])
    ).order_by(DayRecord.date).all()
    tips = []
    morning_missed = evening_missed = morning_total = evening_total = 0
    missed_task = Counter()
    for d in days:
        for g in d.goals:
            if g.on_holiday:
                continue
            if g.start_minutes < 12 * 60:
                morning_total += 1
                if not g.completed:
                    morning_missed += 1
            else:
                evening_total += 1
                if not g.completed:
                    evening_missed += 1
            if not g.completed:
                missed_task[g.name] += 1
    if morning_total and morning_missed / morning_total >= 0.4:
        tips.append("You frequently miss morning tasks — try moving exercise 30 minutes later or shortening the first task.")
    if morning_total and evening_total:
        m_rate = 1 - morning_missed / morning_total
        e_rate = 1 - evening_missed / evening_total
        if e_rate < m_rate - 0.2:
            tips.append("Evening productivity is lower than morning — try shortening evening learning or moving it earlier.")
    for name, n in missed_task.most_common(3):
        if n >= 2:
            tips.append(f"You missed '{name}' {n} times — consider a smaller version or a different time slot.")
    if not tips:
        tips.append("No strong pattern yet — keep confirming days and the engine will learn from your real data.")
    return {"tips": tips, "based_on_confirmed_days": len(days)}


@router.get("/calendar")
def calendar(year: int | None = None, month: int | None = None,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    days = _days(db, user, start, end)
    return {"month": f"{year}-{month:02d}",
            "days": [{"date": d.date.isoformat(), "status": d.status,
                      "percent": d.final_percent if d.status != "open" else day_percent(d),
                      "total": day_counts(d)[2]} for d in days]}
