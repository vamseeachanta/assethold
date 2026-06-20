# ABOUTME: Unit tests for the multifamily financial stress-test engine (issue #36 item e).
# ABOUTME: Checks base-cell reproduces unstressed metrics, stressed cells move the expected way, and matrix dims.

import pytest

from assethold.modules.multifamily.multifamily_analysis import MultiFamily
from assethold.modules.multifamily.multifamily_stress import (
    SENSITIVITY_PARAMETERS,
    get_sensitivity_arrays,
    run_stress_tests,
)


# ---------------------------------------------------------------------------
# Reference: the unstressed metrics from the bundled YAML, computed via the
# existing pipeline (the stress engine must reproduce these at the zero cell).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def base_metrics():
    mf = MultiFamily()
    config = mf.get_config_data("multifamily_2.yaml")
    config = mf.add_missing_inputs(config)
    config = mf.get_metrics(config)
    project = config["projects"][0]
    return {
        "irr": project["cash_flow"]["irr"],
        "equity_multiple": project["cash_flow"]["equity_multiple"],
        "dscr": project["finance"]["loan"]["dscr"],
    }


@pytest.fixture(scope="module")
def grid_result():
    return run_stress_tests("multifamily_2.yaml", mode="grid")


@pytest.fixture(scope="module")
def one_way_result():
    return run_stress_tests("multifamily_2.yaml", mode="one_way")


# ---------------------------------------------------------------------------
# Base case: the unstressed (all-zero) cell reproduces the pipeline metrics
# ---------------------------------------------------------------------------

class TestBaseCaseReproduction:
    def test_result_base_matches_pipeline(self, grid_result, base_metrics):
        assert grid_result["base"]["irr"] == pytest.approx(base_metrics["irr"])
        assert grid_result["base"]["equity_multiple"] == pytest.approx(
            base_metrics["equity_multiple"])
        assert grid_result["base"]["dscr"] == pytest.approx(base_metrics["dscr"])

    def test_known_base_values(self, base_metrics):
        # Sanity anchor on the bundled config (regression guard).
        assert base_metrics["irr"] == pytest.approx(11.2174)
        assert base_metrics["equity_multiple"] == pytest.approx(2.5794)
        assert base_metrics["dscr"] == pytest.approx(1.42)

    def test_grid_zero_cell_reproduces_unstressed(self, grid_result, base_metrics):
        order = grid_result["parameter_order"]
        zero_cells = [
            row for row in grid_result["rows"]
            if all(row[k] == 0 for k in order)
        ]
        assert len(zero_cells) == 1
        cell = zero_cells[0]
        assert cell["irr"] == pytest.approx(base_metrics["irr"])
        assert cell["equity_multiple"] == pytest.approx(base_metrics["equity_multiple"])
        assert cell["dscr"] == pytest.approx(base_metrics["dscr"])


# ---------------------------------------------------------------------------
# Directionality: stressed cells move the expected way
# ---------------------------------------------------------------------------

class TestStressDirectionality:
    def _one_way(self, one_way_result, param):
        return sorted(
            (r for r in one_way_result["rows"] if r["parameter"] == param),
            key=lambda r: r["percent_change"],
        )

    def test_higher_exit_cap_lowers_irr(self, one_way_result):
        rows = self._one_way(one_way_result, "exit_cap_rate")
        irrs = [r["irr"] for r in rows]
        # exit cap sweeps -20, 0, +20 -> IRR strictly decreasing
        assert irrs == sorted(irrs, reverse=True)
        assert irrs[0] > irrs[-1]

    def test_higher_operating_expenses_lowers_irr(self, one_way_result):
        rows = self._one_way(one_way_result, "entry_Operating_Expenses")
        irrs = [r["irr"] for r in rows]
        assert irrs == sorted(irrs, reverse=True)

    def test_higher_renovation_costs_lowers_irr(self, one_way_result):
        rows = self._one_way(one_way_result, "entry_Renovation_Costs")
        irrs = [r["irr"] for r in rows]
        # reno sweeps 0, 50, 100 (% increase) -> more spend, lower IRR
        assert irrs == sorted(irrs, reverse=True)

    def test_higher_exit_cap_lowers_equity_multiple(self, one_way_result):
        rows = self._one_way(one_way_result, "exit_cap_rate")
        ems = [r["equity_multiple"] for r in rows]
        assert ems == sorted(ems, reverse=True)


# ---------------------------------------------------------------------------
# Matrix shape / structure
# ---------------------------------------------------------------------------

class TestMatrixShape:
    def test_shape_matches_array_dims(self, grid_result):
        # finance_Loan_r is empty in the YAML -> excluded; the other four
        # arrays are [5], [3], [2], [3].
        assert grid_result["shape"] == (5, 3, 2, 3)

    def test_row_count_is_product_of_dims(self, grid_result):
        expected = 5 * 3 * 2 * 3
        assert len(grid_result["rows"]) == expected

    def test_empty_arrays_excluded(self, grid_result):
        # finance_Loan_r has an empty list in the config and must not appear.
        assert "finance_Loan_r" not in grid_result["parameter_order"]
        assert "finance_Loan_r" not in grid_result["parameters"]

    def test_parameters_consumed_from_config(self, grid_result):
        for key in grid_result["parameter_order"]:
            assert key in SENSITIVITY_PARAMETERS

    def test_each_row_has_metrics(self, grid_result):
        for row in grid_result["rows"]:
            assert set(row) >= {"irr", "equity_multiple", "dscr"}

    def test_one_way_row_count(self, one_way_result):
        # one row per (parameter, percent) across the four non-empty arrays.
        assert len(one_way_result["rows"]) == 5 + 3 + 2 + 3


# ---------------------------------------------------------------------------
# Array extraction helper
# ---------------------------------------------------------------------------

class TestSensitivityArrays:
    def test_reads_config_arrays(self):
        mf = MultiFamily()
        config = mf.get_config_data("multifamily_2.yaml")
        arrays = get_sensitivity_arrays(config["projects"][0])
        assert arrays["entry_Operating_Expenses"] == [-20, -10, 0, 10, 20]
        assert arrays["entry_Renovation_Costs"] == [0, 50, 100]
        assert arrays["exit_cap_rate"] == [-20, 0, 20]
        assert "finance_Loan_r" not in arrays
