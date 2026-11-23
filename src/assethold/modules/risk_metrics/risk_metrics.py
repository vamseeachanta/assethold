from __future__ import annotations

import pandas as pd

from assethold.modules.workflow_io import output_path, record_outputs, section, write_text
from assethold.risk_metrics import PortfolioRisk


class RiskMetricsWorkflow:
    """Run portfolio risk metrics from an offline returns CSV."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "risk_metrics")
        outputs = settings["outputs"]
        date_column = settings.get("date_column", "date")

        returns = pd.read_csv(settings["returns_csv"])
        if date_column in returns.columns:
            returns[date_column] = pd.to_datetime(returns[date_column])
            returns = returns.set_index(date_column)

        weights = {
            symbol: float(weight)
            for symbol, weight in settings["weights"].items()
        }
        risk = PortfolioRisk(returns[list(weights.keys())], weights)
        risk_free_rate = float(settings.get("risk_free_rate", 0.04))

        metrics_file = output_path(outputs["metrics_csv"])
        report_file = write_text(outputs["report_txt"], risk.report(risk_free_rate))
        pd.DataFrame([risk.compute(risk_free_rate)]).to_csv(
            metrics_file, index=False, lineterminator="\n"
        )

        return record_outputs(cfg, "risk_metrics", [metrics_file, report_file])
