"""
Unit tests for tax-lot aging, LTCG-aware trim selection, and realized P/L.

No network access; pure date / arithmetic logic.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from assethold.analysis.daily_strategy.tax_lots import (
    RealizedLot,
    TaxLot,
    age_lots,
    almost_long_term_lots,
    match_sells_fifo,
    realized_report,
    select_trim_lots,
)


def _lot(buy_date: date, shares: float, basis: float, ticker: str = "XOM") -> TaxLot:
    return TaxLot(
        ticker=ticker,
        account="Individual",
        buy_date=buy_date,
        shares=shares,
        cost_basis_per_share=basis,
    )


# ---------------------------------------------------------------------------
# Holding-period boundary (just under vs just over 1 year)
# ---------------------------------------------------------------------------

def test_boundary_365_days_is_short_term():
    """Exactly 365 days held -> still SHORT term (boundary is strictly > 365)."""
    buy = date(2024, 1, 1)
    lot = _lot(buy, 10, 100.0)
    as_of = buy + timedelta(days=365)
    assert lot.holding_period_days(as_of) == 365
    assert lot.is_long_term(as_of) is False


def test_boundary_366_days_is_long_term():
    """366 days held -> LONG term."""
    buy = date(2024, 1, 1)
    lot = _lot(buy, 10, 100.0)
    as_of = buy + timedelta(days=366)
    assert lot.holding_period_days(as_of) == 366
    assert lot.is_long_term(as_of) is True


def test_boundary_364_days_just_under():
    """364 days -> short term, 1 day from long term."""
    buy = date(2024, 1, 1)
    lot = _lot(buy, 10, 100.0)
    as_of = buy + timedelta(days=364)
    assert lot.is_long_term(as_of) is False
    # Needs 2 more days to exceed 365 (365 is still short, 366 is long).
    assert lot.days_until_long_term(as_of) == 2


def test_days_until_long_term_zero_when_already_long():
    buy = date(2024, 1, 1)
    lot = _lot(buy, 10, 100.0)
    assert lot.days_until_long_term(buy + timedelta(days=400)) == 0


# ---------------------------------------------------------------------------
# Almost-long-term flagging
# ---------------------------------------------------------------------------

def test_almost_long_term_within_window():
    today = date(2025, 1, 1)
    # 350 days held -> 16 days to long term -> flagged within 30, not within 10.
    lot = _lot(today - timedelta(days=350), 10, 100.0)
    aging = age_lots([lot], as_of=today)[0]
    assert aging.almost_long_term(30) is True
    assert aging.almost_long_term(10) is False

    flagged = almost_long_term_lots([lot], within_days=30, as_of=today)
    assert len(flagged) == 1


def test_already_long_term_not_almost():
    today = date(2025, 1, 1)
    lot = _lot(today - timedelta(days=500), 10, 100.0)
    flagged = almost_long_term_lots([lot], within_days=90, as_of=today)
    assert flagged == []


# ---------------------------------------------------------------------------
# Realized gain and loss
# ---------------------------------------------------------------------------

def test_realized_gain():
    rl = RealizedLot(
        ticker="XOM",
        account="Individual",
        buy_date=date(2023, 1, 1),
        sell_date=date(2024, 6, 1),  # > 365 days -> long term
        shares=10,
        cost_basis_per_share=100.0,
        proceeds_per_share=120.0,
    )
    assert rl.is_long_term is True
    assert rl.realized_gain == pytest.approx(200.0)  # (120-100)*10


def test_realized_loss():
    rl = RealizedLot(
        ticker="XOM",
        account="Individual",
        buy_date=date(2024, 1, 1),
        sell_date=date(2024, 5, 1),  # < 365 days -> short term
        shares=5,
        cost_basis_per_share=100.0,
        proceeds_per_share=80.0,
    )
    assert rl.is_long_term is False
    assert rl.realized_gain == pytest.approx(-100.0)  # (80-100)*5


# ---------------------------------------------------------------------------
# Tax-aware trim selection ordering
# ---------------------------------------------------------------------------

def test_trim_prefers_loss_then_long_term_then_short_term():
    """
    Order must be: loss lot -> long-term gain -> short-term gain.

    Price 100. Lots:
      A: long-term GAIN  (basis 80, +20/sh)
      B: short-term GAIN (basis 70, +30/sh) -- highest tax cost, sold last
      C: long-term LOSS  (basis 130, -30/sh) -- harvest first
    """
    today = date(2025, 1, 1)
    a = _lot(today - timedelta(days=400), 10, 80.0)   # long-term gain
    b = _lot(today - timedelta(days=100), 10, 70.0)   # short-term gain
    c = _lot(today - timedelta(days=400), 10, 130.0)  # long-term loss
    price = 100.0

    sel = select_trim_lots([a, b, c], shares_to_trim=30, price=price, as_of=today)
    order = [lot for lot, _ in sel]
    # Loss first, then long-term gain, then short-term gain.
    assert order == [c, a, b]


def test_trim_partial_fill_stops_at_requested_shares():
    today = date(2025, 1, 1)
    a = _lot(today - timedelta(days=400), 10, 80.0)   # long-term gain
    b = _lot(today - timedelta(days=100), 10, 70.0)   # short-term gain
    sel = select_trim_lots([a, b], shares_to_trim=4, price=100.0, as_of=today)
    # Only the long-term lot is touched, and only 4 shares of it.
    assert len(sel) == 1
    assert sel[0][0] is a
    assert sel[0][1] == pytest.approx(4)


def test_trim_short_term_almost_long_clipped_last():
    """Among two short-term gain lots, the one closer to long-term is sold last."""
    today = date(2025, 1, 1)
    almost = _lot(today - timedelta(days=360), 10, 70.0)  # ~6 days to long term
    fresh = _lot(today - timedelta(days=30), 10, 70.0)    # far from long term
    sel = select_trim_lots([almost, fresh], shares_to_trim=10, price=100.0, as_of=today)
    assert sel[0][0] is fresh  # fresh short-term clipped before almost-long-term


# ---------------------------------------------------------------------------
# FIFO matching + yearly realized report
# ---------------------------------------------------------------------------

def test_fifo_matches_oldest_buys_first():
    buys = [
        _lot(date(2023, 1, 10), 10, 100.0),  # oldest
        _lot(date(2024, 3, 5), 10, 110.0),
    ]
    # Sell 15 shares on 2024-06-01 at 130.
    sells = [(date(2024, 6, 1), 15.0, 130.0)]
    realized = match_sells_fifo(buys, sells)
    assert len(realized) == 2
    # First fragment: all 10 from the oldest lot (long-term).
    assert realized[0].buy_date == date(2023, 1, 10)
    assert realized[0].shares == pytest.approx(10)
    assert realized[0].is_long_term is True
    assert realized[0].realized_gain == pytest.approx(300.0)  # (130-100)*10
    # Second fragment: 5 from the newer lot (short-term).
    assert realized[1].buy_date == date(2024, 3, 5)
    assert realized[1].shares == pytest.approx(5)
    assert realized[1].is_long_term is False
    assert realized[1].realized_gain == pytest.approx(100.0)  # (130-110)*5


def test_realized_report_splits_short_and_long_by_year():
    buys = [
        _lot(date(2023, 1, 10), 10, 100.0),
        _lot(date(2024, 3, 5), 10, 110.0),
    ]
    sells = [(date(2024, 6, 1), 15.0, 130.0)]
    realized = match_sells_fifo(buys, sells)
    report = realized_report(realized)
    assert len(report) == 1
    yr = report[0]
    assert yr.year == 2024
    assert yr.long_term_gain == pytest.approx(300.0)
    assert yr.short_term_gain == pytest.approx(100.0)
    assert yr.total_gain == pytest.approx(400.0)
