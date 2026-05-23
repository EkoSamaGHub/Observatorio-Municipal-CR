# Admin Operations Runbook

The admin control center is a secure operations dashboard for the crawler/indexer.
It lets an operator monitor, control, debug, and recover crawl runs **without**
touching Railway, GitHub Actions, or the database directly.

- **UI:** `https://<frontend>/admin` (not linked from the public nav)
- **API:** `https://<api-host>/admin/*` (token-authenticated)

## 1. How it fits the existing architecture

The crawler is a **lease-based task queue** in Postgres:

- `crawl_runs` — one row per run (batch). `status ∈ {running, paused, stopped,
  cancelled, done}`, plus `last_heartbeat`, `mode`, `worker_id`.
- `crawl_tasks` — one row per municipality per run. `status ∈ {pending, running,
  done, failed, dead, skipped}`, with a time-bounded lease (`leased_by`,
  `lease_expires_at`, `heartbeat`, `attempts`/`max_attempts`).

Workers (GitHub Actions ×2 + the Railway `worker.py` reaper/monitor) atomically
**claim** tasks (`SELECT … FOR UPDATE SKIP LOCKED`), heartbeat while working, then
mark them terminal. A dead worker's lease expires and the task is reclaimed — this
is what makes the system crash-safe and resumable.

**The admin API is a control plane, not a crawler.** It never crawls in-process
(that previously exhausted the Postgres pool and took the site down). Instead every
action mutates the durable queue state that workers already obey:

- `claim_task()` returns nothing for a run whose status is `paused`/`stopped`/
  `cancelled`, so **pause/stop/cancel wind every distributed worker down** on its
  next poll — no infrastructure access required.
- A persistent `crawl_events` table records lifecycle + operator actions, giving a
  searchable audit trail that survives container recycles (unlike stdout logs).

## 2. Security

Set `ADMIN_TOKEN` (a long random string) on the **API** service.

- Unset ⇒ all `/admin/*` endpoints return **503** (disabled). Nothing is exposed.
- Set ⇒ every request must send the token as `X-Admin-Token: <token>` or
  `Authorization: Bearer <token>`. Compared with `hmac.compare_digest`.
- The dashboard stores the token in the browser's `localStorage` and sends it on
  each call. Logout clears it. The route is never linked publicly and is useless
  without the token. Secrets (e.g. `DATABASE_URL`) are never returned.

## 3. Starting crawls without infra access

`Start crawl` calls `POST /admin/crawl/start`. It:

1. Refuses if a **live** run already exists (the duplicate-concurrent-crawl
   guard) — override with the **force** checkbox.
2. Enqueues a new run + one `pending` task per selected municipality.
3. If `GH_DISPATCH_TOKEN` + `GH_REPO` are configured, triggers the `crawl.yml`
   workflow so real workers spin up immediately. Otherwise the run simply waits
   for the nightly workflow / Railway monitor to pick it up (the dashboard shows a
   "dispatch not configured" hint).

`Re-crawl` on a single municipality enqueues a one-task run the same way.

## 4. Control actions

| Action | Endpoint | Effect |
|---|---|---|
| Start | `POST /admin/crawl/start` | Enqueue run (+ optional GH dispatch). Guards against duplicates. |
| Pause | `POST /admin/crawl/{id}/pause` | `status=paused`; workers stop claiming. State preserved. |
| Resume | `POST /admin/crawl/{id}/resume` | `status=running`; workers resume. |
| Stop | `POST /admin/crawl/{id}/stop` | Graceful halt: `status=stopped`, `finished_at` set, tasks preserved. |
| Cancel | `POST /admin/crawl/{id}/cancel` | Hard cancel: non-terminal tasks → `dead`, run finalized. |
| Force reset | `POST /admin/crawl/{id}/reset` | Stuck run: every non-terminal task → `pending`, attempts cleared, run reopened. |
| Reap | `POST /admin/crawl/{id}/reap` | Requeue expired-lease tasks, mark exhausted ones dead, finalize if drained. |
| Clear locks | `POST /admin/crawl/clear-locks[?run_id=]` | Release expired leases → stuck `running` tasks back to `pending`. |
| Retry failed | `POST /admin/crawl/{id}/retry-failed` | All `failed`/`dead`/`skipped` in run → `pending`, reopen run. |
| Kill orphans | `POST /admin/crawl/kill-orphans` | Close zombie task-less runs + reap stale active runs. |
| Retry task | `POST /admin/tasks/{task_id}/retry` | Single municipality → `pending`, reopen run. |
| Skip muni | `POST /admin/runs/{id}/municipalities/{mid}/skip` | Mark `skipped` (terminal, never retried). |
| Re-crawl muni | `POST /admin/municipalities/{mid}/recrawl` | New one-task run for that municipality. |

All destructive actions (stop/cancel/reset/kill-orphans) require an inline
**Confirm** in the UI.

## 5. Observability

- `GET /admin/overview` — coverage, queue health, active run, last success/fail,
  workers, system + environment metadata.
- `GET /admin/runs?limit=` — recent runs, each with a **derived state**:
  - `active` — running, fresh heartbeat
  - `stale` — running, heartbeat older than `STALE_MINUTES` (20) → worker likely dead, recoverable via reap/clear-locks
  - `orphaned` — running, no tasks, never finalized (legacy zombie) → kill-orphans
  - `paused` / `stopped` / `cancelled` / `done`
- `GET /admin/runs/{id}/tasks` — per-municipality status, pages, attempts,
  duration, heartbeat age, stale-lock flag, and the last error (expandable).
- `GET /admin/workers` — live workers inferred from current leases + heartbeat age.
- `GET /admin/logs` — searchable/filterable event log (by `run_id`,
  `municipality_id`, `level`, `event`, free-text `search`, `since`/`until`).

The dashboard auto-refreshes every 5s (toggleable).

## 6. Common workflows

**A worker died mid-run (run shows `stale`).** Click **Reap stale** (recommended)
to requeue its in-flight tasks for any healthy worker, or **Clear locks** to only
release expired leases. The nightly/Railway reaper does this automatically every
5 min too.

**A run is wedged and you want a clean restart.** **Force reset** → all tasks back
to `pending`, attempts cleared, run reopened. Then ensure workers are running
(Start crawl with dispatch, or wait for the schedule).

**A handful of municipalities keep failing.** Open the run, filter tasks by
`dead`, read the expanded error, then **Retry** individually or **Skip** the truly
broken sites. Use **Retry failed** to requeue them all at once.

**Old runs stuck `running` after a crash.** **Kill orphaned runs** closes
task-less zombies and reaps stale active runs.

## 7. Environment variables

| Var | Where | Purpose |
|---|---|---|
| `ADMIN_TOKEN` | API service | Enables + protects the control plane. |
| `GH_DISPATCH_TOKEN` | API service | PAT (Actions read+write) to dispatch crawls. |
| `GH_REPO` | API service | `owner/name` for workflow dispatch. |
| `GH_WORKFLOW_FILE` | API (opt) | Default `crawl.yml`. |
| `GH_WORKFLOW_REF` | API (opt) | Default `main`. |
| `NEXT_PUBLIC_API_URL` | Frontend | API base the dashboard talks to. |
