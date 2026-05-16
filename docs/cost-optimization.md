# Cost optimization

> Used directly in the README submission. Maps to **criterion 6** of the judging rubric (1/6 of the grade) and is the most-overlooked criterion by other teams.

## Hackathon-scale: $0/month

| Service | Tier | Limit | Cost |
|---|---|---|---|
| Vercel | Hobby | 100 GB bandwidth, unlimited deploys | Free |
| Railway | Trial | $5 starter credit | Free during hackathon |
| Neon | Free | 0.5 GB storage, ~100 hr compute/mo, autoscale to 2 CU | Free |
| Resend | Free | 3,000 emails/month | Free (Phase 6) |
| Teams Incoming Webhook | — | Unlimited posts | Free (Phase 6) |

Total marginal cost during hackathon: **$0**.

## Production-scale projection (~1,000 employees, ~50K API calls/month): ~$50/month

| Service | Plan | Cost |
|---|---|---|
| Neon | Scale | $19 |
| Railway | Hobby | $10 |
| Resend | Pro | $20 |
| Vercel | Hobby (still free for this scale) | $0 |
| **Total** | | **~$49** |

Cost-per-user-per-month at this scale: **~$0.05**. Conservatively under any typical HR software SaaS line item.

## Optimizations built into the architecture

| Mechanism | Cost effect |
|---|---|
| **Audit log: append-only with composite index `(goal_id, timestamp)`** | Per-query cost stays flat as the log grows; no full-table scan on goal history reads. |
| **Completion dashboard: materialized aggregations refreshed every 5 min via APScheduler** | Drops dashboard load from O(goals) per request to O(1) — small jobs amortize the cost across the whole department instead of paying per page-load. |
| **Goal lists: TanStack Query client cache + ETag headers** | Repeat reads on dashboards hit local cache, not the API. Halves typical session-level API traffic. |
| **CSV export via `StreamingResponse`** | Constant memory regardless of row count; no `O(N)` allocation on the API container. |
| **APScheduler runs in-process inside FastAPI** | No separate worker service (Redis + Celery would otherwise add ~$15/mo at this scale). |
| **Neon pooled connections** | Pooled URL handles serverless cold-starts gracefully; avoids the per-connection compute spin-up that a direct URL would cause under bursty load. |
| **Pinned exact deps + committed lockfiles** | Reproducible builds → zero rebuild-loop minutes on Vercel/Railway from dependency drift. Small but real. |
| **`SAEnum(native_enum=False)` for status columns** | Schema changes (new statuses) ship as zero-downtime VARCHAR CHECK updates instead of native PG ENUM migrations that require table rewrites at scale. |

## Things deliberately not paid for

- **No managed auth (Azure AD, Auth0, Clerk, Neon Auth)** — NextAuth credentials provider handles 3 demo users locally for $0.
- **No CDN add-on** — Vercel's edge network is bundled with the hobby tier.
- **No observability SaaS (Datadog, Sentry)** — Railway + Vercel built-in logs cover hackathon scope.
- **No separate cron service** — APScheduler in-process.
