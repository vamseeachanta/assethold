"""Pluggable market-data providers for the market_alerts workflow.

Default provider is yfinance (free, ~15-min delayed, unofficial). The interface is
deliberately small so a real-time feed (polygon.io, a broker websocket) can be dropped
in later without touching the signal layer. A FixtureProvider gives deterministic
offline runs for CI / tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol

# yfinance uses '-' for share classes (BRK-B); users often type 'BRKB'.
_TICKER_ALIASES = {"BRKB": "BRK-B", "BRK.B": "BRK-B", "BRKA": "BRK-A"}


def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    return _TICKER_ALIASES.get(t, t)


@dataclass
class Quote:
    ticker: str
    price: Optional[float] = None
    prev_close: Optional[float] = None
    pe: Optional[float] = None
    dividend_yield: Optional[float] = None  # fraction, e.g. 0.034 == 3.4%
    error: Optional[str] = None

    @property
    def pct_change(self) -> Optional[float]:
        if self.price is None or not self.prev_close:
            return None
        return (self.price - self.prev_close) / self.prev_close * 100.0


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> Quote: ...


class YFinanceProvider:
    """Live quotes via yfinance: prices from fast_info (reliable); fundamentals
    (P/E, dividend yield) from .info (best-effort, never sinks the quote)."""

    def get_quote(self, ticker: str) -> Quote:
        sym = normalize_ticker(ticker)
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            fi = t.fast_info
            price = _num(getattr(fi, "last_price", None))
            prev = _num(getattr(fi, "previous_close", None))

            pe = dy = None
            try:
                info = t.info or {}
                pe = _num(info.get("trailingPE"))
                # yfinance reports dividendYield in PERCENT (e.g. 2.8 == 2.8%);
                # store as a fraction.
                dy_raw = _num(info.get("dividendYield"))
                dy = dy_raw / 100.0 if dy_raw is not None else None
            except Exception:  # noqa: BLE001 - best-effort fundamentals
                pass

            return Quote(ticker=ticker, price=price, prev_close=prev, pe=pe, dividend_yield=dy)
        except Exception as exc:  # noqa: BLE001 - surface, don't crash the run
            return Quote(ticker=ticker, error=f"{type(exc).__name__}: {exc}")


class FixtureProvider:
    """Deterministic offline provider. quotes: ticker -> Quote | dict of Quote fields."""

    def __init__(self, quotes: Dict[str, object]):
        self._quotes: Dict[str, Quote] = {}
        for k, v in quotes.items():
            self._quotes[normalize_ticker(k)] = v if isinstance(v, Quote) else Quote(ticker=k, **v)

    def get_quote(self, ticker: str) -> Quote:
        q = self._quotes.get(normalize_ticker(ticker))
        return q if q is not None else Quote(ticker=ticker, error="no fixture")


def get_provider(name: str, **kwargs) -> MarketDataProvider:
    if name == "yfinance":
        return YFinanceProvider()
    if name == "fixture":
        return FixtureProvider(kwargs.get("quotes", {}))
    raise ValueError(f"unknown market-data source: {name!r} (expected 'yfinance' or 'fixture')")


def _num(x) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None
