# ABOUTME: Financial stress-test / sensitivity engine for the multifamily model (issue #36 item e).
# ABOUTME: Sweeps the percent-change arrays under `sensitivity:` in multifamily_2.yaml and re-runs the
# ABOUTME: existing underwriting pipeline to tabulate stressed IRR / equity-multiple / DSCR.

import copy
import itertools

from assethold.modules.multifamily.multifamily_analysis import MultiFamily


# Mapping from the sensitivity-array key in the YAML config to the raw input it
# perturbs. Each entry describes how a percent-change value is applied to the
# *raw* project inputs that `add_missing_inputs` / `get_metrics` derive from, so
# the existing underwriting math is reused verbatim (nothing is re-implemented).
#
# All sensitivity values are percent changes: a value `d` scales the base input
# by `(1 + d/100)`.
SENSITIVITY_PARAMETERS = {
    # Operating expenses: scale every per-unit-per-year line in the expense
    # breakdown. add_expenses() sums these, so scaling them scales total opex.
    "entry_Operating_Expenses": {
        "label": "Operating Expenses",
        "kind": "operating_expenses",
    },
    # Renovation costs: scale the lump-sum renovation amount that
    # add_renovation_costs() spreads over the hold period.
    "entry_Renovation_Costs": {
        "label": "Renovation Costs",
        "kind": "renovation_costs",
    },
    # Loan interest rate: scale the annual loan rate `r`.
    "finance_Loan_r": {
        "label": "Loan Interest Rate",
        "kind": "loan_rate",
    },
    # NOI growth: in this config NOI is built from GPR/other-income/expenses
    # (entry Cap_Rate is NULL), so the growth driver is rent_growth_rate.
    "entry_NOI_growth_rate": {
        "label": "NOI Growth Rate",
        "kind": "noi_growth_rate",
    },
    # Exit cap rate: scale the disposition cap rate used for sale proceeds.
    "exit_cap_rate": {
        "label": "Exit Cap Rate",
        "kind": "exit_cap_rate",
    },
}


def _apply_percent_change(project, kind, percent):
    """Apply a percent change to the raw inputs of a (deep-copied) project.

    The project must be an unprocessed raw project dict (derived lists such as
    GPR / NOI / cash_flow still empty) so the pipeline recomputes everything.
    """
    factor = 1 + percent / 100.0

    if kind == "operating_expenses":
        breakdown = project["entry"]["expenses_breakdown"]
        for category, fields in breakdown.items():
            if not isinstance(fields, dict):
                continue
            for field_name, value in fields.items():
                # `growth_rate` is a rate, not an expense level (issue #36 item b),
                # so an "operating expenses ±X%" stress must not rescale it.
                if field_name == "growth_rate":
                    continue
                if isinstance(value, (int, float)):
                    fields[field_name] = value * factor

    elif kind == "renovation_costs":
        project["entry"]["renovation_costs"]["amount"] = (
            project["entry"]["renovation_costs"]["amount"] * factor
        )

    elif kind == "loan_rate":
        project["finance"]["loan"]["r"] = project["finance"]["loan"]["r"] * factor

    elif kind == "noi_growth_rate":
        project["rent_growth_rate"] = project["rent_growth_rate"] * factor

    elif kind == "exit_cap_rate":
        project["exit"]["Cap_Rate"] = project["exit"]["Cap_Rate"] * factor

    else:  # pragma: no cover - guarded by SENSITIVITY_PARAMETERS keys
        raise ValueError(f"Unknown sensitivity kind: {kind}")


def _compute_metrics_for_project(raw_project):
    """Run the full underwriting pipeline on a single raw project and return
    its IRR / equity-multiple / DSCR. Reuses the existing MultiFamily methods."""
    mf = MultiFamily()
    config = {"projects": [copy.deepcopy(raw_project)]}
    config = mf.add_missing_inputs(config)
    config = mf.get_metrics(config)
    project = config["projects"][0]
    return {
        "irr": project["cash_flow"]["irr"],
        "equity_multiple": project["cash_flow"]["equity_multiple"],
        "dscr": project["finance"]["loan"]["dscr"],
    }


