"""
Tax-lot aging and long-term capital-gains (LTCG) optimizer.

Builds per-buy tax lots from Fidelity transaction history and classifies each
lot by holding period so the daily strategy can make tax-aware trim decisions.

Three capabilities are provided:

1.  **Per-lot aging** — each buy transaction becomes a :class:`TaxLot` carrying
    its purchase date, share count, and per-share cost basis.  Holding period
    and short-/long-term status are derived relative to an *as-of* date.

2.  **Tax-aware trim selection** — :func:`select_trim_lots` chooses which lots
    to realize when a trim signal fires, preferring long-term gains and
    loss-harvesting candidates over short-term gains (which are taxed at the
    higher ordinary-income rate).

3.  **Realized gain/loss report** — :func:`realized_report` matches sell
    transactions against buy lots (FIFO) and summarizes realized P/L by tax
    year, split into short-term and long-term buckets.

Holding-period boundary convention
-----------------------------------
US IRS rule: a holding period **longer than one year** qualifies for the
long-term capital-gains rate.  The holding period starts the *day after*
purchase, so a lot is long-term iff::

    (sell_date - buy_date).days > 365

A lot held for exactly 365 days is therefore **short-term**; 366 days is
long-term.  Leap years are handled implicitly because the comparison is on the
real calendar-day delta, not a 365-day approximation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

# US IRS long-term boundary: strictly MORE than 365 calendar days.
_LONG_TERM_BOUNDARY_DAYS = 365

# Default federal tax-rate assumptions (decimal). Used only to rank lots when
# estimating the tax cost of realizing a gain; callers may override.
_DEFAULT_SHORT_TERM_RATE = Decimal("0.35")  # ordinary-income proxy
_DEFAULT_LONG_TERM_RATE = Decimal("0.20")  # top LTCG bracket


@dataclass(frozen=True)
class TaxLot:
    """
    One purchase lot of a security.

    Attributes:
        ticker:               Security symbol (upper-case).
        account:              Owning account label.
        buy_date:             Trade date of the purchase.
        shares:               Number of shares acquired (> 0).
        cost_basis_per_share: Per-share purchase price in USD.
    """

    ticker: str
    account: str
    buy_date: date
    shares: float
    cost_basis_per_share: float

    @property
    def cost_basis(self) -> float:
        """Total cost basis of the lot (shares x per-share basis)."""
        return self.shares * self.cost_basis_per_share

    def holding_period_days(self, as_of: date) -> int:
        """
        Calendar days the lot has been held as of *as_of*.

        Args:
            as_of: Reference date (e.g. today or a hypothetical sell date).

        Returns:
            Non-negative day count. Returns 0 for a same-day or future as_of.
        """
        return max(0, (as_of - self.buy_date).days)

    def is_long_term(self, as_of: date) -> bool:
        """
        True iff the lot qualifies for long-term capital-gains treatment.

        Boundary: long-term iff ``(as_of - buy_date).days > 365`` (see module
        docstring). Exactly 365 days is short-term; 366 days is long-term.
        """
        return self.holding_period_days(as_of) > _LONG_TERM_BOUNDARY_DAYS

    def days_until_long_term(self, as_of: date) -> int:
        """
        Days remaining until the lot turns long-term.

        Returns 0 once the lot is already long-term, otherwise the number of
        additional calendar days needed to cross the 365-day boundary.
        """
        if self.is_long_term(as_of):
            return 0
        return _LONG_TERM_BOUNDARY_DAYS + 1 - self.holding_period_days(as_of)

    def unrealized_gain(self, price: float) -> float:
        """Unrealized P/L at *price* (positive = gain, negative = loss)."""
        return (price - self.cost_basis_per_share) * self.shares


@dataclass(frozen=True)
class LotAging:
    """Aging classification of a single lot at a point in time."""

    lot: TaxLot
    as_of: date

    @property
    def holding_period_days(self) -> int:
        return self.lot.holding_period_days(self.as_of)

    @property
    def is_long_term(self) -> bool:
        return self.lot.is_long_term(self.as_of)

    @property
    def days_until_long_term(self) -> int:
        return self.lot.days_until_long_term(self.as_of)

    def almost_long_term(self, within_days: int) -> bool:
        """
        True when a short-term lot will turn long-term within *within_days*.

        Used to flag "almost long-term — hold" lots (e.g. within 30/60/90 days)
        so a trim is deferred to capture the lower tax rate.
        """
        if self.is_long_term:
            return False
        return 0 < self.days_until_long_term <= within_days


@dataclass(frozen=True)
class RealizedLot:
    """A buy lot (or part of one) matched against a sell to realize P/L."""

    ticker: str
    account: str
    buy_date: date
    sell_date: date
    shares: float
    cost_basis_per_share: float
    proceeds_per_share: float

    @property
    def holding_period_days(self) -> int:
        return max(0, (self.sell_date - self.buy_date).days)

    @property
    def is_long_term(self) -> bool:
        return self.holding_period_days > _LONG_TERM_BOUNDARY_DAYS

    @property
    def realized_gain(self) -> float:
        """Realized P/L for the matched shares (positive = gain)."""
        return (self.proceeds_per_share - self.cost_basis_per_share) * self.shares


@dataclass(frozen=True)
class YearlyRealizedSummary:
    """Aggregated realized P/L for one tax year."""

    year: int
    short_term_gain: float
    long_term_gain: float
    short_term_proceeds: float
    long_term_proceeds: float
    lots: list[RealizedLot] = field(default_factory=list)

    @property
    def total_gain(self) -> float:
        return self.short_term_gain + self.long_term_gain


# ----------------------------------------------------------------------------
# Aging
# ----------------------------------------------------------------------------

def age_lots(lots: list[TaxLot], as_of: Optional[date] = None) -> list[LotAging]:
    """
    Classify each lot's holding period as of *as_of* (default: today).

    Returns the agings sorted oldest-first (longest holding period first), so
    long-term lots lead the list.
    """
    ref = as_of or date.today()
    agings = [LotAging(lot=lot, as_of=ref) for lot in lots]
    return sorted(agings, key=lambda a: a.holding_period_days, reverse=True)


def almost_long_term_lots(
    lots: list[TaxLot],
    within_days: int,
    as_of: Optional[date] = None,
) -> list[LotAging]:
    """
    Return short-term lots that turn long-term within *within_days*.

    Sorted by ascending ``days_until_long_term`` so the lots closest to the
    long-term boundary (the ones most worth holding) appear first.
    """
    ref = as_of or date.today()
    flagged = [
        a
        for a in (LotAging(lot=lot, as_of=ref) for lot in lots)
        if a.almost_long_term(within_days)
    ]
    return sorted(flagged, key=lambda a: a.days_until_long_term)


# ----------------------------------------------------------------------------
# Tax-aware trim selection
# ----------------------------------------------------------------------------

def select_trim_lots(
    lots: list[TaxLot],
    shares_to_trim: float,
    price: float,
    as_of: Optional[date] = None,
) -> list[tuple[TaxLot, float]]:
    """
    Choose which lots (and how many shares of each) to sell for a trim.

    Selection minimizes realized tax cost by preferring, in order:

        1. **Loss lots**  — harvest losses first (offset gains; no tax cost),
           deepest loss per share first.
        2. **Long-term gain lots** — taxed at the lower LTCG rate.
        3. **Short-term gain lots** — taxed at the higher ordinary rate; used
           only as a last resort, smallest gain per share first.

    Within the long-term gain bucket, lots with the smallest gain per share are
    sold first to minimize the realized gain. Almost-long-term short-term gain
    lots are pushed to the very end so a trim never needlessly clips a lot that
    is about to qualify for the lower rate.

    Args:
        lots:           Available lots for one security.
        shares_to_trim: Total shares the trim signal wants to sell (> 0).
        price:          Current market price used to classify gain vs loss.
        as_of:          Reference date for long-/short-term classification.

    Returns:
        Ordered list of ``(lot, shares_from_this_lot)`` pairs whose share counts
        sum to ``min(shares_to_trim, total_available_shares)``.
    """
    ref = as_of or date.today()

    def sort_key(lot: TaxLot) -> tuple:
        gain_per_share = price - lot.cost_basis_per_share
        is_loss = gain_per_share < 0
        long_term = lot.is_long_term(ref)
        # Bucket: 0 = loss (harvest first), 1 = long-term gain, 2 = short-term gain.
        if is_loss:
            bucket = 0
            # Deepest loss per share first (most negative -> sort ascending).
            inner = gain_per_share
        elif long_term:
            bucket = 1
            # Smallest gain per share first to minimize realized gain.
            inner = gain_per_share
        else:
            bucket = 2
            # Short-term gains last; among them, lots farthest from long-term
            # first (so almost-long-term lots are clipped last).
            inner = -lot.days_until_long_term(ref)
        return (bucket, inner)

    ordered = sorted(lots, key=sort_key)

    selection: list[tuple[TaxLot, float]] = []
    remaining = shares_to_trim
    for lot in ordered:
        if remaining <= 1e-9:
            break
        take = min(lot.shares, remaining)
        if take <= 1e-9:
            continue
        selection.append((lot, take))
        remaining -= take
    return selection


# ----------------------------------------------------------------------------
# Realized gain/loss report (FIFO matching)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class _OpenLot:
    buy_date: date
    shares: float
    cost_basis_per_share: float


def match_sells_fifo(
    buys: list[TaxLot],
    sells: list[tuple[date, float, float]],
) -> list[RealizedLot]:
    """
    Match sells against buy lots using FIFO and realize per-lot P/L.

    Args:
        buys:  Buy lots for one (account, ticker), any order; matched oldest
               buy_date first.
        sells: ``(sell_date, shares, proceeds_per_share)`` tuples (shares > 0).

    Returns:
        :class:`RealizedLot` records, one per matched buy fragment, in sell
        order. Sells exceeding available buy shares are matched only up to the
        available quantity (the excess is dropped, as the basis is unknown).
    """
    open_lots = [
        _OpenLot(b.buy_date, b.shares, b.cost_basis_per_share)
        for b in sorted(buys, key=lambda b: b.buy_date)
    ]
    ticker = buys[0].ticker if buys else ""
    account = buys[0].account if buys else ""

    realized: list[RealizedLot] = []
    idx = 0
    for sell_date, sell_shares, proceeds_ps in sorted(sells, key=lambda s: s[0]):
        remaining = sell_shares
        while remaining > 1e-9 and idx < len(open_lots):
            lot = open_lots[idx]
            if lot.shares <= 1e-9:
                idx += 1
                continue
            take = min(lot.shares, remaining)
            realized.append(
                RealizedLot(
                    ticker=ticker,
                    account=account,
                    buy_date=lot.buy_date,
                    sell_date=sell_date,
                    shares=take,
                    cost_basis_per_share=lot.cost_basis_per_share,
                    proceeds_per_share=proceeds_ps,
                )
            )
            open_lots[idx] = _OpenLot(
                lot.buy_date, lot.shares - take, lot.cost_basis_per_share
            )
            remaining -= take
    return realized


def realized_report(
    realized_lots: list[RealizedLot],
) -> list[YearlyRealizedSummary]:
    """
    Aggregate realized lots into per-tax-year short-/long-term summaries.

    Args:
        realized_lots: Output of :func:`match_sells_fifo` (may span tickers).

    Returns:
        One :class:`YearlyRealizedSummary` per sell-year, ascending by year.
    """
    by_year: dict[int, list[RealizedLot]] = {}
    for rl in realized_lots:
        by_year.setdefault(rl.sell_date.year, []).append(rl)

    summaries: list[YearlyRealizedSummary] = []
    for year in sorted(by_year):
        year_lots = by_year[year]
        st_gain = sum(rl.realized_gain for rl in year_lots if not rl.is_long_term)
        lt_gain = sum(rl.realized_gain for rl in year_lots if rl.is_long_term)
        st_proceeds = sum(
            rl.proceeds_per_share * rl.shares for rl in year_lots if not rl.is_long_term
        )
        lt_proceeds = sum(
            rl.proceeds_per_share * rl.shares for rl in year_lots if rl.is_long_term
        )
        summaries.append(
            YearlyRealizedSummary(
                year=year,
                short_term_gain=st_gain,
                long_term_gain=lt_gain,
                short_term_proceeds=st_proceeds,
                long_term_proceeds=lt_proceeds,
                lots=year_lots,
            )
        )
    return summaries
