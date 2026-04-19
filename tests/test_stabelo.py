"""Tests for the Stabelo turbo-stream parser + lookup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insatsvaljare.stabelo import (
    FIXATION_MONTHS,
    RateRecord,
    load_snapshot,
    lookup_rate,
    parse_turbo_stream,
    save_snapshot,
)

SNAPSHOT = Path(__file__).resolve().parents[1] / "ref" / "stabelo_snapshot.json"
FIXTURE = Path("/tmp/stab_data1")  # Raw turbo-stream captured during development


@pytest.fixture
def records():
    """Load records from the committed snapshot."""
    if not SNAPSHOT.exists():
        pytest.skip("snapshot file missing — run the app once to create it")
    return load_snapshot(SNAPSHOT)


class TestParser:
    @pytest.mark.skipif(not FIXTURE.exists(), reason="raw fixture not available")
    def test_parses_raw_stream(self):
        records = parse_turbo_stream(FIXTURE.read_text())
        assert len(records) > 100
        assert all(isinstance(r, RateRecord) for r in records)

    @pytest.mark.skipif(not FIXTURE.exists(), reason="raw fixture not available")
    def test_known_rate_points(self):
        """Sanity-check specific rates observed during exploration."""
        records = parse_turbo_stream(FIXTURE.read_text())
        # LTV 85, 3M, 2 Mkr, EPC B → 2.82% (observed)
        r = lookup_rate(records, ltv_pct=85, binding_months=3, amount_kr=2_000_000)
        assert r == pytest.approx(2.82, abs=0.02)


class TestLookup:
    def test_higher_ltv_not_less_expensive(self, records):
        """Moving from 70 % to 85 % at the same amount should not make it cheaper."""
        r70 = lookup_rate(records, ltv_pct=70, binding_months=3, amount_kr=2_000_000)
        r85 = lookup_rate(records, ltv_pct=85, binding_months=3, amount_kr=2_000_000)
        if r70 is not None and r85 is not None:
            assert r85 >= r70 - 0.001  # allow for tie

    def test_longer_term_more_expensive(self, records):
        r_3m = lookup_rate(records, ltv_pct=85, binding_months=3, amount_kr=2_000_000)
        r_5y = lookup_rate(records, ltv_pct=85, binding_months=60, amount_kr=2_000_000)
        if r_3m is not None and r_5y is not None:
            assert r_5y >= r_3m

    def test_larger_loan_discount(self, records):
        """Big loans get better rates at the same LTV."""
        r_small = lookup_rate(records, ltv_pct=85, binding_months=3, amount_kr=500_000)
        r_large = lookup_rate(records, ltv_pct=85, binding_months=3, amount_kr=2_000_000)
        if r_small is not None and r_large is not None:
            assert r_large <= r_small

    def test_ltv_over_85_returns_none(self, records):
        """Stabelo caps at 85 % — 90 % should return None."""
        r = lookup_rate(records, ltv_pct=90, binding_months=3, amount_kr=2_000_000)
        assert r is None


class TestSnapshot:
    def test_roundtrip(self, tmp_path):
        records = [
            RateRecord(ltv_pct=85, fixation="3M", amount_kr=2_000_000, epc="B", rate_pct=2.82),
            RateRecord(ltv_pct=65, fixation="1Y", amount_kr=1_000_000, epc="B", rate_pct=2.93),
        ]
        p = tmp_path / "snap.json"
        save_snapshot(records, p)
        loaded = load_snapshot(p)
        assert loaded == records

    def test_snapshot_schema(self, tmp_path):
        records = [RateRecord(ltv_pct=85, fixation="3M", amount_kr=2e6, epc="B", rate_pct=2.82)]
        p = tmp_path / "snap.json"
        save_snapshot(records, p)
        payload = json.loads(p.read_text())
        assert "fetched_at" in payload
        assert "source" in payload
        assert payload["count"] == 1
