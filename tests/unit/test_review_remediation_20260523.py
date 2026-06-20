# ABOUTME: Targeted tests for deterministic security/correctness fixes from the
# ABOUTME: 2026-05-23 assethold review (remaining findings after issue #52).
"""Synthetic-data-only tests for the remediation of the remaining
deterministic findings in /home/vamsee/reviews/20260523/assethold.md.

All inputs are fabricated; no real financial data is used.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# --------------------------------------------------------------------------
# Finding #9 — compute_positions must not drive shares negative on over-sell
# --------------------------------------------------------------------------
class TestPositionsOverSellClamp:
    def _txn(self, **kw):
        base = {
            "symbol": "AAA",
            "action_type": "buy",
            "quantity": 0.0,
            "price": 0.0,
            "amount": 0.0,
            "run_date": pd.Timestamp("2024-01-01"),
        }
        base.update(kw)
        return base

    def test_oversell_then_dividend_does_not_see_negative_shares(self):
        from assethold.portfolio.positions import compute_positions

        # Buy 10, sell 25 (over-sell), then a dividend reinvest of the same
        # symbol later in the loop. Pre-fix, shares went to -15 mid-loop.
        rows = [
            self._txn(action_type="buy", quantity=10, price=100, amount=-1000),
            self._txn(action_type="sell", quantity=25, price=100, amount=2500,
                      run_date=pd.Timestamp("2024-02-01")),
            self._txn(action_type="dividend", amount=-5,
                      run_date=pd.Timestamp("2024-03-01")),
        ]
        df = pd.DataFrame(rows)
        positions = compute_positions(df)

        # Position is dropped from output (shares clamped to 0) but dividend
        # kept it alive; shares must never be negative.
        if "AAA" in positions:
            assert positions["AAA"].shares >= 0.0

    def test_oversell_clamps_internal_share_count_to_zero(self, caplog):
        from assethold.portfolio import positions as pos_mod

        rows = [
            self._txn(action_type="buy", quantity=5, price=10, amount=-50),
            self._txn(action_type="sell", quantity=12, price=10, amount=120,
                      run_date=pd.Timestamp("2024-02-01")),
            # Keep the symbol in the output via a dividend.
            self._txn(action_type="dividend", amount=-1,
                      run_date=pd.Timestamp("2024-03-01")),
        ]
        df = pd.DataFrame(rows)
        with caplog.at_level("WARNING"):
            result = pos_mod.compute_positions(df)

        assert result["AAA"].shares == 0.0
        assert any("Over-sell" in r.message for r in caplog.records)

    def test_normal_sell_basis_unchanged(self):
        from assethold.portfolio.positions import compute_positions

        rows = [
            self._txn(action_type="buy", quantity=10, price=100, amount=-1000),
            self._txn(action_type="sell", quantity=4, price=100, amount=400,
                      run_date=pd.Timestamp("2024-02-01")),
        ]
        df = pd.DataFrame(rows)
        p = compute_positions(df)["AAA"]
        assert p.shares == pytest.approx(6.0)
        # 60% of cost basis remains.
        assert p.total_cost == pytest.approx(600.0, abs=0.01)


# --------------------------------------------------------------------------
# Finding #6 — fetch_batch must log the failed-ticker exception
# --------------------------------------------------------------------------
class TestFetchBatchLogging:
    def test_failed_ticker_is_logged_and_returns_none(self, tmp_path, caplog):
        from assethold.signals.data_sources import StockDataSource

        src = StockDataSource(cache_dir=tmp_path)

        def fake_fetch(ticker, *a, **kw):
            if ticker == "BAD":
                raise ValueError("delisted")
            return pd.DataFrame({"Close": [1.0]})

        with patch.object(src, "fetch", side_effect=fake_fetch):
            with caplog.at_level("WARNING"):
                out = src.fetch_batch(["GOOD", "BAD"], "2024-01-01", "2024-01-31")

        assert out["BAD"] is None
        assert out["GOOD"] is not None
        assert any("BAD" in r.message and "delisted" in r.message
                   for r in caplog.records)


# --------------------------------------------------------------------------
# Finding #5 — cache key digest widened to 64 bits (16 hex), sha256
# --------------------------------------------------------------------------
class TestCacheKeyHash:
    def test_cache_path_hash_is_16_hex_chars(self, tmp_path):
        from assethold.signals.data_sources import StockDataSource

        src = StockDataSource(cache_dir=tmp_path)
        path = src._get_cache_path("AAPL", "2024-01-01", "2024-12-31")
        stem = path.stem  # e.g. "AAPL_<hash>"
        digest = stem.split("_", 1)[1]
        assert len(digest) == 16
        assert all(c in "0123456789abcdef" for c in digest)

    def test_distinct_date_ranges_get_distinct_paths(self, tmp_path):
        from assethold.signals.data_sources import StockDataSource

        src = StockDataSource(cache_dir=tmp_path)
        a = src._get_cache_path("AAPL", "2024-01-01", "2024-06-30")
        b = src._get_cache_path("AAPL", "2024-07-01", "2024-12-31")
        assert a != b


# --------------------------------------------------------------------------
# Finding #10 — geocoder surfaces HTTP status & non-JSON instead of opaque error
# --------------------------------------------------------------------------
class TestGeocoderHardening:
    def _resp(self, body: bytes, status: int = 200):
        resp = MagicMock()
        resp.status = status
        resp.read.side_effect = lambda n=None: body if n is None else body[:n]
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    def test_non_200_status_raises_geocode_error_with_status(self):
        from assethold.property.geocoder import Geocoder, GeocodeError

        g = Geocoder()
        g._throttle = lambda: None
        resp = self._resp(b"<html>error</html>", status=503)
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(GeocodeError) as exc:
                g._call_nominatim("123 Main St")
        assert "503" in str(exc.value)

    def test_non_json_body_raises_geocode_error(self):
        from assethold.property.geocoder import Geocoder, GeocodeError

        g = Geocoder()
        g._throttle = lambda: None
        resp = self._resp(b"<html>not json</html>", status=200)
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(GeocodeError):
                g._call_nominatim("123 Main St")

    def test_valid_json_passes_through(self):
        from assethold.property.geocoder import Geocoder

        g = Geocoder()
        g._throttle = lambda: None
        payload = json.dumps([{"lat": "30.0", "lon": "-95.0",
                               "display_name": "x", "address": {}}]).encode()
        resp = self._resp(payload, status=200)
        with patch("urllib.request.urlopen", return_value=resp):
            result = g._call_nominatim("123 Main St")
        assert result is not None
        assert result["lat"] == "30.0"
