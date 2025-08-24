from sqlalchemy import create_engine, text
import os, uuid, hashlib

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ckchurch")
PEPPER = os.getenv("API_KEY_PEPPER", "")

ADMIN_EMAIL = "admin@local"
API_KEY = "dev"  # change later if you want

def h(s): 
    return hashlib.sha256((s + PEPPER).encode("utf-8")).hexdigest()

engine = create_engine(DATABASE_URL)
with engine.begin() as c:
    # role: admin
    role_id = c.execute(text("SELECT id FROM roles WHERE name = :n"), {"n": "admin"}).scalar()
    if not role_id:
        role_id = uuid.uuid4()
        c.execute(text("INSERT INTO roles (id, name, description) VALUES (:id, :n, :d)"),
                  {"id": str(role_id), "n": "admin", "d": "Admin role"})
    for p in ["*", "rbac:*", "rbac:manage"]:
        c.execute(text("""
            INSERT INTO role_permissions (role_id, permission)
            SELECT :rid, :perm
            WHERE NOT EXISTS (
              SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission = :perm
            )
        """), {"rid": str(role_id), "perm": p})

    # user: admin@local with API key "dev"
    user_id = c.execute(text("SELECT id FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}).scalar()
    if not user_id:
        user_id = uuid.uuid4()
        c.execute(text("""
            INSERT INTO users (id, email, display_name, api_key_hash, is_active)
            VALUES (:id, :email, :name, :hash, true)
        """), {"id": str(user_id), "email": ADMIN_EMAIL, "name": "Admin", "hash": h(API_KEY)})

    # link user -> role
    c.execute(text("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT :uid, :rid
        WHERE NOT EXISTS (
          SELECT 1 FROM user_roles WHERE user_id = :uid AND role_id = :rid
        )
    """), {"uid": str(user_id), "rid": str(role_id)})

print("BOOTSTRAP_OK")
