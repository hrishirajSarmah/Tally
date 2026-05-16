# AtomQuest Hackathon 1.0 — Build Brief

> This document is the single source of truth for building the **Goal Setting & Tracking Portal** for AtomQuest Hackathon 1.0. Solo developer, ~72-hour weekend build.

---

## 1. Project context

**What we're building:** A web-based internal HR portal where employees set yearly goals, managers approve them, and everyone updates progress quarterly. Replaces spreadsheet-and-email performance management.

**Three user roles, each with a complete journey:**
- **Employee** — creates goals, logs quarterly progress
- **Manager (L1)** — approves/edits team goals, runs check-ins, leaves feedback
- **Admin / HR** — configures cycles, manages org hierarchy, unlocks locked goals, sees audit logs

**Build constraints:**
- Solo dev, 72-hour weekend
- Must deploy a live demo URL (web-browser-accessible)
- Must submit: hosted URL, Git repo, architecture diagram (PDF/image), credentials for all three roles, live demo

---

## 2. Judging criteria (6 equal-weight)

1. **End-to-end functionality** — every must-have works
2. **BRD adherence** — validation rules enforced exactly
3. **UI friendliness** — non-technical users can navigate
4. **Bug-resilience** — edge cases don't break it
5. **Depth of bonus features** — quality over quantity
6. **Cost optimization** — infra choices, API efficiency, caching, hosting cost awareness

> **Strategic note:** Criterion 6 is unusual for hackathons. Most teams will ignore it. Document infra cost explicitly in the README — it's a free 1/6 of the grade.

---

## 3. Tech stack (decided, don't second-guess mid-build)

### Backend
- **FastAPI** + **SQLModel** + **Alembic** (migrations)
- **PostgreSQL** via **Neon** (serverless, free tier)
- **APScheduler** for cycle window enforcement (NOT Celery/Redis — overkill)
- **Pydantic v2** for validation

### Frontend
- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** (copy-paste components, no design work)
- **TanStack Query** (data fetching, caching, optimistic updates)
- **NextAuth** with credentials provider (3 seeded users)
- **React Hook Form** + **Zod** for form validation

### Hosting
- **Vercel** — frontend (free hobby tier)
- **Railway** — FastAPI backend ($5 credit covers hackathon)
- **Neon** — Postgres (free tier)

### Notifications (bonus module)
- **Resend** — transactional email (3K/month free)
- **Microsoft Teams Incoming Webhook** — adaptive cards (zero auth)

### Tools
- **uv** for Python dependency management
- **pnpm** for Node
- **draw.io** or **excalidraw** for architecture diagram

### Stack rationale (one paragraph)
FastAPI for backend velocity given existing Python familiarity. shadcn/ui chosen specifically as the biggest UI velocity multiplier for a frontend-weaker solo dev — copy-paste accessible components, no design work needed. Neon over Supabase for better cold-start; we don't need Supabase's auth or storage. Resend over SendGrid for cleaner API. Teams webhooks chosen over full Graph API because zero-auth and instantly demo-able.

---

## 4. Scope decisions (read carefully)

### Must-have (Hour 0–48, non-negotiable)
All Phase 1 + Phase 2 + audit trail + CSV export + three role dashboards.

### Bonus pick: Email + Teams (Hour 48–60)
**One bonus, done well**, beats two half-done. Choosing Email + Teams because:
- Demonstrable live during demo (Teams card popping up is visceral)
- Resend setup is ~30 min, Teams webhook is ~15 min
- High judge-visible payoff per hour invested

### Explicitly skipped
- **Azure AD SSO** — needs tenant config, app registration, group claims; 8–12 hours of fragile setup for invisible-to-judges payoff
- **Rule-based escalation engine** — adds complexity, low demo wow
- **Advanced analytics** — basic dashboard covers criterion 1; deep analytics is a separate 10-hour module

If time remains after Hour 60, add a single analytics chart to the admin dashboard (QoQ completion rate). Not before.

---

## 5. Data model

Six tables. Get this right on day one; Phase 2 writes itself.

### `users`
```
id: UUID PK
email: str unique
name: str
password_hash: str          # bcrypt, only for seeded demo users
role: enum (employee, manager, admin)
manager_id: UUID FK → users.id (nullable, self-ref)
department: str
created_at: timestamptz
```

