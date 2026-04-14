# ABOUTME: Tests for the portfolio package — ingest, positions, allocation modules.
# ABOUTME: Uses synthetic CSV fixtures matching both Fidelity export formats.

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fixture CSV data matching real Fidelity formats
# ---------------------------------------------------------------------------

OLD_FORMAT_CSV = """\xef\xbb\xbf\r
\r
Run Date,Account,Action,Symbol,Description,Type,Quantity,Price ($),Commission ($),Fees ($),Accrued Interest ($),Amount ($),Settlement Date\r
 12/16/2020,"Individual" X78707567," YOU BOUGHT BERKSHIRE HATHAWAY INC COM USD0.0033... (BRKB) (Cash)", BRKB," BERKSHIRE HATHAWAY INC COM USD0.0033 CL",Cash,22,222.11,,,,-4886.49,12/18/2020\r
 12/07/2020,"Individual" X78707567," YOU BOUGHT BERKSHIRE HATHAWAY INC COM USD0.0033... (BRKB) (Cash)", BRKB," BERKSHIRE HATHAWAY INC COM USD0.0033 CL",Cash,50,228.86,,,,-11443,12/09/2020\r
 12/29/2020,"Individual" X78707567," YOU BOUGHT EXXON MOBIL CORP COM (XOM) (Cash)", XOM," EXXON MOBIL CORP COM",Cash,60,41.44,,,,-2486.26,12/31/2020\r
 12/29/2020,"Individual" X78707567," YOU SOLD MODERNA INC COM (MRNA) (Cash)", MRNA," MODERNA INC COM",Cash,-50,115.29,,0.13,,5764.54,12/31/2020\r
 11/30/2020,"Individual" X78707567," DIVIDEND RECEIVED CENCORA INC COM (COR) (Cash)", COR," CENCORA INC COM",Cash,0.000,,,,,51.93,\r
 12/31/2020,"Individual" X78707567," REINVESTMENT FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)", SPAXX," FIDELITY GOVERNMENT MONEY MARKET",Cash,0.15,1,,,,-0.15,\r
 12/31/2020,"Individual" X78707567," DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)", SPAXX," FIDELITY GOVERNMENT MONEY MARKET",Cash,0.000,,,,,0.15,\r

"informational purposes only, and is not intended to provide advice"\r
"Brokerage services are provided by Fidelity Brokerage Services LLC"\r

Date downloaded 10/12/2024 10:50 pm\r
"""

NEW_FORMAT_CSV = """\xef\xbb\xbf
\n\
Run Date,Account,Account Number,Action,Symbol,Description,Type,Price ($),Quantity,Commission ($),Fees ($),Accrued Interest ($),Amount ($),Settlement Date
04/02/2026,"Individual - TOD","X78707567","YOU BOUGHT BERKSHIRE HATHAWAY INC COM USD0.0033... (BRKB) (Cash)",BRKB,"BERKSHIRE HATHAWAY INC COM USD0.0033 CL",Cash,477.62,10,,,,-4776.2,04/06/2026
03/27/2026,"Individual - TOD","X78707567","YOU BOUGHT VANGUARD INDEX FUNDS S&P 500 ETF USD (VOO) (Cash)",VOO,"VANGUARD INDEX FUNDS S&P 500 ETF USD",Cash,584.82,10,,,,-5848.15,03/30/2026
03/20/2026,"Individual - TOD","X78707567","YOU SOLD EXXON MOBIL CORP COM (XOM) (Cash)",XOM,"EXXON MOBIL CORP COM",Cash,105.50,-20,,0.02,,2109.98,03/23/2026
03/31/2026,"Individual - TOD","X78707567","DIVIDEND RECEIVED VANGUARD INDEX FUNDS S&P 500 ETF USD (VOO) (Cash)",VOO,"VANGUARD INDEX FUNDS S&P 500 ETF USD",Cash,,0.000,,,,853.81,
03/31/2026,"Traditional IRA","224886419","DIVIDEND RECEIVED VANGUARD INDEX FUNDS S&P 500 ETF USD (VOO) (Cash)",VOO,"VANGUARD INDEX FUNDS S&P 500 ETF USD",Cash,,0.000,,,,255.35,
03/31/2026,"Individual - TOD","X78707567","REINVESTMENT FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)",SPAXX,"FIDELITY GOVERNMENT MONEY MARKET",Cash,1,38.93,,,,-38.93,

"informational purposes only, and is not intended to provide advice"
"Brokerage services are provided by Fidelity Brokerage Services LLC"

Date downloaded 04/13/2026 6:22 pm
"""

