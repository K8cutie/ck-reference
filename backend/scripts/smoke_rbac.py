# scripts/smoke_rbac.py
from __future__ import annotations
import argparse, os, sys, time, uuid, json

try:
    import requests  # type: ignore
except ModuleNotFoundError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    raise

def req(method: str, url: str, key: str | None = None, json_body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if key: headers["X-API-Key"] = key
    r = requests.request(method, url, headers=headers, json=json_body, timeout=15)
    try: body = r.json()
    except Exception: body = r.text
    return r.status_code, body

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-key", required=True)
    ap.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    admin_key = args.admin_key

    # 1) Create role
    role_name = f"smoke_admin_{uuid.uuid4().hex[:8]}"
    s, b = req("POST", f"{base}/rbac/roles", admin_key, {
        "name": role_name, "description": "Smoke test role", "permissions": ["rbac:manage"]
    })
    if s != 201: print("❌ create role failed", s, b, file=sys.stderr); return 1
    role_id = b["id"]; print(f"✅ role created: {role_name} ({role_id})")

    # 2) Create user with that role
    email = f"smoke+{int(time.time())}@clearkeep.local"
    s, b = req("POST", f"{base}/rbac/users", admin_key, {
        "email": email, "display_name": "Smoke User", "role_ids": [role_id]
    })
    if s != 201: print("❌ create user failed", s, b, file=sys.stderr); return 1
    smoke_key = b.get("api_key"); uid = b["id"]
    if not smoke_key: print("❌ user creation did not return api_key", file=sys.stderr); return 1
    print(f"✅ user created: {email} ({uid})")
    print(f"🔑 SMOKE KEY: {smoke_key}")

    # 3) Protected call with new key
    s, b = req("GET", f"{base}/rbac/roles", smoke_key)
    if s != 200: print("❌ protected call failed", s, b, file=sys.stderr); return 1
    print("✅ protected call OK (/rbac/roles)")

    # 4) whoami (optional)
    s, b = req("GET", f"{base}/rbac/whoami", smoke_key)
    if s == 200: print("👤 whoami:", json.dumps(b, indent=2))
    else: print("⚠️ whoami not accessible with this role (status:", s, ")")

    print("🎉 SMOKE PASSED"); return 0

if __name__ == "__main__":
    raise SystemExit(main())
