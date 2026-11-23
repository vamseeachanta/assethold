from __future__ import annotations

import pandas as pd

from assethold.dividend_forecast import (
    dividend_coverage,
    forecast_dividends,
    gordon_growth_model,
    payout_ratio,
    yield_on_cost,
)
from assethold.modules.workflow_io import (
    output_path,
    record_outputs,
    section,
    write_json,
)


class DividendForecastWorkflow:
    """Run dividend valuation, forecast, and safety metrics from cfg."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "dividend_forecast")
        outputs = settings["outputs"]

        growth = gordon_growth_model(
            current_dividend=float(settings["current_dividend"]),
            growth_rate=float(settings["growth_rate"]),
            required_return=float(settings["required_return"]),
        )
        forecast = forecast_dividends(
            current_dividend=float(settings["current_dividend"]),
            growth_rate=float(settings["growth_rate"]),
            years=int(settings["years"]),
        )
        summary = {
            "gordon_growth": growth,
            "forecast": forecast,
            "yield_on_cost": yield_on_cost(
                float(settings["current_dividend"]),
                float(settings["purchase_price"]),
            ),
            "payout_ratio": payout_ratio(
                float(settings["current_dividend"]),
                float(settings["earnings_per_share"]),
            ),
            "dividend_coverage": dividend_coverage(
                float(settings["earnings_per_share"]),
                float(settings["current_dividend"]),
            ),
        }

        forecast_file = output_path(outputs["forecast_csv"])
        pd.DataFrame(
            {
                "year": range(1, forecast.years + 1),
                "dividend": forecast.dividends,
            }
        ).to_csv(forecast_file, index=False, lineterminator="\n")
        summary_file = write_json(outputs["summary_json"], summary)

        return record_outputs(
            cfg,
            "dividend_forecast",
            [forecast_file, summary_file],
        )
