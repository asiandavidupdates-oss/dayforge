# Deploying DayForge publicly — step by step

> No public URL exists yet. These steps create one. What the deployer still
> needs: **a hosting account** (Render or Railway, free tier works to start).
> A custom domain is **optional** — Render/Railway give you a free public URL.

## Option A — Render (recommended, single service)

`render.yaml` in this repo already describes the web service + Postgres
database (Infrastructure as Code).

1. Push this folder to a GitHub repository (do **not** include `.env` or any
   `*.db` file — `.gitignore` already excludes them).
2. Go to https://dashboard.render.com → **New → Blueprint** → connect the repo.
   Render reads `render.yaml` and creates:
   - a **Web Service** (`dayforge`, Docker) and
   - a **Postgres database** (`dayforge-db`), wiring `DATABASE_URL` automatically.
   - `SECRET_KEY` is auto-generated (`generateValue: true`).
3. Wait for the first deploy to finish (a few minutes). The service log should
   show `Application startup complete` and `Uvicorn running on ...`.
4. Open the public URL Render shows (like `https://dayforge-xxxx.onrender.com`).
   Register a new account, complete onboarding, and add a goal to confirm it
   works. Your old Muse-artifact data does **not** transfer automatically —
   export JSON from the old app and use Settings → Restore if you want it back.
5. (Optional) Add a custom domain in Render → service → Settings → Custom
   Domains, and point your DNS there.

Free-tier notes: Render's free web service sleeps after inactivity, so the
first load after a pause can take ~30–60 seconds. Paid plans avoid this.

## Option B — Railway (alternative)

1. Push the folder to GitHub.
2. Railway → **New Project → Deploy from GitHub** → select the repo.
3. Add a **Postgres** service to the same project.
4. On the web service, set variables:
   - `SECRET_KEY` = a long random string (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `DATABASE_URL` = the Postgres connection string Railway shows
     (use the internal URL if Railway offers one).
5. Railway deploys the `Dockerfile` automatically and gives you a public URL
   (generate one under Settings → Networking if it does not appear).

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes (production) | Signs JWT tokens. Long random string. Never share it. |
| `DATABASE_URL` | Yes (production) | Postgres URL, e.g. `postgresql://user:pass@host:5432/dayforge`. Leave unset locally for SQLite. |
| `ALLOW_RESET_TOKEN_IN_RESPONSE` | No | `true` only for local testing — makes forgot-password return the reset token. Keep unset/false in production. |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | No | Reserved for a future mailer. Password-reset emails are NOT sent today (see API.md). |

## After deployment — checklist

- [ ] Open the public URL, register, onboard, add a goal, complete the day.
- [ ] Confirm the dashboard, weekly report, and profile show real numbers.
- [ ] Check the database service is running (Render/Railway dashboard).
- [ ] Back up regularly: Settings → Backup JSON in the app, plus your
      host's database backups.
- [ ] If you add a custom domain, force HTTPS (on by default on both hosts).

## What is NOT included

- A mobile app / APK / Play Store listing (that is a separate build and
  store process, not produced here).
- Browser push notifications (in-app only; a push server would need to be
  added by the deployer).
- Email delivery for password resets (token endpoint only; see API.md).