def get_sensitivity_arrays(project):
    """Return the {parameter_key: [percent, ...]} sensitivity arrays from the
    project config, restricted to known/non-empty parameters."""
    sensitivity = project.get("sensitivity", {}) or {}
    arrays = {}
    for key, deltas in sensitivity.items():
        if key not in SENSITIVITY_PARAMETERS:
            continue
        if not deltas:
            continue
        arrays[key] = list(deltas)
    return arrays


def run_one_way_sensitivity(raw_project):
    """One-way (tornado) sensitivity: vary each parameter independently while
    holding the others at base, sweeping each parameter's percent-change array.

    Returns a list of result rows (dicts) suitable for a report table::

        {parameter, label, percent_change, irr, equity_multiple, dscr}
    """
    raw_project = copy.deepcopy(raw_project)
    arrays = get_sensitivity_arrays(raw_project)
    rows = []
    for key, deltas in arrays.items():
        label = SENSITIVITY_PARAMETERS[key]["label"]
        kind = SENSITIVITY_PARAMETERS[key]["kind"]
        for percent in deltas:
            stressed = copy.deepcopy(raw_project)
            _apply_percent_change(stressed, kind, percent)
            metrics = _compute_metrics_for_project(stressed)
            rows.append({
                "parameter": key,
                "label": label,
                "percent_change": percent,
                **metrics,
            })
    return rows


def run_stress_tests(config_filename="multifamily_2.yaml", project_index=0,
                     mode="grid"):
    """Run financial stress tests for a multifamily project (issue #36 item e).

    Consumes the percent-change arrays under the project's ``sensitivity:`` block
    in the YAML config and re-runs the existing underwriting pipeline for each
    parameter combination, producing a stressed IRR / equity-multiple / DSCR
    matrix.

    Parameters
    ----------
    config_filename : str
        YAML config to load (resolved relative to the module dir if not found).
    project_index : int
        Which project in the config to stress-test.
    mode : {"grid", "one_way"}
        ``"grid"`` sweeps the full Cartesian product of all sensitivity arrays
        (combined stress). ``"one_way"`` varies one parameter at a time (tornado).

    Returns
    -------
    dict
        {
          "base": {irr, equity_multiple, dscr},          # unstressed metrics
          "parameters": {key: [percent, ...]},           # arrays consumed
          "parameter_order": [key, ...],                  # column order for grid
          "shape": (n0, n1, ...),                          # dims of the grid
          "rows": [ {<deltas...>, irr, equity_multiple, dscr}, ... ],
          "mode": mode,
        }
    """
    mf = MultiFamily()
    config = mf.get_config_data(config_filename)
    raw_project = copy.deepcopy(config["projects"][project_index])

    base = _compute_metrics_for_project(raw_project)
    arrays = get_sensitivity_arrays(raw_project)
    parameter_order = list(arrays.keys())

    result = {
        "base": base,
        "parameters": arrays,
        "parameter_order": parameter_order,
        "mode": mode,
    }

    if mode == "one_way":
        result["rows"] = run_one_way_sensitivity(raw_project)
        result["shape"] = (sum(len(v) for v in arrays.values()),)
        return result

    # mode == "grid": full Cartesian product of the percent-change arrays
    shape = tuple(len(arrays[k]) for k in parameter_order)
    result["shape"] = shape

    rows = []
    delta_lists = [arrays[k] for k in parameter_order]
    for combo in itertools.product(*delta_lists):
        stressed = copy.deepcopy(raw_project)
        for key, percent in zip(parameter_order, combo):
            kind = SENSITIVITY_PARAMETERS[key]["kind"]
            _apply_percent_change(stressed, kind, percent)
        metrics = _compute_metrics_for_project(stressed)
        row = {key: percent for key, percent in zip(parameter_order, combo)}
        row.update(metrics)
        rows.append(row)

    result["rows"] = rows
    return result


def stress_matrix_to_dataframe(result):
    """Convert a run_stress_tests result into a pandas DataFrame (optional
    convenience for report tables). Imported lazily so pandas stays optional."""
    import pandas as pd

    return pd.DataFrame(result["rows"])
