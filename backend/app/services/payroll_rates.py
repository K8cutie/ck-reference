# backend/app/services/payroll_rates.py
"""
ClearKeep Payroll Rate Tables — loader + compute helpers

Config precedence per rate component:
    1) Environment variables (override specific fields)
    2) JSON files under app/data/payroll/<year>/
    3) Built-in defaults (keeps app working without data files)

Year resolution:
    - CK_PAYROLL_RATES_YEAR (ALWAYS used if set, even if folders are missing)
    - requested year (if folder exists; else closest available; else the requested year)
    - default 2025 (closest available; else 2025)

Implemented now:
    • PhilHealth — default total rate 5%, min ₱10,000, cap ₱80,000, split 50%/50%
    • Pag-IBIG  — default base cap ₱5,000; EE 1% if pay ≤ ₱1,500 else 2%; ER 2%
    • SSS       — default total 14% (EE 4.5% / ER 9.5%), base clamped ₱4,000–₱30,000; WISP 0.00
    • BIR       — JSON-driven brackets; env fallback (flat rate above monthly exempt); default 0.00
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from typing import Any, Dict, Optional, List

# ---------------------------- Utilities ---------------------------- #

def D(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")

def q2(val: Decimal) -> Decimal:
    return D(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _data_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))  # .../app/services
    return os.path.normpath(os.path.join(here, "..", "data", "payroll"))

def _year_dir(year: int) -> str:
    return os.path.join(_data_root(), str(year))

def _list_available_years() -> List[int]:
    root = _data_root()
    try:
        entries = os.listdir(root)
    except FileNotFoundError:
        return []
    yrs: List[int] = []
    for name in entries:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            try:
                yrs.append(int(name))
            except ValueError:
                pass
    return sorted(set(yrs))

def _env_decimal(key: str, default: Decimal) -> Decimal:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return D(raw)
    except Exception:
        return default

def _resolve_year(requested: Optional[int]) -> int:
    env_override = os.getenv("CK_PAYROLL_RATES_YEAR")
    avail = _list_available_years()

    def _closest(target: int) -> Optional[int]:
        if not avail:
            return None
        return min(avail, key=lambda y: abs(y - target))

    if env_override:
        try:
            return int(env_override)
        except ValueError:
            pass

    if requested is not None:
        if requested in avail:
            return requested
        closest = _closest(requested)
        return closest if closest is not None else requested

    default_target = 2025
    closest = _closest(default_target)
    return closest if closest is not None else default_target

# ---------------------------- Data holders ---------------------------- #

@dataclass(frozen=True)
class SSSRates:
    raw: Dict[str, Any]

@dataclass(frozen=True)
class PhilHealthRates:
    raw: Dict[str, Any]

@dataclass(frozen=True)
class PagibigRates:
    raw: Dict[str, Any]

@dataclass(frozen=True)
class BIRWithholding:
    raw: Dict[str, Any]

@dataclass(frozen=True)
class PayrollRates:
    year: int
    sss: Optional[SSSRates]
    philhealth: Optional[PhilHealthRates]
    pagibig: Optional[PagibigRates]
    bir: Optional[BIRWithholding]

# ---------------------------- Loader ---------------------------- #

def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None

@lru_cache(maxsize=32)
def _load_rates_for_year(effective_year: int) -> PayrollRates:
    base = _year_dir(effective_year)
    sss = _load_json(os.path.join(base, "sss.json"))
    phil = _load_json(os.path.join(base, "philhealth.json"))
    pag = _load_json(os.path.join(base, "pagibig.json"))
    bir = _load_json(os.path.join(base, "bir_withholding.json"))
    return PayrollRates(
        year=effective_year,
        sss=SSSRates(sss) if sss else None,
        philhealth=PhilHealthRates(phil) if phil else None,
        pagibig=PagibigRates(pag) if pag else None,
        bir=BIRWithholding(bir) if bir else None,
    )

def load_rates(year: int = 2025) -> PayrollRates:
    effective = _resolve_year(year)
    return _load_rates_for_year(effective)

# ---------------------------- Compute helpers ---------------------------- #

def compute_sss(monthly_basic: Decimal | float | int, *, year: int = 2025) -> Dict[str, Decimal]:
    cfg = (load_rates(year).sss.raw if load_rates(year).sss else {}) or {}

    total_rate = D(cfg.get("total_rate", "0.14"))
    ee_rate    = D(cfg.get("ee_rate",    "0.045"))
    er_rate    = D(cfg.get("er_rate",    "0.095"))
    min_base   = D(cfg.get("min_base",   "4000"))
    max_base   = D(cfg.get("max_base",   "30000"))

    total_rate = _env_decimal("CK_SSS_TOTAL_RATE", total_rate)
    ee_rate    = _env_decimal("CK_SSS_EE_RATE",    ee_rate)
    er_rate    = _env_decimal("CK_SSS_ER_RATE",    er_rate)
    min_base   = _env_decimal("CK_SSS_MIN_BASE",   min_base)
    max_base   = _env_decimal("CK_SSS_MAX_BASE",   max_base)

    base = D(monthly_basic)
    if min_base > 0 and base < min_base:
        base = min_base
    if max_base > 0 and base > max_base:
        base = max_base

    if total_rate <= 0 and (ee_rate + er_rate) > 0:
        total_rate = ee_rate + er_rate
    if total_rate <= 0:
        return {"ee": q2(0), "er": q2(0), "wisp_ee": q2(0), "wisp_er": q2(0), "total_er": q2(0)}

    total = q2(base * total_rate)
    if (ee_rate + er_rate) > 0:
        ee = q2(total * (ee_rate / (ee_rate + er_rate)))
    else:
        ee = q2(total * D("0.321428571"))  # 4.5/14
    er = q2(total - ee)

    return {"ee": ee, "er": er, "wisp_ee": q2(0), "wisp_er": q2(0), "total_er": er}

def compute_philhealth(monthly_basic: Decimal | float | int, *, year: int = 2025) -> Dict[str, Decimal]:
    rates = load_rates(year).philhealth
    rate = D("0.05"); min_base = D("10000"); max_base = D("80000")
    ee_share = D("0.5"); er_share = D("0.5")

    if rates and isinstance(rates.raw, dict):
        raw = rates.raw
        rate     = D(raw.get("rate",     rate))
        min_base = D(raw.get("min_base", min_base))
        max_base = D(raw.get("max_base", max_base))
        ee_share = D(raw.get("ee_share", ee_share))
        er_share = D(raw.get("er_share", er_share))

    rate     = _env_decimal("CK_PHILHEALTH_RATE",     rate)
    min_base = _env_decimal("CK_PHILHEALTH_MIN",      min_base)
    max_base = _env_decimal("CK_PHILHEALTH_MAX",      max_base)
    ee_share = _env_decimal("CK_PHILHEALTH_EE_SHARE", ee_share)
    er_share = _env_decimal("CK_PHILHEALTH_ER_SHARE", er_share)
    if ee_share + er_share == 0:
        ee_share, er_share = D("0.5"), D("0.5")

    base = D(monthly_basic)
    if min_base > 0 and base < min_base:
        base = min_base
    if max_base > 0 and base > max_base:
        base = max_base

    total = q2(base * rate)
    ee = q2(total * ee_share)
    er = q2(total - ee)
    return {"ee": ee, "er": er}

def compute_pagibig(monthly_basic: Decimal | float | int, *, year: int = 2025) -> Dict[str, Decimal]:
    cfg = (load_rates(year).pagibig.raw if load_rates(year).pagibig else {}) or {}

    base_cap      = _env_decimal("CK_PAGIBIG_BASE_CAP",      D(cfg.get("base_cap",      "5000")))
    low_threshold = _env_decimal("CK_PAGIBIG_LOW_THRESHOLD", D(cfg.get("low_threshold", "1500")))
    ee_low        = _env_decimal("CK_PAGIBIG_EE_RATE_LOW",   D(cfg.get("ee_rate_low",   "0.01")))
    ee_high       = _env_decimal("CK_PAGIBIG_EE_RATE_HIGH",  D(cfg.get("ee_rate_high",  "0.02")))
    er_rate       = _env_decimal("CK_PAGIBIG_ER_RATE",       D(cfg.get("er_rate",       "0.02")))

    comp = D(monthly_basic)
    ee_rate = ee_low if comp <= low_threshold else ee_high
    base = comp if comp < base_cap else base_cap

    ee = q2(base * ee_rate)
    er = q2(base * er_rate)
    return {"ee": ee, "er": er}

def compute_withholding(taxable_monthly: Decimal | float | int, *, status: str = "S", year: int = 2025) -> Dict[str, Decimal]:
    """
    BIR Withholding (JSON → ENV → default).

    JSON (app/data/payroll/<year>/bir_withholding.json) schema:
    {
      "brackets": [
        {"up_to": 20833,  "base_tax": 0,      "rate": 0.00, "excess_over": 0},
        {"up_to": 33333,  "base_tax": 0,      "rate": 0.15, "excess_over": 20833},
        {"up_to": 66667,  "base_tax": 1875,   "rate": 0.20, "excess_over": 33333},
        {"up_to": 166667, "base_tax": 8541.8, "rate": 0.25, "excess_over": 66667},
        {"up_to": 666667, "base_tax": 33541.8,"rate": 0.30, "excess_over": 166667},
        {"up_to": null,   "base_tax": 183541.8,"rate": 0.35,"excess_over": 666667}
      ]
    }

    ENV fallback (flat): CK_BIR_MONTHLY_RATE, CK_BIR_MONTHLY_EXEMPT
      If set, tax = max(0, (taxable - EXEMPT)) * RATE
    Default if neither JSON nor ENV: 0.00
    """
    # Try JSON table first
    bir = load_rates(year).bir
    tx = D(taxable_monthly)

    if bir and isinstance(bir.raw, dict) and isinstance(bir.raw.get("brackets"), list):
        try:
            brackets = bir.raw["brackets"]
            # Find first bracket where up_to is None or tx <= up_to
            chosen = None
            for b in brackets:
                up_to = b.get("up_to", None)
                if up_to is None or tx <= D(up_to):
                    chosen = b
                    break
            if chosen:
                base_tax = D(chosen.get("base_tax", "0"))
                rate = D(chosen.get("rate", "0"))
                excess_over = D(chosen.get("excess_over", "0"))
                tax = base_tax + rate * (tx - excess_over if tx > excess_over else Decimal("0"))
                return {"tax": q2(tax)}
        except Exception:
            pass  # fall back to ENV/default below

    # ENV flat fallback
    flat_rate = os.getenv("CK_BIR_MONTHLY_RATE")
    exempt = os.getenv("CK_BIR_MONTHLY_EXEMPT")
    if flat_rate is not None or exempt is not None:
        r = D(flat_rate or "0")
        ex = D(exempt or "0")
        tax = q2((tx - ex) * r) if tx > ex and r > 0 else q2(0)
        return {"tax": tax}

    # Default
    return {"tax": q2(0)}

# ---------------------------- Aggregate helper ---------------------------- #

def compute_government_deductions(
    monthly_basic: Decimal | float | int,
    *,
    taxable_monthly: Optional[Decimal | float | int] = None,
    status: str = "S",
    year: int = 2025,
) -> Dict[str, Dict[str, Decimal]]:
    mb = D(monthly_basic)
    tx = D(taxable_monthly) if taxable_monthly is not None else mb
    return {
        "sss": compute_sss(mb, year=year),
        "philhealth": compute_philhealth(mb, year=year),
        "pagibig": compute_pagibig(mb, year=year),
        "withholding": compute_withholding(tx, status=status, year=year),
    }

__all__ = [
    "load_rates",
    "compute_sss",
    "compute_philhealth",
    "compute_pagibig",
    "compute_withholding",
    "compute_government_deductions",
]

