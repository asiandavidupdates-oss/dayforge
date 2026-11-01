# DayForge public version — test report

Tested: 2026-11-01, locally (SQLite fallback), on a test user only.
No real user data was touched. No public URL exists.

## Commands run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
SECRET_KEY=<test-only-secret> ALLOW_RESET_TOKEN_IN_RESPONSE=true \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
.venv/bin/python /tmp/test_dayforge.py   # end-to-end API script (curl-equivalent)
curl -s http://127.0.0.1:8123/health
curl -s http://127.0.0.1:8123/ | grep "Morning Walk, Workout, Business Work, Sleep"
```

## Bug found and fixed during testing

- **First run failed:** registration returned HTTP 500. Root cause: passlib
  is incompatible with bcrypt ≥ 4.1 (its backend probe raises
  "password cannot be longer than 72 bytes"). Fix: removed passlib and
  switched `app/auth.py` to direct `bcrypt` hashing/checking (passwords
  truncated to 72 bytes consistently on both sides). `requirements.txt`
  was updated accordingly. After the fix, registration and login work.

## End-to-end results (all passed)

| Step | Result |
|---|---|
| Register `test@example.com` | 200, JWT returned |
| Onboarding (name Tester, age 30, timezone Asia/Karachi) | 200 — Day 1 = 2026-11-01, day_number 1 |
| Add goal "Business Work" 9:38–10:00 AM (custom minute **38** = start_minutes 578) | 200, start_minutes 578 |
| Add goal "Workout" 6:00–7:00 AM marked on holiday | 200, on_holiday true |
| Complete "Business Work" | 200, XP 10 |
| Dashboard progress | **100%**, total counted **1**, on_holiday **1** — holiday goal correctly excluded from % |
| Complete Day | 200, final **100%**, status `confirmed`, streak **1** |
| Confirmation history after confirm | `['confirm']` |
| Undo Confirmation | 200, status back to `open` |
| Confirmation history after undo | `['confirm', 'undo']` — original confirmation preserved, not overwritten |
| Re-complete Day | 200, final 100% |
| Weekly analytics (Monday-start week) | percent **100**, completed **1**, scheduled **1**, confirmed_days **1** |
| Profile | name Tester, age **30**, achievements `first_task`, `first_day`, `perfect_day` |
| Copy this day → next day | copied **2** goals to 2026-11-02 (holiday flag reset for the new day), next day returned for navigation |
| Data isolation: second user `other@example.com` | Own dashboard shows total 0; completing the first user's day returns **404** ("Day not found") |
| Frontend served at `/` | Placeholder `Morning Walk, Workout, Business Work, Sleep…` present; custom-minute input in `app.js` starts empty (`custom.value = ""`) so a leading 0 cannot stick |
| Health check | `{"status":"ok","app":"DayForge"}` |

## What was NOT tested (stated plainly)

- **Postgres in production:** only the SQLite fallback was exercised locally.
  `schema.sql` matches the models and `DATABASE_URL` handling (including
  `postgres://` → `postgresql+psycopg://` conversion) is in the code, but a
  live Render/Railway Postgres deploy was not run — the deployer should
  verify it with the DEPLOYMENT.md checklist.
- **Frontend in a real browser:** the API and the served HTML/JS were
  verified by fetching them, but clicks were not driven in a browser
  (no live-browser tooling in this environment). The custom-minute
  clearability fix is implemented in code (empty initial value, digit-only
  input, backspace/delete clears it) but was not click-tested in a browser.
- **Password-reset email delivery:** no mailer is configured (documented in
  API.md); only the token-creation endpoint logic was implemented, not
  exercised end-to-end in this run.
- **Browser push notifications:** intentionally not implemented (in-app only).
- **Render/Railway deployment itself:** not performed — no hosting account
  was available, and no public URL exists.

## Verdict

Core API flows (auth → onboarding → goal with custom minute 38 → holiday
exclusion → 100% progress → Complete Day lock → Undo with history preserved
→ weekly analytics → profile/achievements → copy-to-next → data isolation)
all pass. The items above are the honest untested remainder.
