"""Offline tests for the market_alerts workflow (fixture provider, no network)."""
from assethold.modules.market_alerts.marketdata import FixtureProvider, Quote, normalize_ticker
from assethold.modules.market_alerts.market_alerts import MarketAlertsWorkflow


def _cfg(tmp_path):
    return {
        "basename": "market_alerts",
        "market_alerts": {
            "data": {"source": "fixture"},
            "positions": [
                {"ticker": "XOM", "usd": 1000},
                {"ticker": "BRKB", "usd": 3000},
            ],
            "signals": {"price_move_pct": 1.0, "fundamentals": {"pe_max": 30, "div_yield_min": 3.0}},
            "outputs": {
                "snapshot_csv": str(tmp_path / "snapshot.csv"),
                "alerts_json": str(tmp_path / "alerts.json"),
            },
        },
    }


def _provider():
    return FixtureProvider({
        "XOM": Quote(ticker="XOM", price=110.0, prev_close=100.0, pe=12.0, dividend_yield=0.035),
        "BRK-B": Quote(ticker="BRKB", price=400.0, prev_close=399.0, pe=9.0, dividend_yield=0.0),
    })


def test_brkb_alias():
    assert normalize_ticker("BRKB") == "BRK-B"


def test_move_alert_and_outputs_written(tmp_path):
    cfg = _cfg(tmp_path)
    out = MarketAlertsWorkflow().router(cfg, provider=_provider())
    alerts = out["market_alerts_result"]["alerts"]
    moves = [a for a in alerts if a["kind"] == "move"]
    assert len(moves) == 1 and moves[0]["ticker"] == "XOM"  # +10% vs prev close
    assert (tmp_path / "snapshot.csv").exists()
    assert (tmp_path / "alerts.json").exists()


def test_weighted_move_uses_dollar_weights(tmp_path):
    out = MarketAlertsWorkflow().router(_cfg(tmp_path), provider=_provider())
    pm = out["market_alerts_result"]["portfolio"]["weighted_move_pct"]
    assert 2.6 < pm < 2.8  # XOM +10% @0.25 + BRKB ~+0.25% @0.75


def test_fixture_quotes_from_cfg(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["market_alerts"]["data"] = {
        "source": "fixture",
        "quotes": {"XOM": {"price": 110.0, "prev_close": 100.0}, "BRKB": {"price": 400.0, "prev_close": 399.0}},
    }
    out = MarketAlertsWorkflow().router(cfg)  # provider built from cfg, not injected
    assert any(a["kind"] == "move" for a in out["market_alerts_result"]["alerts"])
