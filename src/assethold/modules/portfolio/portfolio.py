from __future__ import annotations

from pathlib import Path

from assethold.modules.workflow_io import output_path, record_outputs, section
from assethold.portfolio.allocation import (
    allocation_to_dataframe,
    compute_allocation,
)
from assethold.portfolio.ingest import load_all_csvs, load_config
from assethold.portfolio.positions import compute_positions, positions_to_dataframe


class PortfolioWorkflow:
    """Run portfolio position and allocation reports from cfg."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "portfolio")
        outputs = settings["outputs"]

        config = load_config(Path(settings["targets"]))
        transactions = load_all_csvs(Path(settings["data_dir"]), config=config)
        positions = compute_positions(transactions)

        prices = {
            symbol: float(price)
            for symbol, price in settings.get("prices", {}).items()
        }
        trim_pct = float(config.get("trim_rules", {}).get("threshold_pct", 5.0))
        allocation = compute_allocation(
            positions,
            config.get("target_allocation", {}),
            prices=prices,
            trim_threshold_pct=trim_pct,
        )

        positions_file = output_path(outputs["positions_csv"])
        allocation_file = output_path(outputs["allocation_csv"])
        # lineterminator is pinned to LF so the emitted bytes are identical on
        # every platform. pandas writes through a text-mode handle, so Windows
        # would otherwise translate \n to \r\n, changing each file's sha256 and
        # size -- and these files feed the workflow_api result_hash, which is
        # contractually a cross-platform determinism value. See assethold#85.
        positions_to_dataframe(positions).to_csv(
            positions_file, index=False, lineterminator="\n"
        )
        allocation_to_dataframe(allocation).to_csv(
            allocation_file, index=False, lineterminator="\n"
        )

        return record_outputs(cfg, "portfolio", [positions_file, allocation_file])
