"""Covered call analyser: option chain ingestion and premium yield calculator.

Ingests option chains via yfinance, calculates key covered-call metrics for
each strike, filters by user criteria, and returns a ranked DataFrame.

Public API
----------
calculate_premium_yield_annual  -- annualised premium / current_price
calculate_downside_protection   -- absolute premium / current_price
calculate_break_even            -- current_price - premium
calculate_if_called_return_annual -- annualised (strike - price + premium) / price
filter_option_chain             -- apply DTE / premium / delta filters
build_covered_call_table        -- build per-strike metrics DataFrame
analyse_covered_calls           -- top-level entry: holdings → ranked table
"""

# Standard library
import logging
from datetime import date
from typing import Any, Dict, List, Optional

# Third-party
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_DAYS_PER_YEAR: float = 365.0


# ---------------------------------------------------------------------------
# Core scalar calculators
# ---------------------------------------------------------------------------

def calculate_premium_yield_annual(
    premium: float,
    current_price: float,
    days_to_expiry: int,
) -> float:
    """Return annualised premium yield as a decimal.

    Formula: (premium / current_price) * (365 / days_to_expiry)

    Raises
    ------
    ValueError
        When days_to_expiry is zero.
    ZeroDivisionError
        When current_price is zero.
    """
    if days_to_expiry == 0:
        raise ValueError("days_to_expiry must be non-zero")
    return (premium / current_price) * (_DAYS_PER_YEAR / days_to_expiry)


def calculate_downside_protection(
    premium: float,
    current_price: float,
) -> float:
    """Return absolute downside protection as a decimal fraction.

    Formula: premium / current_price

    Raises
    ------
    ZeroDivisionError
        When current_price is zero.
    ValueError
        When current_price is zero (explicit guard).
    """
    if current_price == 0:
        raise ValueError("current_price must be non-zero")
    return premium / current_price


def calculate_break_even(current_price: float, premium: float) -> float:
    """Return break-even price after receiving the premium.

    Formula: current_price - premium
    """
    return float(current_price - premium)


def calculate_if_called_return_annual(
    strike: float,
    current_price: float,
    premium: float,
    days_to_expiry: int,
) -> float:
    """Return annualised if-called return as a decimal.

    Formula: ((strike - current_price + premium) / current_price)
              * (365 / days_to_expiry)

    Raises
    ------
    ValueError
        When days_to_expiry is zero.
    """
    if days_to_expiry == 0:
        raise ValueError("days_to_expiry must be non-zero")
    raw = (strike - current_price + premium) / current_price
    return raw * (_DAYS_PER_YEAR / days_to_expiry)


# ---------------------------------------------------------------------------
# Filter helper
# ---------------------------------------------------------------------------

def filter_option_chain(
    calls_df: pd.DataFrame,
    days_to_expiry: int,
    min_days_to_expiry: int = 0,
    min_premium: float = 0.0,
    max_delta: Optional[float] = None,
) -> pd.DataFrame:
    """Return a filtered copy of *calls_df* applying user-specified gates.

    Parameters
    ----------
    calls_df:
        Raw calls DataFrame from yfinance option_chain().calls.
    days_to_expiry:
        Calendar days until this expiry date.
    min_days_to_expiry:
        Minimum acceptable DTE.  Rows are dropped when
        days_to_expiry < min_days_to_expiry.
    min_premium:
        Minimum option premium (uses ``lastPrice`` column).
    max_delta:
        Maximum absolute delta.  Ignored when the ``delta`` column is absent.
    """
    if calls_df.empty:
        return calls_df.copy()

    if days_to_expiry < min_days_to_expiry:
        return calls_df.iloc[0:0].copy()

    mask = pd.Series([True] * len(calls_df), index=calls_df.index)

    if "lastPrice" in calls_df.columns and min_premium > 0.0:
        mask &= calls_df["lastPrice"] >= min_premium

    if max_delta is not None and "delta" in calls_df.columns:
        mask &= calls_df["delta"].abs() <= max_delta

    return calls_df.loc[mask].copy()


# ---------------------------------------------------------------------------
# Per-expiry table builder
# ---------------------------------------------------------------------------

