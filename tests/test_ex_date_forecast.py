"""Tests for ex-dividend date forecasting (issue #26).

Deterministic: all inputs are fixed date/amount lists, so projected
ex-dates and amounts are exact.
"""
from datetime import date

import pytest

from assethold.dividend_forecast import (
    forecast_ex_dates,
    infer_cadence,
)

# VOO-like quarterly ex-date history (real-ish spacing ~91 days).
QUARTERLY_HISTORY = [
    date(2024, 3, 21),
    date(2024, 6, 21),
    date(2024, 9, 30),
    date(2024, 12, 23),
]


class TestInferCadence:
    def test_quarterly(self):
        result = infer_cadence([rec for rec in QUARTERLY_HISTORY])
        assert result.cadence == "quarterly"
        assert result.periods_per_year == 4
        assert result.sample_size == 3  # 4 dates -> 3 gaps

    def test_monthly(self):
        dates = [date(2024, m, 15) for m in range(1, 7)]  # ~30/31 day gaps
        result = infer_cadence(dates)
        assert result.cadence == "monthly"
        assert result.periods_per_year == 12

    def test_semiannual(self):
        dates = [date(2023, 1, 10), date(2023, 7, 12), date(2024, 1, 9)]
        result = infer_cadence(dates)
        assert result.cadence == "semiannual"
        assert result.periods_per_year == 2

    def test_annual(self):
        dates = [date(2022, 5, 10), date(2023, 5, 11), date(2024, 5, 9)]
        result = infer_cadence(dates)
        assert result.cadence == "annual"
        assert result.periods_per_year == 1

    def test_median_robust_to_one_missed_payment(self):
        # 3 quarterly gaps, then one ~182-day gap (a missed payment).
        # median of [91, 92, 91, 182] -> ~91.5 still classifies quarterly.
        dates = [
            date(2024, 1, 1),
            date(2024, 4, 1),  # 91
            date(2024, 7, 2),  # 92
            date(2024, 10, 1),  # 91
            date(2025, 4, 1),  # 182 (missed Jan)
        ]
        result = infer_cadence(dates)
        assert result.cadence == "quarterly"

    def test_irregular(self):
        dates = [date(2024, 1, 1), date(2024, 3, 5), date(2024, 11, 1)]
        # gaps 64, 241 -> median 152.5 lands in the semiannual band; use a
        # genuinely unclassifiable pair instead.
        dates = [date(2024, 1, 1), date(2024, 3, 20)]  # single 79-day gap
        result = infer_cadence(dates)
        # 79 days is below the quarterly band lower bound (75)? -> in band.
        # Use a clearly out-of-band gap:
        dates = [date(2024, 1, 1), date(2024, 2, 25)]  # 55-day gap
        result = infer_cadence(dates)
        assert result.cadence == "irregular"
        assert result.periods_per_year == 0

    def test_single_date_raises(self):
        with pytest.raises(ValueError, match="two distinct"):
            infer_cadence([date(2024, 1, 1)])


class TestForecastExDates:
    def test_quarterly_next_four_spacing(self):
        hist = [(d, 1.40) for d in QUARTERLY_HISTORY]
        sched = forecast_ex_dates(hist, periods=4)
        assert sched.cadence.cadence == "quarterly"
        assert len(sched.events) == 4
        # Steps of 91 days from last ex-date 2024-12-23.
        assert sched.events[0].ex_date == date(2025, 3, 24)
        assert sched.events[1].ex_date == date(2025, 6, 23)
        assert sched.events[2].ex_date == date(2025, 9, 22)
        assert sched.events[3].ex_date == date(2025, 12, 22)
        # ~91-day spacing between consecutive projected ex-dates.
        gaps = [
            (sched.events[i + 1].ex_date - sched.events[i].ex_date).days
            for i in range(3)
        ]
        assert gaps == [91, 91, 91]
        # period_index is 1-based.
        assert [e.period_index for e in sched.events] == [1, 2, 3, 4]

    def test_amount_flat_no_growth(self):
        hist = [(d, 1.40) for d in QUARTERLY_HISTORY]
        sched = forecast_ex_dates(hist, periods=4)
        assert all(abs(e.amount - 1.40) < 1e-9 for e in sched.events)
        assert abs(sched.total_amount - 5.60) < 1e-9  # 4 * 1.40

    def test_amount_growth_compounds(self):
        hist = [(d, 1.40) for d in QUARTERLY_HISTORY]
        sched = forecast_ex_dates(hist, periods=3, growth_rate=0.02)
        assert abs(sched.events[0].amount - 1.40 * 1.02) < 1e-9
        assert abs(sched.events[1].amount - 1.40 * 1.02**2) < 1e-9
        assert abs(sched.events[2].amount - 1.40 * 1.02**3) < 1e-9

    def test_unsorted_history_anchors_on_latest(self):
        # Shuffled input must still anchor on the most-recent ex-date/amount.
        hist = [
            (date(2024, 9, 30), 1.50),
            (date(2024, 3, 21), 1.30),
            (date(2024, 12, 23), 1.60),  # latest -> anchor
            (date(2024, 6, 21), 1.40),
        ]
        sched = forecast_ex_dates(hist, periods=1)
        assert sched.events[0].ex_date == date(2025, 3, 24)  # 12-23 + 91
        assert abs(sched.events[0].amount - 1.60) < 1e-9

    def test_irregular_gap_uses_median_fallback(self):
        # No recognisable cadence -> step by observed median gap.
        hist = [
            (date(2024, 1, 1), 1.0),
            (date(2024, 2, 25), 1.0),  # 55-day gap
            (date(2024, 4, 20), 1.0),  # 55-day gap
        ]
        sched = forecast_ex_dates(hist, periods=2)
        assert sched.cadence.cadence == "irregular"
        # median gap = 55 days -> step forward 55 days from 2024-04-20.
        assert sched.events[0].ex_date == date(2024, 6, 14)
        assert sched.events[1].ex_date == date(2024, 8, 8)

    def test_cadence_override(self):
        hist = [(date(2024, 1, 15), 0.25), (date(2024, 2, 15), 0.25)]
        sched = forecast_ex_dates(hist, periods=2, cadence_override="monthly")
        assert sched.cadence.cadence == "monthly"
        # +30 days from 2024-02-15.
        assert sched.events[0].ex_date == date(2024, 3, 16)
        assert sched.events[1].ex_date == date(2024, 4, 15)

    def test_bad_override_raises(self):
        hist = [(date(2024, 1, 15), 0.25), (date(2024, 2, 15), 0.25)]
        with pytest.raises(ValueError, match="unknown cadence"):
            forecast_ex_dates(hist, periods=1, cadence_override="weekly")

    def test_single_date_no_override_raises(self):
        with pytest.raises(ValueError, match="single ex-date"):
            forecast_ex_dates([(date(2024, 1, 1), 1.0)], periods=2)

    def test_periods_must_be_positive(self):
        hist = [(d, 1.40) for d in QUARTERLY_HISTORY]
        with pytest.raises(ValueError, match="periods"):
            forecast_ex_dates(hist, periods=0)

    def test_empty_history_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            forecast_ex_dates([], periods=1)
