# ANVIL — Autonomous Vulnerability Neutralization & Intelligence Layer

> Multi-agent CPN pipeline: clone → recon → exploit → verify → patch → PR

---

## Architecture

```
User Browser
    │  POST /api/scan (GitHub OAuth cookie)
    │  GET  /api/scan/{id}/stream  ← SSE
    ▼
FastAPI :8000
    │  asyncio.to_thread
    ▼
CPN Engine (graph.py)
    ├── Recon Agent    (GPT-4o source analysis)
    ├── Exploit Agent  (AST-validated sandbox)
    ├── Verifier       (deterministic)
    └── Patcher Agent  (GitHub PR via PyGitHub)
        │
        ▼
    SQLite WAL  ←─ checkpoint after every transition
    Redis       ←─ SSE event queue (local Redis server)
```

## Quick Start — Localhost (No Docker)

### Prerequisites

- **Python 3.11+** — `python --version`
- **Node.js 20+** — `node --version`
- **Redis** installed locally:
  - macOS:   `brew install redis`
  - Ubuntu:  `sudo apt install redis-server`
  - Windows: Use [Memurai](https://www.memurai.com/) or WSL
- **OpenAI API key**
- **GitHub OAuth App** ([create here](https://github.com/settings/developers))
  - Homepage URL: `http://localhost:5173`
  - Callback URL:  `http://localhost:8000/api/auth/callback`

---

### Step 1 — Configure the backend

```bash
cd backend
cp .env.example .env
```

Open `.env` and fill in:

```env
OPENAI_API_KEY=sk-your-key-here
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
SESSION_SECRET=run-python-c-import-secrets-print-secrets.token_hex-32
```

Everything else can stay as the defaults — Redis and SQLite are already
pointed at `localhost`.

---

### Step 2 — Start Redis

```bash
# macOS / Linux
redis-server

# Or as a background service on Linux:
sudo systemctl start redis
```

Verify it is running: `redis-cli ping` → should print `PONG`.

---

### Step 3 — Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API docs will be at: http://localhost:8000/docs

---

### Step 4 — Start the frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The app will be available at: **http://localhost:5173**

---

## Workflow

1. **Connect GitHub** — click "Connect GitHub to Start Scanning" (OAuth flow)
2. **Enter target repo** — any public GitHub repo URL
3. **Start Scan** — ANVIL clones the repo, runs source-code recon with GPT-4o
4. **Watch the pipeline** — Petri net lights up, terminal streams real SSE events
5. **Exploit fires** — payload executes in sandboxed subprocess
6. **Verifier confirms** — deterministic stdout check (retries up to 3×)
7. **Patcher opens PR** — AST rewrite committed to a `fix/` branch on your repo
8. **Review results** — flag captured, diff shown, PR link

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/auth/github`      | Redirect → GitHub OAuth |
| `GET`  | `/api/auth/callback`    | OAuth code exchange |
| `GET`  | `/api/auth/me`          | Get current GitHub user |
| `POST` | `/api/auth/logout`      | Clear session |
| `POST` | `/api/scan`             | Start scan `{repo_url, base_branch}` |
| `GET`  | `/api/scan/{id}/stream` | SSE stream of ScanEvents |
| `GET`  | `/api/scan/{id}`        | Full ScanResult |
| `GET`  | `/api/scans`            | List all scans |
| `GET`  | `/health`               | Health check |

## SSE Event Stages

```
queued → cloning → recon → exploit → verify → patch → pushing → completed
                                         ↑ retry loop (max 3×) ↑
```

Each event: `{ scan_id, stage, status, message, detail, pr_url, vuln_count, progress_pct }`

## Environment Variables

See `backend/.env.example` for all configuration options.