def build_covered_call_table(
    ticker: str,
    current_price: float,
    calls_df: pd.DataFrame,
    expiry_date: date,
    today: date,
) -> pd.DataFrame:
    """Build a per-strike metrics DataFrame for a single expiry.

    Uses mid-price (bid + ask) / 2 as the premium when both columns are
    present; falls back to ``lastPrice`` otherwise.

    Parameters
    ----------
    ticker:
        Equity ticker symbol.
    current_price:
        Current underlying price.
    calls_df:
        Calls slice (already filtered if desired).
    expiry_date:
        Option expiry date.
    today:
        Reference date for DTE calculation (injectable for testing).

    Returns
    -------
    pd.DataFrame with columns:
        ticker, expiry, strike, premium, days_to_expiry,
        premium_yield_annual, downside_protection, break_even,
        if_called_return_annual
    """
    if calls_df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "expiry",
                "strike",
                "premium",
                "days_to_expiry",
                "premium_yield_annual",
                "downside_protection",
                "break_even",
                "if_called_return_annual",
            ]
        )

    dte = (expiry_date - today).days
    rows: List[Dict[str, Any]] = []

    for _, opt in calls_df.iterrows():
        strike = float(opt["strike"])

        if "bid" in calls_df.columns and "ask" in calls_df.columns:
            bid = float(opt.get("bid", 0.0) or 0.0)
            ask = float(opt.get("ask", 0.0) or 0.0)
            if bid > 0 and ask > 0:
                premium = (bid + ask) / 2.0
            else:
                premium = float(opt.get("lastPrice", 0.0) or 0.0)
        else:
            premium = float(opt.get("lastPrice", 0.0) or 0.0)

        if dte <= 0 or current_price <= 0:
            logger.warning(
                "Skipping row: dte=%d current_price=%.2f", dte, current_price
            )
            continue

        rows.append(
            {
                "ticker": ticker,
                "expiry": expiry_date,
                "strike": strike,
                "premium": premium,
                "days_to_expiry": dte,
                "premium_yield_annual": calculate_premium_yield_annual(
                    premium, current_price, dte
                ),
                "downside_protection": calculate_downside_protection(
                    premium, current_price
                ),
                "break_even": calculate_break_even(current_price, premium),
                "if_called_return_annual": calculate_if_called_return_annual(
                    strike, current_price, premium, dte
                ),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def analyse_covered_calls(
    holdings: List[Dict[str, Any]],
    today: Optional[date] = None,
    min_days_to_expiry: int = 0,
    min_premium: float = 0.0,
    max_delta: Optional[float] = None,
) -> pd.DataFrame:
    """Fetch option chains and return a ranked covered-call opportunities table.

    Parameters
    ----------
    holdings:
        List of dicts, each with keys:
          ``ticker``        -- equity ticker symbol (str)
          ``shares``        -- number of shares held (int)
          ``current_price`` -- current price used as fallback (float)
    today:
        Reference date; defaults to ``date.today()`` when None.
    min_days_to_expiry:
        Filter: drop expiries with fewer days than this threshold.
    min_premium:
        Filter: drop option rows with premium below this value.
    max_delta:
        Filter: drop option rows where |delta| exceeds this value.
        Silently ignored when the delta column is absent.

    Returns
    -------
    pd.DataFrame
        Ranked by ``premium_yield_annual`` descending.  Empty DataFrame when
        no holdings or no suitable options are found.
    """
    if today is None:
        today = date.today()

    if not holdings:
        return pd.DataFrame()

    all_tables: List[pd.DataFrame] = []

    for holding in holdings:
        ticker_symbol: str = holding["ticker"]
        fallback_price: float = float(holding.get("current_price", 0.0))

        try:
            yf_ticker = yf.Ticker(ticker_symbol)
            info = yf_ticker.info or {}
            current_price = float(
                info.get("regularMarketPrice") or fallback_price
            )
            expiry_dates = tuple(yf_ticker.options)
        except Exception as exc:
            logger.warning(
                "Failed to fetch data for %s: %s", ticker_symbol, exc
            )
            continue

        if not expiry_dates:
            logger.info("No option expiries for %s — skipping", ticker_symbol)
            continue

        for expiry_str in expiry_dates:
            try:
                expiry_date = date.fromisoformat(expiry_str)
            except ValueError:
                logger.warning(
                    "Unrecognised expiry format '%s' for %s",
                    expiry_str,
                    ticker_symbol,
                )
                continue

            dte = (expiry_date - today).days

            try:
                chain = yf_ticker.option_chain(expiry_str)
                calls_df = chain.calls
            except Exception as exc:
                logger.warning(
                    "Could not fetch chain for %s %s: %s",
                    ticker_symbol,
                    expiry_str,
                    exc,
                )
                continue

            filtered = filter_option_chain(
                calls_df=calls_df,
                days_to_expiry=dte,
                min_days_to_expiry=min_days_to_expiry,
                min_premium=min_premium,
                max_delta=max_delta,
            )

            if filtered.empty:
                continue

            table = build_covered_call_table(
                ticker=ticker_symbol,
                current_price=current_price,
                calls_df=filtered,
                expiry_date=expiry_date,
                today=today,
            )

            if not table.empty:
                all_tables.append(table)

    if not all_tables:
        return pd.DataFrame()

    combined = pd.concat(all_tables, ignore_index=True)
    return combined.sort_values("premium_yield_annual", ascending=False).reset_index(
        drop=True
    )
