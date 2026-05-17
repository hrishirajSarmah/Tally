# CLAUDE.md — Tally (AtomQuest Hackathon 1.0)

Goal Setting & Tracking Portal for AtomQuest Hackathon 1.0. Internal HR portal where employees set yearly goals, managers approve them, everyone updates progress quarterly. Three roles: **employee**, **manager (L1)**, **admin/HR**. Solo build, ~72-hour weekend timeline.

**Production**: web https://tally-five-orpin.vercel.app · api https://tally-production-2d82.up.railway.app · db Neon Postgres (`neondb`).

**Current schema**: alembic head `0504db5a33ca` (initial 6-table schema applied).

---

## 1. Build & Development Commands

### Toolchain (required, exact major versions)

| Tool | Version | Install (macOS) |
|---|---|---|
| Node | 22.x | `brew install node` |
| pnpm | 11.x | `brew install pnpm` |
| Python | 3.12 | `brew install python@3.12` |
| uv | 0.11.x | `brew install uv` |

### Bootstrap a fresh checkout

```bash
# 1. Frontend deps
cd web && pnpm install --frozen-lockfile

# 2. Backend deps + venv
cd ../api && uv sync --frozen

# 3. Local secrets — copy template and fill in DATABASE_URL + JWT_SECRET
cp api/.env.example api/.env
# DATABASE_URL: pooled Neon URL (host contains `-pooler`); same value as Railway env.
# JWT_SECRET: generate locally with
python3 -c "import secrets; print(secrets.token_hex(32))"
# FRONTEND_ORIGIN: http://localhost:3000 for local; the Vercel URL in prod.

# 4. Verify schema is at head
cd api && uv run alembic current     # expect: 0504db5a33ca (head)
```

### Repo layout

```
tally/
├── web/                 # Next.js 14 App Router → Vercel (root dir: web/)
│   └── src/app/         # Pages, layouts; private dirs prefixed with _
├── api/                 # FastAPI + SQLModel → Railway (root dir: api/)
│   ├── main.py          # FastAPI app, endpoints
│   ├── settings.py      # pydantic-settings Settings, instantiated once
│   ├── db.py            # engine + get_session() dependency
│   ├── models.py        # All 6 SQLModel tables + 6 enums (single module)
│   ├── alembic.ini      # Alembic config
│   ├── alembic/         # env.py customized; versions/ holds migrations
│   ├── railway.toml     # Build/deploy/healthcheck config
│   └── .env             # Gitignored — DATABASE_URL, JWT_SECRET, FRONTEND_ORIGIN
└── docs/                # Architecture diagram (later submission artifact)
```

### Frontend commands (run from `web/`)

| Action | Command |
|---|---|
| Install | `pnpm install --frozen-lockfile` |
| Dev server (:3000) | `pnpm dev` |
| Production build | `pnpm build` |
| Production preview | `pnpm start` (runs `pnpm build` output) |
| Add dep (exact pin) | `pnpm add <pkg>@<exact-version> --save-exact` |

### Backend commands (run from `api/`)

| Action | Command |
|---|---|
| Install | `uv sync --frozen` |
| Dev server (:8000, reload) | `uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload` |
| Add dep (exact pin) | `uv add "<pkg>==<exact-version>"` |
| Import smoke check | `uv run python -c "from main import app; print('ok')"` |

### Migrations (run from `api/`)

```bash
# Apply pending migrations (idempotent)
uv run alembic upgrade head

# Generate a new migration after editing models.py
uv run alembic revision --autogenerate -m "what changed"
# ALWAYS inspect the generated file in alembic/versions/ before applying.

# State inspection
uv run alembic current     # current revision in DB
uv run alembic history     # all revisions
```

**Schema change protocol** (mandatory):
1. Edit `api/models.py`.
2. Generate migration locally (`alembic revision --autogenerate`).
3. **Inspect the generated migration file** — autogenerate misses renames, complex CHECKs, type-only changes. Hand-edit if needed.
4. Apply locally to Neon (`alembic upgrade head`).
5. Verify with `alembic current` + spot-check the affected table.
6. Commit the migration file and push. Railway deploy does **not** auto-apply migrations.

### Lint / Format

**None configured.** No ESLint, no Prettier, no Biome, no Ruff, no Black, no mypy. No pre-commit hooks. Discipline is manual: run `pnpm build` (web) or import-check (api) before commit.

If adding later: prefer Biome for `web/` (one tool, fast); prefer Ruff for `api/`.

