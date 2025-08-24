from sqlalchemy import create_engine, text
import os, secrets, hashlib, re, pathlib

DB_URL = os.getenv("DATABASE_URL","postgresql+psycopg2://postgres:postgres@localhost:5432/ckchurch")
PEPPER = "ckpep_" + secrets.token_urlsafe(18)
NEW_KEY = secrets.token_urlsafe(32)
HASH = hashlib.sha256((NEW_KEY + PEPPER).encode("utf-8")).hexdigest()

# Update DB hash for admin@local
e = create_engine(DB_URL)
with e.begin() as c:
    c.execute(text("UPDATE users SET api_key_hash=:h WHERE email='admin@local'"), {"h": HASH})

# Update .env (backup first)
p = pathlib.Path(".env")
if p.exists():
    p_backup = pathlib.Path(".env.bak")
    p_backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
text = p.read_text(encoding="utf-8") if p.exists() else ""
if re.search(r"^API_KEY_PEPPER=.*$", text, flags=re.M):
    text = re.sub(r"^API_KEY_PEPPER=.*$", f"API_KEY_PEPPER={PEPPER}", text, flags=re.M)
else:
    if text and not text.endswith("\n"): text += "\n"
    text += f"API_KEY_PEPPER={PEPPER}\n"
p.write_text(text, encoding="utf-8")

print("NEW_API_KEY:", NEW_KEY)       # Copy this somewhere safe. Do NOT paste it here.
print("PEPPER_SET_IN_.ENV")          # Pepper was written to .env (backup .env.bak created if file existed).
