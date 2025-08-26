from __future__ import annotations

from datetime import date, datetime
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
import csv
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.gl_accounting import fetch_books_view

router = APIRouter()  # mounted under /compliance/books

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/export")
def api_books_export_zip(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_html_transmittal: bool = True,
    db: Session = Depends(get_db),
):
    try:
        view_keys = ["general_journal", "general_ledger", "cash_receipts_book", "cash_disbursements_book"]
        data = {k: fetch_books_view(db, k, date_from=date_from, date_to=date_to) for k in view_keys}

        headers = {
            "general_journal": ["date", "entry_no", "reference", "description", "account_code", "account_title", "debit", "credit"],
            "general_ledger": ["account_code", "account_title", "date", "description", "reference", "debit", "credit", "running_balance"],
            "cash_receipts_book": ["date", "reference", "description", "credit_accounts", "amount_received"],
            "cash_disbursements_book": ["date", "reference", "description", "debit_accounts", "amount_disbursed"],
        }

        def csv_bytes(view: str, rows: List[dict]) -> bytes:
            buf = StringIO()
            writer = csv.DictWriter(buf, fieldnames=headers[view], extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
            return buf.getvalue().encode("utf-8-sig")

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
        raise HTTPException(status_code=500, detail=f"Books export failed: {e}")

@router.get("/view/{view_key}")
def api_books_json(
    view_key: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    try:
        rows = fetch_books_view(db, view_key, date_from=date_from, date_to=date_to)
        return {"view": view_key, "count": len(rows), "rows": rows}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Books fetch failed: {e}")

def _render_transmittal_html(date_from: Optional[date], date_to: Optional[date], data: dict) -> str:
    df = date_from.isoformat() if date_from else "(none)"
    dt = date_to.isoformat() if date_to else "(none)"
    counts = {k: len(v) for k, v in data.items()}
    total_rows = sum(counts.values())

    return f"""\
# Books Export Transmittal

Generated: {datetime.now().isoformat(timespec='seconds')}

Date range: {df} to {dt}

| View | Rows |
| --- | ---: |
| General Journal | {counts.get('general_journal', 0)} |
| General Ledger | {counts.get('general_ledger', 0)} |
| Cash Receipts Book | {counts.get('cash_receipts_book', 0)} |
| Cash Disbursements Book | {counts.get('cash_disbursements_book', 0)} |
| **Total** | **{total_rows}** |

This archive contains CSV files for each book and this transmittal summary.
"""
