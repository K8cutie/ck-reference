# app/api/gl_accounting.py
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
import csv
import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text  # for simple period-lock checks where needed

from app.db import SessionLocal
from app.schemas.gl_accounting import (
    GLAccountCreate, GLAccountUpdate, GLAccountOut,
    JournalEntryCreate, JournalEntryOut,
)
from app.services.gl_accounting import (
    # accounts
    create_gl_account, update_gl_account, list_gl_accounts,
    # journal
    create_journal_entry, post_journal_entry, list_journal_entries,
    unpost_journal_entry, reverse_journal_entry,
    # reports
    fetch_books_view,
    # period services
    close_period, reopen_period,
)

# -----------------------------
# DB dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Routers
# -----------------------------
gl_router = APIRouter(prefix="/gl", tags=["Accounting (Books-Only)"])
# NOTE: put the books endpoints under a distinct prefix to avoid clashes
compliance_router = APIRouter(prefix="/compliance/books", tags=["BIR Books"])

# ------------------------------------
# GL Accounts (Chart of Accounts)
# ------------------------------------
@gl_router.get("/accounts", response_model=List[GLAccountOut])
def api_list_gl_accounts(
    q: Optional[str] = Query(None, description="Search by code/name"),
    type: Optional[str] = Query(None, pattern="^(asset|liability|equity|income|expense)$"),
    is_active: Optional[bool] = None,
    is_cash: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return list_gl_accounts(db, q=q, type_=type, is_active=is_active, is_cash=is_cash, limit=limit, offset=offset)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"GL list failed: {e}")


@gl_router.post("/accounts", response_model=GLAccountOut)
def api_create_gl_account(payload: GLAccountCreate, db: Session = Depends(get_db)):
    try:
        acct = create_gl_account(
            db,
            code=payload.code,
            name=payload.name,
            type_=payload.type.value if hasattr(payload.type, "value") else payload.type,
            normal_side=payload.normal_side.value if hasattr(payload.normal_side, "value") else payload.normal_side,
            is_cash=payload.is_cash,
            description=payload.description,
        )
        return acct
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"GL create failed: {e}")


@gl_router.patch("/accounts/{account_id}", response_model=GLAccountOut)
def api_update_gl_account(account_id: int, payload: GLAccountUpdate, db: Session = Depends(get_db)):
    try:
        acct = update_gl_account(
            db,
            account_id,
            code=payload.code,
            name=payload.name,
            type_=payload.type.value if getattr(payload, "type", None) else None,
            normal_side=payload.normal_side.value if getattr(payload, "normal_side", None) else None,
            is_cash=payload.is_cash,
            description=payload.description,
            is_active=payload.is_active,
        )
        return acct
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"GL update failed: {e}")

# ------------------------------------
# Journal Entries
# ------------------------------------
@gl_router.get("/journal", response_model=List[JournalEntryOut])
def api_list_journal_entries(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    reference_no: Optional[str] = None,
    source_module: Optional[str] = None,
    is_locked: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return list_journal_entries(
            db,
            date_from=date_from,
            date_to=date_to,
            reference_no=reference_no,
            source_module=source_module,
            is_locked=is_locked,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"JE list failed: {e}")


@gl_router.post("/journal", response_model=JournalEntryOut)
def api_create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    try:
        je = create_journal_entry(
            db,
            entry_date=payload.entry_date,
            memo=payload.memo,
            currency_code=payload.currency_code,
            reference_no=payload.reference_no,
            source_module=payload.source_module,
            source_id=payload.source_id,
            lines=[l.model_dump() for l in payload.lines],
            created_by_user_id=None,
        )
        return je
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"JE create failed: {e}")


@gl_router.post("/journal/{je_id}/post", response_model=JournalEntryOut)
def api_post_journal_entry(je_id: int, db: Session = Depends(get_db)):
    try:
        return post_journal_entry(db, je_id, posted_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"JE post failed: {e}")


@gl_router.post("/journal/{je_id}/unpost", response_model=JournalEntryOut)
def api_unpost_journal_entry(je_id: int, db: Session = Depends(get_db)):
    try:
        return unpost_journal_entry(db, je_id, unposted_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"JE unpost failed: {e}")


@gl_router.post("/journal/{je_id}/reverse", response_model=JournalEntryOut)
def api_reverse_journal_entry(
    je_id: int,
    as_of: Optional[date] = Query(None, description="Reverse as of this date; defaults to source JE date"),
    db: Session = Depends(get_db),
):
    try:
        return reverse_journal_entry(db, je_id, as_of=as_of, created_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"JE reverse failed: {e}")