TARGETS_YAML = """\
target_allocation:
  VOO: 0.45
  BRKB: 0.35
  XOM: 0.12
  RIG: 0.05
  COR: 0.015
  CASH: 0.02

new_money_split:
  VOO: 0.55
  BRKB: 0.45

trim_rules:
  threshold_pct: 5.0
  require_profitable: true
  prefer_long_term_gains: true

dca_cadence:
  VOO:
    interval_days: 6
    lot_size_usd: 4500
  BRKB:
    interval_days: 12
    lot_size_usd: 4500

cash_reserve_pct: 0.02

money_market_symbols:
  - SPAXX
  - QPIGQ
  - FDRXX
  - FCASH

legacy_positions:
  RIG:
    action: reduce
    exit_above: 4.58
"""


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Write fixture CSV files and targets.yaml into a temp directory."""
    (tmp_path / "2020.csv").write_text(OLD_FORMAT_CSV, encoding="utf-8")
    (tmp_path / "01.01.2026 to 04.13.2026.csv").write_text(
        NEW_FORMAT_CSV, encoding="utf-8"
    )
    config_dir = tmp_path.parent / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "targets.yaml").write_text(TARGETS_YAML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(tmp_path: Path) -> dict:
    import yaml
    return yaml.safe_load(TARGETS_YAML)


# ═══════════════════════════════════════════════════════════════════════════
# Ingest tests
# ═══════════════════════════════════════════════════════════════════════════


class TestIngestParseCSV:
    """Test CSV parsing for both Fidelity formats."""

    def test_parse_old_format(self, tmp_path: Path) -> None:
        fp = tmp_path / "old.csv"
        fp.write_text(OLD_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import parse_csv

        df = parse_csv(fp)
        assert not df.empty
        # Should have 7 data rows (excluding header, footer, blanks).
        assert len(df) == 7

    def test_parse_new_format(self, tmp_path: Path) -> None:
        fp = tmp_path / "new.csv"
        fp.write_text(NEW_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import parse_csv

        df = parse_csv(fp)
        assert not df.empty
        assert len(df) == 6

    def test_old_format_columns_normalized(self, tmp_path: Path) -> None:
        fp = tmp_path / "old.csv"
        fp.write_text(OLD_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import NORMALIZED_COLUMNS, parse_csv

        df = parse_csv(fp)
        for col in NORMALIZED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_old_format_buy_values(self, tmp_path: Path) -> None:
        fp = tmp_path / "old.csv"
        fp.write_text(OLD_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import parse_csv

        df = parse_csv(fp)
        brkb_buys = df[(df["symbol"] == "BRKB") & (df["quantity"] > 0)]
        assert len(brkb_buys) == 2
        assert brkb_buys.iloc[0]["quantity"] == 22.0
        assert brkb_buys.iloc[0]["price"] == 222.11

    def test_new_format_account_number(self, tmp_path: Path) -> None:
        fp = tmp_path / "new.csv"
        fp.write_text(NEW_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import parse_csv

        df = parse_csv(fp)
        assert "X78707567" in df["account_number"].values

    def test_footer_stripped(self, tmp_path: Path) -> None:
        fp = tmp_path / "new.csv"
        fp.write_text(NEW_FORMAT_CSV, encoding="utf-8")

        from assethold.portfolio.ingest import parse_csv

        df = parse_csv(fp)
        actions = df["action"].str.lower()
        assert not actions.str.contains("informational").any()
        assert not actions.str.contains("brokerage services").any()


class TestIngestClassifyAction:
    def test_buy(self) -> None:
        from assethold.portfolio.ingest import classify_action
        assert classify_action("YOU BOUGHT VANGUARD INDEX FUNDS") == "buy"

    def test_sell(self) -> None:
        from assethold.portfolio.ingest import classify_action
        assert classify_action("YOU SOLD MODERNA INC COM") == "sell"

    def test_dividend(self) -> None:
        from assethold.portfolio.ingest import classify_action
        assert classify_action("DIVIDEND RECEIVED VANGUARD") == "dividend"

    def test_reinvestment(self) -> None:
        from assethold.portfolio.ingest import classify_action
        assert classify_action("REINVESTMENT FIDELITY") == "reinvestment"


class TestIngestLoadAll:
    def test_load_excludes_money_market(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.ingest import load_all_csvs

        df = load_all_csvs(data_dir, config=config)
        assert "SPAXX" not in df["symbol"].values

    def test_load_has_action_type(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.ingest import load_all_csvs

        df = load_all_csvs(data_dir, config=config)
        assert "action_type" in df.columns
        assert set(df["action_type"].unique()) <= {
            "buy", "sell", "dividend", "reinvestment", "interest", "transfer", "other"
        }

    def test_load_sorted_by_date(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.ingest import load_all_csvs

        df = load_all_csvs(data_dir, config=config)
        dates = df["run_date"].dropna()
        assert (dates == dates.sort_values()).all()


# ═══════════════════════════════════════════════════════════════════════════
# Positions tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPositions:
    def _load_txns(self, data_dir: Path, config: dict) -> pd.DataFrame:
        from assethold.portfolio.ingest import load_all_csvs
        return load_all_csvs(data_dir, config=config)

    def test_net_shares_brkb(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import compute_positions

        txns = self._load_txns(data_dir, config)
        positions = compute_positions(txns)
        brkb = positions.get("BRKB")
        assert brkb is not None
        # 22 + 50 (old) + 10 (new) = 82
        assert brkb.shares == 82.0

    def test_sell_reduces_shares(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import compute_positions

        txns = self._load_txns(data_dir, config)
        positions = compute_positions(txns)
        xom = positions.get("XOM")
        assert xom is not None
        # Bought 60 (old), sold 20 (new) = 40
        assert xom.shares == 40.0

    def test_sold_out_position_not_in_results(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import compute_positions

        txns = self._load_txns(data_dir, config)
        positions = compute_positions(txns)
        mrna = positions.get("MRNA")
        # MRNA: sold 50 shares (never bought in fixture) → negative, excluded
        assert mrna is None or mrna.shares <= 0

    def test_cost_basis_average(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import compute_positions

        txns = self._load_txns(data_dir, config)
        positions = compute_positions(txns)
        brkb = positions["BRKB"]
        # Avg cost should reflect weighted average of 3 buys.
        assert brkb.avg_cost > 0
        assert brkb.total_cost > 0

    def test_dividend_tracked(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import compute_positions

        txns = self._load_txns(data_dir, config)
        positions = compute_positions(txns)
        # COR had a $51.93 dividend in old file.
        cor = positions.get("COR")
        assert cor is not None
        assert cor.total_dividends >= 51.0

    def test_buying_cadence(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import buying_cadence

        txns = self._load_txns(data_dir, config)
        cadence = buying_cadence(txns, "BRKB")
        assert len(cadence) == 3  # 2 old + 1 new buy
        assert "days_since_last" in cadence.columns

    def test_dividend_summary(self, data_dir: Path, config: dict) -> None:
        from assethold.portfolio.positions import dividend_summary

        txns = self._load_txns(data_dir, config)
        div_df = dividend_summary(txns)
        assert not div_df.empty
        assert "symbol" in div_df.columns
        assert "year" in div_df.columns


# ═══════════════════════════════════════════════════════════════════════════
# Allocation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAllocation:
    def test_compute_allocation_signals(self) -> None:
        from assethold.portfolio.allocation import compute_allocation
        from assethold.portfolio.positions import Position

        positions = {
            "VOO": Position("VOO", 100, 500.0, 50000, 0, 10, 0, None, None),
            "BRKB": Position("BRKB", 50, 400.0, 20000, 0, 5, 0, None, None),
            "XOM": Position("XOM", 1000, 40.0, 40000, 0, 20, 0, None, None),
        }
        targets = {"VOO": 0.45, "BRKB": 0.35, "XOM": 0.12}
        prices = {"VOO": 600.0, "BRKB": 480.0, "XOM": 100.0}

        rows = compute_allocation(positions, targets, prices=prices)
        assert len(rows) > 0
        symbols = {r.symbol for r in rows}
        assert "VOO" in symbols

        # XOM is heavily overweight at 100k / total — should be trim.
        xom_row = next(r for r in rows if r.symbol == "XOM")
        assert xom_row.signal == "trim"

    def test_new_money_split(self) -> None:
        from assethold.portfolio.allocation import new_money_split

        split = new_money_split(
            10000.0,
            {"VOO": 0.55, "BRKB": 0.45},
            prices={"VOO": 600.0, "BRKB": 480.0},
        )
        assert split.total_usd == 10000.0
        assert len(split.allocations) == 2

        voo_alloc = next(a for a in split.allocations if a[0] == "VOO")
        assert voo_alloc[1] == 5500.0  # 55% of 10k
        assert voo_alloc[2] == 9  # int(5500/600) = 9 shares

        brkb_alloc = next(a for a in split.allocations if a[0] == "BRKB")
        assert brkb_alloc[1] == 4500.0
        assert brkb_alloc[2] == 9  # int(4500/480) = 9 shares

    def test_allocation_to_dataframe(self) -> None:
        from assethold.portfolio.allocation import AllocationRow, allocation_to_dataframe

        rows = [
            AllocationRow("VOO", 100, 600.0, 60000.0, 40.0, 45.0, -5.0, "hold"),
            AllocationRow("XOM", 500, 100.0, 50000.0, 33.0, 12.0, 21.0, "trim"),
        ]
        df = allocation_to_dataframe(rows)
        assert len(df) == 2
        assert "Signal" in df.columns
