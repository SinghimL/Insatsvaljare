"""Fetch + parse SCB's kommunalskatt table (total: kommun + region).

Endpoint: https://api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0101/Kommunalskatter2000

The API is SCB's PxWeb v1. Metadata comes from a GET, the actual data
from a POST with a query body. Output rows shape:

    {
        "code":   str,    # SCB region code (2-digit län or 4-digit kommun)
        "name":   str,    # human-readable name ("Stockholm", "Göteborg", …)
        "level":  str,    # "kommun" | "region" | "riket"
        "rate":   float,  # total municipal rate in percent, e.g. 30.55
        "year":   int,    # 2026
    }

Only municipalities (4-digit codes) are kept by default — länsrader
and "Riket" are available but not needed for kommun selection in UI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

SCB_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0101/Kommunalskatter2000"
SCB_TOTAL_CONTENT_CODE = "OE0101D1"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (insatsvaljare-model)",
}


def _build_query(year: int) -> dict[str, Any]:
    return {
        "query": [
            {"code": "Region", "selection": {"filter": "all", "values": ["*"]}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": [SCB_TOTAL_CONTENT_CODE]}},
            {"code": "Tid", "selection": {"filter": "item", "values": [str(year)]}},
        ],
        "response": {"format": "json"},
    }


def _fetch_region_names(client: httpx.Client) -> dict[str, str]:
    """GET metadata → map SCB region code → human name."""
    resp = client.get(SCB_URL, timeout=30.0)
    resp.raise_for_status()
    meta = resp.json()
    region_var = next(v for v in meta["variables"] if v["code"] == "Region")
    return dict(zip(region_var["values"], region_var["valueTexts"]))


def _classify_level(code: str) -> str:
    if code == "00":
        return "riket"
    if len(code) == 2:
        return "region"
    return "kommun"


def fetch_kommunalskatt_table(year: int = 2026) -> list[dict[str, Any]]:
    """Hit SCB for every kommun's total municipal tax rate for the given year."""
    with httpx.Client(headers=DEFAULT_HEADERS) as client:
        names = _fetch_region_names(client)
        resp = client.post(SCB_URL, json=_build_query(year), timeout=30.0)
        resp.raise_for_status()
        payload = resp.json()

    records: list[dict[str, Any]] = []
    for row in payload.get("data", []):
        code = row["key"][0]
        rate_str = row["values"][0]
        try:
            rate = float(rate_str)
        except (TypeError, ValueError):
            continue
        records.append({
            "code": code,
            "name": names.get(code, code),
            "level": _classify_level(code),
            "rate": rate,
            "year": year,
        })
    records.sort(key=lambda r: (r["level"] != "kommun", r["name"]))
    return records


def save_snapshot(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": SCB_URL,
        "records": records,
    }
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("records", [])


def load_or_fetch(
    path: Path,
    year: int = 2026,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Load from disk if present, otherwise hit SCB and cache."""
    if path.exists() and not force_refresh:
        try:
            return load_snapshot(path)
        except (json.JSONDecodeError, OSError):
            pass
    records = fetch_kommunalskatt_table(year=year)
    save_snapshot(records, path)
    return records


def kommun_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to only kommun-level entries (for UI dropdowns)."""
    return [r for r in records if r["level"] == "kommun"]


def lookup_rate(records: Iterable[dict[str, Any]], code: str) -> float | None:
    """Look up a kommun's total rate (percent) by SCB region code."""
    for r in records:
        if r["code"] == code:
            return float(r["rate"])
    return None


def lookup_by_name(
    records: Iterable[dict[str, Any]],
    name: str,
) -> dict[str, Any] | None:
    """Case-insensitive lookup by kommun name."""
    key = name.strip().lower()
    for r in records:
        if r["name"].lower() == key:
            return r
    return None