# ------------------------------------
# Opening Balances — create & post one opening JE for the month
# ------------------------------------
@gl_router.post("/opening-balances", response_model=JournalEntryOut)
def api_opening_balances(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    """
    Creates a posted Opening Balances JE on the **first day** of the month of `payload.entry_date`,
    with reference OPEN-YYYYMM. Rejects locked months or duplicates for the same month.
    Only the `lines` are used from payload; other fields are normalized.
    """
    try:
        if not payload.entry_date:
            raise HTTPException(status_code=400, detail="entry_date is required")

        first = date(payload.entry_date.year, payload.entry_date.month, 1)
        y_m = first.strftime("%Y-%m")
        ref = f"OPEN-{first.strftime('%Y%m')}"

        # Reject locked period
        row = db.execute(
            text("SELECT is_locked FROM gl_period_locks WHERE period_month = :pm LIMIT 1"),
            {"pm": first},
        ).first()
        if row and bool(row[0]):
            raise HTTPException(status_code=400, detail=f"Cannot create opening balances: period {y_m} is locked.")

        # Prevent duplicate opening JE for the month (reference + posted)
        existing = list_journal_entries(db, reference_no=ref, is_locked=True, limit=1, offset=0)
        if existing:
            raise HTTPException(status_code=409, detail=f"Opening balances already posted for {y_m}.")

        # Create draft JE on the first of the month
        je = create_journal_entry(
            db,
            entry_date=first,
            memo="Opening Balances",
            currency_code=payload.currency_code or "PHP",
            reference_no=ref,
            source_module="opening",
            source_id=ref,
            lines=[l.model_dump() for l in payload.lines],
            created_by_user_id=None,
        )

        # Post it
        je = post_journal_entry(db, je.id, posted_by_user_id=None)
        return je

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Opening balances failed: {e}")

# ------------------------------------
# Period Close / Reopen
# ------------------------------------
@gl_router.post("/close/{year}-{month}", response_model=JournalEntryOut)
def api_close_period(
    year: int,
    month: int,
    equity_account_id: int = Query(..., description="Equity account to receive Net Income/Loss"),
    note: Optional[str] = Query(None, description="Optional note stored in the period lock"),
    db: Session = Depends(get_db),
):
    """
    Close Income/Expense into Equity for (year, month). Creates a JE with ref CLOSE-YYYYMM
    dated on the last day of the month, then locks the month.
    """
    try:
        je = close_period(
            db,
            year,
            month,
            equity_account_id=equity_account_id,
            note=note,
            created_by_user_id=None,
        )
        return je
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Close period failed: {e}")


@gl_router.post("/reopen/{year}-{month}")
def api_reopen_period(
    year: int,
    month: int,
    note: Optional[str] = Query(None, description="Reason for reopening"),
    db: Session = Depends(get_db),
):
    """
    Reopen a previously locked period. Does NOT reverse closing entries.
    """
    try:
        return reopen_period(db, year, month, note=note)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Reopen period failed: {e}")

# ------------------------------------
# Books (JSON and Export ZIP)
# ------------------------------------
@compliance_router.get("/export")
def api_books_export_zip(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_html_transmittal: bool = True,
    db: Session = Depends(get_db),
):
    """
    Exports CSVs for BIR Books (GJ, GL, CRB, CDB) and a simple HTML transmittal.
    """
    try:
        # Pull all four views
        view_keys = ["general_journal", "general_ledger", "cash_receipts_book", "cash_disbursements_book"]
        data = {k: fetch_books_view(db, k, date_from=date_from, date_to=date_to) for k in view_keys}

        # CSV header orders per view
        headers = {
            "general_journal": ["date", "entry_no", "reference", "description", "account_code", "account_title", "debit", "credit"],
            "general_ledger":  ["account_code", "account_title", "date", "description", "reference", "debit", "credit", "running_balance"],
            "cash_receipts_book": ["date", "reference", "description", "credit_accounts", "amount_received"],
            "cash_disbursements_book": ["date", "reference", "description", "debit_accounts", "amount_disbursed"],
        }

        def csv_bytes(view: str, rows: List[dict]) -> bytes:
            buf = StringIO()
            writer = csv.DictWriter(buf, fieldnames=headers[view], extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
            return buf.getvalue().encode("utf-8-sig")  # BOM for Excel-friendliness

        # Build ZIP in-memory
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_buf = BytesIO()
        with ZipFile(zip_buf, "w", ZIP_DEFLATED) as zf:
            for vk in view_keys:
                zf.writestr(f"{vk}.csv", csv_bytes(vk, data[vk]))
            if include_html_transmittal:
                html = _render_transmittal_html(date_from, date_to, data)
                zf.writestr("transmittal.html", html.encode("utf-8"))

        zip_buf.seek(0)
        filename = f"books_export_{now}.zip"
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Books export failed: {e}")


@compliance_router.get("/view/{view_key}")
def api_books_json(
    view_key: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    view_key: one of general_journal, general_ledger, cash_receipts_book, cash_disbursements_book
    """
    try:
        rows = fetch_books_view(db, view_key, date_from=date_from, date_to=date_to)
        return {"view": view_key, "count": len(rows), "rows": rows}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Books fetch failed: {e}")

# ------------------------------------
# Helper: Transmittal HTML
# ------------------------------------
def _render_transmittal_html(date_from: Optional[date], date_to: Optional[date], data: dict) -> str:
    df = date_from.isoformat() if date_from else "(none)"
    dt = date_to.isoformat() if date_to else "(none)"
    counts = {k: len(v) for k, v in data.items()}
    total_rows = sum(counts.values())
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Books Transmittal</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
h1 {{ margin: 0 0 8px; }}
table {{ border-collapse: collapse; margin-top: 16px; }}
td, th {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
small {{ color: #555; }}
</style>
</head>
<body>
  <h1>Books Export Transmittal</h1>
  <small>Generated: {datetime.now().isoformat(timespec='seconds')}</small>
  <p>Date range: <b>{df}</b> to <b>{dt}</b></p>
  <table>
    <thead><tr><th>View</th><th>Rows</th></tr></thead>
    <tbody>
      <tr><td>General Journal</td><td>{counts.get('general_journal', 0)}</td></tr>
      <tr><td>General Ledger</td><td>{counts.get('general_ledger', 0)}</td></tr>
      <tr><td>Cash Receipts Book</td><td>{counts.get('cash_receipts_book', 0)}</td></tr>
      <tr><td>Cash Disbursements Book</td><td>{counts.get('cash_disbursements_book', 0)}</td></tr>
      <tr><th>Total</th><th>{total_rows}</th></tr>
    </tbody>
  </table>
  <p>This archive contains CSV files for each book and this transmittal summary.</p>
</body>
</html>"""
