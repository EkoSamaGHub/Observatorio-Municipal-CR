"""
Queue-core tests against the SQLite backend (runnable without pytest):

    python tests/test_task_queue.py

Validates the lease lifecycle: claim → heartbeat → complete/fail → retry →
dead → reap/requeue → run finalization. The Postgres path differs only by
adding FOR UPDATE SKIP LOCKED to the claim SELECT.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Force SQLite backend before importing the app DB layer.
os.environ.pop("DATABASE_URL", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs.db import get_connection  # noqa: E402
from configs.init_db import init_db  # noqa: E402
from modules import task_queue  # noqa: E402

WORKER = "test-worker"


def _reset(run_id):
    conn = get_connection()
    conn.execute("DELETE FROM crawl_tasks WHERE run_id=%s", (run_id,))
    conn.execute("DELETE FROM crawl_runs WHERE id=%s", (run_id,))
    conn.commit()
    conn.close()


def _expire_lease(task_id):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    conn = get_connection()
    conn.execute("UPDATE crawl_tasks SET lease_expires_at=%s WHERE id=%s", (past, task_id))
    conn.commit()
    conn.close()


def _status(task_id):
    conn = get_connection()
    row = conn.execute("SELECT status, attempts FROM crawl_tasks WHERE id=%s", (task_id,)).fetchone()
    conn.close()
    return row["status"], row["attempts"]


def main():
    init_db()
    run_id = task_queue.create_run(["MZ001", "MZ002", "MZ003"], "discover", max_attempts=3)
    try:
        prog = task_queue.run_progress(run_id)
        assert prog["total"] == 3 and prog["pending"] == 3, prog

        # Claim all three, fourth claim returns None.
        t1 = task_queue.claim_task(run_id, WORKER)
        t2 = task_queue.claim_task(run_id, WORKER)
        t3 = task_queue.claim_task(run_id, WORKER)
        assert t1 and t2 and t3, "should claim 3 distinct tasks"
        assert len({t1["id"], t2["id"], t3["id"]}) == 3, "claims must be distinct"
        assert task_queue.claim_task(run_id, WORKER) is None, "no 4th task"
        assert _status(t1["id"]) == ("running", 1)

        # Heartbeat extends the lease and records pages.
        task_queue.heartbeat(t1["id"], WORKER, lease_seconds=600, pages_found=42)
        conn = get_connection()
        hb = conn.execute("SELECT pages_found FROM crawl_tasks WHERE id=%s", (t1["id"],)).fetchone()
        conn.close()
        assert hb["pages_found"] == 42, hb

        # Complete t1.
        task_queue.complete_task(t1["id"], pages_found=42, sitemap_total=50, completeness_pct=84.0)
        assert _status(t1["id"])[0] == "done"

        # t2: fail repeatedly until dead (max_attempts=3).
        task_queue.fail_task(t2["id"], "boom")          # attempts already 1 -> failed
        assert _status(t2["id"]) == ("failed", 1)
        r = task_queue.claim_task(run_id, WORKER)        # re-claim failed
        assert r and r["id"] == t2["id"] and _status(t2["id"]) == ("running", 2)
        task_queue.fail_task(t2["id"], "boom")
        assert _status(t2["id"]) == ("failed", 2)
        r = task_queue.claim_task(run_id, WORKER)
        assert r and r["id"] == t2["id"] and _status(t2["id"]) == ("running", 3)
        task_queue.fail_task(t2["id"], "boom")           # attempts 3 >= max -> dead
        assert _status(t2["id"]) == ("dead", 3), _status(t2["id"])
        assert task_queue.claim_task(run_id, WORKER) is None, "dead task not re-claimable; t3 still leased"

        # t3: simulate a crashed worker (lease expires) -> reap requeues it.
        _expire_lease(t3["id"])
        prog = task_queue.reap_run(run_id)
        assert _status(t3["id"])[0] == "pending", _status(t3["id"])
        r = task_queue.claim_task(run_id, WORKER)
        assert r and r["id"] == t3["id"]
        task_queue.complete_task(t3["id"], pages_found=10)

        # All terminal -> reap finalizes the run.
        prog = task_queue.reap_run(run_id)
        assert prog["pending"] == 0 and prog["running"] == 0, prog
        assert prog["done"] == 2 and prog["dead"] == 1, prog
        assert prog["pct"] == 100.0, prog

        conn = get_connection()
        run = conn.execute("SELECT status, finished_at FROM crawl_runs WHERE id=%s", (run_id,)).fetchone()
        conn.close()
        assert run["status"] == "done" and run["finished_at"], run

        print("ALL QUEUE TESTS PASSED")
    finally:
        _reset(run_id)


if __name__ == "__main__":
    main()
