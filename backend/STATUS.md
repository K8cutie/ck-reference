# ClearKeep — Backend STATUS

**Date:** 2025-08-27 (Asia/Manila)  
**Repo:** `github.com/K8cutie/ck-reference` @ **main** (HEAD: f1ddf7e)  
**Local root:** `C:\ckchurch1`  •  **Mirror:** `C:\ck-reference`  
**Launchers:** `C:\ckchurch1\start_backend.ps1`  •  Frontend: `http://localhost:3000`

---

## Working Agreement (active)
- **Single-Step Lock** • **Read-First + Anchors** • **Accept/Block gate** • **One-File Rule**  
- **Acceptance checks required** • **Canonicals** • **Continuity Guard** • **`STATUS.md` = source of truth**

---

## Current Sprint
**Sprint 2 — Accounting Core**

- **Current step:** GL modularization + range ops + concurrency + QA/perf (**done**)  
- **Next:** RBAC guards (post/unpost/reverse/close/reopen/reclose/opening) — **last**

---

## Change Log — 2025-08-27 (Accounting QA, Perf & RBAC)

- **Reports correctness (v2) — ✅**  
  NI vs CLOSE equity matches for **2025-08** (NI=₱4,100.00, Equity=₱4,100.00; entries analyzed=31).

- **Duplicate closings scan — ✅**  
  `python -m scripts.admin_scan_closing_duplicates` → no unresolved older closings.

- **Journal sequence — ✅**  
  `entry_no` 1…35, strict increasing, no gaps.

- **Perf indexes — ✅ applied (Alembic `ca054ec32245`)**  
  - `ix_journal_entries_is_locked_entry_date`  
  - `ix_journal_entries_reference_no`  
  - `ix_journal_lines_entry_id`  
  - `ix_gl_period_locks_period_month`

- **RBAC wiring (dev-bypass ON) — ✅**  
  Guards added:
  - **Journal:** post (`gl:journal:post`), unpost (`gl:journal:unpost`), reverse (`gl:journal:reverse`)
  - **Periods:** close (`gl:close`), reopen (`gl:reopen`), reclose (`gl:reclose`)
  - **Ranges:** close-range (`gl:close:range`), reopen-range (`gl:reopen:range`), reclose-range (`gl:reclose:range`)
  - **Locks status** stays public (read-only)  
  **RBAC mode:** `RBAC_ENFORCE=false` (default; fast dev).  
  **Helper:** `scripts/ps_api_helpers.ps1` (`ckget`, `ckpost`, `ckreclose`); if `CK_API` is set, it auto-sends `X-API-Key`.

---

## Change Log — 2025-08-26 (GL modularization & range)

### What we shipped
- **Services split** → `app/services/gl/`  
  `books.py` • `locks.py` • `journal.py` • `accounts.py` • `periods.py` (+ `__init__.py`)
- **Routers split** → `app/api/`  
  `gl_accounts.py` • `gl_journal.py` • `gl_periods.py` • `gl_books.py`  
  **Aggregator remains:** `app/api/gl_accounting.py` (now only includes sub-routers)
- **New endpoints**
  - `POST /gl/reclose/{YYYY-MM}` (canonical service)
  - `POST /gl/reclose-range/{start}/{end}` (inclusive)
  - `POST /gl/reopen-range/{start}/{end}`
  - `POST /gl/close-range/{start}/{end}`
  - `GET  /gl/locks/status?from=YYYY-MM&to=YYYY-MM`
- **Concurrency hardening**
  - Per-month **Postgres advisory locks** in `services/gl/periods.py` to prevent duplicate closes/recloses

### Result snapshots (dev)
- **Reclose:** ✅ `POST /gl/reclose/2025-08` returns 200 with `CLOSE-202508` posted
- **Range:** ✅ `POST /gl/reclose-range/2025-07/2025-08` → summary (`2025-07` nothing to close; `2025-08` ok)
- **Locks status:** ✅ `GET /gl/locks/status?from=2025-07&to=2025-08` reflects reopened/closed states
- **Race condition:** advisory lock yields one success + one “busy” (re-run may yield {200,400})

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
  - `POST /gl/journal/{id}/post` *(RBAC: `gl:journal:post`)*
  - `POST /gl/journal/{id}/unpost` *(RBAC: `gl:journal:unpost`)*
  - `POST /gl/journal/{id}/reverse` *(RBAC: `gl:journal:reverse`)*
- **Periods**
  - `POST /gl/close/{YYYY-MM}` *(RBAC: `gl:close`)*
  - `POST /gl/reopen/{YYYY-MM}` *(RBAC: `gl:reopen`)*
  - `POST /gl/reclose/{YYYY-MM}` *(RBAC: `gl:reclose`)*
  - `POST /gl/close-range/{start}/{end}` *(RBAC: `gl:close:range`)*
  - `POST /gl/reopen-range/{start}/{end}` *(RBAC: `gl:reopen:range`)*
  - `POST /gl/reclose-range/{start}/{end}` *(RBAC: `gl:reclose:range`)*
  - `GET  /gl/locks/status?from=YYYY-MM&to=YYYY-MM` *(public)*

### /compliance/books
- `GET /compliance/books/view/{view_key}` *(general_journal | general_ledger | cash_receipts_book | cash_disbursements_book)*
- `GET /compliance/books/export` *(ZIP of CSVs + transmittal)*

---

## File Structure (key parts)

