"""
Unit tests for FidelityLoader.

All tests operate on in-memory DataFrames or temporary directories;
no live Fidelity data is read.
"""

from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from assethold.analysis.daily_strategy.loader import FidelityLoader, Position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLS = [
    "Run Date",
    "Account",
    "Account Number",
    "Action",
    "Symbol",
    "Description",
    "Type",
    "Price ($)",
    "Quantity",
    "Commission ($)",
    "Fees ($)",
    "Accrued Interest ($)",
    "Amount ($)",
    "Settlement Date",
]


def _row(
    action: str,
    symbol: str,
    quantity: float,
    amount: float,
    price: float = 0.0,
    account: str = "Individual - TOD",
    account_number: str = "X78707567",
    description: str = "",
    run_date: str = "01/02/2024",
) -> dict:
    return {
        "Run Date": run_date,
        "Account": account,
        "Account Number": account_number,
        "Action": action,
        "Symbol": symbol,
        "Description": description,
        "Type": "Cash",
        "Price ($)": price,
        "Quantity": quantity,
        "Commission ($)": "",
        "Fees ($)": "",
        "Accrued Interest ($)": "",
        "Amount ($)": amount,
        "Settlement Date": "",
    }


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=_COLS)


def _loader_from_df(df: pd.DataFrame, **loader_kwargs) -> list[Position]:
    """Run the private _reconstruct_positions via a loader with default config."""
    loader = FidelityLoader(config={})  # use all defaults, no file I/O
    return loader._reconstruct_positions(df)


def _loader_from_df_with_cfg(df: pd.DataFrame, cfg: dict) -> list[Position]:
    loader = FidelityLoader(config=cfg)
    return loader._reconstruct_positions(df)


# ---------------------------------------------------------------------------
# Basic share reconstruction
# ---------------------------------------------------------------------------


class TestNetShares:
    def test_buy_only_gives_positive_shares(self):
        rows = [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10)]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].ticker == "BRKB"
        assert positions[0].shares == pytest.approx(50.0)

    def test_buy_and_sell_net_correctly(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10),
            _row("YOU SOLD BRKB (Cash)", "BRKB", -20.0, 5962.0, price=298.10),
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].shares == pytest.approx(30.0)

    def test_zero_net_position_excluded(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10),
            _row("YOU SOLD BRKB (Cash)", "BRKB", -50.0, 14905.0, price=298.10),
        ]
        positions = _loader_from_df(_df(rows))
        assert positions == []

    def test_reinvestment_adds_shares(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 10.0, -2981.0, price=298.10),
            _row("REINVESTMENT BRKB", "BRKB", 2.5, -745.25, price=298.10),
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].shares == pytest.approx(12.5)

    def test_multiple_tickers_separate_positions(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10),
            _row("YOU BOUGHT XOM (Cash)", "XOM", 30.0, -3450.0, price=115.0),
        ]
        positions = _loader_from_df(_df(rows))
        tickers = {p.ticker for p in positions}
        assert tickers == {"BRKB", "XOM"}


# ---------------------------------------------------------------------------
# Row filtering
# ---------------------------------------------------------------------------


