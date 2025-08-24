# scripts/set_category_gl_map.py
# Usage examples (run from C:\ckchurch1\backend, venv active):
#   python scripts/set_category_gl_map.py --category "Baptism" --debit-code 5000 --credit-code 1000
#   python scripts/set_category_gl_map.py --category-id 2 --debit-code 1000 --credit-code 4000
#   python scripts/set_category_gl_map.py --category-id 12 --debit 3 --credit 1
#
# Flags:
#   --category "Name"      (or) --category-id <id>
#   --debit <account_id>   (or) --debit-code <account_code>
#   --credit <account_id>  (or) --credit-code <account_code>

from __future__ import annotations

# --- Ensure project root (../) is on sys.path so "app" package imports work ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.categories import Category  # noqa: E402
from app.models.gl_accounting import GLAccount  # noqa: E402
from app.models.category_gl_map import CategoryGLMap  # noqa: E402


def find_account_by_code(db, code: str | int):
    return db.execute(
        select(GLAccount).where(GLAccount.code == str(code))
    ).scalars().first()


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="Category name (exact match)")
    ap.add_argument("--category-id", type=int, help="Category id")
    ap.add_argument("--debit", dest="debit_id", type=int, help="Debit GL account id")
    ap.add_argument("--credit", dest="credit_id", type=int, help="Credit GL account id")
    ap.add_argument("--debit-code", help="Debit GL account code (e.g., 5000)")
    ap.add_argument("--credit-code", help="Credit GL account code (e.g., 1000)")
    args = ap.parse_args()

    if not (args.category or args.category_id):
        raise SystemExit("Provide --category or --category-id")

    with SessionLocal() as db:
        # Resolve category
        if args.category_id:
            cat = db.get(Category, args.category_id)
        else:
            cat = db.execute(
                select(Category).where(Category.name == args.category)
            ).scalars().first()
        if not cat:
            raise SystemExit("Category not found")

        # Resolve debit/credit
        debit_id = args.debit_id
        credit_id = args.credit_id

        if args.debit_code and not debit_id:
            a = find_account_by_code(db, args.debit_code)
            if not a:
                raise SystemExit(f"Debit account code {args.debit_code} not found")
            debit_id = a.id

        if args.credit_code and not credit_id:
            a = find_account_by_code(db, args.credit_code)
            if not a:
                raise SystemExit(f"Credit account code {args.credit_code} not found")
            credit_id = a.id

        # Upsert mapping
        m = db.execute(
            select(CategoryGLMap).where(CategoryGLMap.category_id == cat.id)
        ).scalars().first()
        if not m:
            m = CategoryGLMap(category_id=cat.id)
            db.add(m)

        m.debit_account_id = debit_id
        m.credit_account_id = credit_id
        db.commit()

        print(
            f"Set mapping for category '{cat.name}' (id={cat.id}): "
            f"debit={m.debit_account_id}, credit={m.credit_account_id}"
        )


if __name__ == "__main__":
    main()
