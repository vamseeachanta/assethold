"""Market data-as-of provenance tests (workspace-hub#3287 AC#3).

Pure-unit: no engine, no market data. Verifies the precedence + fail-soft-warn
contract of ``market_data_as_of``.
"""

from __future__ import annotations

from assethold.workflow_api.provenance import market_data_as_of


def test_data_as_of_from_portfolio_prices_as_of():
    cfg = {"portfolio": {"prices_as_of": "2026-06-27", "prices": {"VOO": 1.0}}}
    as_of, warns = market_data_as_of(cfg, None)
    assert as_of == "2026-06-27"
    assert warns == []


def test_data_as_of_from_analysis_when_portfolio_absent():
    cfg = {"Analysis": {"data_as_of": "2026-01-01"}, "portfolio": {"prices": {"VOO": 1.0}}}
    as_of, warns = market_data_as_of(cfg, None)
    assert as_of == "2026-01-01"
    assert warns == []


def test_data_as_of_from_registry_row_fallback():
    cfg = {"portfolio": {"prices": {"VOO": 1.0}}}
    row = {"market_data_as_of": "2025-12-31"}
    as_of, warns = market_data_as_of(cfg, row)
    assert as_of == "2025-12-31"
    assert warns == []


def test_precedence_portfolio_over_analysis_over_row():
    cfg = {
        "portfolio": {"prices_as_of": "P", "prices": {"VOO": 1.0}},
        "Analysis": {"data_as_of": "A"},
    }
    row = {"market_data_as_of": "R"}
    as_of, _ = market_data_as_of(cfg, row)
    assert as_of == "P"


def test_market_inputs_without_as_of_warns_and_none():
    cfg = {"portfolio": {"prices": {"VOO": 1.0}}}
    as_of, warns = market_data_as_of(cfg, None)
    assert as_of is None
    assert warns and "data_as_of" in warns[0]


def test_no_market_inputs_no_warning():
    cfg = {"portfolio": {"data_dir": "x"}}
    as_of, warns = market_data_as_of(cfg, None)
    assert as_of is None
    assert warns == []
