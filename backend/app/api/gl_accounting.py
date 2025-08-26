# app/api/gl_accounting.py
from __future__ import annotations

from fastapi import APIRouter

# Sub-routers (no prefixes inside; we mount them here)
from app.api.gl_accounts import router as accounts_router
from app.api.gl_journal import router as journal_router
from app.api.gl_periods import router as periods_router
from app.api.gl_books import router as books_router

# Public routers exported under the same names as before
gl_router = APIRouter(prefix="/gl", tags=["Accounting (Books-Only)"])
gl_router.include_router(accounts_router)
gl_router.include_router(journal_router)
gl_router.include_router(periods_router)

compliance_router = APIRouter(prefix="/compliance/books", tags=["BIR Books"])
compliance_router.include_router(books_router)
