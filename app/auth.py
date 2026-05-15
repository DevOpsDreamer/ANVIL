"""
GitHub OAuth authentication router.

Handles the full OAuth flow:
  1. GET /api/auth/github   → redirect to GitHub authorization page
  2. GET /api/auth/callback → exchange code for token, set cookie
  3. GET /api/auth/me       → return current user info
  4. POST /api/auth/logout  → clear cookie
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import GITHUB_CLIENT_ID, GITHUB_REDIRECT_URI, SESSION_SECRET
from app.github_service import exchange_code_for_token, get_github_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Signed cookie serializer
_signer = URLSafeSerializer(SESSION_SECRET, salt="github-token")

_COOKIE_NAME = "anvil_session"
_COOKIE_MAX_AGE = 86400 * 7  # 7 days


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

    state = secrets.token_urlsafe(16)
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo",
        "state": state,
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/callback")
async def github_callback(code: str, state: str | None = None):
    """
    GitHub redirects here after user authorizes.
    Exchange the code for a token and set a signed cookie.
    """
    try:
        token = await exchange_code_for_token(code)
    except Exception as exc:
        logger.error("OAuth token exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"OAuth failed: {exc}")

    # Sign the token into a cookie
    signed = _signer.dumps(token)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=signed,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
    )
    logger.info("GitHub OAuth complete — cookie set")
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
