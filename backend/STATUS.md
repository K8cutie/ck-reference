# ClearKeep — STATUS.md
**Date:** 2025-09-10 (Asia/Manila)  
**Canonical local root:** `C:\ckchurch1`  
**Launcher:** `start_backend.ps1` (passes `--env-file .env`)  
**Timezone:** Asia/Manila

---

## Process Guardrails (do not deviate)
- **Single-Step** — one instruction at a time; move only after success is verified.
- **Read-First + Anchors** — *No anchor = no patch*. Always read current file(s) and quote unique anchors before proposing changes.
- **One-File Rule** — each step changes **exactly one file** (full copy-paste or a single new Alembic revision).
- **Acceptance Check** — every step includes explicit checks/commands and expected results.
- **STATUS.md is source-of-truth** for environment & sprint alignment.

---

## Environment & Launch
- **Python**: 3.12  • **Framework**: FastAPI + Uvicorn  • **DB**: PostgreSQL 16 (Docker: `ckchurch-db-1`)
- **DB URL**: from `.env`
  ```
  DATABASE_URL=postgresql+psycopg2://ckchurch_app:cksecret@localhost:5432/sampletest
  ```
- **Start backend**
  ```powershell
  # from C:\ckchurch1
  .\start_backend.ps1
  ```
  Expected logs: “Application startup complete.”

---

## Current Sprint (Sprint 3 — Organization Layer)
**Goal:** Enable a Diocese (parent org) to view finances across parishes, without breaking solo-parish installs.

### Feature status (✅ = done in this sprint)
- ✅ Org core tables: `organizations`, `org_units`, `memberships`
- ✅ Scoped facts with `org_id`/`unit_id`:  
  `journal_entries`, `journal_lines`, `gl_period_locks`, `transactions`, `categories`,  
  `sacraments`, `calendar_events`, `employees`, `payslips`, `pledges`, `parishioners`
- ✅ Org APIs (`/orgs/*`): KPIs, unit leaderboard, financials CSV
- ✅ Compliance (period locks) endpoint **present but disabled by default**
- 🔜 UI: Org Command Center (frontend)

---

## RBAC / Flags
- **RBAC**: building behind dev bypass (turn on before prod)
  ```
  RBAC_ENFORCE=false
  ```
- **Org Compliance Locks** (not required for church finance / non-BIR):
  ```
  ORG_LOCKS_ENABLED=false  # set true to enable /orgs/{id}/compliance/period-locks
  ```

---

## Endpoint Map (high-level)
- Ops: `/transactions`, `/categories`, `/parishioners`, `/sacraments`, `/expenses`, `/accounts`, `/funds`, `/transfers`, `/pledges`, `/calendar`, `/payroll`, `/reports`, `/compliance`, `/rbac`, `/sigma/*`
- Books (GL): `/gl/*`, `/compliance/books/*`, `/gl/locks/*`, `/gl/reports/*`
- **Organization (new)**:
  - `GET /orgs/{org_id}/kpis?month=YYYY-MM`
  - `GET /orgs/{org_id}/units/leaderboard?month=YYYY-MM&metric=revenue|revenue_growth&limit=N`
  - `GET /orgs/{org_id}/reports/financials?from=YYYY-MM&to=YYYY-MM` (CSV)
  - `GET /orgs/{org_id}/compliance/period-locks?month=YYYY-MM` (returns `"feature":"disabled"` unless `ORG_LOCKS_ENABLED=true`)

---

## Alembic Migrations (applied this sprint)
Order reflects ancestry; last item is current head.
- `b1a2c3d4e5f6` — **org_layer_foundation** (organizations, org_units, memberships)
- `f7a1e2c3d4e6` — **merge heads** (employee comp history + org foundation)
- `c2d3e4f5a6b7` — scope **journal_entries**, **gl_period_locks**
- `d3e4f5a6b7c8` — scope **journal_lines**
- `e4f5a6b7c8d9` — scope **transactions**
- `f6a7b8c9d0e1` — scope **categories** (org-wide; unit optional)
- `a7b8c9d0e1f2` — scope **sacraments**
- `b8c9d0e1f2a3` — scope **calendar_events**
- `c9d0e1f2a3b4` — scope **employees**
- `d0e1f2a3b4c5` — scope **payslips**
- `e1f2a3b4c6d7` — scope **pledges**
- `f1a2b3c4d5e6` — scope **parishioners**  ← **HEAD**

**Index pattern added where relevant**  
- `ix_<table>_org_unit_<time_or_fk>` e.g.  
  `ix_transactions_org_unit_date`, `ix_journal_entries_org_unit_entry_date`,  
  `ix_gl_period_locks_org_unit_period_month`, `ix_calendar_events_org_unit_start_at`,  
  `ix_employees_org_unit_last_name`, `ix_payslips_org_unit_created_at`,  
  `ix_parishioners_org_unit_last_name`, `ix_sacraments_org_unit_date`,  
  `ix_categories_org_unit_name`