### `cycles`
```
id: UUID PK
name: str                   # e.g. "FY26"
goal_setting_opens: date    # May
q1_opens: date              # July
q2_opens: date              # October
q3_opens: date              # January
q4_opens: date              # March/April (annual + Q4)
current_phase: enum (closed, goal_setting, q1, q2, q3, q4_annual)
is_active: bool
```

### `thrust_areas`
```
id: UUID PK
name: str                   # seeded list
```

### `goals`
```
id: UUID PK
employee_id: UUID FK → users.id
cycle_id: UUID FK → cycles.id
thrust_area_id: UUID FK → thrust_areas.id
title: str
description: text
uom_type: enum (numeric_min, numeric_max, percent_min, percent_max, timeline, zero)
target_value: decimal (nullable for timeline/zero)
target_date: date (nullable, only for timeline)
weightage: int              # 10..100, integer percent
status: enum (draft, submitted, approved, locked)
shared_parent_id: UUID FK → goals.id (nullable, self-ref)
manager_comment: text (nullable)
created_at, updated_at: timestamptz
```

### `achievements`
```
id: UUID PK
goal_id: UUID FK → goals.id
quarter: enum (q1, q2, q3, q4)
actual_value: decimal (nullable)
actual_date: date (nullable)
status: enum (not_started, on_track, completed)
manager_comment: text (nullable)
created_at, updated_at: timestamptz

UNIQUE(goal_id, quarter)
```

### `audit_log`
```
id: UUID PK
goal_id: UUID FK → goals.id
user_id: UUID FK → users.id
action: str                 # "edit_after_lock", "unlock", "approve", etc.
field_changed: str (nullable)
old_value: text (nullable)
new_value: text (nullable)
timestamp: timestamptz

INDEX (goal_id, timestamp DESC)
```

### Shared-goal mechanic
`shared_parent_id` points to the primary owner's goal. When achievement is updated on the parent, a backend task copies `actual_value` and `status` to all children. On children: `title`, `description`, `target_value` are read-only; only `weightage` is editable per-employee. This is a flagship BRD requirement — judges will check it.

---

## 6. Validation rules (these are scored)

Enforce on backend; mirror on frontend for UX.

### Goal creation
- Maximum 8 goals per employee per cycle
- Each goal weightage ≥ 10%
- Total weightage of all goals = exactly 100%
- Cannot submit goals outside `goal_setting` phase

### UoM-specific
- `numeric_min`, `numeric_max`, `percent_min`, `percent_max`: require `target_value`
- `timeline`: require `target_date`
- `zero`: no target required

### Lock state
- Once `status = locked`, only Admin can unlock
- Any edit to a locked goal → write `audit_log` entry
- Manager can edit during `submitted` state, before approval

### Check-in windows
- Q1 check-ins only writable when `current_phase = q1`
- Same for q2, q3, q4_annual
- Backend rejects with 403 + clear error message outside window

### Implementation tip
Build a single FastAPI dependency `require_active_phase(allowed_phases: list)` and apply it to every check-in endpoint. Frontend reads phase from `/api/cycle/current` and disables UI accordingly.

---

## 7. Progress score formulas

Computed on read, not stored. Tracking only — NOT used for ratings.

```python
def progress_score(uom_type, target, actual, target_date=None, actual_date=None):
    if uom_type in ("numeric_min", "percent_min"):
        # higher is better
        return min(actual / target, 1.0) * 100 if target else 0

    if uom_type in ("numeric_max", "percent_max"):
        # lower is better
        return min(target / actual, 1.0) * 100 if actual else 0

    if uom_type == "timeline":
        # completed on or before target_date = 100%, else 0
        if actual_date and actual_date <= target_date:
            return 100
        return 0

    if uom_type == "zero":
        # achievement is binary: actual == 0 → 100, else 0
        return 100 if actual == 0 else 0
```

---

