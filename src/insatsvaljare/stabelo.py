"""Fetch + parse Stabelo's public rate table.

Endpoint: https://api.stabelo.se/rate-table.data
Format:   Remix turbo-stream (flat JSON array with index references)

The parser dereferences the stream into structured Python objects, then
flattens into a list of records with shape:

    {
        "ltv_pct":  float,   # 60..85, or None if unspecified tier
        "fixation": str,     # "3M", "1Y", "2Y", "3Y", "5Y", "10Y"
        "amount_kr": float,  # loan-size bracket lower bound
        "epc":      str,     # "B" (standard) or None
        "rate_pct": float,   # interest rate, e.g. 2.82
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

STABELO_URL = "https://api.stabelo.se/rate-table.data"
DEFAULT_HEADERS = {
    "Accept": "text/x-script",
    "User-Agent": "Mozilla/5.0 (insatsvaljare-model)",
}
FIXATION_MONTHS = {"3M": 3, "1Y": 12, "2Y": 24, "3Y": 36, "5Y": 60, "10Y": 120}


@dataclass(frozen=True)
class RateRecord:
    ltv_pct: float | None
    fixation: str
    amount_kr: float | None
    epc: str | None
    rate_pct: float

    def fixation_months(self) -> int:
        return FIXATION_MONTHS.get(self.fixation, 3)


# ------------------------------------------------------------------
# Turbo-stream parser
# ------------------------------------------------------------------

def _deref(
    idx: int,
    data: list[Any],
    visited: frozenset[int] = frozenset(),
    depth: int = 0,
) -> Any:
    """Dereference a turbo-stream index into its concrete value.

    Returns the literal if the index points to a primitive, a dict for
    encoded objects, or a list for encoded arrays. Cycles and depth are
    bounded defensively — the real stream is well-formed.
    """
    if not isinstance(idx, int) or idx < 0 or idx >= len(data):
        return idx
    if idx in visited or depth > 50:
        return None
    visited = visited | {idx}
    val = data[idx]

    if isinstance(val, dict):
        out: dict[str, Any] = {}
        for k, v in val.items():
            if k.startswith("_"):
                try:
                    key = data[int(k[1:])]
                except (ValueError, IndexError):
                    key = k
            else:
                key = k
            if not isinstance(key, str):
                continue
            out[key] = (
                _deref(v, data, visited, depth + 1) if isinstance(v, int) else v
            )
        return out

    if isinstance(val, list):
        return [
            _deref(item, data, visited, depth + 1) if isinstance(item, int) else item
            for item in val
        ]

    return val


def _find_rate_table_root(data: list[Any]) -> int | None:
    """Locate the rateTable object by scanning for its anchor string."""
    for i, item in enumerate(data):
        if item == "rateTable" and i + 1 < len(data):
            return i + 1
    return None


def parse_turbo_stream(text: str) -> list[RateRecord]:
    """Parse a turbo-stream response body into a list of RateRecord."""
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("turbo-stream root is not a list")

    root_idx = _find_rate_table_root(data)
    if root_idx is None:
        raise ValueError("rateTable anchor not found in stream")

    rate_table = _deref(root_idx, data)
    items = rate_table.get("interest_rate_items", []) if isinstance(rate_table, dict) else []

    records: list[RateRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cfg = item.get("product_configuration") or {}
        rate = item.get("interest_rate") or {}
        if not isinstance(cfg, dict) or not isinstance(rate, dict):
            continue

        ltv = cfg.get("ltv")
        ltv_pct = ltv.get("bps") / 100 if isinstance(ltv, dict) and ltv.get("bps") else None

        amt = cfg.get("product_amount")
        amount_kr = amt.get("value") / 100 if isinstance(amt, dict) and amt.get("value") is not None else None

        epc = cfg.get("epc_classification")
        epc_clean = epc if isinstance(epc, str) else None

        fix = cfg.get("rate_fixation")
        rate_bps = rate.get("bps")
        if not isinstance(fix, str) or not isinstance(rate_bps, int):
            continue

        records.append(RateRecord(
            ltv_pct=ltv_pct,
            fixation=fix,
            amount_kr=amount_kr,
            epc=epc_clean,
            rate_pct=rate_bps / 100,
        ))

    return records


# ------------------------------------------------------------------
# Fetch + snapshot
# ------------------------------------------------------------------

def fetch_rate_table(timeout: float = 10.0) -> list[RateRecord]:
    """Fetch live rates from Stabelo. Raises on HTTP or parse failure."""
    r = httpx.get(STABELO_URL, headers=DEFAULT_HEADERS, timeout=timeout)
    r.raise_for_status()
    return parse_turbo_stream(r.text)


def save_snapshot(records: list[RateRecord], path: Path) -> None:
    """Persist records to disk as a JSON snapshot with metadata."""
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": STABELO_URL,
        "count": len(records),
        "records": [r.__dict__ for r in records],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def load_snapshot(path: Path) -> list[RateRecord]:
    """Read a previously-saved snapshot from disk."""
    payload = json.loads(path.read_text())
    return [RateRecord(**r) for r in payload["records"]]


def load_or_fetch(path: Path, force_refresh: bool = False) -> list[RateRecord]:
    """Use local snapshot if available; refresh from API otherwise.

    Failures during refresh fall back to the snapshot if it exists.
    """
    if path.exists() and not force_refresh:
        return load_snapshot(path)
    try:
        records = fetch_rate_table()
        save_snapshot(records, path)
        return records
    except Exception:
        if path.exists():
            return load_snapshot(path)
        raise


# ------------------------------------------------------------------
# Lookup
# ------------------------------------------------------------------

def lookup_rate(
    records: list[RateRecord],
    ltv_pct: float,
    binding_months: int,
    amount_kr: float,
    epc: str | None = "B",
) -> float | None:
    """Nearest-neighbor lookup from a flat record list.

    • LTV: pick the highest bracket ≤ request (Stabelo prices by ceiling
      thresholds — 85 % bracket covers 80 < ltv ≤ 85).
    • Amount: pick the highest bracket ≤ request (larger loans → better
      rate; use the bracket that applies to at least this amount).
    • Fixation: exact match on FIXATION_MONTHS label.
    • EPC: prefer the requested class; fall back to any if none match.

    Returns rate in percent (e.g. 2.82 for 2.82 %), or None if no match.
    """
    fixation_label = next(
        (k for k, v in FIXATION_MONTHS.items() if v == binding_months),
        None,
    )
    if fixation_label is None:
        return None

    candidates = [
        r for r in records
        if r.fixation == fixation_label
        and r.ltv_pct is not None
        and r.amount_kr is not None
        and r.ltv_pct >= ltv_pct  # LTV bracket is an upper bound
        and r.amount_kr <= amount_kr  # amount bracket is a lower bound
        and (epc is None or r.epc == epc or r.epc is None)
    ]
    if not candidates:
        return None

    # Choose the tightest-fitting bracket: smallest LTV ≥ request,
    # largest amount ≤ request.
    candidates.sort(key=lambda r: (r.ltv_pct, -r.amount_kr))
    return candidates[0].rate_pct