---

## Architecture Baseline — Organization Layer (2025-09-10)
**Goal:** Support both solo churches and Diocese oversight without forcing hierarchy. This is the **canonical structure**; new work must align with it.

### A) Deployment Modes (choose per install)
1. **Solo Parish (default)**  
   - One **organization** = the church itself.  
   - One **org_unit** = “Main Parish” (or similar).  
   - **/orgs/** endpoints hidden by RBAC for parish users.
2. **Diocese-managed (multi-parish, single tenant)**  
   - One **organization** = the Diocese.  
   - Each **parish** = an **org_unit** under that org.  
   - Diocese roles see all units; parish roles see their own unit.
3. **Federated oversight (optional)**  
   - Each church is its **own organization**.  
   - Diocese consumes **CSV/API** exports for oversight; no cross-tenant DB sharing.

> **Default install behavior:** create **1 organization + 1 org_unit**; all facts scoped there.

### B) Data Model & Scoping (canonical)
- Control tables:  
  - `organizations(id, code, name, created_at)`  
  - `org_units(id, org_id→organizations.id, code, name, unit_type, is_active, created_at)`  
  - `memberships(id, principal_kind, principal_id, org_id, unit_id?, role, created_at)`  
    - Unique: `(org_id, unit_id, principal_id, role)`
- **All fact tables must carry**:  
  `org_id BIGINT NOT NULL`, `unit_id BIGINT [NOT NULL unless explicitly org-wide]` with FKs.
- **Backfill invariant:** when adding scope to a legacy table → create defaults (`DIO-DEFAULT`, `PAR-DEFAULT`) → backfill → `SET NOT NULL` → add indexes → add FKs.
- **Index rule for new facts:**  
  `CREATE INDEX ix_<table>_org_unit_<time_or_fk> ON <table>(org_id, unit_id, <time_or_fk>);`

### C) RBAC & Visibility (canonical)
- Minimum roles:  
  - **diocese_admin (org)** — full org-wide access  
  - **finance_officer (org)** — dashboards/exports  
  - **parish_admin (unit)** — CRUD within unit  
  - **auditor (org/unit)** — read-only  
- Permission keys:  
  - `org:dashboard:view`, `org:reports:export`
- Dev mode (`RBAC_ENFORCE=false`) is allowed while building; enable before prod.

### D) Feature Flags (defaults)
- **Period-locks compliance** (not required for non-BIR church finance):  
  - Endpoint present but **disabled** by default (`ORG_LOCKS_ENABLED=false`)  
  - Set `true` to enable coverage reporting.

### E) Org-level APIs (current)
- `GET /orgs/{org_id}/kpis?month=YYYY-MM` → revenue, expense, net, freshness  
- `GET /orgs/{org_id}/units/leaderboard?month=YYYY-MM&metric=revenue|revenue_growth&limit=N`  
- `GET /orgs/{org_id}/reports/financials?from=YYYY-MM&to=YYYY-MM` → CSV (month, unit_code, revenue, expense, net)  
- `GET /orgs/{org_id}/compliance/period-locks?month=YYYY-MM` → **feature-flagged** (returns `"feature":"disabled"` when off)

**SQL pattern (org-safe queries)**
```sql
-- Always filter by org, then unit or time
... WHERE t.org_id = :org_id
      AND (:unit_id IS NULL OR t.unit_id = :unit_id)
      AND t.date >= :start AND t.date < :end
```

### F) Frontend Guidance (first cut)
- Add **Diocese Command Center**: `/orgs/{id}/dashboard`  
  - Tiles: Revenue vs Budget (later), Pledges vs Collections, Top/Bottom Parishes, Data Freshness  
  - Table: unit leaderboard (metric switcher), CSV export link  
- Solo installs: hide Org nav unless user has org-level role.

### G) Migrations & Compatibility Rules
1. One file per change; reversible `upgrade()/downgrade()`.
2. Order: **nullable cols → backfill → NOT NULL → indexes → FKs**.
3. Multiple heads → add a **merge revision** (no-op schema).
4. Never drop user data on downgrade.

### H) Operational Defaults
- **Install:** creates org + unit; seed categories per module as usual.
- **Demo:** may seed multiple `org_units`; transactions can be sampled from default unit and scaled for variety.
- **Backups/Isolation:** **organization** is the tenant boundary (exports, restores, billing).

---

## Quick Smoke (Org)
```powershell
# Org 1 KPIs (month with activity)
Invoke-RestMethod http://127.0.0.1:8000/orgs/1/kpis?month=2023-12

# Unit leaderboard
Invoke-RestMethod http://127.0.0.1:8000/orgs/1/units/leaderboard?month=2023-12&metric=revenue

# CSV export (Q4 2023)
Invoke-WebRequest "http://127.0.0.1:8000/orgs/1/reports/financials?from=2023-10&to=2023-12" -OutFile "$env:TEMP\org_1_fin_2023Q4.csv"
```
