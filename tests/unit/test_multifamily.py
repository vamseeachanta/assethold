# ABOUTME: Unit tests for the multifamily real-estate analysis model.
# ABOUTME: Covers income/expense/NOI math, loan metrics, partnership waterfall, and end-to-end YAML run.

import copy

import numpy_financial as npf
import pytest

from assethold.modules.multifamily.multifamily_analysis import (
    MultiFamily,
    MultiFamilyCharts,
)


# ---------------------------------------------------------------------------
# Synthetic config builders (minimal dicts wired for each unit method)
# ---------------------------------------------------------------------------

def _project_stub(hold_years: int = 10) -> dict:
    return {
        "Name": "unit-test",
        "hold_years": hold_years,
        "rent_growth_rate": 0,
        "expense_growth_rate": 0,
        "entry": {
            "total_units": 10,
            "average_rent_per_unit": 1000,
            "other_income_per_month": {"parking": 0, "laundry": 0},
            "expenses_breakdown": {
                "personnel": {"per_unit_per_year": 0},
                "general_and_administration": {"per_unit_per_year": 0},
                "marketing": {"per_unit_per_year": 0},
                "turnover": {"per_unit_per_year": 0},
                "repair_and_maintenance": {"per_unit_per_year": 0},
                "contract_servies": {"per_unit_per_year": 0},
                "utilities": {
                    "per_unit_per_year": 0,
                    "reimbursments_per_unit_per_year": 0,
                },
                "property_taxes": {"per_unit_per_year": 0},
                "insurance": {"per_unit_per_year": 0},
                "capital_expense_reserve": {"per_unit_per_year": 0},
            },
        },
        "other_income": [],
        "expenses": [],
        "GPR": [],
        "vacancy": {"amount": [], "percent": 0},
        "NOI": {"amount": []},
        "property_management_fee": {"amount": [], "percent_of_EGR": 0},
    }


def _config_with(project: dict) -> dict:
    return {"projects": [project]}


# ---------------------------------------------------------------------------
# Average rent / GPR
# ---------------------------------------------------------------------------

class TestAverageRentPerUnit:
    def test_weighted_average_from_unit_mix(self):
        project = _project_stub()
        project["entry"]["average_rent_per_unit"] = None
        project["unit_mix"] = [
            {"number": 10, "rent": 1000},
            {"number": 30, "rent": 2000},
        ]
        config = _config_with(project)

        MultiFamily().add_average_rent_per_unit(config)

        # (10*1000 + 30*2000) / 40 = 1750
        assert project["entry"]["average_rent_per_unit"] == pytest.approx(1750.0)
        assert project["entry"]["total_units"] == 40

    def test_noop_when_already_set(self):
        project = _project_stub()
        project["entry"]["average_rent_per_unit"] = 1234
        project["unit_mix"] = [{"number": 1, "rent": 9999}]
        config = _config_with(project)

        MultiFamily().add_average_rent_per_unit(config)

        assert project["entry"]["average_rent_per_unit"] == 1234


class TestGPR:
    def test_first_year_is_units_times_rent_times_12(self):
        project = _project_stub()
        project["entry"]["total_units"] = 100
        project["entry"]["average_rent_per_unit"] = 1500
        config = _config_with(project)

        MultiFamily().add_GPR(config)

        # 100 units × $1,500/month × 12 months
        assert project["GPR"][0] == pytest.approx(1_800_000)

    def test_growth_rate_compounds_across_hold_years(self):
        project = _project_stub(hold_years=3)
        project["entry"]["total_units"] = 10
        project["entry"]["average_rent_per_unit"] = 1000
        project["rent_growth_rate"] = 5  # percent
        config = _config_with(project)

        MultiFamily().add_GPR(config)

        # 11 entries: year-0 + 3 hold years. Wait — hold_years=3 yields 4 entries.
        assert len(project["GPR"]) == 4
        assert project["GPR"][0] == pytest.approx(120_000)  # 10*1000*12
        assert project["GPR"][1] == pytest.approx(round(120_000 * 1.05, 0))
        assert project["GPR"][3] == pytest.approx(round(120_000 * 1.05 ** 3, 0))


# ---------------------------------------------------------------------------
# Other income / expenses / vacancy / property management
# ---------------------------------------------------------------------------

class TestOtherIncome:
    def test_annualized_per_unit_income(self):
        project = _project_stub()
        project["entry"]["total_units"] = 100
        project["entry"]["other_income_per_month"] = {"parking": 40, "laundry": 10}
        config = _config_with(project)

        MultiFamily().add_other_income(config)

        # (40+10) * 100 units * 12 months = 60,000 first year
        assert project["other_income"][0] == pytest.approx(60_000)

    def test_growth_applied_year_over_year(self):
        project = _project_stub(hold_years=2)
        project["entry"]["total_units"] = 10
        project["entry"]["other_income_per_month"] = {"parking": 100}
        project["rent_growth_rate"] = 10
        config = _config_with(project)

        MultiFamily().add_other_income(config)

        base = 100 * 10 * 12
        assert project["other_income"][0] == pytest.approx(round(base, 0))
        assert project["other_income"][1] == pytest.approx(round(base * 1.10, 0))
        assert project["other_income"][2] == pytest.approx(round(base * 1.10 ** 2, 0))