## 8. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Employee, Manager, Admin sessions)                │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Next.js 14 on Vercel                                       │
│  - App Router, server components for dashboards             │
│  - shadcn/ui + Tailwind                                     │
│  - TanStack Query for client data fetching                  │
│  - NextAuth credentials provider                            │
│  - Role-based middleware (employee | manager | admin)       │
└────────────────────────────┬────────────────────────────────┘
                             │ REST + JWT
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI on Railway                                         │
│  - SQLModel + Alembic                                       │
│  - JWT auth, RBAC via dependencies                          │
│  - Validation: Pydantic + business rules                    │
│  - APScheduler: window enforcement, reminder cron           │
│  - CSV/Excel export via StreamingResponse                   │
│  - Audit logger as SQLAlchemy event listener                │
└──────┬───────────────────┬──────────────────┬───────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
┌─────────────┐     ┌──────────────┐    ┌──────────────────┐
│ Neon        │     │ Resend       │    │ Teams webhook    │
│ Postgres    │     │ Email API    │    │ Adaptive cards   │
│ Append-only │     │ Submission,  │    │ Manager pings on │
│ audit log   │     │ approval,    │    │ submission,      │
│             │     │ reminders    │    │ approval         │
└─────────────┘     └──────────────┘    └──────────────────┘
```

> Export this diagram as a polished version using draw.io or excalidraw for the submission. Save as `docs/architecture.pdf`.

---

## 9. API surface (target shape)

Not exhaustive; implement as needed.

### Auth
- `POST /api/auth/login` → JWT
- `GET /api/auth/me` → current user + role

### Cycles
- `GET /api/cycles/current` → active cycle + current_phase
- `POST /api/cycles` (admin) → create cycle
- `PATCH /api/cycles/{id}/phase` (admin) → manually advance phase (for demo)

### Goals
- `GET /api/goals/mine` (employee)
- `GET /api/goals/team` (manager) → all reports' goals
- `GET /api/goals/all` (admin)
- `POST /api/goals` (employee, only in goal_setting phase)
- `PATCH /api/goals/{id}` (employee if draft; manager if submitted; admin always)
- `POST /api/goals/{id}/submit` (employee)
- `POST /api/goals/{id}/approve` (manager) → triggers lock
- `POST /api/goals/{id}/unlock` (admin)
- `POST /api/goals/shared` (manager) → create one goal pushed to N employees

### Achievements (check-ins)
- `GET /api/achievements/goal/{goal_id}`
- `PUT /api/achievements/{goal_id}/{quarter}` (employee, only in matching phase)
- `PATCH /api/achievements/{goal_id}/{quarter}/comment` (manager)

### Reporting
- `GET /api/reports/achievement.csv` → streaming CSV export
- `GET /api/reports/dashboard` → completion stats by status, by team
- `GET /api/audit/{goal_id}` (admin) → audit trail

### Notifications (bonus)
- `POST /api/notifications/test` (admin) → fire test email + Teams card

---

## 10. Build plan (72-hour breakdown)

Assuming ~58 productive hours after sleep.

### Hour 0–4: Foundation
- [ ] `create-next-app` with TS + Tailwind + App Router
- [ ] FastAPI repo: `uv init`, install fastapi/sqlmodel/alembic/passlib/python-jose
- [ ] Create Neon project, copy connection string
- [ ] Deploy hello-world to Vercel + Railway **immediately** (broken deploys at hour 60 are the classic killer)
- [ ] Set up environment variables: `DATABASE_URL`, `JWT_SECRET`, `RESEND_API_KEY`, `TEAMS_WEBHOOK_URL`
- [ ] Initialize Git repo, push to GitHub

### Hour 4–12: Auth + data model + seeds
- [ ] Define all 6 SQLModel tables
- [ ] First Alembic migration, run against Neon
- [ ] Seed script: 3 users (employee@demo, manager@demo, admin@demo, password "demo"), 1 active cycle, thrust areas
- [ ] FastAPI JWT auth + `require_role` dependency
- [ ] NextAuth credentials provider hitting `/api/auth/login`
- [ ] Role-based middleware in Next.js `middleware.ts`
- [ ] Login page, redirect by role

### Hour 12–28: Phase 1 — Goal creation & approval
- [ ] Employee goal-creation form with **real-time weightage validation** (sum to 100, min 10, max 8 — show running total as user types)
- [ ] UoM-conditional fields (target_value vs target_date vs nothing)
- [ ] Backend validation matching frontend
- [ ] Submit → status transitions to `submitted`
- [ ] Manager approval queue with inline edit
- [ ] Approve → status transitions to `locked`
- [ ] Shared goals: manager can create one goal, push to multiple employees
- [ ] Test edge cases: 7 goals → can add one more; 8 goals → blocked; weightage 99/101 → blocked

> **Budget 4 hours for weightage validation alone.** Real-time sum-to-100 across a dynamic list with inline edits is fiddly React. Don't underestimate.

### Hour 28–40: Phase 2 — Quarterly check-ins
- [ ] Employee check-in interface (per quarter, per goal)
- [ ] Status enum (not_started, on_track, completed)
- [ ] Manager check-in view: planned vs actual side-by-side, comment field
- [ ] Implement 4 progress score formulas, expose via API
- [ ] Cycle window enforcement: `require_active_phase` dependency on every check-in endpoint
- [ ] Admin "advance phase" button to demo Q1 → Q2 transition

### Hour 40–48: Reporting, audit, admin
- [ ] CSV export endpoint using FastAPI `StreamingResponse`
- [ ] Completion dashboard: counts by status, grouped by team
- [ ] Audit log: SQLAlchemy event listener that fires on every post-lock mutation, writes one row
- [ ] Admin cycle config UI
- [ ] Admin "unlock goal" action with mandatory reason field
- [ ] Audit log viewer page (admin only)

### Hour 48–60: Bonus — Email + Teams
- [ ] Resend account, API key
- [ ] Email templates: goal submitted, goal approved, check-in reminder
- [ ] Trigger on relevant state transitions (background task, don't block API response)
- [ ] Teams Incoming Webhook URL (create test channel in personal tenant)
- [ ] Adaptive card JSON for goal submission notification
- [ ] Admin "trigger reminder now" button for live demo

### Hour 60–72: Polish + submission
- [ ] README with screenshots, setup instructions, demo credentials
- [ ] Architecture diagram exported as PDF
- [ ] Demo script: write verbatim, time it, rehearse twice
- [ ] Smoke test every flow end-to-end
- [ ] Backup database before demo day
- [ ] Final deploy + sanity check

---

## 11. Cost optimization talking points

Document in README. This is criterion 6 — 1/6 of the grade.

**Hackathon-scale: $0/month**
- Vercel hobby (free)
- Railway $5 credit (free trial)
- Neon free tier (0.5 GB storage, 100 hours compute)
- Resend free tier (3K emails/month)
- Teams webhook (free)

**Production-scale projection (1000 employees, ~50K API calls/month): ~$50/month**
- Neon Scale: $19
- Railway: $10
- Resend Pro: $20
- Vercel still free

**Optimizations built in**
- Audit log: append-only with composite index `(goal_id, timestamp DESC)` — query cost flat as log grows
- Completion dashboard: materialized aggregations refreshed every 5 min via APScheduler, not full table scan per request — drops dashboard load from O(goals) to O(1)
- Goal lists: TanStack Query client cache + ETag headers — repeat reads hit cache, not API
- CSV export: streaming response — constant memory regardless of row count
- No background worker service — APScheduler runs in-process inside FastAPI, saving the cost of a separate Redis + Celery worker

---

## 12. Submission checklist

- [ ] Hosted demo URL accessible from any browser
- [ ] Git repo link (public)
- [ ] Architecture diagram PDF at `docs/architecture.pdf`
- [ ] README with: setup, demo credentials, feature list, cost analysis
- [ ] Three working logins (employee, manager, admin) or a role-switcher
- [ ] Demo script tested and timed (target: 5 minutes)
- [ ] All must-haves verified working in production deploy, not just localhost

---

## 13. Risk register (things that will trip me up)

1. **Weightage validation eats 4+ hours** — start it early, don't over-engineer, use React Hook Form's `watch` for running totals.
2. **Cycle window enforcement is easy to forget** — bake it into a FastAPI dependency, not just frontend. Judges will curl the API.
3. **The demo is half the grade** — last 4 hours go to demo prep, not features. Scripted, timed, rehearsed.
4. **Audit log via event listener is the cleanest implementation** — implementing per-endpoint is error-prone and easy to miss spots.
5. **Don't deploy late** — push to prod every 4 hours. Local-only demos fail at hackathons.
6. **Shared goals is the BRD-flagship feature** — judges will specifically test it. Don't skip.

---

## 14. Supply chain security (non-negotiable)

Recent npm and PyPI compromises (Shai-Hulud worm, GlueStack, ongoing PyPI typosquats) make fresh package versions actively dangerous. **Apply the 5-day rule to every dependency.**

### The 5-day rule
- **Never install a package version released within the last 5 days.**
- This applies to direct deps AND transitive deps that get pulled in.
- Trade-off accepted: we forgo the newest features in exchange for not being patient-zero for a compromise. Worth it.

### Before installing anything

**For npm:**
```bash
# Check release date before installing
npm view <package> time --json | tail -20
# Look at the latest version's timestamp. If < 5 days ago, pin to the previous version.
```

**For pip:**
```bash
# Use pip index, or check PyPI JSON API
pip index versions <package>
curl -s https://pypi.org/pypi/<package>/json | jq '.releases | keys[-3:]'
# Cross-reference with PyPI release history page.
```

### Pinning strategy

**package.json:** Use exact versions, not `^` or `~`. Hand-pick versions released > 5 days ago.
```json
{
  "dependencies": {
    "next": "14.2.18",            // NOT "^14.2.18"
    "@tanstack/react-query": "5.59.20"
  }
}
```

**Python (uv):** Pin exact versions in `pyproject.toml`. Generate `uv.lock` and commit it.
```toml
[project]
dependencies = [
    "fastapi==0.115.5",          # exact, not >=
    "sqlmodel==0.0.22",
]
```

### Verification steps before each install

1. Check version release date (`npm view` / PyPI JSON API)
2. Confirm > 5 days old
3. Scan recent advisories: `npm audit` or `pip-audit` after install
4. For high-risk packages (auth, crypto, anything that runs `postinstall`), check the package's GitHub for recent suspicious commits

### Trusted-base approach

Use the latest **stable** version that's at least 5 days old. For our stack today:

**Frontend (verify dates at install time):**
- `next@14.2.x` (avoid 15.x bleeding edge during hackathon)
- `react@18.3.x` (NOT 19.x)
- `@tanstack/react-query@5.x` (pick a version ≥ 5 days old)
- `next-auth@4.24.x` (v5 still beta, skip)
- `tailwindcss@3.4.x` (NOT 4.x, ecosystem still catching up)
- `zod@3.23.x`
- `react-hook-form@7.x`

**Backend:**
- `fastapi` latest stable - 1 minor (e.g. if latest is 0.116, use 0.115.x)
- `sqlmodel` - latest stable, verify date
- `alembic` - very low churn, latest is fine if > 5 days old
- `pydantic` 2.x stable
- `apscheduler` 3.x (NOT 4.x beta)
- `resend` SDK - verify date carefully, this is exactly the kind of package targeted

### Lockfile discipline

- `pnpm-lock.yaml` and `uv.lock` MUST be committed.
- Never run `npm install <pkg>` without `--save-exact`.
- Never run `pip install <pkg>` without a version specifier.
- CI/deploy MUST use `pnpm install --frozen-lockfile` and `uv sync --frozen` — block any dependency drift between local and production.

### Red flags to watch for during install

If any of these appear, **stop and investigate**:
- A package runs a `postinstall` script you didn't expect
- A package version that didn't exist yesterday now exists
- A maintainer transfer notice on the npm page
- Sudden new dependencies in a patch-version bump
- A package suddenly larger than its previous version
- Network requests during install to unfamiliar domains

### shadcn/ui exception
shadcn/ui is copy-paste, not a published package — you pull components into your repo via the CLI. The CLI itself is a package (apply 5-day rule), but the components are vendored into your code and reviewable. This is actually safer than most npm packages and a real argument for the choice.

### If a compromise is discovered mid-build

1. Stop work immediately
2. `pnpm why <pkg>` / `pip show <pkg>` to find every place it's used
3. Pin to a known-good earlier version
4. Rotate any secrets the build machine had access to (Vercel/Railway/Neon/Resend API keys)
5. Force-reinstall from clean `node_modules` / `.venv`

---

## 15. Working agreement with Claude Code

When starting work:
1. Read this file first.
2. Confirm current phase (which hour bucket are we in).
3. Stick to the tech stack — no substitutions without explicit discussion.
4. **Before installing any package: verify its latest version is > 5 days old (see §14). If not, pin to the previous version.**
5. **All version pins are EXACT — no `^`, `~`, `>=`. Lockfiles committed always.**
6. Always write the SQLModel/Pydantic model before the endpoint.
7. Always write the backend validation before the frontend form.
8. Mirror backend rules in frontend Zod schemas for consistent UX.
9. Use TanStack Query for all client data fetching — no raw `fetch` in components.
10. Use shadcn/ui components — don't hand-roll UI primitives.
11. Every new feature: add to the must-have checklist with `[x]` when done.
12. Commit after every working feature, never in broken state.

---

## 16. Open questions to resolve as we go

- Exact thrust area list (seed with 5–6 plausible ones: "Customer Success", "Product Delivery", "Operational Excellence", "People Development", "Innovation", "Compliance")
- Whether "shared goal weightage" can differ per employee (assume yes — BRD says weightage is per-employee)
- Whether annual rating is in scope (BRD says progress score is tracking only, NOT for ratings — skip rating logic entirely)
- Whether Q4 is separate from Annual or combined (assume combined as `q4_annual` to simplify)
