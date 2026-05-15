"""
GitHub OAuth authentication router.

Handles the full OAuth flow:
  1. GET /api/auth/github   → redirect to GitHub authorization page
  2. GET /api/auth/callback → exchange code for token, set cookie
  3. GET /api/auth/me       → return current user info
  4. POST /api/auth/logout  → clear cookie

Security:
  - OAuth state nonce is stored in a short-lived signed cookie to prevent CSRF.
  - Session cookie secure flag is environment-driven (COOKIE_SECURE env var).
"""

from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import GITHUB_CLIENT_ID, GITHUB_REDIRECT_URI, SESSION_SECRET
from app.github_service import exchange_code_for_token, get_github_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Signed cookie serializer (shared salt for tokens, separate salt for state nonces)
_signer = URLSafeSerializer(SESSION_SECRET, salt="github-token")
_state_signer = URLSafeSerializer(SESSION_SECRET, salt="oauth-state")

_COOKIE_NAME = "anvil_session"
_STATE_COOKIE_NAME = "anvil_oauth_state"
_COOKIE_MAX_AGE = 86400 * 7  # 7 days
_STATE_COOKIE_MAX_AGE = 600  # 10 minutes — state nonces expire quickly

# Production cookie security: set COOKIE_SECURE=true when behind HTTPS
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")


def _get_token_from_cookie(request: Request) -> str | None:
    """Extract and verify the GitHub token from the signed cookie."""
    raw = request.cookies.get(_COOKIE_NAME)
    if not raw:
        return None
    try:
        return _signer.loads(raw)
    except BadSignature:
        return None


def require_auth(request: Request) -> str:
    """Return the GitHub token or raise 401."""
    token = _get_token_from_cookie(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Connect GitHub first.")
    return token


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    """Redirect the user to GitHub's OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GITHUB_CLIENT_ID not configured")

    # Generate a cryptographic nonce and store it in a signed cookie
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo",
        "state": state,
    })

    response = RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")
    # Store the state nonce in a short-lived, signed, httponly cookie
    response.set_cookie(
        key=_STATE_COOKIE_NAME,
        value=_state_signer.dumps(state),
        max_age=_STATE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_COOKIE_SECURE,
    )
    return response


@router.get("/callback")
async def github_callback(code: str, state: str | None = None, request: Request = None):
    """
    GitHub redirects here after user authorizes.
    Validates the state nonce against the stored cookie to prevent CSRF,
    then exchanges the code for a token and sets a signed session cookie.
    """
    # ── CSRF Protection: validate the state nonce ─────────────────────────
    stored_state_raw = request.cookies.get(_STATE_COOKIE_NAME) if request else None
    if not state or not stored_state_raw:
        raise HTTPException(
            status_code=400,
            detail="OAuth state parameter missing — possible CSRF attack.",
        )

    try:
        stored_state = _state_signer.loads(stored_state_raw)
    except BadSignature:
        raise HTTPException(
            status_code=400,
            detail="OAuth state cookie tampered — possible CSRF attack.",
        )

    if not secrets.compare_digest(state, stored_state):
        raise HTTPException(
            status_code=400,
            detail="OAuth state mismatch — possible CSRF attack.",
        )

    # ── Exchange code for token ───────────────────────────────────────────
    try:
        token = await exchange_code_for_token(code)
    except Exception as exc:
        logger.error("OAuth token exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"OAuth failed: {exc}")

    # Sign the token into a session cookie
    signed = _signer.dumps(token)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=signed,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_COOKIE_SECURE,
    )
    # Clear the one-time state cookie
    response.delete_cookie(_STATE_COOKIE_NAME)
    logger.info("GitHub OAuth complete — session cookie set (secure=%s)", _COOKIE_SECURE)
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """Return the authenticated GitHub user profile."""
    token = require_auth(request)
    try:
        user = get_github_user(token)
        return JSONResponse(user)
    except Exception as exc:
        logger.error("Failed to fetch GitHub user: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/logout")
async def logout():
    """Clear the session cookie."""
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(_COOKIE_NAME)
    return response
