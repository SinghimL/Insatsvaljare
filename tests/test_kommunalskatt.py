"""Unit tests for the kommunalskatt module (snapshot + lookup)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insatsvaljare.kommunalskatt import (
    kommun_records,
    load_snapshot,
    lookup_by_name,
    lookup_rate,
    save_snapshot,
)


SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "ref" / "kommunalskatt_snapshot.json"


@pytest.fixture(scope="module")
def snapshot():
    assert SNAPSHOT_PATH.exists(), (
        f"Missing snapshot at {SNAPSHOT_PATH}; run fetch_kommunalskatt_table() "
        "to create it."
    )
    return load_snapshot(SNAPSHOT_PATH)


def test_snapshot_has_290_kommuner(snapshot):
    kommuner = kommun_records(snapshot)
    assert len(kommuner) == 290


def test_snapshot_includes_riket_and_regions(snapshot):
    codes = {r["code"] for r in snapshot}
    assert "00" in codes  # Riket
    # At least 20 län codes (2-digit); actual count is 21 (Stockholms…Norrbottens).
    len_regions = sum(1 for r in snapshot if r["level"] == "region")
    assert len_regions >= 20


def test_lookup_stockholm(snapshot):
    r = lookup_by_name(snapshot, "Stockholm")
    assert r is not None
    assert r["rate"] == pytest.approx(30.55)
    assert r["code"] == "0180"
    assert r["level"] == "kommun"


def test_lookup_extremes(snapshot):
    # Lowest and highest in 2026 per SCB press release.
    osteraker = lookup_by_name(snapshot, "Österåker")
    assert osteraker["rate"] == pytest.approx(28.93)
    dorotea = lookup_by_name(snapshot, "Dorotea")
    assert dorotea["rate"] == pytest.approx(35.65)


def test_lookup_case_insensitive(snapshot):
    assert lookup_by_name(snapshot, "stockholm") is not None
    assert lookup_by_name(snapshot, "STOCKHOLM") is not None


def test_lookup_rate_by_code(snapshot):
    rate = lookup_rate(snapshot, "0180")
    assert rate == pytest.approx(30.55)


def test_lookup_missing_returns_none(snapshot):
    assert lookup_by_name(snapshot, "Gondor") is None
    assert lookup_rate(snapshot, "9999") is None


def test_all_rates_within_reasonable_range(snapshot):
    # Sanity check: every kommun between 28 % and 36 %.
    for r in kommun_records(snapshot):
        assert 28.0 <= r["rate"] <= 36.5, f"{r['name']}: {r['rate']}"


def test_snapshot_roundtrip(tmp_path):
    records = [
        {"code": "0180", "name": "Stockholm", "level": "kommun", "rate": 30.55, "year": 2026},
        {"code": "0117", "name": "Österåker", "level": "kommun", "rate": 28.93, "year": 2026},
    ]
    path = tmp_path / "snap.json"
    save_snapshot(records, path)
    loaded = load_snapshot(path)
    assert loaded == records


def test_snapshot_roundtrip_reads_legacy_list(tmp_path):
    # Older versions might have stored the list directly (no wrapper dict).
    records = [{"code": "0180", "name": "Stockholm", "level": "kommun", "rate": 30.55, "year": 2026}]
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(records))
    loaded = load_snapshot(path)
    assert loaded == records