class TestExpenses:
    def test_sum_of_all_expense_categories_is_negative(self):
        project = _project_stub()
        project["entry"]["total_units"] = 10
        breakdown = project["entry"]["expenses_breakdown"]
        # 10 per-unit-per-year slots at $100 each → $1,000/unit × 10 units = $10,000
        # (utilities.reimbursments stays 0, so the reimbursement slot does not add.)
        for key in breakdown:
            breakdown[key]["per_unit_per_year"] = 100
        config = _config_with(project)

        MultiFamily().add_expenses(config)

        assert project["expenses"][0] == pytest.approx(-10_000)

    def test_utility_reimbursements_net_against_utilities(self):
        project = _project_stub()
        project["entry"]["total_units"] = 5
        project["entry"]["expenses_breakdown"]["utilities"] = {
            "per_unit_per_year": 800,
            "reimbursments_per_unit_per_year": -200,  # reimbursement reduces cost
        }
        config = _config_with(project)

        MultiFamily().add_expenses(config)

        # net utilities = 600 per unit × 5 = 3000 (negative)
        assert project["expenses"][0] == pytest.approx(-3_000)


class TestVacancy:
    def test_vacancy_is_negative_percentage_of_GPR_plus_other_income(self):
        project = _project_stub(hold_years=1)
        project["GPR"] = [1_000_000, 1_050_000]
        project["other_income"] = [100_000, 110_000]
        project["vacancy"]["percent"] = 5
        config = _config_with(project)

        MultiFamily().add_vacancy(config)

        # (1,000,000 + 100,000) * -5% = -55,000
        assert project["vacancy"]["amount"][0] == pytest.approx(-55_000)
        assert project["vacancy"]["amount"][1] == pytest.approx(-58_000)


class TestPropertyManagement:
    def test_pm_fee_based_on_effective_gross_revenue(self):
        project = _project_stub(hold_years=0)
        project["GPR"] = [1_000_000]
        project["other_income"] = [100_000]
        project["vacancy"]["amount"] = [-55_000]
        project["property_management_fee"]["percent_of_EGR"] = 3
        config = _config_with(project)

        MultiFamily().add_property_management(config)

        # EGR = 1,000,000 + 100,000 - 55,000 = 1,045,000 → -3% = -31,350
        assert project["property_management_fee"]["amount"][0] == pytest.approx(-31_350)


# ---------------------------------------------------------------------------
# NOI
# ---------------------------------------------------------------------------

class TestNOI:
    def test_noi_sums_revenue_and_expense_components(self):
        project = _project_stub(hold_years=0)
        project["entry"]["Cap_Rate"] = None
        project["GPR"] = [1_000_000]
        project["other_income"] = [50_000]
        project["vacancy"]["amount"] = [-55_000]
        project["expenses"] = [-400_000]
        project["property_management_fee"]["amount"] = [-30_000]
        config = _config_with(project)

        MultiFamily().add_NOI(config)

        assert project["NOI"]["amount"][0] == pytest.approx(565_000)

    def test_noi_from_cap_rate_when_provided(self):
        project = _project_stub(hold_years=2)
        project["entry"]["Purchase_Price"] = 10_000_000
        project["entry"]["Cap_Rate"] = 6  # 6%
        project["NOI"]["growth_rate"] = 3
        config = _config_with(project)

        MultiFamily().add_NOI(config)

        # Year 0: 10M × 6% = 600k; Year 1: 600k × 1.03; Year 2: × 1.03²
        assert project["NOI"]["amount"][0] == pytest.approx(600_000)
        assert project["NOI"]["amount"][1] == pytest.approx(round(600_000 * 1.03, 2))
        assert project["NOI"]["amount"][2] == pytest.approx(round(600_000 * 1.03 ** 2, 2))


# ---------------------------------------------------------------------------
# Loan mathematics
# ---------------------------------------------------------------------------

class TestLoanPayments:
    def test_annual_loan_payment_matches_npf(self):
        config = {
            "projects": [
                {
                    "finance": {
                        "loan": {
                            "Amount": 1_000_000,
                            "r": 6,
                            "Amortization": 30,
                            "annual_loan_payment": None,
                        }
                    }
                }
            ]
        }

        MultiFamily().add_annual_loan_payment(config)

        expected = -npf.pmt(0.06 / 12, 360, 1_000_000) * 12
        assert config["projects"][0]["finance"]["loan"][
            "annual_loan_payment"
        ] == pytest.approx(round(expected, 2))

    def test_annual_loan_payment_is_noop_when_already_set(self):
        config = {
            "projects": [
                {
                    "finance": {
                        "loan": {
                            "Amount": 1_000_000,
                            "r": 6,
                            "Amortization": 30,
                            "annual_loan_payment": 999,
                        }
                    }
                }
            ]
        }

        MultiFamily().add_annual_loan_payment(config)

        assert config["projects"][0]["finance"]["loan"]["annual_loan_payment"] == 999


