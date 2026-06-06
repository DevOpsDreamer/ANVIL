"""
Target domain allowlist — ingress hardening (AEGIS v8).

Loads a JSON allowlist from ``config/allowed_targets.json`` at import time
and exposes :func:`validate_target` for URL-level enforcement.

Design principles:
  * **Fail-closed** — if the config file is missing or malformed the
    default allowlist is ``localhost`` + ``127.0.0.1`` only.
  * **Wildcard support** — entries like ``*.github.com`` match any
    subdomain (e.g. ``api.github.com``, ``raw.github.com``).
  * Rejected targets are logged at WARNING level for audit trails.

File format (``config/allowed_targets.json``)::

    {
      "version": 1,
      "domains": ["localhost", "127.0.0.1", "*.github.com"]
    }
"""

from __future__ import annotations

import fnmatch
import json
import logging
from pathlib import Path
from typing import List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Resolve config path relative to the backend root (one level above app/)
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "allowed_targets.json"

# Fail-closed default — only loopback when the config file is absent
_DEFAULT_DOMAINS: List[str] = ["localhost", "127.0.0.1"]

_allowed_domains: List[str] = []


# ── Load allowlist at module import ──────────────────────────────────────────

def _load_allowlist() -> List[str]:
    """
    Read and parse the allowlist JSON file.

    Returns the ``domains`` list on success, or :data:`_DEFAULT_DOMAINS`
    if the file is missing, unreadable, or has an unexpected schema.
    """
    if not _CONFIG_PATH.is_file():
        logger.warning(
            "Allowlist config not found at %s — defaulting to loopback only",
            _CONFIG_PATH,
        )
        return list(_DEFAULT_DOMAINS)

    try:
        raw = _CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)

        if not isinstance(data, dict) or "domains" not in data:
            logger.warning(
                "Allowlist config missing 'domains' key — defaulting to loopback only"
            )
            return list(_DEFAULT_DOMAINS)

        domains = data["domains"]
        if not isinstance(domains, list) or not all(
            isinstance(d, str) for d in domains
        ):
            logger.warning(
                "Allowlist 'domains' is not a list of strings — defaulting to loopback only"
            )
            return list(_DEFAULT_DOMAINS)

        logger.info(
            "Loaded target allowlist (v%s): %d domain pattern(s)",
            data.get("version", "?"),
            len(domains),
        )
        return [d.lower().strip() for d in domains if d.strip()]

    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to load allowlist config (%s) — defaulting to loopback only",
            exc,
        )
        return list(_DEFAULT_DOMAINS)


_allowed_domains = _load_allowlist()


# ── Public API ───────────────────────────────────────────────────────────────

def _domain_matches(domain: str, pattern: str) -> bool:
    """
    Check whether *domain* matches a single allowlist *pattern*.

    Supports simple wildcard entries (``*.github.com``) via
    :func:`fnmatch.fnmatch`.
    """
    return fnmatch.fnmatch(domain, pattern)


def validate_target(url: str) -> bool:
    """
    Validate that the domain of *url* appears in the allowlist.

    Parameters
    ----------
    url:
        An absolute URL (``https://github.com/owner/repo``) or a plain
        hostname/IP.  The scheme may be omitted — the function will
        attempt to parse it regardless.

    Returns
    -------
    bool
        ``True`` if the target domain matches any allowlist entry,
        ``False`` otherwise.
    """
    if not url:
        logger.warning("validate_target called with empty URL — rejected")
        return False

    # Ensure the URL has a scheme so urlparse extracts the hostname
    parse_url = url if "://" in url else f"https://{url}"

    try:
        parsed = urlparse(parse_url)
        domain = (parsed.hostname or "").lower().strip()
    except Exception:
        logger.warning("Failed to parse URL '%s' — rejected", url)
        return False

    if not domain:
        logger.warning("No domain extracted from URL '%s' — rejected", url)
        return False

    for pattern in _allowed_domains:
        if _domain_matches(domain, pattern):
            return True

    logger.warning(
        "Target domain '%s' (from '%s') not in allowlist — rejected", domain, url
    )
    return False


def get_allowed_domains() -> List[str]:
    """Return a copy of the currently loaded allowlist patterns."""
    return list(_allowed_domains)
