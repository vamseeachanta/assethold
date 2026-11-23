# ABOUTME: Unit tests for fixed deposit interest calculator.
# ABOUTME: Tests simple/compound interest, rate comparison, and maturity laddering.

import pytest
from assethold.modules.fixed_interest.fd import (
    simple_interest,
    compound_interest,
    FixedDeposit,
    InterestResult,
    LadderRung,
)


class TestSimpleInterest:
    def test_basic_calculation(self):
        # $10,000 at 5% for 2 years = $1,000
        assert simple_interest(10000, 0.05, 2.0) == pytest.approx(1000.0)

    def test_one_year(self):
        assert simple_interest(1000, 0.10, 1.0) == pytest.approx(100.0)

    def test_partial_year(self):
        # 6 months = 0.5 years
        assert simple_interest(1000, 0.06, 0.5) == pytest.approx(30.0)

    def test_zero_principal(self):
        assert simple_interest(0, 0.05, 1.0) == 0.0

    def test_zero_rate(self):
        assert simple_interest(1000, 0.0, 5.0) == 0.0


class TestCompoundInterest:
    def test_annual_compounding(self):
        # $1000 at 10% for 2 years, annual compounding
        # CI = 1000 * (1 + 0.10)^2 - 1000 = 210
        result = compound_interest(1000, 0.10, 2.0, frequency=1)
        assert result == pytest.approx(210.0)

    def test_quarterly_compounding(self):
        # $10,000 at 5% for 1 year, quarterly
        # CI = 10000 * (1 + 0.05/4)^(4*1) - 10000
        expected = 10000 * ((1 + 0.05 / 4) ** 4 - 1)
        result = compound_interest(10000, 0.05, 1.0, frequency=4)
        assert result == pytest.approx(expected)

    def test_monthly_compounding(self):
        result = compound_interest(5000, 0.06, 3.0, frequency=12)
        expected = 5000 * ((1 + 0.06 / 12) ** (12 * 3) - 1)
        assert result == pytest.approx(expected)

    def test_compound_exceeds_simple(self):
        si = simple_interest(1000, 0.10, 5.0)
        ci = compound_interest(1000, 0.10, 5.0, frequency=4)
        assert ci > si

    def test_zero_principal(self):
        assert compound_interest(0, 0.05, 1.0) == 0.0


class TestFixedDeposit:
    def setup_method(self):
        self.fd = FixedDeposit()

    def test_calculate_interest_returns_result(self):
        result = self.fd.calculate_interest(10000, 0.05, 2.0)
        assert isinstance(result, InterestResult)
        assert result.principal == 10000
        assert result.annual_rate == 0.05
        assert result.time_years == 2.0

    def test_calculate_interest_totals(self):
        result = self.fd.calculate_interest(10000, 0.05, 2.0)
        assert result.simple_total == pytest.approx(result.principal + result.simple_interest)
        assert result.compound_total == pytest.approx(result.principal + result.compound_interest)
        assert result.compound_total > result.simple_total

    def test_compare_rates_ordering(self):
        rates = {
            "Bank A": 0.04,
            "Bank B": 0.06,
            "Bank C": 0.05,
        }
        results = self.fd.compare_rates(10000, 1.0, rates)
        assert len(results) == 3
        assert results[0]["bank"] == "Bank B"
        assert results[-1]["bank"] == "Bank A"

    def test_compare_rates_structure(self):
        rates = {"Test Bank": 0.05}
        results = self.fd.compare_rates(1000, 1.0, rates)
        assert results[0]["bank"] == "Test Bank"
        assert "compound_interest" in results[0]
        assert "compound_total" in results[0]
        assert results[0]["compound_total"] > 1000

    def test_maturity_ladder_count(self):
        ladder = self.fd.maturity_ladder(12000, rungs=4, annual_rate=0.05)
        assert len(ladder) == 4

    def test_maturity_ladder_equal_principal(self):
        ladder = self.fd.maturity_ladder(12000, rungs=4, annual_rate=0.05)
        for rung in ladder:
            assert rung.principal == pytest.approx(3000.0)

    def test_maturity_ladder_increasing_terms(self):
        ladder = self.fd.maturity_ladder(12000, rungs=4, annual_rate=0.05, base_term_months=3)
        terms = [r.term_months for r in ladder]
        assert terms == [3, 6, 9, 12]

    def test_maturity_ladder_increasing_interest(self):
        ladder = self.fd.maturity_ladder(12000, rungs=4, annual_rate=0.05)
        interests = [r.interest_earned for r in ladder]
        # Longer terms earn more interest
        assert all(interests[i] < interests[i + 1] for i in range(len(interests) - 1))

    def test_maturity_value_equals_principal_plus_interest(self):
        ladder = self.fd.maturity_ladder(10000, rungs=3, annual_rate=0.06)
        for rung in ladder:
            assert isinstance(rung, LadderRung)
            assert rung.maturity_value == pytest.approx(rung.principal + rung.interest_earned)


class TestMaturityValue:
    def setup_method(self):
        self.fd = FixedDeposit()

    def test_compound_textbook_value(self):
        # Textbook: P=1000, r=0.05, t=2, n=1 -> A = 1000*(1.05)^2 = 1102.50
        mv = self.fd.maturity_value(1000, 0.05, 2.0, method="compound", compounding_frequency=1)
        assert mv == pytest.approx(1102.50)

    def test_simple_textbook_value(self):
        # Textbook simple: P=1000, r=0.10, t=1 -> I=100 -> A = 1100
        mv = self.fd.maturity_value(1000, 0.10, 1.0, method="simple")
        assert mv == pytest.approx(1100.0)

    def test_simple_matches_helper(self):
        mv = self.fd.maturity_value(5000, 0.04, 3.0, method="simple")
        assert mv == pytest.approx(5000 + simple_interest(5000, 0.04, 3.0))

    def test_compound_matches_calculate_interest(self):
        mv = self.fd.maturity_value(10000, 0.05, 2.0, method="compound", compounding_frequency=4)
        result = self.fd.calculate_interest(10000, 0.05, 2.0, compounding_frequency=4)
        assert mv == pytest.approx(result.compound_total)

    def test_compound_exceeds_simple_maturity(self):
        compound = self.fd.maturity_value(1000, 0.10, 5.0, method="compound", compounding_frequency=4)
        simple = self.fd.maturity_value(1000, 0.10, 5.0, method="simple")
        assert compound > simple

    def test_invalid_method_raises(self):
        with pytest.raises(ValueError):
            self.fd.maturity_value(1000, 0.05, 1.0, method="continuous")