class TestLoanMetrics:
    def _loan_project(self):
        return {
            "entry": {"Purchase_Price": 10_000_000},
            "finance": {
                "loan": {
                    "Amount": 7_500_000,
                    "annual_loan_payment": 500_000,
                }
            },
            "renovation_costs": [0] * 10,
            "exit": {"closing_cost_percentage": 2.5},
            "NOI": {"amount": [750_000]},
        }

    def test_ltv_is_loan_over_purchase_price(self):
        config = {"projects": [self._loan_project()]}

        MultiFamily().add_loan_metrics(config)

        assert config["projects"][0]["finance"]["loan"]["ltv"] == pytest.approx(75.0)

    def test_dscr_is_noi_over_debt_service(self):
        config = {"projects": [self._loan_project()]}

        MultiFamily().add_loan_metrics(config)

        # 750,000 / 500,000 = 1.5
        assert config["projects"][0]["finance"]["loan"]["dscr"] == pytest.approx(1.5)

    def test_debt_ratio_is_noi_over_loan(self):
        config = {"projects": [self._loan_project()]}

        MultiFamily().add_loan_metrics(config)

        # 750,000 / 7,500,000 = 10%
        assert config["projects"][0]["finance"]["loan"]["debt_ratio"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# End-to-end integration against the bundled YAML
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def computed_config():
    mf = MultiFamily()
    config = mf.get_config_data("multifamily_2.yaml")
    config = mf.add_missing_inputs(config)
    config = mf.get_metrics(config)
    return config


class TestIntegrationMultifamily2:
    def test_loads_bundled_yaml_without_filename(self):
        # get_config_data with no arg falls back to multifamily_2.yaml
        config = MultiFamily().get_config_data()
        assert "projects" in config
        assert len(config["projects"]) >= 1

    def test_populates_total_units_from_unit_mix(self, computed_config):
        project = computed_config["projects"][0]
        # 5 + 25 + 45 + 10 = 85 units
        assert project["entry"]["total_units"] == 85

    def test_computes_weighted_average_rent(self, computed_config):
        project = computed_config["projects"][0]
        avg = project["entry"]["average_rent_per_unit"]
        # All unit rents are between 925 and 1800, so the weighted avg must be in range
        assert 925 < avg < 1800

    def test_noi_series_has_hold_years_plus_one_entries(self, computed_config):
        project = computed_config["projects"][0]
        assert len(project["NOI"]["amount"]) == project["hold_years"] + 1

    def test_irr_is_computed_and_reasonable(self, computed_config):
        project = computed_config["projects"][0]
        irr = project["cash_flow"]["irr"]
        assert isinstance(irr, float)
        assert -50 < irr < 100  # rough sanity bound for a realistic real-estate deal

    def test_equity_multiple_is_positive(self, computed_config):
        project = computed_config["projects"][0]
        assert project["cash_flow"]["equity_multiple"] > 0

    def test_ltv_under_100(self, computed_config):
        project = computed_config["projects"][0]
        assert project["finance"]["loan"]["ltv"] < 100

    def test_gp_and_lp_receive_cash_flows(self, computed_config):
        equity = computed_config["projects"][0]["finance"]["equity"]
        assert len(equity["general_partner"]["cash_flow"]) > 0
        assert len(equity["limited_partner"]["cash_flow"]) > 0

    def test_gp_lp_equity_percents_sum_to_100(self, computed_config):
        equity = computed_config["projects"][0]["finance"]["equity"]
        total = (
            equity["general_partner"]["equity_percent"]
            + equity["limited_partner"]["equity_percent"]
        )
        assert total == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# MultiFamilyCharts data aggregation (no HTML I/O)
# ---------------------------------------------------------------------------

class TestMultiFamilyChartsData:
    def test_get_common_chart_data_populates_series(self, computed_config):
        charts = MultiFamilyCharts()
        charts.get_common_chart_data(outputs=[computed_config])

        assert charts.Name == [computed_config["projects"][0]["Name"]]
        assert len(charts.irr) == 1
        assert len(charts.equity_multiple) == 1
        assert charts.hold_years == [computed_config["projects"][0]["hold_years"]]

    def test_free_cash_flow_prefixed_with_zero(self, computed_config):
        charts = MultiFamilyCharts()
        charts.get_common_chart_data(outputs=[computed_config])
        # Leading 0 is injected so year-0 aligns with plot_years axis
        assert charts.free_cash_flow[0][0] == 0

    def test_plot_years_spans_max_hold_years(self, computed_config):
        charts = MultiFamilyCharts()
        charts.get_common_chart_data(outputs=[computed_config])
        assert charts.plot_years == list(
            range(1, max(charts.hold_years) + 1)
        )

    def test_multiple_projects_stacked_into_parallel_lists(self, computed_config):
        charts = MultiFamilyCharts()
        other = copy.deepcopy(computed_config)
        other["projects"][0]["Name"] = "clone"
        charts.get_common_chart_data(outputs=[computed_config, other])

        assert len(charts.Name) == 2
        assert charts.Name[1] == "clone"
        assert len(charts.irr) == 2