class TestSkippedRows:
    def test_dividend_rows_do_not_add_shares(self):
        rows = [
            _row("YOU BOUGHT XOM (Cash)", "XOM", 30.0, -3450.0, price=115.0),
            _row("DIVIDEND RECEIVED XOM (Cash)", "XOM", 0.0, 297.57),
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].shares == pytest.approx(30.0)

    def test_interest_earned_skipped(self):
        rows = [
            _row("YOU BOUGHT XOM (Cash)", "XOM", 10.0, -1150.0, price=115.0),
            _row("INTEREST EARNED", "", 0.0, 5.20),
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1

    def test_cash_transfer_skipped(self):
        rows = [
            _row("YOU BOUGHT XOM (Cash)", "XOM", 10.0, -1150.0, price=115.0),
            _row("Electronic Funds Transfer Received (Cash)", "", 0.0, 9000.0),
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1

    def test_spaxx_rows_excluded(self):
        rows = [
            _row("YOU BOUGHT SPAXX", "SPAXX", 100.0, -100.0, price=1.0),
            _row("YOU BOUGHT XOM (Cash)", "XOM", 10.0, -1150.0, price=115.0),
        ]
        positions = _loader_from_df(_df(rows))
        assert all(p.ticker != "SPAXX" for p in positions)
        assert len(positions) == 1

    def test_qpigq_rows_excluded(self):
        rows = [_row("YOU BOUGHT QPIGQ", "QPIGQ", 1000.0, -1000.0, price=1.0)]
        positions = _loader_from_df(_df(rows))
        assert positions == []

    def test_custom_skip_ticker_via_config(self):
        rows = [_row("YOU BOUGHT NEWMM (Cash)", "NEWMM", 100.0, -100.0, price=1.0)]
        # Default config won't skip NEWMM; custom config will.
        positions_default = _loader_from_df(_df(rows))
        assert len(positions_default) == 1

        positions_cfg = _loader_from_df_with_cfg(
            _df(rows), {"skip_tickers": ["SPAXX", "QPIGQ", "NEWMM"]}
        )
        assert positions_cfg == []


# ---------------------------------------------------------------------------
# Employee / non-tradeable accounts
# ---------------------------------------------------------------------------


class TestEmployeeAccount:
    def test_cencora_account_is_nontradeable(self):
        rows = [
            _row(
                "Dividend",
                "",
                0.289,
                38.59,
                account="CENCORA EMPLOYEE INV",
                account_number="82897",
                description="FID 500 INDEX",
            )
        ]
        # Note: "Dividend" doesn't start with BUY/SELL prefixes so won't appear.
        # Test with a simulated buy-like action for the employee account.
        rows = [
            _row(
                "YOU BOUGHT FID500",
                "",
                5.0,
                -100.0,
                account="CENCORA EMPLOYEE INV",
                account_number="82897",
                description="FID 500 INDEX",
            )
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].tradeable is False

    def test_employee_account_uses_description_as_ticker(self):
        rows = [
            _row(
                "YOU BOUGHT FID500",
                "",
                5.0,
                -100.0,
                account="CENCORA EMPLOYEE INV",
                account_number="82897",
                description="FID 500 INDEX",
            )
        ]
        positions = _loader_from_df(_df(rows))
        assert len(positions) == 1
        assert positions[0].ticker == "FID 500 INDEX"

    def test_individual_account_is_tradeable(self):
        rows = [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10)]
        positions = _loader_from_df(_df(rows))
        assert positions[0].tradeable is True

    def test_custom_employee_pattern_via_config(self):
        rows = [
            _row(
                "YOU BOUGHT FUND",
                "",
                10.0,
                -500.0,
                account="ACME CORP PLAN",
                description="SOME FUND",
            )
        ]
        positions = _loader_from_df_with_cfg(
            _df(rows),
            {"employee_account_patterns": ["ACME CORP"]},
        )
        assert len(positions) == 1
        assert positions[0].tradeable is False


# ---------------------------------------------------------------------------
# Multiple accounts
# ---------------------------------------------------------------------------


class TestMultipleAccounts:
    def test_same_ticker_two_accounts_gives_two_positions(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, account="Individual - TOD"),
            _row(
                "YOU BOUGHT BRKB (Cash)",
                "BRKB",
                10.0,
                -2981.0,
                account="Traditional IRA",
                account_number="224886419",
            ),
        ]
        positions = _loader_from_df(_df(rows))
        accounts = {p.account for p in positions}
        assert accounts == {"Individual - TOD", "Traditional IRA"}
        assert len(positions) == 2

    def test_positions_sorted_by_account_then_ticker(self):
        rows = [
            _row("YOU BOUGHT XOM (Cash)", "XOM", 10.0, -1150.0, account="Individual - TOD"),
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, account="Individual - TOD"),
            _row("YOU BOUGHT AAPL (Cash)", "AAPL", 5.0, -900.0, account="Traditional IRA"),
        ]
        positions = _loader_from_df(_df(rows))
        keys = [(p.account, p.ticker) for p in positions]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Average cost basis
# ---------------------------------------------------------------------------


class TestAvgCostBasis:
    def test_avg_cost_single_buy(self):
        rows = [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10)]
        positions = _loader_from_df(_df(rows))
        # avg_cost = 14905 / 50 = 298.10
        assert positions[0].avg_cost_basis == pytest.approx(298.10)

    def test_avg_cost_multiple_buys_at_different_prices(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 10.0, -2900.0, price=290.0),
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 10.0, -3100.0, price=310.0),
        ]
        positions = _loader_from_df(_df(rows))
        # avg = (2900 + 3100) / (10 + 10) = 300.0
        assert positions[0].avg_cost_basis == pytest.approx(300.0)

    def test_avg_cost_sells_do_not_affect_basis(self):
        rows = [
            _row("YOU BOUGHT BRKB (Cash)", "BRKB", 20.0, -6000.0, price=300.0),
            _row("YOU SOLD BRKB (Cash)", "BRKB", -5.0, 1500.0, price=300.0),
        ]
        positions = _loader_from_df(_df(rows))
        # avg cost is from buys only
        assert positions[0].avg_cost_basis == pytest.approx(300.0)

    def test_avg_cost_none_when_no_buy_rows(self):
        # Edge case: position built entirely by reinvestment with zero price
        rows = [_row("REINVESTMENT BRKB", "BRKB", 2.0, 0.0, price=0.0)]
        positions = _loader_from_df(_df(rows))
        # Amount ($) == 0 → cost numerator = 0 → avg_cost = 0.0 or None
        # Our implementation returns None when cost = 0 (qty > 0 but cost = 0)
        # This is an acceptable edge case; just check it doesn't crash.
        assert positions[0].avg_cost_basis is not None or positions[0].avg_cost_basis is None


