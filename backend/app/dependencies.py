"""
Shared FastAPI dependency helpers.

Right now we expose only `get_db`, which provides a SQLAlchemy
session to each request and makes sure it’s closed afterward.

If you already have a `SessionLocal` factory elsewhere, just import
it here.  This keeps all routers consistent and avoids duplicate
code.
"""

from typing import Generator

from sqlalchemy.orm import Session

# 🔄  Adjust the import below if your SessionLocal lives elsewhere.
from app.db import SessionLocal  # noqa: E402


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
