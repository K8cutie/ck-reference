from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure all SQLAlchemy models are imported so relationships resolve
import app.models  # noqa: F401
import app.models.gl_accounting  # noqa: F401  # GL models (books-only)

# --- Auto-post hooks (side-effect import) ---
# Registers SQLAlchemy session hooks so newly-created ops Transactions
# automatically create & post a Journal Entry in Books.
import app.api.ops_gl_autopost_hooks  # noqa: F401

from app.api import (
    transactions,
    categories,
    parishioners,
    sacraments,
    expenses,
    accounts,
    funds,
    transfers,
    pledges,
    reports,          # /reports
    compliance,       # /compliance (existing)
    calendar_events,  # /calendar
    sigma,            # /sigma (logs/summary/control-chart)
    sigma_pareto,     # /sigma (defects + pareto)
    rbac,             # /rbac
)

# Explicit import so payroll is available even if __init__ doesn’t export it
import app.api.payroll as payroll  # provides payroll.router

# Ops/system endpoints (/health, /version)
from app.api.system import router as system_router

# Category → GL mapping endpoints
from app.api.category_gl_map import router as category_gl_map_router  # -> /categories/{id}/glmap

# GL Accounting (Books-Only)
from app.api.gl_accounting import (
    gl_router as gl_accounting_router,             # -> /gl
    compliance_router as books_compliance_router,  # -> /compliance/books, /compliance/books/export
)

# Period lock management
from app.api.gl_locks import router as gl_locks_router  # -> /gl/locks

# GL Reports
from app.api.trial_balance import router as trial_balance_router            # -> /gl/reports/trial_balance
from app.api.income_statement import router as income_statement_router      # -> /gl/reports/income_statement
from app.api.balance_sheet import router as balance_sheet_router            # -> /gl/reports/balance_sheet

app = FastAPI()

# --- CORS for local frontend dev ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(system_router)  # /health, /version

app.include_router(transactions.router, tags=["Transactions"])  # /transactions (router defines its own prefix)
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
app.include_router(category_gl_map_router)  # /categories/{id}/glmap (GET/PATCH)
app.include_router(parishioners.router, prefix="/parishioners", tags=["Parishioners"])

# Sacraments (router defines its own prefix="/sacraments")
app.include_router(sacraments.router)

# Expenses
app.include_router(expenses.router)  # /expenses

# Accounts & Funds
app.include_router(accounts.router)  # /accounts
app.include_router(funds.router)     # /funds

# Transfers & Pledges
app.include_router(transfers.router)  # /transfers
app.include_router(pledges.router)    # /pledges

# Reports
app.include_router(reports.router)    # /reports

# Compliance (existing module)
app.include_router(compliance.router)  # /compliance

# Calendar
app.include_router(calendar_events.router)  # /calendar

# Payroll (new)
app.include_router(payroll.router)  # /payroll

# Six Sigma
app.include_router(sigma.router)        # /sigma (logs/summary/control-chart)
app.include_router(sigma_pareto.router) # /sigma (defects + pareto)

# RBAC (admin)
app.include_router(rbac.router)  # /rbac

# --- Accounting (Books-Only) ---
app.include_router(gl_accounting_router)    # /gl
app.include_router(books_compliance_router) # /compliance/books, /compliance/books/export

# --- Period Locks ---
app.include_router(gl_locks_router)  # /gl/locks

# --- GL Reports ---
app.include_router(trial_balance_router)    # /gl/reports/trial_balance
app.include_router(income_statement_router) # /gl/reports/income_statement
app.include_router(balance_sheet_router)    # /gl/reports/balance_sheet
