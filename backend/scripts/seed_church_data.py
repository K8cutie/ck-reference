# backend/scripts/seed_church_data.py
"""
Seed realistic 3-year church data into a target PostgreSQL database (e.g., 'sampletest').

✅ Features
- Auto-create target DB (PostgreSQL) if missing
- Auto-run Alembic migrations against the target DB
- Idempotent category upsert; deterministic batch_id for non-sacrament Tx
- Parishioners (~2,000), Sacraments (with linked income Tx),
  Sunday-peaked offertory/intentions, monthly/seasonal expenses,
  Year-end Calendar Drive (income + printing COGS)
- Payment methods with rising GCash adoption across years

Usage (from repo root):
  python backend/scripts/seed_church_data.py --from 2023-01-01 --to 2025-08-31 \
      --profile parish_medium --db-name sampletest --dry-run

  python backend/scripts/seed_church_data.py --from 2023-01-01 --to 2025-08-31 \
      --profile parish_medium --db-name sampletest

Notes:
- No extra pip deps required (no Faker). Names are generated from built-in lists.
- Does NOT change your default DATABASE_URL; runs entirely against the target DB.
"""
from __future__ import annotations

import argparse
import configparser
import dataclasses
import json
import math
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Paths & import setup (so "import app" works regardless of CWD)
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve()
BACKEND_ROOT = HERE.parents[1]          # .../backend
REPO_ROOT = BACKEND_ROOT.parent         # repo root

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _parse_date(s: str) -> date:
    return date.fromisoformat(s)

def _choices_profile() -> List[str]:
    return ["parish_medium"]

parser = argparse.ArgumentParser(description="Seed ClearKeep Church sample data.")
parser.add_argument("--from", dest="date_from", type=_parse_date, required=True)
parser.add_argument("--to", dest="date_to", type=_parse_date, required=True)
parser.add_argument("--profile", dest="profile", choices=_choices_profile(), default="parish_medium")
parser.add_argument("--db-name", dest="db_name", help="Target database name to create/use (e.g., sampletest)")
parser.add_argument("--db-url", dest="db_url", help="Full SQLAlchemy URL for the target DB (overrides --db-name)")
parser.add_argument("--dry-run", dest="dry_run", action="store_true")
parser.add_argument("--reset", dest="reset", action="store_true", help="Remove rows in the window before seeding")
parser.add_argument("--parishioners", dest="parishioner_target", type=int, default=2000)
parser.add_argument("--seed", dest="rng_seed", type=int, default=42)
parser.add_argument("--no-migrate", dest="no_migrate", action="store_true", help="Skip Alembic migrations (not recommended)")

# -----------------------------------------------------------------------------
# Utilities (DB URL build, DB ensure, Alembic)
# -----------------------------------------------------------------------------
def _read_base_db_url_from_env_or_ini() -> str:
    # Prefer env (how the app runs), else fallback to alembic.ini
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    ini = BACKEND_ROOT / "alembic.ini"
    cfg = configparser.ConfigParser()
    cfg.read(ini)
    url = cfg.get("alembic", "sqlalchemy.url", fallback=None)
    if not url:
        raise SystemExit("Cannot find a base DATABASE_URL. Set env or fill backend/alembic.ini.")
    return url

def _split_db_url(url: str) -> Tuple[str, str]:
    # Split ".../dbname?query" → ("prefix", "dbname?query")
    m = re.match(r"^(?P<prefix>.*://[^/]+/)(?P<dbpart>[^?]+(?:\?.*)?)$", url)
    if not m:
        raise ValueError(f"Unrecognized DB URL: {url}")
    return m.group("prefix"), m.group("dbpart")

def _replace_dbname(url: str, new_db: str) -> str:
    prefix, _ = _split_db_url(url)
    return f"{prefix}{new_db}"

def _build_target_db_url(db_name: Optional[str], db_url: Optional[str]) -> str:
    if db_url:
        return db_url
    base = _read_base_db_url_from_env_or_ini()
    return _replace_dbname(base, db_name or "sampletest")

def _with_db(url: str, dbname: str) -> str:
    return _replace_dbname(url, dbname)

