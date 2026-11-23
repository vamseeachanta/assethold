# ABOUTME: Fixed deposit interest calculator — simple/compound interest, maturity laddering.
# ABOUTME: Compares FD rates across banks and computes optimal maturity schedules.
"""
Fixed deposit interest calculator.

Provides simple and compound interest calculations for fixed deposits,
maturity ladder scheduling for liquidity optimization, and multi-bank
rate comparison utilities.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InterestResult:
    """Result of an interest calculation."""

    principal: float
    annual_rate: float
    time_years: float
    simple_interest: float
    compound_interest: float
    simple_total: float
    compound_total: float
    compounding_frequency: int


@dataclass
class LadderRung:
    """A single rung in a maturity ladder."""

    principal: float
    annual_rate: float
    term_months: int
    maturity_value: float
    interest_earned: float


def simple_interest(
    principal: float,
    annual_rate: float,
    time_years: float,
) -> float:
    """Compute simple interest: I = P * r * t.

    Args:
        principal: Initial deposit amount.
        annual_rate: Annual interest rate as a decimal (e.g. 0.05 for 5%).
        time_years: Duration in years.

    Returns:
        Interest earned (not including principal).
    """
    return principal * annual_rate * time_years


def compound_interest(
    principal: float,
    annual_rate: float,
    time_years: float,
    frequency: int = 4,
) -> float:
    """Compute compound interest: I = P * (1 + r/n)^(n*t) - P.

    Args:
        principal: Initial deposit amount.
        annual_rate: Annual interest rate as a decimal.
        time_years: Duration in years.
        frequency: Compounding periods per year (default: 4 = quarterly).

    Returns:
        Interest earned (not including principal).
    """
    return principal * ((1 + annual_rate / frequency) ** (frequency * time_years) - 1)


class FixedDeposit:
    """Fixed deposit interest calculator with comparison and laddering."""

    def calculate_interest(
        self,
        principal: float,
        annual_rate: float,
        time_years: float,
        compounding_frequency: int = 4,
    ) -> InterestResult:
        """Calculate both simple and compound interest for a fixed deposit.

        Args:
            principal: Deposit amount.
            annual_rate: Annual rate as decimal (e.g. 0.05 for 5%).
            time_years: Duration in years.
            compounding_frequency: Compounding periods per year.

        Returns:
            InterestResult with both simple and compound calculations.
        """
        si = simple_interest(principal, annual_rate, time_years)
        ci = compound_interest(principal, annual_rate, time_years, compounding_frequency)

        return InterestResult(
            principal=principal,
            annual_rate=annual_rate,
            time_years=time_years,
            simple_interest=si,
            compound_interest=ci,
            simple_total=principal + si,
            compound_total=principal + ci,
            compounding_frequency=compounding_frequency,
        )

    def maturity_value(
        self,
        principal: float,
        annual_rate: float,
        time_years: float,
        method: str = "compound",
        compounding_frequency: int = 4,
    ) -> float:
        """Compute the maturity (future) value of a fixed deposit.

        For ``method="simple"`` the maturity value is ``P + P*r*t``.
        For ``method="compound"`` it is the standard future-value formula
        ``A = P * (1 + r/n)^(n*t)``.

        Args:
            principal: Initial deposit amount.
            annual_rate: Annual interest rate as a decimal (e.g. 0.05 for 5%).
            time_years: Duration in years.
            method: Either ``"simple"`` or ``"compound"`` (default).
            compounding_frequency: Compounding periods per year (compound only).

        Returns:
            Maturity value (principal + interest earned).

        Raises:
            ValueError: If ``method`` is not ``"simple"`` or ``"compound"``.
        """
        if method == "simple":
            return principal + simple_interest(principal, annual_rate, time_years)
        if method == "compound":
            return principal + compound_interest(
                principal, annual_rate, time_years, compounding_frequency
            )
        raise ValueError(
            f"method must be 'simple' or 'compound', got {method!r}"
        )

    def compare_rates(
        self,
        principal: float,
        time_years: float,
        rates: dict[str, float],
        compounding_frequency: int = 4,
    ) -> list[dict]:
        """Compare fixed deposit returns across multiple banks/institutions.

        Args:
            principal: Deposit amount.
            time_years: Duration in years.
            rates: Dict mapping bank name to annual rate (decimal).
            compounding_frequency: Compounding periods per year.

        Returns:
            List of dicts sorted by compound total descending, each with
            keys: bank, annual_rate, compound_interest, compound_total.
        """
        results = []
        for bank, rate in rates.items():
            ci = compound_interest(principal, rate, time_years, compounding_frequency)
            results.append({
                "bank": bank,
                "annual_rate": rate,
                "compound_interest": ci,
                "compound_total": principal + ci,
            })
        results.sort(key=lambda r: r["compound_total"], reverse=True)
        return results

    def maturity_ladder(
        self,
        total_principal: float,
        rungs: int,
        annual_rate: float,
        base_term_months: int = 3,
        compounding_frequency: int = 4,
    ) -> list[LadderRung]:
        """Build a maturity ladder splitting principal across staggered terms.

        Each rung gets an equal share of the principal but matures at
        increasingly longer intervals (base_term_months * rung_number).

        Args:
            total_principal: Total amount to invest.
            rungs: Number of ladder rungs.
            annual_rate: Annual rate applied to all rungs.
            base_term_months: Shortest rung term in months.
            compounding_frequency: Compounding periods per year.

        Returns:
            List of LadderRung objects ordered by maturity date.
        """
        per_rung = total_principal / rungs
        ladder = []
        for i in range(1, rungs + 1):
            term_months = base_term_months * i
            time_years = term_months / 12.0
            ci = compound_interest(per_rung, annual_rate, time_years, compounding_frequency)
            ladder.append(LadderRung(
                principal=per_rung,
                annual_rate=annual_rate,
                term_months=term_months,
                maturity_value=per_rung + ci,
                interest_earned=ci,
            ))
        return ladder
