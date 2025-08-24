# ClearKeep — STATUS

Date: 2025-08-25 (Asia/Manila)

Local project path: C:\ckchurch1  (pure local; no Drive junction)
Local mirror repo:  C:\ck-reference
GitHub repo:        K8cutie/ck-reference
Mirror script:      C:\ckchurch1\sync_to_github.bat

Process contract: see `PROCESS.md` (single-step, read-first, anchors, wait-for-next)

Timezone: Asia/Manila
API base (dev): http://127.0.0.1:8000
DB URL (redacted): postgresql+psycopg2://<user>:***@localhost:5432/<db>

Alembic head revision: 4b7f1c2d9e00
Alembic head message: gl_period_locks: month-level locks for posted journals

Python: 3.12.10
FastAPI: 0.116.1
SQLAlchemy: 2.0.42

Current sprint: Sprint 2 — Accounting Core
Current step: Step 1 — Posting engine (journals + lines, post/unpost, locks)
Notes: Run `C:\ckchurch1\sync_to_github.bat` before asking the assistant to read fresh state.