def _ensure_database_exists(target_url: str) -> None:
    """
    Try connecting; if fails with 'does not exist', connect to 'postgres' DB and CREATE DATABASE.
    """
    from sqlalchemy import create_engine, text
    try:
        eng = create_engine(target_url, isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" not in msg and "unknown database" not in msg:
            print(f"[ensure_database_exists] connect failed: {e}")
            raise

    base = _read_base_db_url_from_env_or_ini()
    maint = _with_db(base, "postgres")
    target_db_name = _split_db_url(target_url)[1].split("?")[0]
    from sqlalchemy import create_engine, text
    eng = create_engine(maint, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        print(f"[ensure_database_exists] Creating database {target_db_name} ...")
        conn.execute(text(f'CREATE DATABASE "{target_db_name}"'))

def _alembic_upgrade_head(target_url: str) -> None:
    ini_path = BACKEND_ROOT / "alembic.ini"
    env = os.environ.copy()
    env["DATABASE_URL"] = target_url
    env["PYTHONPATH"] = f"{BACKEND_ROOT}{os.pathsep}{env.get('PYTHONPATH','')}"
    cmd = ["alembic", "-c", str(ini_path), "upgrade", "head"]
    print("[alembic]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(BACKEND_ROOT), env=env)

# -----------------------------------------------------------------------------
# Domain constants & helpers
# -----------------------------------------------------------------------------
PH_FIRST = [
    "Juan", "Jose", "Pedro", "Carlos", "Miguel", "Antonio", "Ramon", "Andres",
    "Maria", "Ana", "Rosa", "Carmen", "Angela", "Teresa", "Luz", "Isabel",
    "Mark", "John", "Paul", "James", "Grace", "Joy", "Faith", "Hope", "Marie",
]
PH_LAST = [
    "Dela Cruz", "Santos", "Reyes", "Garcia", "Lopez", "Gonzales", "Castillo",
    "Aquino", "Ramos", "Cruz", "Torres", "Mendoza", "Flores", "Bautista",
    "Villanueva", "Diaz", "Navarro", "Rivera", "Romero", "Domingo",
]
PH_SUFFIX = [None, None, None, "Jr.", "III"]

INCOME_CATS = [
    "Offertory – Sunday",
    "Offertory – Weekday",
    "Mass Intentions",
    "Donations – Unrestricted",
    "Sacraments – Baptism",
    "Sacraments – Confirmation",
    "Sacraments – Marriage",
    "Sacraments – Funeral",
    "Fundraising – Calendar Drive",
    "Stipends & Honoraria",
]
EXPENSE_CATS = [
    "Utilities – Electricity",
    "Utilities – Water",
    "Utilities – Internet/Phone",
    "Salaries & Honoraria",
    "Liturgical Supplies",
    "Office Supplies",
    "Repairs & Maintenance",
    "Charity/Outreach",
    "Banking & Fees",
    "Transportation/Fuel",
    "Calendar Printing (COGS)",
]
ALL_CATEGORY_NAMES = INCOME_CATS + EXPENSE_CATS

SUNDAY_MASS_TIMES = ["06:00", "08:00", "10:00", "17:00"]
WEEKDAY_MASS_TIME = "06:00"

def daterange(d0: date, d1: date) -> Iterable[date]:
    cur = d0
    step = timedelta(days=1)
    while cur <= d1:
        yield cur
        cur += step

def is_holy_week(d: date) -> bool:
    Y = d.year
    a = Y % 19
    b = Y // 100
    c = Y % 100
    d1 = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d1 - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*L) // 451
    month = (h + L - 7*m + 114) // 31
    day = ((h + L - 7*m + 114) % 31) + 1
    easter = date(Y, month, day)
    start = easter - timedelta(days=7)
    return start <= d <= easter

def is_simbang_gabi(d: date) -> bool:
    return (d.month == 12 and 16 <= d.day <= 24)

def gcash_share_for_year(y: int) -> float:
    return {2023: 0.18, 2024: 0.26, 2025: 0.36}.get(y, 0.30)

def pick_payment_method(rng: random.Random, y: int) -> str:
    p_gcash = gcash_share_for_year(y)
    r = rng.random()
    if r < p_gcash:
        return "gcash"
    r -= p_gcash
    if r < 0.55:
        return "cash"
    r -= 0.55
    if r < 0.20:
        return "check"
    r -= 0.20
    if r < 0.20:
        return "bank"
    return "other"

def lnorm_amount(rng: random.Random, mean: float, sigma: float, floor: float, ceil: float) -> float:
    mu = math.log(max(mean, 1e-6)) - (sigma ** 2) / 2.0
    val = rng.lognormvariate(mu, sigma)
    val = max(floor, min(ceil, val))
    return round(val, 2)

# -----------------------------------------------------------------------------
# Seeding internals (run AFTER we point DATABASE_URL at target)
# -----------------------------------------------------------------------------
@dataclass
class SeedStats:
    categories_upserted: int = 0
    parishioners_created: int = 0
    sacraments_created: Counter = dataclasses.field(default_factory=Counter)
    tx_created: int = 0
    tx_income: Decimal = Decimal("0.00")
    tx_expense: Decimal = Decimal("0.00")

def _import_app_modules():
    from app.db import Base, SessionLocal  # noqa: F401
    import importlib, pkgutil
    import app.models as m
    for _, modname, _ in pkgutil.walk_packages(m.__path__, m.__name__ + "."):
        importlib.import_module(modname)
    # Keep available for _delete_window
    from app.services import sacraments as sac_svc  # noqa: F401
    return True

def _session():
    from app.db import SessionLocal
    return SessionLocal()

def _upsert_categories(db, names: List[str]) -> int:
    from sqlalchemy import text
    upserted = 0
    for name in names:
        row = db.execute(text("SELECT id FROM categories WHERE name=:n LIMIT 1"), {"n": name}).first()
        if row:
            continue
        db.execute(
            text("INSERT INTO categories (name, description) VALUES (:n, :d)"),
            {"n": name, "d": None},
        )
        upserted += 1
    db.commit()
    return upserted

def _ensure_parishioners(db, target_count: int, rng: random.Random) -> int:
    from sqlalchemy import text
    cur = db.execute(text("SELECT COUNT(*) FROM parishioners")).scalar() or 0
    to_make = max(0, target_count - int(cur))
    if to_make <= 0:
        return 0
    rows = []
    for _ in range(to_make):
        fn = rng.choice(PH_FIRST)
        ln = rng.choice(PH_LAST)
        mn = None if rng.random() < 0.7 else rng.choice(PH_FIRST)[:1]
        sf = rng.choice(PH_SUFFIX)
        contact = None
        rows.append((fn, mn, ln, sf, contact))
    from sqlalchemy import text
    db.execute(text("""
        INSERT INTO parishioners (first_name, middle_name, last_name, suffix, contact_number)
        VALUES {}""".format(
        ",".join(["(:f{0}, :m{0}, :l{0}, :s{0}, :c{0})".format(i) for i in range(len(rows))])
    )), {
        **{f"f{i}": r[0] for i, r in enumerate(rows)},
        **{f"m{i}": r[1] for i, r in enumerate(rows)},
        **{f"l{i}": r[2] for i, r in enumerate(rows)},
        **{f"s{i}": r[3] for i, r in enumerate(rows)},
        **{f"c{i}": r[4] for i, r in enumerate(rows)},
    })
    db.commit()
    return to_make

def _get_any_parishioner_ids(db, limit: int, rng: random.Random) -> List[int]:
    from sqlalchemy import text
    rows = db.execute(text("SELECT id FROM parishioners ORDER BY id")).fetchall()
    ids = [int(r[0]) for r in rows]
    rng.shuffle(ids)
    return ids[:limit] if limit <= len(ids) else ids

def _get_category_id(db, name: str) -> Optional[int]:
    from sqlalchemy import text
    row = db.execute(text("SELECT id FROM categories WHERE name=:n LIMIT 1"), {"n": name}).first()
    return int(row[0]) if row else None

def _insert_tx(
    db,
    d: date,
    description: str,
    amount: float,
    ttype: str,  # "income" or "expense"
    category_name: str,
    payment_method: str,
    batch_id: str,
) -> None:
    from app.models.transactions import Transaction, TransactionType, PaymentMethod
    cat_id = _get_category_id(db, category_name)
    tx = Transaction(
        date=d,
        description=description,
        amount=Decimal(str(amount)),
        type=TransactionType.income if ttype == "income" else TransactionType.expense,
        category_id=cat_id,
        payment_method=PaymentMethod(payment_method),
        reference_no=None,
        batch_id=batch_id,
    )
    db.add(tx)

def _create_sacrament_and_tx(
    db,
    d: date,
    sac_type: str,             # 'baptism' | 'marriage' | 'death' | 'confirmation' | 'first_communion' | 'anointing'
    fee_val: Decimal,
    pid: Optional[int],
    notes: str,
    details: Dict[str, Any],
    batch_id: str,
    rng: random.Random,
    stats: SeedStats,
) -> None:
    from app.models.sacrament import Sacrament, SacramentType
    from app.models.transactions import Transaction, TransactionType, PaymentMethod

    type_map = {
        "baptism": SacramentType.BAPTISM,
        "marriage": SacramentType.MARRIAGE,
        "death": SacramentType.DEATH,
        "confirmation": SacramentType.CONFIRMATION,
        "first_communion": SacramentType.FIRST_COMMUNION,
        "anointing": SacramentType.ANOINTING,
    }
    cat_map = {
        "baptism": "Sacraments – Baptism",
        "marriage": "Sacraments – Marriage",
        "death": "Sacraments – Funeral",
        "confirmation": "Sacraments – Confirmation",
        "first_communion": "Sacraments – Confirmation",
        "anointing": "Sacraments – Funeral",
    }

    s = Sacrament(
        type=type_map[sac_type],
        date=d,
        parishioner_id=pid,
        fee=Decimal(str(fee_val)),
        details=details or {},
        notes=notes,
    )
    db.add(s)
    db.flush()  # get s.id

    pm = pick_payment_method(rng, d.year)
    tx = Transaction(
        date=d,
        description=f"Sacrament fee – {sac_type.replace('_',' ').title()}",
        amount=Decimal(str(fee_val)),
        type=TransactionType.income,
        category_id=_get_category_id(db, cat_map[sac_type]),
        payment_method=PaymentMethod(pm),
        reference_no=f"SAC-{s.id}",
        batch_id=batch_id,
    )
    db.add(tx)
    stats.sacraments_created[sac_type] += 1

def _seed_sacraments_for_month(db, year: int, month: int, rng: random.Random, batch_id: str, stats: SeedStats) -> None:
    """
    Create realistic sacrament rows + linked income transactions.
    - Baptisms: ~18 ± 6 / month (cluster on Saturdays)
    - Marriages: ~6 ± 3 / month (peaks in June/Dec)
    - Funerals: ~12 ± 4 / month (spread)
    - Confirmation: Apr & Oct batches
    - First Communion: May batches
    """
    p_ids = _get_any_parishioner_ids(db, 500, rng)

    base_bap = max(6, int(rng.normalvariate(18, 6)))
    base_mar = max(1, int(rng.normalvariate(6, 3)))
    if month in (6, 12):
        base_mar = int(base_mar * 1.6)
    base_fun = max(5, int(rng.normalvariate(12, 4)))

    first_day = date(year, month, 1)
    last_day = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
    saturdays = [d for d in days if d.weekday() == 5]
    weekends = [d for d in days if d.weekday() in (5, 6)]

    # Baptisms (Saturdays)
    per_sat = [0] * max(1, len(saturdays))
    for _ in range(base_bap):
        per_sat[rng.randrange(len(per_sat))] += 1
    for d, count in zip(saturdays, per_sat):
        for _ in range(count):
            pid = rng.choice(p_ids) if p_ids else None
            fee = Decimal(str(rng.choice([300, 350, 400, 450, 500])))
            _create_sacrament_and_tx(
                db, d, "baptism", fee, pid, "Scheduled Saturday baptism",
                {"time": rng.choice(["09:00", "10:00", "11:00"]), "location": "Main Church"},
                batch_id, rng, stats
            )

    # Marriages (weekends)
    for _ in range(base_mar):
        d = rng.choice(weekends) if weekends else first_day
        pid = rng.choice(p_ids) if p_ids else None
        fee = Decimal(str(rng.choice([1500, 2000, 2500, 3000])))
        _create_sacrament_and_tx(
            db, d, "marriage", fee, pid, "Wedding service",
            {"time": rng.choice(["09:00", "10:00", "15:00"]), "location": "Main Church"},
            batch_id, rng, stats
        )

    # Funerals (spread)
    for _ in range(base_fun):
        d = rng.choice(days)
        pid = rng.choice(p_ids) if p_ids else None
        fee = Decimal(str(rng.choice([0, 0, 300, 500, 700])))
        _create_sacrament_and_tx(
            db, d, "death", fee, pid, "Funeral service",
            {"time": rng.choice(["08:00", "10:00", "14:00"]), "location": "Chapel"},
            batch_id, rng, stats
        )

    # Confirmations (Apr & Oct) batches
    if month in (4, 10):
        batches = 2 if rng.random() < 0.4 else 1
        for _ in range(batches):
            d = rng.choice(weekends) if weekends else first_day
            for _ in range(rng.randint(30, 80)):
                pid = rng.choice(p_ids) if p_ids else None
                _create_sacrament_and_tx(
                    db, d, "confirmation", Decimal("450"), pid, "Confirmation batch",
                    {"time": "16:00", "location": "Main Church", "preparation_class_batch": f"{year}-Q{1 if month==4 else 3}"},
                    batch_id, rng, stats
                )

    # First Communion (May) batches
    if month == 5:
        d = rng.choice(weekends) if weekends else first_day
        for _ in range(rng.randint(60, 140)):
            pid = rng.choice(p_ids) if p_ids else None
            _create_sacrament_and_tx(
                db, d, "first_communion", Decimal("300"), pid, "First Communion batch",
                {"time": "08:00", "location": "Main Church"},
                batch_id, rng, stats
            )

def _seed_offertory_and_intentions(db, d: date, rng: random.Random, batch_id: str, stats: SeedStats) -> None:
    y = d.year
    pm = pick_payment_method(rng, y)

    if d.weekday() == 6:  # Sunday
        for t in SUNDAY_MASS_TIMES:
            mean = 7500.0
            if is_holy_week(d) or (d.month == 12 and d.day in (24, 25)):
                mean *= 1.8
            if is_simbang_gabi(d):
                mean *= 1.35
            amt = lnorm_amount(rng, mean=mean, sigma=0.55, floor=1200, ceil=25000)
            _insert_tx(db, d, f"Offertory – Sunday {t}", amt, "income", "Offertory – Sunday", pm, batch_id)
            stats.tx_created += 1
            stats.tx_income += Decimal(str(amt))
        intentions = lnorm_amount(rng, mean=1800.0, sigma=0.6, floor=200, ceil=8000)
        _insert_tx(db, d, "Mass Intentions (aggregated)", intentions, "income", "Mass Intentions", pm, batch_id)
        stats.tx_created += 1
        stats.tx_income += Decimal(str(intentions))
    else:
        mean = 900.0
        if is_simbang_gabi(d):
            mean = 2800.0
        amt = lnorm_amount(rng, mean=mean, sigma=0.6, floor=100, ceil=6000)
        _insert_tx(db, d, f"Offertory – Weekday {WEEKDAY_MASS_TIME}", amt, "income", "Offertory – Weekday", pm, batch_id)
        stats.tx_created += 1
        stats.tx_income += Decimal(str(amt))
        if rng.random() < 0.35:
            intentions = lnorm_amount(rng, mean=450.0, sigma=0.7, floor=50, ceil=3000)
            _insert_tx(db, d, "Mass Intentions (weekday)", intentions, "income", "Mass Intentions", pm, batch_id)
            stats.tx_created += 1
            stats.tx_income += Decimal(str(intentions))

def _seed_regular_expenses_for_month(db, year: int, month: int, rng: random.Random, batch_id: str, stats: SeedStats) -> None:
    d = date(year, month, min(5, (date(year, month, 28) + timedelta(days=4)).replace(day=1).day))
    pm = "bank"

    elec = lnorm_amount(rng, mean=8000.0 * (1.15 if month in (3,4,5) else 1.0), sigma=0.45, floor=2000, ceil=18000)
    water = lnorm_amount(rng, mean=1200.0, sigma=0.5, floor=300, ceil=3000)
    netph = lnorm_amount(rng, mean=1800.0, sigma=0.35, floor=800, ceil=4000)
    for desc, amt, cat in [
        ("Electricity bill", elec, "Utilities – Electricity"),
        ("Water bill", water, "Utilities – Water"),
        ("Internet/Phone", netph, "Utilities – Internet/Phone"),
    ]:
        _insert_tx(db, d, desc, amt, "expense", cat, pm, batch_id)
        stats.tx_created += 1
        stats.tx_expense += Decimal(str(amt))

    sal = lnorm_amount(rng, mean=25000.0, sigma=0.25, floor=18000, ceil=40000)
    _insert_tx(db, d, "Monthly salaries & honoraria", sal, "expense", "Salaries & Honoraria", pm, batch_id)
    stats.tx_created += 1
    stats.tx_expense += Decimal(str(sal))

    if rng.random() < 0.85:
        lit = lnorm_amount(rng, mean=2200.0, sigma=0.5, floor=500, ceil=8000)
        _insert_tx(db, d, "Liturgical supplies", lit, "expense", "Liturgical Supplies", pm, batch_id)
        stats.tx_created += 1
        stats.tx_expense += Decimal(str(lit))
    if rng.random() < 0.60:
        off = lnorm_amount(rng, mean=1400.0, sigma=0.6, floor=300, ceil=6000)
        _insert_tx(db, d, "Office supplies", off, "expense", "Office Supplies", pm, batch_id)
        stats.tx_created += 1
        stats.tx_expense += Decimal(str(off))

    if rng.random() < (0.55 if month in (6,7,8,9,10) else 0.30):
        rep = lnorm_amount(rng, mean=4000.0, sigma=0.8, floor=500, ceil=35000)
        _insert_tx(db, d, "Repairs & maintenance", rep, "expense", "Repairs & Maintenance", pm, batch_id)
        stats.tx_created += 1
        stats.tx_expense += Decimal(str(rep))

    fees = lnorm_amount(rng, mean=200.0, sigma=0.4, floor=50, ceil=800)
    _insert_tx(db, d, "Banking & fees", fees, "expense", "Banking & Fees", pm, batch_id)
    stats.tx_created += 1
    stats.tx_expense += Decimal(str(fees))

def _seed_transport_weeklies(db, y: int, m: int, rng: random.Random, batch_id: str, stats: SeedStats) -> None:
    first = date(y, m, 1)
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    cur = first
    while cur <= last:
        if cur.weekday() == 5:  # Saturday
            amt = lnorm_amount(rng, mean=800.0, sigma=0.5, floor=200, ceil=2500)
            _insert_tx(db, cur, "Transportation/Fuel", amt, "expense", "Transportation/Fuel", "cash", batch_id)
            stats.tx_created += 1
            stats.tx_expense += Decimal(str(amt))
        cur += timedelta(days=1)

def _seed_calendar_drive(db, year: int, rng: random.Random, batch_id: str, stats: SeedStats) -> None:
    price = 150.0
    base_units = {2023: 900, 2024: 1050, 2025: 1200}.get(year, 1000)
    expected_income = base_units * price
    cogs = expected_income * 0.60
    cogs_date = date(year, 11, 10)
    _insert_tx(db, cogs_date, "Calendar Printing (COGS)", cogs, "expense", "Calendar Printing (COGS)", "bank", batch_id)
    stats.tx_created += 1
    stats.tx_expense += Decimal(str(cogs))

    start = date(year, 11, 15)
    end = date(year, 12, 31)
    total_units = 0
    for d in daterange(start, end):
        sunday_boost = 1.0 if d.weekday() != 6 else 2.2
        units = int(max(0, rng.normalvariate(18.0 * sunday_boost, 7.0)))
        if units == 0:
            continue
        amt = units * price
        _insert_tx(db, d, "Calendar Drive sales", amt, "income", "Fundraising – Calendar Drive", pick_payment_method(rng, year), batch_id)
        stats.tx_created += 1
        stats.tx_income += Decimal(str(amt))
        total_units += units
    if total_units > base_units * 1.1:
        extra_cogs = (total_units - base_units) * price * 0.60
        d = date(year, 12, 10)
        _insert_tx(db, d, "Calendar Printing (COGS) – reprint", extra_cogs, "expense", "Calendar Printing (COGS)", "bank", batch_id)
        stats.tx_created += 1
        stats.tx_expense += Decimal(str(extra_cogs))

def _delete_window(db, d0: date, d1: date) -> None:
    from sqlalchemy import text
    from app.services import sacraments as sac_svc
    rows = db.execute(text("SELECT id FROM sacraments WHERE date BETWEEN :a AND :b"), {"a": d0, "b": d1}).fetchall()
    for (sid,) in rows:
        sac_svc.delete_sacrament(db, int(sid))
    db.execute(text("DELETE FROM transactions WHERE date BETWEEN :a AND :b AND (reference_no IS NULL OR reference_no NOT LIKE 'SAC-%')"),
               {"a": d0, "b": d1})
    db.commit()

def run_seed(args) -> Dict[str, Any]:
    rng = random.Random(args.rng_seed)
    target_url = _build_target_db_url(args.db_name, args.db_url)

    _ensure_database_exists(target_url)
    if not args.no_migrate:
        _alembic_upgrade_head(target_url)

    os.environ["DATABASE_URL"] = target_url
    _import_app_modules()

    stats = SeedStats()
    db = _session()

    stats.categories_upserted = _upsert_categories(db, ALL_CATEGORY_NAMES)
    stats.parishioners_created = _ensure_parishioners(db, args.parishioner_target, rng)

    if args.reset:
        _delete_window(db, args.date_from, args.date_to)

    batch_id = f"seed:{args.date_from.isoformat()}..{args.date_to.isoformat()}:{args.profile}"

    if not args.dry_run:
        for d in daterange(args.date_from, args.date_to):
            _seed_offertory_and_intentions(db, d, rng, batch_id, stats)

    first_ym = (args.date_from.year, args.date_from.month)
    last_ym = (args.date_to.year, args.date_to.month)
    y, m = first_ym
    while (y, m) <= last_ym:
        if not args.dry_run:
            _seed_regular_expenses_for_month(db, y, m, rng, batch_id, stats)
            _seed_transport_weeklies(db, y, m, rng, batch_id, stats)
            _seed_sacraments_for_month(db, y, m, rng, batch_id, stats)
        if m == 12:
            m = 1
            y += 1
        else:
            m += 1

    years = sorted(set(d.year for d in daterange(args.date_from, args.date_to)))
    if not args.dry_run:
        for yy in years:
            _seed_calendar_drive(db, yy, rng, batch_id, stats)
        db.commit()

    from sqlalchemy import text
    total_tx = db.execute(text("SELECT COUNT(*) FROM transactions WHERE date BETWEEN :a AND :b"),
                          {"a": args.date_from, "b": args.date_to}).scalar() or 0
    sunday_avg = db.execute(text("""
        SELECT AVG(amount)::numeric(12,2)
        FROM transactions
        WHERE date BETWEEN :a AND :b
          AND type = 'income'
          AND category_id = (SELECT id FROM categories WHERE name='Offertory – Sunday' LIMIT 1)
    """), {"a": args.date_from, "b": args.date_to}).scalar()
    weekday_avg = db.execute(text("""
        SELECT AVG(amount)::numeric(12,2)
        FROM transactions
        WHERE date BETWEEN :a AND :b
          AND type = 'income'
          AND category_id = (SELECT id FROM categories WHERE name='Offertory – Weekday' LIMIT 1)
    """), {"a": args.date_from, "b": args.date_to}).scalar()

    summary = {
        "target_url": target_url,
        "window": [args.date_from.isoformat(), args.date_to.isoformat()],
        "profile": args.profile,
        "dry_run": args.dry_run,
        "categories_upserted": stats.categories_upserted,
        "parishioners_created": stats.parishioners_created,
        "sacraments_created": dict(stats.sacraments_created),
        "tx_created_estimate": stats.tx_created,
        "tx_income_estimate": str(stats.tx_income),
        "tx_expense_estimate": str(stats.tx_expense),
        "total_transactions_in_window_after": int(total_tx),
        "offertory_avg": {
            "sunday_income_avg": str(sunday_avg) if sunday_avg is not None else None,
            "weekday_income_avg": str(weekday_avg) if weekday_avg is not None else None,
        },
    }

    exports = BACKEND_ROOT / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    out = exports / "seed_summary.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary

def main():
    args = parser.parse_args()
    if args.date_to < args.date_from:
        raise SystemExit("--to cannot be earlier than --from")

    target_url = _build_target_db_url(args.db_name, args.db_url)
    print(f"→ Target DB: {target_url}")

    if args.dry_run:
        _ensure_database_exists(target_url)
        if not args.no_migrate:
            _alembic_upgrade_head(target_url)
        os.environ["DATABASE_URL"] = target_url
        _import_app_modules()
    summary = run_seed(args)
    print("\n=== SEED SUMMARY ===")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
