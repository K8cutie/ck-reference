from sqlalchemy import create_engine, text
import secrets, hashlib

DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ckchurch"

NEW_KEY = secrets.token_urlsafe(32)  # e.g., "m0pQ..."; keep this safe
HASH = hashlib.sha256(NEW_KEY.encode("utf-8")).hexdigest()  # pepper is blank today

e = create_engine(DATABASE_URL)
with e.begin() as c:
    c.execute(text("UPDATE users SET api_key_hash = :h WHERE email = :e"),
              {"h": HASH, "e": "admin@local"})
print("NEW_API_KEY:", NEW_KEY)
