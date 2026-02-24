# ABOUTME: Fundamentals scoring — P/E, P/B, EV/EBITDA ranking from yfinance (WRK-322)
# ABOUTME: Fetches valuation metrics and scores/ranks holdings by value attractiveness
"""
Fundamentals scoring module.

Provides functions to fetch and score equity holdings by key valuation
metrics (P/E, P/B, EV/EBITDA) sourced from yfinance, and to rank a
portfolio by composite value attractiveness.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

try:
    import yfinance  # type: ignore[import]
except ImportError:
    yfinance = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Individual metric scoring helpers
# ---------------------------------------------------------------------------

def score_pe_ratio(pe: Optional[float]) -> float:
    """Return a 0-10 value score for a trailing P/E ratio.

    Lower P/E indicates better value; missing data yields 0 (neutral).

    Bands:
        < 10  → 10
        10-15 → 8
        15-20 → 6
        20-25 → 4
        > 25  → 2
        None  → 0
    """
    if pe is None:
        return 0.0
    if pe < 10:
        return 10.0
    if pe < 15:
        return 8.0
    if pe < 20:
        return 6.0
    if pe < 25:
        return 4.0
    return 2.0


def score_pb_ratio(pb: Optional[float]) -> float:
    """Return a 0-10 value score for a price-to-book ratio.

    Lower P/B indicates better value; missing data yields 0 (neutral).

    Bands:
        < 1  → 10
        1-2  → 8
        2-3  → 6
        3-5  → 4
        > 5  → 2
        None → 0
    """
    if pb is None:
        return 0.0
    if pb < 1:
        return 10.0
    if pb < 2:
        return 8.0
    if pb < 3:
        return 6.0
    if pb < 5:
        return 4.0
    return 2.0


def score_ev_ebitda(ev_ebitda: Optional[float]) -> float:
    """Return a 0-10 value score for an EV/EBITDA multiple.

    Lower EV/EBITDA indicates better value; missing data yields 0 (neutral).

    Bands:
        < 8   → 10
        8-12  → 8
        12-16 → 6
        16-20 → 4
        > 20  → 2
        None  → 0
    """
    if ev_ebitda is None:
        return 0.0
    if ev_ebitda < 8:
        return 10.0
    if ev_ebitda < 12:
        return 8.0
    if ev_ebitda < 16:
        return 6.0
    if ev_ebitda < 20:
        return 4.0
    return 2.0


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_fundamentals(ticker: str) -> dict:
    """Fetch P/E, P/B, EV/EBITDA, and forward EPS for a ticker via yfinance.

    Args:
        ticker: Stock ticker symbol (case-insensitive; normalised to upper).

    Returns:
        Dict with keys: ticker, pe, pb, ev_ebitda, forward_eps.
        Missing fields are represented as None.

    Raises:
        ImportError: If yfinance is not installed.
    """
    if yfinance is None:
        raise ImportError(
            "yfinance is required for fetch_fundamentals. "
            "Install it with: pip install yfinance"
        )

    symbol = ticker.upper().strip()
    info: dict = yfinance.Ticker(symbol).info

    return {
        "ticker": symbol,
        "pe": info.get("trailingPE") or None,
        "pb": info.get("priceToBook") or None,
        "ev_ebitda": info.get("enterpriseToEbitda") or None,
        "forward_eps": info.get("forwardEps") or None,
    }


# ---------------------------------------------------------------------------
# Scorer class
# ---------------------------------------------------------------------------

_PE_WEIGHT: float = 0.35
_PB_WEIGHT: float = 0.35
_EV_WEIGHT: float = 0.30


class FundamentalsScorer:
    """Score and rank holdings by composite valuation attractiveness.

    Composite formula:
        score = P/E_score * 0.35 + P/B_score * 0.35 + EV/EBITDA_score * 0.30

    Higher composite score → more attractive value.
    """

    def score(self, ticker_data: dict) -> float:
        """Compute weighted composite score for a single holding dict.

        Args:
            ticker_data: Dict containing optional float fields:
                         pe, pb, ev_ebitda.

        Returns:
            Composite float score in range [0, 10].
        """
        pe_score = score_pe_ratio(ticker_data.get("pe"))
        pb_score = score_pb_ratio(ticker_data.get("pb"))
        ev_score = score_ev_ebitda(ticker_data.get("ev_ebitda"))
        return (
            pe_score * _PE_WEIGHT
            + pb_score * _PB_WEIGHT
            + ev_score * _EV_WEIGHT
        )

    def rank(self, holdings: list[dict]) -> list[dict]:
        """Return holdings sorted by composite score, highest first.

        Each output dict is a shallow copy of the input dict with an added
        ``score`` key containing the computed composite score.

        Args:
            holdings: List of dicts each containing at minimum a ``ticker``
                      key plus optional pe, pb, ev_ebitda float fields.

        Returns:
            New list of enriched dicts ordered by score descending.
        """
        scored = []
        for holding in holdings:
            enriched = dict(holding)
            enriched["score"] = self.score(holding)
            scored.append(enriched)
        scored.sort(key=lambda h: h["score"], reverse=True)
        return scored

    def fetch_and_rank(self, tickers: list[str]) -> pd.DataFrame:
        """Fetch fundamentals from yfinance and return a ranked DataFrame.

        Args:
            tickers: List of stock ticker symbols.

        Returns:
            DataFrame with columns ticker, pe, pb, ev_ebitda, forward_eps,
            score; sorted by score descending.
        """
        holdings = [fetch_fundamentals(t) for t in tickers]
        ranked = self.rank(holdings)
        return pd.DataFrame(ranked)
