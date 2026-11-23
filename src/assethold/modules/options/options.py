from __future__ import annotations

from datetime import date

import pandas as pd

from assethold.modules.workflow_io import output_path, record_outputs, section
from assethold.options.covered_call import (
    build_covered_call_table,
    filter_option_chain,
)


class OptionsWorkflow:
    """Run an offline covered-call opportunity table from cfg."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "options")
        filters = settings.get("filters", {})
        outputs = settings["outputs"]

        calls = pd.read_csv(settings["chain_csv"])
        today = date.fromisoformat(str(settings["today"]))
        expiry = date.fromisoformat(str(settings["expiry"]))
        days_to_expiry = (expiry - today).days
        filtered = filter_option_chain(
            calls,
            days_to_expiry=days_to_expiry,
            min_days_to_expiry=int(filters.get("min_days_to_expiry", 0)),
            min_premium=float(filters.get("min_premium", 0.0)),
            max_delta=filters.get("max_delta"),
        )
        table = build_covered_call_table(
            ticker=str(settings["ticker"]),
            current_price=float(settings["current_price"]),
            calls_df=filtered,
            expiry_date=expiry,
            today=today,
        )
        if not table.empty:
            table = table.sort_values(
                "premium_yield_annual", ascending=False
            ).reset_index(drop=True)

        output_file = output_path(outputs["opportunities_csv"])
        table.to_csv(output_file, index=False, lineterminator="\n")
        return record_outputs(cfg, "options", [output_file])
