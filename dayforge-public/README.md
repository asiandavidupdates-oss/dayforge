# DayForge — Public Version (source code only, NOT deployed yet)

DayForge is a daily productivity & achievement web app: build a daily routine
with start/end times, track completion, confirm each day, grow streaks and XP,
and review weekly/monthly analytics.

> **This delivery is source code + deployment instructions only. It is NOT
> already live on a public URL.** Follow `DEPLOYMENT.md` to put it online.
> Nothing here contains a real secret, password, or token.

## What it is — adaptation note

The original plan called for separate Next.js + FastAPI services. This public
version is **one deployable FastAPI service that serves both the API and the
frontend** (vanilla HTML/CSS/JS, no build step). That keeps public deployment
to a single service (e.g. Render) while preserving the features: auth,
onboarding, daily routine, Complete Day + Undo, history quick-add, plan/copy
next day, profile, holiday goals, weekly/monthly analytics, achievements,
calendar, templates, categories, settings, export/backup, and in-app
notifications.

Differences from the Muse-artifact version the user already uses:
- Real multi-user accounts with password login (JWT), per-user data isolation.
- Data lives in Postgres in production (SQLite fallback for local dev only).
- Browser push is **not** promised: notifications are in-app only unless the
  deployer adds a push server later.
- Password recovery is token-based; email sending is **not** configured
  (see `API.md`). With `ALLOW_RESET_TOKEN_IN_RESPONSE=true` (dev only) the
  forgot-password endpoint returns the token for testing.

## Design (premium restyle, 2026-11-01)

Only the frontend was restyled (`app/static/index.html`, `styles.css`,
`app.js`): premium card layout, desktop sidebar with the profile strip
under the DayForge name, an animated SVG progress ring, streak/XP pills,
time/category chips, holiday badges, CSS confetti + toast on Complete Day,
and a mobile bottom navigation — matching the Muse-artifact app's feel as
closely as possible with plain CSS/JS. The backend and API are unchanged,
all element IDs and API calls still work, and the custom-minute field
still starts empty and is fully clearable. Deploying is unchanged: push
the `app/static/` changes to GitHub and Render redeploys. Full test
results are in `RESTYLE_TEST_REPORT.md`.

## Features

- **Auth:** register, login, logout, JWT, bcrypt password hashing, per-user
  isolation on every query, rate-limited auth endpoints.
- **Onboarding:** name, age, timezone, notification preferences; the first
  login/local date becomes Day 1 and that day's record is auto-created.
- **Dashboard:** date, Day number, weekday, live clock, progress %, streak,
  XP/level, Previous/Next Day navigation.
- **Daily Routine:** unlimited Add Goal, 12-hour AM/PM pickers with a
  **Custom minute option** — the custom field starts empty (never a stuck
  `0`), can be fully cleared with backspace/delete, and accepts any minute
  0–59 (e.g. 38). Auto duration, invalid-range validation, overlap warnings,
  category, notes, edit/delete/reorder, instant progress on checkbox toggle.
  Zero-task days show 0% (no divide-by-zero).
- **History quick-add:** goals from previous days listed when adding, one
  click re-adds them.
- **Complete Day:** confirmation dialog with completed/incomplete counts and
  final %; locks the day, celebrates, updates XP/streak/analytics.
  **Undo Confirmation** is clearly visible, reopens the day, keeps an
  append-only confirmation history, and recalculates on re-confirm — history
  is never silently overwritten.
- **Plan next day:** after Complete Day, "Plan next day" and "Copy this day"
  copy goals to the next day and **navigate straight to that next day**
  (duplicates auto-skip; holiday flags reset for the new day).
- **Profile:** under the DayForge name — name, age, Day number, Level, XP,
  timezone, journey start; a dedicated Profile page edits name/age/timezone.
- **Holiday:** any goal can be marked "on holiday" for its day (button or
  Add/Edit checkbox). It stays in the routine with an amber "On holiday"
  badge but is excluded from that day's %, totals, streak/XP and
  weekly/monthly stats. "End holiday" restores it.
- **Analytics:** Monday-start weekly (totals, best/lowest day, daily chart
  data, per-task/per-category, confirmed vs auto-confirmed vs open) and
  monthly (%, totals, average, best/weakest day, week comparison, trends,
  consistency score, personal records, written monthly review). A rule-based
  improvement engine uses **only real confirmed data**.
- **Achievements/XP/streaks:** First Task Completed, First Day Completed,
  7-Day Consistency, 30-Day Journey, 100 Tasks Completed, Perfect Day.
  Task completion +10 XP, day completion +50 XP, perfect day +25 XP bonus.
- **Calendar, search & filters** (category/date/status), routine templates
  (save/apply), custom categories.
- **Settings:** Light / Dark / System theme switch (applies instantly and
  persists), notification toggles, auto day confirmation setting. If enabled,
  a forgotten previous day auto-finalizes as "Automatically Confirmed"
  counting unfinished as incomplete — never marking unfinished as completed.
  If disabled, the unconfirmed record is preserved.
- **Data:** CSV export, JSON backup/restore, full account/data deletion.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit SECRET_KEY
uvicorn app.main:app --reload --port 8000
# Open http://127.0.0.1:8000
```

With Docker Compose (Postgres + app):

```bash
docker compose up --build
# Open http://127.0.0.1:8000
```

## Project layout

```
app/
  main.py            # app factory, CORS, rate-limit handler, static serving
  database.py        # engine/session (Postgres via DATABASE_URL, SQLite fallback)
  models.py          # SQLAlchemy models (mirrors schema.sql)
  schemas.py         # Pydantic validation
  auth.py            # bcrypt hashing + JWT
  services/progress.py  # %, XP, streak, achievements, finalize/undo, auto-confirm
  routers/
    auth.py          # register/login/logout/me/password reset
    days.py          # onboarding, dashboard, complete/undo, copy-to-next, profile
    goals.py         # goal CRUD, toggle, holiday, reorder, history, quick-add
    analytics.py     # weekly, monthly, improvements, calendar
    misc.py          # templates, categories, settings, notifications, export/import, search
  static/            # frontend: index.html, styles.css, app.js (no build step)
schema.sql           # PostgreSQL DDL
Dockerfile  docker-compose.yml  render.yaml  .env.example
README.md  DEPLOYMENT.md  API.md  TEST_REPORT.md
```

## Security notes

- Secrets only via environment variables (`SECRET_KEY`, `DATABASE_URL`).
- All queries are filtered by the authenticated user.
- Pydantic validation on inputs; end time must be after start time.
- Auth endpoints are rate-limited (slowapi); security headers are set.
- In production, serve behind HTTPS (Render/Railway do this by default) and
  set a long random `SECRET_KEY`. Never commit a real `.env`.
