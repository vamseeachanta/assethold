# ABOUTME: Fundamentals scoring — P/E, P/B, EV/EBITDA ranking from yfinance (WRK-322)
# ABOUTME: Fetches valuation metrics and scores/ranks holdings by value attractiveness
"""
Fundamentals scoring module.

Provides functions to fetch and score equity holdings by key valuation
metrics (P/E, P/B, EV/EBITDA) sourced from yfinance, and to rank a
portfolio by composite value attractiveness.

Classes:
    FundamentalsScorer  — score and rank holdings by composite value score
    SectorPeerRanker    — add percentile ranks within GICS sector peers;
                          flag deep-value opportunities
    FundamentalsReport  — render scored holdings to CSV and console output
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

try:
    import yfinance  # type: ignore[import]
except ImportError:
    yfinance = None  # type: ignore[assignment]

# Minimum sector-peer count required to assign a deep-value flag
_DEEP_VALUE_MIN_PEERS: int = 5
# Top quintile threshold: score_pct >= 80% within sector = deep value
_DEEP_VALUE_THRESHOLD: float = 80.0


# ---------------------------------------------------------------------------
# Individual metric scoring helpers
# ---------------------------------------------------------------------------

def score_pe_ratio(pe: Optional[float]) -> float:
    """Return a 0-10 value score for a trailing P/E ratio.

    Lower P/E indicates better value; missing or negative data yields 0
    (neutral / not meaningful). Negative P/E means the company is
    loss-making and should not be rewarded as cheap.

    Bands:
        <= 0  → 0  (loss-making or undefined)
        < 10  → 10
        10-15 → 8
        15-20 → 6
        20-25 → 4
        > 25  → 2
        None  → 0
    """
    if pe is None or pe <= 0:
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

    Lower P/B indicates better value; missing or negative data yields 0
    (neutral / not meaningful). Negative P/B indicates negative book value
    (stockholder deficit) and should not be rewarded.

    Bands:
        <= 0  → 0  (negative book value or undefined)
        < 1   → 10
        1-2   → 8
        2-3   → 6
        3-5   → 4
        > 5   → 2
        None  → 0
    """
    if pb is None or pb <= 0:
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

    Lower EV/EBITDA indicates better value; missing or negative data yields 0
    (neutral / not meaningful). Negative EV/EBITDA typically means negative
    EBITDA (operating losses) and should not be rewarded.

    Bands:
        <= 0  → 0  (negative EBITDA / undefined)
        < 8   → 10
        8-12  → 8
        12-16 → 6
        16-20 → 4
        > 20  → 2
        None  → 0
    """
    if ev_ebitda is None or ev_ebitda <= 0:
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
    """Fetch P/E, P/B, EV/EBITDA, forward EPS, sector, and dividend yield
    for a ticker via yfinance.

    Args:
        ticker: Stock ticker symbol (case-insensitive; normalised to upper).

    Returns:
        Dict with keys: ticker, pe, pb, ev_ebitda, forward_eps,
        sector, dividend_yield.
        Missing numeric fields are represented as None.
        Missing sector returns "Unknown".

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
        "sector": str(info.get("sector") or "Unknown"),
        "dividend_yield": info.get("dividendYield") or None,
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
            sector, dividend_yield, score; sorted by score descending.
        """
        holdings = [fetch_fundamentals(t) for t in tickers]
        ranked = self.rank(holdings)
        return pd.DataFrame(ranked)


# ---------------------------------------------------------------------------
# Sector peer ranker
# ---------------------------------------------------------------------------

def _percentile_rank_lower_is_better(
    values: list[Optional[float]],
    target_idx: int,
) -> Optional[float]:
    """Return the percentile rank of values[target_idx] where lower raw values
    earn a higher percentile (more value-attractive).

    A holding with the lowest raw metric (cheapest) gets close to 100.0.

    Returns None when the target value is None.
    """
    target = values[target_idx]
    if target is None:
        return None

    valid = [v for v in values if v is not None]
    n = len(valid)
    if n == 1:
        return 100.0

    # Count how many valid peers have a value >= target (equal or more expensive)
    worse_or_equal = sum(1 for v in valid if v >= target)
    return round(worse_or_equal / n * 100.0, 1)


def _percentile_rank_higher_is_better(
    values: list[Optional[float]],
    target_idx: int,
) -> Optional[float]:
    """Return the percentile rank where higher raw values earn a higher percentile.

    Used for composite score (higher score = more value-attractive).

    Returns None when the target value is None.
    """
    target = values[target_idx]
    if target is None:
        return None

    valid = [v for v in values if v is not None]
    n = len(valid)
    if n == 1:
        return 100.0

    # Count how many valid peers have a value <= target (worse or equal score)
    worse_or_equal = sum(1 for v in valid if v <= target)
    return round(worse_or_equal / n * 100.0, 1)


class SectorPeerRanker:
    """Add sector-peer percentile ranks and deep-value flags to holdings.

    Holdings are grouped by their ``sector`` field (GICS sector string).
    Within each group, each holding receives a percentile rank per metric
    (pe_pct, pb_pct, ev_ebitda_pct) where 100 = cheapest peer.

    A ``deep_value`` boolean is set when the composite ``score`` percentile
    within the sector is >= 80% (top quintile of value).  Requires at least
    5 sector peers to be meaningful; set to None otherwise.
    """

    def add_sector_percentiles(self, holdings: list[dict]) -> list[dict]:
        """Enrich holdings with per-sector percentile ranks and deep-value flag.

        Args:
            holdings: List of holding dicts.  Each must have at minimum a
                      ``sector`` key.  Supported metric keys: pe, pb,
                      ev_ebitda, score.

        Returns:
            New list of enriched dicts (shallow copies) with added keys:
            pe_pct, pb_pct, ev_ebitda_pct, deep_value.
        """
        # Group indices by sector
        sector_indices: dict[str, list[int]] = {}
        for idx, h in enumerate(holdings):
            sector = h.get("sector", "Unknown")
            sector_indices.setdefault(sector, []).append(idx)

        enriched = [dict(h) for h in holdings]

        for sector, indices in sector_indices.items():
            group = [enriched[i] for i in indices]

            for metric in ("pe", "pb", "ev_ebitda"):
                values: list[Optional[float]] = [h.get(metric) for h in group]
                for local_idx, global_idx in enumerate(indices):
                    pct = _percentile_rank_lower_is_better(values, local_idx)
                    enriched[global_idx][f"{metric}_pct"] = pct

            # Deep-value flag: based on composite score percentile
            n_peers = len(indices)
            score_values: list[Optional[float]] = [h.get("score") for h in group]
            for local_idx, global_idx in enumerate(indices):
                if n_peers < _DEEP_VALUE_MIN_PEERS:
                    enriched[global_idx]["deep_value"] = None
                    continue
                score_pct = _percentile_rank_higher_is_better(
                    score_values, local_idx
                )
                if score_pct is None:
                    enriched[global_idx]["deep_value"] = None
                else:
                    enriched[global_idx]["deep_value"] = (
                        score_pct >= _DEEP_VALUE_THRESHOLD
                    )

        return enriched


# ---------------------------------------------------------------------------
# Output: CSV and console table
# ---------------------------------------------------------------------------
# FundamentalsReport is in fundamentals_report.py (split for 400-line limit).
# Re-exported here to keep the public API at assethold.fundamentals.

from assethold.fundamentals_report import FundamentalsReport  # noqa: F401, E402