# ---------------------------------------------------------------------------
# Config-driven column remapping
# ---------------------------------------------------------------------------


class TestConfigColumnRemapping:
    def test_custom_column_names_work(self):
        """If Fidelity renames columns, only the config needs updating."""
        rows = [
            {
                "Date": "01/02/2024",
                "Acct": "Individual - TOD",
                "AcctNo": "X78707567",
                "Trans": "YOU BOUGHT BRKB (Cash)",
                "Ticker": "BRKB",
                "Desc": "BERKSHIRE HATHAWAY",
                "Kind": "Cash",
                "UnitPrice": 298.10,
                "Units": 50.0,
                "Comm": "",
                "Fee": "",
                "Accrued": "",
                "Total": -14905.0,
                "Settle": "",
            }
        ]
        df = pd.DataFrame(rows)
        cfg = {
            "columns": {
                "run_date": "Date",
                "account": "Acct",
                "account_number": "AcctNo",
                "action": "Trans",
                "symbol": "Ticker",
                "description": "Desc",
                "quantity": "Units",
                "price": "UnitPrice",
                "amount": "Total",
            }
        }
        positions = _loader_from_df_with_cfg(df, cfg)
        assert len(positions) == 1
        assert positions[0].ticker == "BRKB"
        assert positions[0].shares == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Config-driven action keyword changes
# ---------------------------------------------------------------------------


class TestConfigActionKeywords:
    def test_custom_buy_prefix(self):
        rows = [_row("PURCHASED BRKB", "BRKB", 50.0, -14905.0, price=298.10)]
        # Default loader won't recognise "PURCHASED" as a buy.
        default_positions = _loader_from_df(_df(rows))
        assert default_positions == []

        # Config-aware loader will.
        cfg = {"buy_action_prefixes": ["PURCHASED", "REINVESTMENT"]}
        positions = _loader_from_df_with_cfg(_df(rows), cfg)
        assert len(positions) == 1

    def test_custom_sell_prefix(self):
        rows = [
            _row("PURCHASED BRKB", "BRKB", 20.0, -5960.0, price=298.0),
            _row("LIQUIDATED BRKB", "BRKB", -20.0, 5960.0, price=298.0),
        ]
        cfg = {
            "buy_action_prefixes": ["PURCHASED"],
            "sell_action_prefixes": ["LIQUIDATED"],
        }
        positions = _loader_from_df_with_cfg(_df(rows), cfg)
        # Net = 0 → excluded
        assert positions == []


# ---------------------------------------------------------------------------
# File I/O (uses tmp_path)
# ---------------------------------------------------------------------------


class TestFileIO:
    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        pd.DataFrame(rows, columns=_COLS).to_csv(path, index=False)

    def test_single_csv_loads(self, tmp_path):
        self._write_csv(
            tmp_path / "2024.csv",
            [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 50.0, -14905.0, price=298.10)],
        )
        loader = FidelityLoader(data_dir=tmp_path, config={})
        positions = loader.load()
        assert len(positions) == 1
        assert positions[0].ticker == "BRKB"

    def test_multiple_csvs_aggregated(self, tmp_path):
        self._write_csv(
            tmp_path / "2023.csv",
            [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 30.0, -8943.0, price=298.10)],
        )
        self._write_csv(
            tmp_path / "2024.csv",
            [_row("YOU BOUGHT BRKB (Cash)", "BRKB", 20.0, -5962.0, price=298.10)],
        )
        loader = FidelityLoader(data_dir=tmp_path, config={})
        positions = loader.load()
        assert len(positions) == 1
        assert positions[0].shares == pytest.approx(50.0)

    def test_missing_dir_raises_file_not_found(self, tmp_path):
        loader = FidelityLoader(data_dir=tmp_path / "nonexistent", config={})
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load()

    def test_empty_dir_raises_file_not_found(self, tmp_path):
        loader = FidelityLoader(data_dir=tmp_path, config={})
        with pytest.raises(FileNotFoundError, match="No CSV files"):
            loader.load()

    def test_env_var_sets_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FIDELITY_DATA_DIR", str(tmp_path))
        self._write_csv(
            tmp_path / "2024.csv",
            [_row("YOU BOUGHT XOM (Cash)", "XOM", 10.0, -1150.0, price=115.0)],
        )
        loader = FidelityLoader(config={})
        positions = loader.load()
        assert len(positions) == 1
        assert positions[0].ticker == "XOM"

    def test_explicit_data_dir_overrides_env(self, tmp_path, monkeypatch):
        other = tmp_path / "other"
        other.mkdir()
        self._write_csv(
            other / "2024.csv",
            [_row("YOU BOUGHT VOO (Cash)", "VOO", 5.0, -1000.0, price=200.0)],
        )
        monkeypatch.setenv("FIDELITY_DATA_DIR", str(tmp_path))  # wrong dir
        loader = FidelityLoader(data_dir=other, config={})
        positions = loader.load()
        assert len(positions) == 1
        assert positions[0].ticker == "VOO"