### Supply chain rules (enforced on every dep install)

- **5-day rule**: never install a package version released within the last 5 days. Verify before `pnpm add` or `uv add`. Helper script in Appendix.
- **Exact pin only**: no `^`, `~`, `>=` in `package.json` or `pyproject.toml`.
- **Lockfiles committed**: `pnpm-lock.yaml` and `uv.lock`. Never bypass with `--no-frozen-lockfile`.
- **CI/deploy installs**: always `--frozen-lockfile` (pnpm) and `--frozen` (uv).
- **shadcn/ui exception**: components are copy-paste into `src/components/ui/`, not a published dep. The shadcn CLI itself is subject to the 5-day rule.

---

## 2. Test & Verification Pipelines

### Tests

**None configured.** No pytest, no vitest, no playwright. Hackathon scope opts for curl + browser smoke verification over automated tests. Do not invent test commands; do not assume `pnpm test` or `pytest` works.

If adding later: pytest for `api/`, vitest for `web/`.

### Smoke verification (the "is it green" commands)

```bash
# Frontend prod (anonymous, public access)
curl -s -o /dev/null -w "%{http_code}\n" https://tally-five-orpin.vercel.app/
# Expect: 200

# Backend prod healthcheck
curl -s https://tally-production-2d82.up.railway.app/health
# Expect: {"status":"ok"}

# Backend prod DB connectivity (Railway → Neon)
curl -s https://tally-production-2d82.up.railway.app/db-health
# Expect: {"status":"ok","scalar":1,"database":"neondb"}

# Local backend import graph (no DB connection required if .env is set)
cd api && uv run python -c "from main import app; print([r.path for r in app.routes if hasattr(r,'path')])"

# All 6 SQLModel tables import cleanly
cd api && uv run python -c "from models import User, Cycle, ThrustArea, Goal, Achievement, AuditLog; print('ok')"

# Confirm Neon has all tables at expected migration head
cd api && uv run alembic current
# Expect: 0504db5a33ca (head)
```

### CI/CD guardrails

**None at git level.** No GitHub Actions, no pre-commit hook. Push to `main` auto-deploys both targets:

- **Vercel** watches `main`, root dir `web/`, framework preset Next.js, builds with pnpm. Auto-deploys on push.
- **Railway** watches `main`, root dir `api/`, nixpacks builder. Auto-deploys on push (see [§3 deployment pipeline](#deployment-pipeline) for env var requirements).

The only pre-deploy gate is your local discipline. Before pushing:

1. `pnpm build` (web) succeeds OR `uv run python -c "from main import app"` (api) succeeds.
2. If `models.py` changed, `alembic upgrade head` already ran locally against Neon.
3. New env vars (if any) are already set in Vercel/Railway, **and** a manual redeploy was triggered (Railway and Vercel do not always auto-redeploy on env var changes alone).

---

## 3. Architecture & Code Style Guidelines

### System diagram

```
┌──────────────────────────────────────────────────────────┐
│ Browser (3 role sessions: employee / manager / admin)    │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTPS
                             ▼
┌──────────────────────────────────────────────────────────┐
│ Next.js 14 on Vercel  (web/, root dir = web/)            │
│  - App Router; RSC by default; client opt-in             │
│  - NextAuth credentials provider → calls FastAPI /login  │
│  - Role-based middleware.ts                              │
│  - TanStack Query for client data (added in Phase 2)     │
│  - shadcn/ui copy-paste components                       │
└────────────────────────────┬─────────────────────────────┘
                             │ REST + JWT (Bearer in Authorization header)
                             ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI on Railway  (api/, root dir = api/)              │
│  - SQLModel ORM + Alembic migrations                     │
│  - JWT via python-jose; bcrypt via passlib               │
│  - Pydantic-settings for typed config                    │
│  - APScheduler for cycle window + reminders (Phase 2+)   │
│  - CSV/Excel via StreamingResponse                       │
│  - Audit log as SQLAlchemy event listener (Phase 5)      │
└──┬────────────────────────┬─────────────────────────────┬┘
   │                        │                             │
   ▼                        ▼                             ▼
┌────────────┐      ┌──────────────────┐      ┌────────────────────┐
│ Neon       │      │ Resend           │      │ Teams Incoming     │
│ Postgres   │      │ Transactional    │      │ Webhook            │
│ (pooled)   │      │ email (Phase 6)  │      │ (Phase 6)          │
└────────────┘      └──────────────────┘      └────────────────────┘
```

### Tech stack (decided — do not substitute mid-build)

| Layer | Pick | Why |
|---|---|---|
| Frontend | Next.js 14.2.x + TS + Tailwind + shadcn/ui | App Router; copy-paste UI velocity |
| Frontend state | TanStack Query (Phase 2+) | Cache, optimistic updates |
| Frontend forms | React Hook Form + Zod | Mirror backend validation |
| Auth | NextAuth credentials provider | Wraps backend `/auth/login` |
| Backend | FastAPI 0.135.x + SQLModel 0.0.38 | Speed; one model = DB + API schema |
| DB | Neon Postgres (pooled) | Serverless free tier; us-east-1 |
| Migrations | Alembic | autogenerate from `SQLModel.metadata` |
| Auth crypto | `passlib[bcrypt]` + `python-jose[cryptography]` | bcrypt password hashing + JWT |
| Hosting | Vercel (web) + Railway (api) | Free tier + $5 trial covers hackathon |
| Email (bonus) | Resend | 3K/mo free tier |
| Teams (bonus) | Incoming Webhook | Zero-auth; live-demo-friendly |

**Explicit non-choices**: no Azure AD SSO, no Neon Auth, no Supabase, no Celery/Redis (APScheduler in-process), no Docker for local dev.

### Backend code style (api/)

- **Always use SQLModel for both DB and API schemas.** One class, two purposes (`table=True` for DB rows, `table=False` for request/response).
- **Always declare enums as `class X(str, enum.Enum)`** and store them with `SAEnum(EnumClass, native_enum=False, length=N)` via `Field(sa_column=Column(...))`. Never use Postgres native ENUM types — migration-hostile.
- **Always store timestamps as `DateTime(timezone=True)`** (TIMESTAMPTZ). Use both Pydantic `default_factory=_utcnow` AND SQLAlchemy `default=_utcnow` for belt-and-suspenders.
- **Always inject DB sessions via `Depends(get_session)`.** Never call `Session(engine)` inline in endpoints.
- **Always read config through `from settings import settings`.** Never call `os.getenv` outside `settings.py`.
- **Phase-gated endpoints**: use a single FastAPI dependency `require_active_phase(["q1","q2",...])` and apply to every check-in endpoint. Frontend reads phase from `/api/cycles/current` to disable UI.
- **RBAC endpoints**: use `require_role(Role.X)` dependency. Never check role inline in endpoint bodies.
- **Audit log**: implement as a single SQLAlchemy `after_update` event listener on `Goal` where `status='locked'`, **not** sprinkled per-endpoint.
- **Always write Pydantic validators before frontend Zod schemas.** Backend is source of truth — judges will curl the API.

### Frontend code style (web/)

- **Always use Next.js App Router conventions** (`src/app/`). RSC by default; opt into client with `"use client"` at file top.
- **Private folders use `_` prefix** (e.g. `_components/`) to exclude from routing.
- **Always style with Tailwind utility classes.** No CSS modules, no styled-components, no inline `style={}` for layout.
- **shadcn/ui components live at `src/components/ui/`** and are vendored copy-paste, not installed.
- **Always use React Hook Form + Zod for forms.** Mirror backend Pydantic rules in Zod schemas.
- **Always use TanStack Query for app data** (Phase 2+). Never raw `fetch` in components for business data. The home-page API-status pill is a one-off bootstrap exception, not a pattern.
- **API base URL**: `process.env.NEXT_PUBLIC_API_URL`. **NEXT_PUBLIC_\* is inlined at build time** — changing it requires a redeploy with cache cleared.
- **NextAuth session shape**: JWT lives in `session.accessToken` (or similar); attach as `Authorization: Bearer <jwt>` on API calls.

### Data model (6 tables — full schema in `api/models.py`, summary here)

| Table | Purpose | Notable structure |
|---|---|---|
| `users` | Employees, managers, admins | `email` UNIQUE+indexed; self-FK `manager_id → users.id`; `role` enum |
| `cycles` | Performance cycles (FY) | `current_phase` enum drives global state; `is_active` bool |
| `thrust_areas` | Goal categories | Seeded list (Customer Success, Product Delivery, etc.) |
| `goals` | Employee goals per cycle | FKs to users/cycles/thrust_areas + self-FK `shared_parent_id` for shared-goal mechanic; `uom_type` enum drives `target_value` vs `target_date` requirement; `status` enum (draft→submitted→approved→locked) |
| `achievements` | Quarterly check-ins | **`UNIQUE(goal_id, quarter)`** — flagship BRD rule |
| `audit_log` | Post-lock mutations | **Composite `Index(goal_id, timestamp)`** — keeps audit queries O(log n) |

**Shared-goal mechanic** (judges will test this): `shared_parent_id` points to the primary owner's goal. When the parent's achievement is updated, a backend task copies `actual_value` and `status` to all children. On children, `title/description/target_value` are read-only; only `weightage` is per-employee editable.

**Schema is FROZEN at migration `0504db5a33ca`.** Any column add/rename/type change requires a new migration + redeploy + targeted regression check.

### Validation rules (BRD-scored — enforce on backend, mirror on frontend)

**Goal creation**:
- Max 8 goals per employee per cycle.
- Each goal `weightage >= 10`.
- Sum of weightages across an employee's goals in a cycle = exactly 100.
- Cannot submit goals outside `goal_setting` phase.

**UoM conditional requirements**:
- `numeric_min` | `numeric_max` | `percent_min` | `percent_max`: require `target_value`.
- `timeline`: require `target_date`.
- `zero`: no target required.

**Lock state**:
- Once `status = locked`, only admin can unlock.
- Any edit to a locked goal writes one `audit_log` row.
- Manager can edit during `submitted` state, before approval.

**Check-in windows**: Q1 achievements writable only when `current_phase = q1`; same for q2/q3/q4_annual. Backend rejects 403 with clear error message outside the window.

### Progress score formulas (compute on read, never store)

```python
def progress_score(uom_type, target, actual, target_date=None, actual_date=None):
    if uom_type in ("numeric_min", "percent_min"):
        return min(actual / target, 1.0) * 100 if target else 0
    if uom_type in ("numeric_max", "percent_max"):
        return min(target / actual, 1.0) * 100 if actual else 0
    if uom_type == "timeline":
        return 100 if (actual_date and actual_date <= target_date) else 0
    if uom_type == "zero":
        return 100 if actual == 0 else 0
```

Tracking only. **Never** used for ratings or performance scoring.

### Deployment pipeline (preconditions, must be true on every push)

| Target | Setting | Value |
|---|---|---|
| Vercel | Root Directory | `web` |
| Vercel | Framework Preset | **Next.js** (defaults to "Other" — must explicitly set) |
| Vercel | Deployment Protection | **Disabled** (otherwise anonymous visitors get 401) |
| Vercel env vars | `NEXT_PUBLIC_API_URL` | Railway public URL, no trailing slash. **Not** marked Sensitive. |
| Railway | Root Directory | `api` |
| Railway env vars | `DATABASE_URL` | Pooled Neon URL (host contains `-pooler`) |
| Railway env vars | `JWT_SECRET` | 64-char hex (`secrets.token_hex(32)`) |
| Railway env vars | `NIXPACKS_UV_VERSION` | `0.11.12` (without this, build fails on `pip install uv==`) |
| Railway env vars | `FRONTEND_ORIGIN` | Vercel prod URL (Phase 1.9; currently unset → CORS wildcard) |
| Neon | Region | AWS us-east-1 (matches Railway IAD for low latency) |
| Neon | Connection | Pooled URL only — direct connections will exhaust limits |

### Common gotchas (learned from Phase 0/1)

- `create-next-app --src-dir` skips `public/` creation; Vercel still requires it. Always ensure `web/public/.gitkeep` exists.
- Vercel auto-detection occasionally sets Framework Preset to "Other" → post-build fails with *"No Output Directory named 'public' found"*. Fix in project Settings → Build and Deployment.
- Railway nixpacks autodetects `uv` but ships an empty `$NIXPACKS_UV_VERSION` → `pip install uv==` fails. Always set the env var explicitly.
- `NEXT_PUBLIC_*` vars cannot be marked Sensitive (Vercel blocks Development env). They are public by design — inlined into the client bundle.
- `NEXT_PUBLIC_*` changes only apply on a fresh build. After updating, redeploy with "Use existing Build Cache" **off**.
- Railway does not always auto-redeploy on env var changes alone. After changing a var, manually click Deploy.
- Neon's project-creation splash shows the direct connection string with no edit affordance — convert to pooled by manually inserting `-pooler` after the endpoint ID in the host.
- `passlib 1.7.4` + `bcrypt 5.x` **crashes at import time**. passlib's `detect_wrap_bug` probe at module load uses a password >72 bytes; bcrypt 5.0 raises `ValueError` (4.x silently truncated). Fix: pin `bcrypt==4.3.0` (committed in 1.5). passlib then emits a harmless `(trapped) error reading bcrypt version` log line at first use — its version-detection fallback — but hashing + verify both work.

---

## 4. Active Session Context

**Current objective**: Phase 1 — schema + auth. Sub-tasks 1.1–1.5 complete. **Next**: 1.6 (JWT auth — `POST /auth/login`, `GET /auth/me`, `require_role(Role.X)` dependency).

**Open decisions / blockers**:
- CORS currently wildcard (`allow_origins=["*"]`). To be tightened in 1.9 by setting `FRONTEND_ORIGIN=https://tally-five-orpin.vercel.app` on Railway.
- No Railway-side migration automation. All `alembic upgrade head` runs are local; Railway redeploy of `api/` does not migrate. Decide before adding a second migration whether to wire alembic into Railway's release phase.

**Phase 1 gate (not yet met)**: all 3 demo users log in via the production Vercel URL, each lands on its role-specific dashboard stub, `GET /api/auth/me` (with JWT) returns the correct user+role, all 6 tables visible in Neon dashboard with seeded data.

**Working protocol for sub-phases (1.6 onwards)**:
Deliver the **7-Layer Build Protocol** documented in `prompts/protocol.md` (gitignored, local-only — ask the user to share if not present). Strictly adhere to it. **Do not** reference or follow any other prompt file (including `prompts/curator.md` if present) — the user has explicitly opted out.
- One layer per response, never collapsed. Wait for the user's input between each layer.
- Layer 0 (reading) is done independently by the user before invoking the protocol — wait for "Layer 0 done" before starting Layer 1. Do not suggest a reading list or topics to read.
- Active checkpoints: Layer 1 wants the user's one-sentence summary back; Layer 2 wants their connection prediction; Layer 3 compares prediction to actual behavior; Layer 4 wants 2+ failure modes; Layer 5 cites doc pages; Layer 6 includes a 5-second predict-before-reveal pause per file; Layer 7 produces 3 LEARNINGS.md questions + 1–2 transferable idioms.
- Rule: if the user's prediction is wrong at any layer, ask them to refine before explaining the gap.

**Recent commits** (most recent first):
- `0ee6655` phase 1.5: idempotent seed (3 users + FY26 cycle + 6 thrust areas) + bcrypt 4.3.0 pin
- `0801219` docs: refine CLAUDE.md as operational manual, extract cost optimization to docs/
- `12b4e5f` phase 1.4: alembic scaffold + 0504db5a33ca initial schema
- `02612ed` phase 1.3: typed settings + sqlmodel engine + /db-health
- `b1a7a0c` phase 1.2: define 6 SQLModel tables

---

## Appendix — 5-day rule helpers

**npm** (frontend):
```bash
npm view <pkg> time --json | python3 -c "
import json, sys
from datetime import datetime, timezone, timedelta
data = json.load(sys.stdin); cutoff = datetime.now(timezone.utc) - timedelta(days=5)
items = sorted(((v,t) for v,t in data.items() if v not in ('created','modified')), key=lambda x: x[1])
for v, t in items[-10:]:
    rel = datetime.fromisoformat(t.replace('Z','+00:00'))
    age = (datetime.now(timezone.utc) - rel).days
    print(f'{v:14s} {rel.date()} ({age}d) {\"OK\" if rel<cutoff else \"TOO NEW\"}')
"
```

**PyPI** (backend):
```bash
curl -s https://pypi.org/pypi/<pkg>/json | python3 -c "
import json, sys
from datetime import datetime, timezone, timedelta
data = json.load(sys.stdin); cutoff = datetime.now(timezone.utc) - timedelta(days=5)
items = []
for v, files in data['releases'].items():
    if not files: continue
    items.append((v, files[0]['upload_time_iso_8601']))
items.sort(key=lambda x: x[1])
for v, t in items[-10:]:
    rel = datetime.fromisoformat(t.replace('Z','+00:00'))
    age = (datetime.now(timezone.utc) - rel).days
    print(f'{v:14s} {rel.date()} ({age}d) {\"OK\" if rel<cutoff else \"TOO NEW\"}')
"
```

Always pick the latest version >5 days old. Pin exact. Regenerate and commit the lockfile.
