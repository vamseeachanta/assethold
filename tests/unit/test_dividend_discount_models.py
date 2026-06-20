# ABOUTME: Unit tests for dividend-discount valuation models (WRK-1198 / issue #17).
# ABOUTME: Tests Gordon (direct form), H-model, and multi-stage DDM against textbook values.

import pytest
from assethold.dividend_forecast import (
    gordon_growth_value,
    h_model_value,
    multi_stage_ddm,
)


class TestGordonGrowthValue:
    def test_textbook_value(self):
        # D1=2, r=0.10, g=0.05 -> 2 / (0.10 - 0.05) = 40.00
        assert gordon_growth_value(2.0, 0.10, 0.05) == pytest.approx(40.0)

    def test_zero_growth(self):
        # Perpetuity: D1=5, r=0.08, g=0 -> 5 / 0.08 = 62.5
        assert gordon_growth_value(5.0, 0.08, 0.0) == pytest.approx(62.5)

    def test_return_equals_growth_raises(self):
        with pytest.raises(ValueError, match="required return"):
            gordon_growth_value(2.0, 0.05, 0.05)

    def test_return_below_growth_raises(self):
        with pytest.raises(ValueError, match="required return"):
            gordon_growth_value(2.0, 0.04, 0.06)


class TestHModelValue:
    def test_textbook_value(self):
        # D0=2, r=0.10, g_long=0.05, g_short=0.15, H=5
        # stable = 2 * 1.05 = 2.10
        # excess = 2 * 5 * (0.15 - 0.05) = 1.00
        # (2.10 + 1.00) / (0.10 - 0.05) = 3.10 / 0.05 = 62.00
        assert h_model_value(2.0, 0.10, 0.05, 0.15, 5.0) == pytest.approx(62.0)

    def test_no_excess_growth_reduces_to_gordon(self):
        # g_short == g_long -> excess term vanishes; equals Gordon on D0*(1+g).
        h = h_model_value(2.0, 0.10, 0.05, 0.05, 5.0)
        gordon = gordon_growth_value(2.0 * 1.05, 0.10, 0.05)
        assert h == pytest.approx(gordon)
        assert h == pytest.approx(42.0)

    def test_return_below_long_growth_raises(self):
        with pytest.raises(ValueError, match="required return"):
            h_model_value(2.0, 0.04, 0.05, 0.15, 5.0)

    def test_negative_half_life_raises(self):
        with pytest.raises(ValueError, match="half_life_years"):
            h_model_value(2.0, 0.10, 0.05, 0.15, -1.0)


class TestMultiStageDDM:
    def test_textbook_value(self):
        # D0=1, stage (g=0.10, 2yr), terminal_g=0.04, r=0.10
        # D1=1.10 PV=1.00 ; D2=1.21 PV=1.00
        # TV@2 = 1.21*1.04/(0.10-0.04) = 1.2584/0.06 = 20.973333...
        # PV(TV) = 20.973333.../1.21 = 17.333333...
        # total = 1.00 + 1.00 + 17.333333... = 19.333333...
        value = multi_stage_ddm(1.0, [(0.10, 2)], 0.04, 0.10)
        assert value == pytest.approx(19.33333333, abs=1e-6)

    def test_single_stage_one_year_matches_manual(self):
        # D0=1, stage (g=0.05, 1yr), terminal_g=0.03, r=0.08
        # D1 = 1.05 ; PV(D1) = 1.05/1.08
        # TV@1 = 1.05*1.03/(0.08-0.03) = 1.0815/0.05 = 21.63
        # PV(TV) = 21.63/1.08
        expected = 1.05 / 1.08 + (1.05 * 1.03 / 0.05) / 1.08
        assert multi_stage_ddm(1.0, [(0.05, 1)], 0.03, 0.08) == pytest.approx(
            expected
        )

    def test_two_stages_compose(self):
        # Two explicit stages: dividend grown sequentially across stages.
        value = multi_stage_ddm(
            2.0, [(0.20, 3), (0.10, 2)], 0.04, 0.12
        )
        # Reconstruct PV independently.
        r = 0.12
        divs = []
        d = 2.0
        for g, n in [(0.20, 3), (0.10, 2)]:
            for _ in range(n):
                d *= 1 + g
                divs.append(d)
        pv = sum(div / (1 + r) ** (t + 1) for t, div in enumerate(divs))
        tv = divs[-1] * 1.04 / (r - 0.04)
        pv += tv / (1 + r) ** len(divs)
        assert value == pytest.approx(pv)

    def test_empty_stages_raises(self):
        with pytest.raises(ValueError, match="at least one growth stage"):
            multi_stage_ddm(1.0, [], 0.04, 0.10)

    def test_return_below_terminal_raises(self):
        with pytest.raises(ValueError, match="required return"):
            multi_stage_ddm(1.0, [(0.10, 2)], 0.10, 0.08)

    def test_stage_with_zero_years_raises(self):
        with pytest.raises(ValueError, match="at least 1 year"):
            multi_stage_ddm(1.0, [(0.10, 0)], 0.04, 0.10)
