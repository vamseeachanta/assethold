from __future__ import annotations

import pandas as pd

from assethold.fundamentals import (
    FundamentalsReport,
    FundamentalsScorer,
    SectorPeerRanker,
)
from assethold.modules.workflow_io import output_path, record_outputs, section, write_text


class FundamentalsWorkflow:
    """Run offline fundamentals scoring from a holdings CSV."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "fundamentals")
        outputs = settings["outputs"]

        holdings_df = pd.read_csv(settings["holdings_csv"])
        holdings = (
            holdings_df.where(pd.notnull(holdings_df), None)
            .to_dict(orient="records")
        )
        scored = FundamentalsScorer().rank(holdings)
        ranked = SectorPeerRanker().add_sector_percentiles(scored)
        ranked_df = pd.DataFrame(ranked)

        ranked_file = output_path(outputs["ranked_csv"])
        ranked_df.to_csv(ranked_file, index=False, lineterminator="\n")
        report_file = write_text(
            outputs["report_txt"],
            FundamentalsReport().console_table(ranked_df),
        )

        return record_outputs(
            cfg,
            "fundamentals",
            [ranked_file, report_file],
        )
