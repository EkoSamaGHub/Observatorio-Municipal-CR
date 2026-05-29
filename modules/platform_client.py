"""
HTTP client for the crawler-platform API.

Set PLATFORM_API_URL to the base URL of the running platform
(default: http://localhost:3000 for local Docker Compose).
"""
from __future__ import annotations

import os
import time

import requests
from requests.exceptions import RequestException

from modules.logger import logger

PLATFORM_API_URL = os.environ.get("PLATFORM_API_URL", "http://localhost:3000")

_TERMINAL: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELED"})


class CrawlerPlatformClient:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self._base = (base_url or PLATFORM_API_URL).rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._timeout = timeout

    # ── job lifecycle ──────────────────────────────────────────────────────────

    def create_job(
        self,
        name: str,
        seeds: list[str],
        *,
        max_depth: int = 3,
        max_pages: int = 500,
        max_duration_sec: int = 3600,
        scope_mode: str = "SEED_HOST",
        rendering_mode: str = "AUTO",
    ) -> dict:
        """POST /v1/crawls — create a new crawl job. Returns the job object."""
        payload = {
            "name": name,
            "seeds": seeds,
            "strategy": "BFS",
            "limits": {
                "maxDepth": max_depth,
                "maxPages": max_pages,
                "maxDurationSec": max_duration_sec,
            },
            "scope": {"mode": scope_mode},
            "rendering": {"mode": rendering_mode},
            "extraction": {
                "markdown": True,
                "embeddings": {"enabled": False},
            },
        }
        r = self._session.post(
            f"{self._base}/v1/crawls", json=payload, timeout=self._timeout
        )
        r.raise_for_status()
        return r.json()

    def get_job(self, job_id: str) -> dict:
        """GET /v1/crawls/:id"""
        r = self._session.get(
            f"{self._base}/v1/crawls/{job_id}", timeout=self._timeout
        )
        r.raise_for_status()
        return r.json()

    def cancel_job(self, job_id: str) -> None:
        try:
            self._session.post(
                f"{self._base}/v1/crawls/{job_id}/cancel", timeout=self._timeout
            )
        except RequestException as e:
            logger.warning(f"[platform] cancel {job_id}: {e}")

    def is_terminal(self, status: str) -> bool:
        return status in _TERMINAL

    # ── page listing ───────────────────────────────────────────────────────────

    def list_pages(self, job_id: str, page_size: int = 500) -> list[dict]:
        """Paginate GET /v1/crawls/:id/pages and return all items."""
        items: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {"limit": page_size}
            if cursor:
                params["cursor"] = cursor
            r = self._session.get(
                f"{self._base}/v1/crawls/{job_id}/pages",
                params=params,
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            items.extend(data.get("items", []))
            cursor = data.get("nextCursor")
            if not cursor:
                break
        return items

    # ── errors ───────────────────────────────────────────────────────────────────

    def list_errors(self, job_id: str, limit: int = 50, stage: str | None = None) -> list[dict]:
        """GET /v1/crawls/:id/errors — recorded CrawlError rows, newest first."""
        params: dict = {"limit": limit}
        if stage:
            params["stage"] = stage
        r = self._session.get(
            f"{self._base}/v1/crawls/{job_id}/errors",
            params=params,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json().get("items", [])

    # ── polling ────────────────────────────────────────────────────────────────

    def wait_for_all(
        self,
        job_ids: list[str],
        *,
        poll_sec: int = 30,
        timeout_sec: int = 7200,
    ) -> dict[str, dict]:
        """
        Block until every job_id reaches a terminal state.
        Returns {job_id: job_data}. Gracefully handles timeout.
        """
        results: dict[str, dict] = {}
        pending = list(job_ids)
        deadline = time.monotonic() + timeout_sec

        while pending and time.monotonic() < deadline:
            still_pending: list[str] = []
            for job_id in pending:
                try:
                    job = self.get_job(job_id)
                    if self.is_terminal(job.get("status", "")):
                        results[job_id] = job
                        extracted = (job.get("stats") or {}).get(
                            "pagesExtracted", job.get("pagesExtracted", 0)
                        )
                        logger.info(
                            f"[platform] {job_id} -> {job['status']} "
                            f"(extracted={extracted})"
                        )
                    else:
                        still_pending.append(job_id)
                except RequestException as e:
                    logger.warning(f"[platform] get_job {job_id}: {e}")
                    still_pending.append(job_id)
            pending = still_pending
            if pending:
                logger.info(
                    f"[platform] {len(pending)} job(s) still running — "
                    f"sleeping {poll_sec}s"
                )
                time.sleep(poll_sec)

        for job_id in pending:
            logger.warning(f"[platform] timed out waiting for {job_id}")
            try:
                results[job_id] = self.get_job(job_id)
            except Exception:
                results[job_id] = {"id": job_id, "status": "UNKNOWN"}

        return results

    # ── health ─────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        try:
            r = self._session.get(f"{self._base}/healthz", timeout=5)
            return r.ok
        except RequestException:
            return False

    # ── context manager ────────────────────────────────────────────────────────

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "CrawlerPlatformClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
