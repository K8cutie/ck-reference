# backend/app/models/__init__.py
"""
Central model registry with guarded imports.

Import this once at startup (e.g., in main.py) so SQLAlchemy sees all mapped
classes. Optional models are imported only if their dependencies are present.
"""
from app.db import Base  # re-export Base


def _try_import(stmt: str) -> bool:
    """Exec a single import statement, return True if it succeeded."""
    try:
        exec(stmt, globals(), globals())
        return True
    except Exception:
        return False


# ---- Optional/legacy models (safe best-effort) --------------------------------
_try_import("from .expense import Expense")                     # noqa: F401
_try_import("from .category import Category")                   # noqa: F401
_try_import("from .account import Account")                     # noqa: F401
_try_import("from .fund import Fund")                           # noqa: F401

# Parishioner may not exist in some deployments
_HAS_PARISHIONER = _try_import("from .parishioner import Parishioner")  # noqa: F401

# Models that depend (directly/indirectly) on Parishioner
if _HAS_PARISHIONER:
    _try_import("from .pledge import Pledge")                   # noqa: F401
    _try_import("from .transactions import Transaction")        # noqa: F401
# else: skip to avoid mapper init errors when relationships point to "Parishioner"

# Compliance / RBAC (independent)
_try_import("from .compliance import ComplianceConfig, ComplianceConfigAudit")  # noqa: F401
_try_import("from .rbac import User, Role, UserRole, RolePermission")          # noqa: F401

# ---- NEW: GL (books-only) models (always safe/independent) -------------------
_try_import("from .gl_accounting import GLAccount, JournalEntry, JournalLine, AuditLog")  # noqa: F401
