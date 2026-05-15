"""
GitHub Service — handles all GitHub API interactions.

Provides OAuth token exchange, repo cloning, branch creation,
file pushing, and Pull Request creation via PyGithub.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from github import Auth, Github, GithubException, InputGitTreeElement

from app.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_REDIRECT_URI,
    SCAN_TEMP_DIR,
)

logger = logging.getLogger(__name__)


# ── OAuth helpers ────────────────────────────────────────────────────────────

async def exchange_code_for_token(code: str) -> str:
    """
    Exchange a GitHub OAuth authorization code for an access token.
    Returns the raw access_token string.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise ValueError(f"GitHub OAuth error: {data['error_description']}")

    token = data["access_token"]
    logger.info("GitHub OAuth token obtained (scope=%s)", data.get("scope"))
    return token


def get_github_user(token: str) -> Dict:
    """Return the authenticated user's profile as a dict."""
    g = Github(auth=Auth.Token(token))
    user = g.get_user()
    return {
        "login": user.login,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "html_url": user.html_url,
    }


# ── Repo parsing ─────────────────────────────────────────────────────────────

def parse_repo_full_name(repo_url: str) -> str:
    """
    Extract 'owner/repo' from various GitHub URL formats:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
      git@github.com:owner/repo.git
    """
    # HTTPS format
    match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_url)
    if match:
        return match.group(1)

    # SSH format
    match = re.match(r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?$", repo_url)
    if match:
        return match.group(1)

    raise ValueError(f"Cannot parse GitHub repo from URL: {repo_url}")


# ── Clone ────────────────────────────────────────────────────────────────────

def clone_repo(token: str, repo_url: str, scan_id: str) -> str:
    """
    Clone a GitHub repo into a temporary directory inside SCAN_TEMP_DIR.
    Uses the token for HTTPS authentication.
    Returns the absolute path to the cloned directory.
    """
    full_name = parse_repo_full_name(repo_url)
    clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"

    dest = Path(SCAN_TEMP_DIR) / scan_id
    dest.mkdir(parents=True, exist_ok=True)

    logger.info("Cloning %s into %s", full_name, dest)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(dest / "repo")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr}")

    repo_dir = str(dest / "repo")
    logger.info("Clone complete: %s", repo_dir)
    return repo_dir


# ── Read repo files for analysis ─────────────────────────────────────────────

# Extensions we'll feed to the recon agent for vulnerability analysis
_SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".rb", ".php",
    ".go", ".rs", ".c", ".cpp", ".h", ".cs", ".swift", ".kt",
    ".html", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".env", ".sql", ".sh", ".bash", ".dockerfile",
}

_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "vendor", ".tox",
}

_MAX_FILE_SIZE = 50_000  # 50 KB per file
_MAX_FILES = 60          # at most 60 files to scan


def read_repo_files(repo_dir: str) -> List[Dict[str, str]]:
    """
    Walk the cloned repo and return a list of
    [{"path": "relative/path.py", "content": "..."}] for scannable files.
    """
    files = []
    root = Path(repo_dir)

    for fpath in sorted(root.rglob("*")):
        if len(files) >= _MAX_FILES:
            break

        # Skip directories in the ignore list
        if any(part in _SKIP_DIRS for part in fpath.parts):
            continue

        if not fpath.is_file():
            continue

        if fpath.suffix.lower() not in _SCANNABLE_EXTENSIONS:
            continue

        if fpath.stat().st_size > _MAX_FILE_SIZE:
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            rel = str(fpath.relative_to(root)).replace("\\", "/")
            files.append({"path": rel, "content": content})
        except Exception:
            continue

    logger.info("Read %d scannable files from %s", len(files), repo_dir)
    return files


# ── Branch + PR via GitHub API ───────────────────────────────────────────────

def create_branch_and_pr(
    token: str,
    repo_full_name: str,
    base_branch: str,
    fix_branch: str,
    fixed_files: List[Dict[str, str]],
    pr_title: str,
    pr_body: str,
) -> str:
    """
    Create a new branch on the user's GitHub repo, push fixed files,
    and open a Pull Request. Returns the PR URL.

    fixed_files: [{"path": "server.py", "content": "...fixed code..."}]
    """
    g = Github(auth=Auth.Token(token))
    repo = g.get_repo(repo_full_name)

    # Get the SHA of the base branch
    base_ref = repo.get_branch(base_branch)
    base_sha = base_ref.commit.sha
    logger.info("Base branch %s at SHA %s", base_branch, base_sha[:12])

    # Create the fix branch
    try:
        repo.create_git_ref(ref=f"refs/heads/{fix_branch}", sha=base_sha)
        logger.info("Created branch %s", fix_branch)
    except GithubException as exc:
        if exc.status == 422:
            # Branch already exists — update it
            ref = repo.get_git_ref(f"heads/{fix_branch}")
            ref.edit(sha=base_sha, force=True)
            logger.info("Reset existing branch %s to %s", fix_branch, base_sha[:12])
        else:
            raise

    # Create blobs + tree for the fixed files
    base_tree = repo.get_git_tree(base_sha)
    tree_elements = []
    for f in fixed_files:
        blob = repo.create_git_blob(f["content"], "utf-8")
        tree_elements.append(
            InputGitTreeElement(
                path=f["path"],
                mode="100644",
                type="blob",
                sha=blob.sha,
            )
        )

    new_tree = repo.create_git_tree(tree_elements, base_tree)
    parent_commit = repo.get_git_commit(base_sha)
    commit = repo.create_git_commit(
        message=pr_title,
        tree=new_tree,
        parents=[parent_commit],
    )

    # Update the branch ref to the new commit
    ref = repo.get_git_ref(f"heads/{fix_branch}")
    ref.edit(sha=commit.sha)
    logger.info("Pushed commit %s to %s", commit.sha[:12], fix_branch)

    # Create the Pull Request
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=fix_branch,
        base=base_branch,
    )

    logger.info("Created PR #%d: %s", pr.number, pr.html_url)
    return pr.html_url


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup_scan_dir(scan_id: str) -> None:
    """Remove the temporary clone directory for a scan."""
    dest = Path(SCAN_TEMP_DIR) / scan_id
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
        logger.info("Cleaned up scan directory: %s", dest)
