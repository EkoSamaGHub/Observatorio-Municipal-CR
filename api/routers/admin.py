"""
Admin control-plane API.

Security model: every endpoint requires the `ADMIN_TOKEN` env var to be set and
the caller to present it (header `X-Admin-Token: <token>` or
`Authorization: Bearer <token>`). If `ADMIN_TOKEN` is unset the whole router is
disabled (503) — the control plane is never exposed publicly by default.

These endpoints are the control plane only; they mutate durable queue state in
Postgres. The actual crawling is performed by the distributed workers
(GitHub Actions + Railway worker.py) that already obey that state.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from modules import admin_ops, events

router = APIRouter(prefix="/admin", tags=["admin"])


# ── auth ──────────────────────────────────────────────────────────────────────
#
# Two accepted credentials:
#   1) Signed session cookie set by the Discord OAuth callback (UI flow).
#   2) X-Admin-Token / Bearer header matching ADMIN_TOKEN (scripts / curl).
# Either is sufficient. ADMIN_TOKEN must still be set — it doubles as the
# session signing secret unless SESSION_SECRET is configured separately.

SESSION_COOKIE = "obsmuni_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 12  # 12h
OAUTH_STATE_COOKIE = "obsmuni_admin_oauth_state"


def _signing_secret() -> str:
    return os.environ.get("SESSION_SECRET") or os.environ.get("ADMIN_TOKEN") or ""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign_session(payload: dict) -> str:
    secret = _signing_secret().encode()
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url_encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _verify_session(cookie_val: str | None) -> dict | None:
    if not cookie_val or "." not in cookie_val:
        return None
    secret = _signing_secret().encode()
    if not secret:
        return None
    body, sig = cookie_val.rsplit(".", 1)
    expected = _b64url_encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


def _admin_discord_ids() -> set[str]:
    raw = os.environ.get("ADMIN_DISCORD_IDS", "")
    return {s.strip() for s in raw.split(",") if s.strip()}


def require_admin(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="Admin disabled: ADMIN_TOKEN not set")

    # 1) Session cookie from Discord SSO
    session = _verify_session(session_cookie)
    if session and session.get("sub") in _admin_discord_ids():
        return

    # 2) Header token (scripts / curl)
    provided = x_admin_token
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1]
    if provided and hmac.compare_digest(provided, token):
        return

    raise HTTPException(status_code=401, detail="Invalid or missing admin credentials")


_auth = [Depends(require_admin)]


# ── Discord OAuth ───────────────────────────────────────────────────────────

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


def _frontend_admin_url() -> str:
    return os.environ.get("ADMIN_FRONTEND_URL", "http://localhost:3000") + "/admin"


def _oauth_config() -> tuple[str, str, str]:
    client_id = os.environ.get("DISCORD_CLIENT_ID", "").strip().strip('"').strip("'")
    client_secret = os.environ.get("DISCORD_CLIENT_SECRET", "").strip().strip('"').strip("'")
    redirect_uri = os.environ.get("DISCORD_REDIRECT_URI", "").strip().strip('"').strip("'")
    missing = [
        name for name, val in (
            ("DISCORD_CLIENT_ID", client_id),
            ("DISCORD_CLIENT_SECRET", client_secret),
            ("DISCORD_REDIRECT_URI", redirect_uri),
        ) if not val
    ]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Discord SSO not configured — missing: {', '.join(missing)}",
        )
    return client_id, client_secret, redirect_uri


@router.get("/auth/diag")
def auth_diag():
    # No secrets returned — only presence flags. Safe to expose; helps when
    # configuring env vars on a new deploy.
    def present(name: str) -> bool:
        return bool(os.environ.get(name, "").strip().strip('"').strip("'"))
    return {
        "ADMIN_TOKEN": present("ADMIN_TOKEN"),
        "SESSION_SECRET": present("SESSION_SECRET"),
        "ADMIN_DISCORD_IDS": present("ADMIN_DISCORD_IDS"),
        "ADMIN_DISCORD_IDS_count": len(_admin_discord_ids()),
        "ADMIN_FRONTEND_URL": present("ADMIN_FRONTEND_URL"),
        "DISCORD_CLIENT_ID": present("DISCORD_CLIENT_ID"),
        "DISCORD_CLIENT_SECRET": present("DISCORD_CLIENT_SECRET"),
        "DISCORD_REDIRECT_URI": present("DISCORD_REDIRECT_URI"),
    }


def _set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    # SameSite=None is required because the SPA on Vercel and the API on Railway
    # are different sites; the cookie must be sent on cross-site fetches.
    resp.set_cookie(
        name, value,
        max_age=max_age, httponly=True, secure=True, samesite="none", path="/",
    )


@router.get("/auth/me")
def auth_me(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    session = _verify_session(session_cookie)
    if session and session.get("sub") in _admin_discord_ids():
        return {
            "authenticated": True,
            "discord_id": session.get("sub"),
            "username": session.get("name"),
            "exp": session.get("exp"),
        }
    return {"authenticated": False}


@router.get("/auth/discord/login")
def discord_login():
    client_id, _secret, redirect_uri = _oauth_config()
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    }
    resp = RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}", status_code=302)
    _set_cookie(resp, OAUTH_STATE_COOKIE, state, max_age=600)
    return resp


@router.get("/auth/discord/callback")
def discord_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Discord returned: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not oauth_state or not hmac.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="State mismatch — try again")

    client_id, client_secret, redirect_uri = _oauth_config()
    try:
        tok = requests.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        tok.raise_for_status()
        access_token = tok.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="Discord did not return an access token")

        ur = requests.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        ur.raise_for_status()
        user = ur.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Discord upstream error: {e}")

    discord_id = str(user.get("id", ""))
    if discord_id not in _admin_discord_ids():
        raise HTTPException(status_code=403, detail="Not on the admin allowlist")
    if not _signing_secret():
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN/SESSION_SECRET not set on the API")

    payload = {
        "sub": discord_id,
        "name": user.get("username") or user.get("global_name"),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    cookie_val = _sign_session(payload)

    resp = RedirectResponse(_frontend_admin_url(), status_code=302)
    _set_cookie(resp, SESSION_COOKIE, cookie_val, max_age=SESSION_TTL_SECONDS)
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return resp


@router.post("/auth/logout")
def auth_logout():
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# ── request bodies ──────────────────────────────────────────────────────────

class StartCrawlBody(BaseModel):
    mode: str = "discover"
    only_missing: bool = False
    ids: list[str] | None = None
    force: bool = False
    dispatch: bool = True


class RecrawlBody(BaseModel):
    mode: str = "discover"
    dispatch: bool = True


# ── observability (GET) ─────────────────────────────────────────────────────

@router.get("/overview", dependencies=_auth)
def get_overview():
    return admin_ops.overview()


@router.get("/runs", dependencies=_auth)
def get_runs(limit: int = 25):
    return admin_ops.list_runs(limit=limit)


@router.get("/runs/{run_id}/tasks", dependencies=_auth)
def get_run_tasks(run_id: int):
    return admin_ops.run_tasks(run_id)


@router.get("/workers", dependencies=_auth)
def get_workers():
    return admin_ops.workers()


@router.get("/logs", dependencies=_auth)
def get_logs(
    run_id: int | None = None,
    municipality_id: str | None = None,
    level: str | None = None,
    event: str | None = None,
    search: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    return events.query_events(
        run_id=run_id, municipality_id=municipality_id, level=level, event=event,
        search=search, since=since, until=until, limit=min(limit, 1000), offset=offset,
    )


# ── crawl control (POST) ────────────────────────────────────────────────────

@router.post("/crawl/start", dependencies=_auth)
def start_crawl(body: StartCrawlBody):
    try:
        return admin_ops.start_crawl(
            mode=body.mode, only_missing=body.only_missing, ids=body.ids,
            force=body.force, dispatch=body.dispatch,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/crawl/{run_id}/pause", dependencies=_auth)
def pause(run_id: int):
    return admin_ops.pause_run(run_id)


@router.post("/crawl/{run_id}/resume", dependencies=_auth)
def resume(run_id: int):
    return admin_ops.resume_run(run_id)


@router.post("/crawl/{run_id}/stop", dependencies=_auth)
def stop(run_id: int):
    return admin_ops.stop_run(run_id)


@router.post("/crawl/{run_id}/cancel", dependencies=_auth)
def cancel(run_id: int):
    return admin_ops.cancel_run(run_id)


@router.post("/crawl/{run_id}/reset", dependencies=_auth)
def reset_stuck(run_id: int):
    return admin_ops.reset_stuck_run(run_id)


@router.post("/crawl/{run_id}/reap", dependencies=_auth)
def reap(run_id: int):
    return admin_ops.reap(run_id=run_id)


@router.post("/crawl/{run_id}/retry-failed", dependencies=_auth)
def retry_failed(run_id: int):
    return admin_ops.retry_all_failed(run_id)


@router.post("/crawl/clear-locks", dependencies=_auth)
def clear_locks(run_id: int | None = None):
    return admin_ops.clear_stale_locks(run_id=run_id)


@router.post("/crawl/kill-orphans", dependencies=_auth)
def kill_orphans():
    return admin_ops.kill_orphans()


# ── task / municipality control (POST) ──────────────────────────────────────

@router.post("/tasks/{task_id}/retry", dependencies=_auth)
def retry_task(task_id: int):
    return admin_ops.retry_task(task_id)


@router.post("/tasks/{task_id}/reset", dependencies=_auth)
def reset_task(task_id: int):
    return admin_ops.reset_task(task_id)


@router.post("/runs/{run_id}/municipalities/{municipality_id}/skip", dependencies=_auth)
def skip_muni(run_id: int, municipality_id: str):
    return admin_ops.skip_municipality(run_id, municipality_id)


@router.post("/municipalities/{municipality_id}/recrawl", dependencies=_auth)
def recrawl_muni(municipality_id: str, body: RecrawlBody):
    return admin_ops.recrawl_municipality(
        municipality_id, mode=body.mode, dispatch=body.dispatch
    )
