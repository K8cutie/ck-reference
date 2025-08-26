# ClearKeep — Backend STATUS

**Date:** 2025-08-26 (Asia/Manila)  
**Repo:** `github.com/K8cutie/ck-reference` @ **main** (HEAD: `f1ddf7e`)  
**Local root:** `C:\ckchurch1`  •  **Mirror:** `C:\ck-reference`  
**Launchers:** `C:\ckchurch1\start_backend.ps1`  •  Frontend: `http://localhost:3000`

---

## Working Agreement (active)
- **Single-Step Lock** • **Read-First + Anchors** • **Accept/Block gate** • **One-File Rule**  
- **Acceptance checks required** • **Canonicals** • **Continuity Guard** • **`STATUS.md` = source of truth**

---

## Current Sprint
**Sprint 2 — Accounting Core**

- **Current step:** Step 2 — GL modularization + range ops + concurrency (**done**)  
- **Next:** Duplicate-closing cleanup → Reports correctness smoke → Indexes & perf  
- **RBAC:** Defer to the end (explicitly)

---

## Today’s Change Log — 2025-08-26

### What we shipped
- **Services split** → `app/services/gl/`
  - `books.py` • `locks.py` • `journal.py` • `accounts.py` • `periods.py` (+ `__init__.py`)
- **Routers split** → `app/api/`
  - `gl_accounts.py` • `gl_journal.py` • `gl_periods.py` • `gl_books.py`  
  - **Aggregator remains:** `app/api/gl_accounting.py` (now only includes sub-routers)
- **New endpoints**
  - `POST /gl/reclose/{YYYY-MM}` (canonical service)
  - `POST /gl/reclose-range/{start}/{end}` (inclusive)
  - `POST /gl/reopen-range/{start}/{end}`
  - `POST /gl/close-range/{start}/{end}`
  - `GET  /gl/locks/status?from=YYYY-MM&to=YYYY-MM`
- **Concurrency hardening**
  - Per-month **Postgres advisory locks** in `services/gl/periods.py` to prevent duplicate closes/recloses
- **Smokes added** (under `backend/scripts/`)
  - `smoke_gl_reclose.py`
  - `smoke_gl_reclose_range.py`
  - `smoke_gl_close_reopen_range.py`
  - `smoke_reclose_race.py`
  - *(optional next)* `smoke_reports_correctness.py` — ready to add

### Result snapshots (dev)
- **Reclose:** ✅ `POST /gl/reclose/2025-08` returns 200 with `CLOSE-202508` posted
- **Range:** ✅ `POST /gl/reclose-range/2025-07/2025-08` returns summary (`2025-07` nothing to close; `2025-08` ok)
- **Locks status:** ✅ `GET /gl/locks/status?from=2025-07&to=2025-08` reflects reopened/closed states as expected
- **Race condition test:** Advisory lock produces one success + one “busy” (re-run may yield {200,400})

---

## Endpoint Map (Accounting)

### /gl (Books-only operations)
- **Accounts**
  - `GET /gl/accounts`
  - `POST /gl/accounts`
  - `PATCH /gl/accounts/{account_id}`
- **Journal Entries**
  - `GET /gl/journal`
  - `POST /gl/journal`
  - `POST /gl/journal/{id}/post`
  - `POST /gl/journal/{id}/unpost`
  - `POST /gl/journal/{id}/reverse`
- **Periods**
  - `POST /gl/close/{YYYY-MM}`
  - `POST /gl/reopen/{YYYY-MM}`
  - `POST /gl/reclose/{YYYY-MM}`
  - `POST /gl/close-range/{start}/{end}`
  - `POST /gl/reopen-range/{start}/{end}`
  - `POST /gl/reclose-range/{start}/{end}`
  - `GET  /gl/locks/status?from=YYYY-MM&to=YYYY-MM`

### /compliance/books
- `GET /compliance/books/view/{view_key}`  *(general_journal | general_ledger | cash_receipts_book | cash_disbursements_book)*
- `GET /compliance/books/export` *(ZIP of CSVs + transmittal)*

---

## File Structure (key parts)

