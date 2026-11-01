# DayForge API

Base URL: `/` (frontend) and `/api/...` (JSON). Auth: `Authorization: Bearer <JWT>`
from login/register. Every endpoint filters by the authenticated user — a user
can never read or modify another user's days, goals, or settings (verified in
TEST_REPORT.md).

## Auth — `/api/auth`

| Method & path | Body | Notes |
|---|---|---|
| POST `/api/auth/register` | `{email, password (≥8), name}` | Creates user + default categories. Returns JWT. Rate-limited. |
| POST `/api/auth/login` | `{email, password}` | Returns JWT. Rate-limited. |
| POST `/api/auth/logout` | — | JWT is stateless: client discards the token. |
| GET `/api/auth/me` | — | Current user (name, age, timezone, theme, xp, …). |
| POST `/api/auth/forgot-password` | `{email}` | Always returns the same message (no account-enumeration leak). Creates a 1-hour reset token. **Email is NOT sent** unless a mailer is added; with `ALLOW_RESET_TOKEN_IN_RESPONSE=true` (dev only) the token is returned in the response for testing. In production, wire an SMTP mailer to this endpoint. |
| POST `/api/auth/reset-password` | `{token, new_password (≥8)}` | Consumes the token (single use). |

## Onboarding / dashboard / days — `/api`

| Method & path | Notes |
|---|---|
| POST `/api/onboarding` | `{name?, age?, timezone, notification_prefs, auto_confirm}`. First date becomes Day 1; today's record is auto-created. |
| GET `/api/dashboard?date_str=YYYY-MM-DD` | Date, weekday, Day number, day record, %, streak, XP/level, append-only confirmation history. Also auto-confirms overdue open days if the user enabled auto-confirm. |
| POST `/api/days/{id}/complete` | Locks the day at its real final %. Errors if already confirmed. |
| POST `/api/days/{id}/undo` | Reopens a confirmed day; appends an `undo` entry to history; day bonus XP is removed. |
| POST `/api/days/{id}/copy-to-next` | Copies the day's goals to the next day (duplicates skipped, holiday reset) and **returns the next day** — the frontend navigates straight to it. |
| GET `/api/profile` / PATCH `/api/profile` | Full profile (name, age, Day number, Level, XP, timezone, journey start, achievements, total completed tasks); PATCH edits name/age/timezone. |

## Goals — `/api`

| Method & path | Notes |
|---|---|
| POST `/api/days/{id}/goals` | `{name, start_minutes, end_minutes, category, notes, on_holiday}`. Validates end > start. Returns `overlap_warnings` (warnings only, not a rejection). Locked days reject with 400. |
| PATCH `/api/goals/{id}` | Partial update; `completed: true` awards +10 XP and may award First Task. Setting `on_holiday: true` clears completion. |
| POST `/api/goals/{id}/toggle` | Flips completion (refuses for on-holiday goals). |
| DELETE `/api/goals/{id}` | Deletes the goal. |
| POST `/api/days/{id}/goals/reorder` | Body: ordered list of goal ids. |
| GET `/api/goals/history` | Distinct past goals, most recent first (one-click re-add source). |
| POST `/api/days/{id}/goals/quick-add` | `{source_goal_id}` — adds a copy of a past goal to the day. |

## Analytics — `/api/analytics`

| Method & path | Notes |
|---|---|
| GET `/api/analytics/weekly?date_str=…` | Monday-start week: daily %, confirmed/auto/open counts, totals, best/lowest day, per-task and per-category records. |
| GET `/api/analytics/monthly?year=&month=` | Monthly %, average daily %, consistency score, best/weakest day, week comparison, written monthly review (did well / struggled / habits to improve). |
| GET `/api/analytics/improvements` | Rule-based tips from **confirmed days only** (morning misses, evening vs morning, repeatedly missed tasks). |
| GET `/api/analytics/calendar?year=&month=` | Per-day status + % for the month. |

## Misc — `/api`

| Method & path | Notes |
|---|---|
| GET/PATCH `/api/settings` | `{theme: light\|dark\|system, auto_confirm, notification_prefs}`. |
| GET/POST `/api/templates`, POST `/api/templates/{id}/apply?day_id=` | Save a routine; apply it to a day. |
| GET/POST `/api/categories` | Custom categories (defaults seeded at registration). |
| GET `/api/notifications`, POST `/api/notifications/{id}/read` | In-app notifications only. |
| GET `/api/search?q=&category=&status=` | Search goals by name/category/status. |
| GET `/api/export/csv`, GET `/api/export/json` | Download all goals / full backup. |
| POST `/api/import/json` | `{data}` — restore a JSON backup. |
| DELETE `/api/account` | Deletes the user and all their data (cascade). |

## Health

`GET /health` → `{"status": "ok", "app": "DayForge"}` (no auth).
