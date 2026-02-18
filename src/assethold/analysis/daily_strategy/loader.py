"""
Fidelity transaction history parser.

Reads Fidelity CSV exports (activity history) and reconstructs current
holdings as net shares per (account, ticker).

All parsing behaviour is driven by ``config/daily_strategy.yaml`` so that
column names, action keywords, and skip-lists can be updated without touching
code when Fidelity changes its export format.

Config lookup order:
    1. ``config`` dict passed directly to ``FidelityLoader(config=...)``
    2. ``config_path`` YAML file path passed to ``FidelityLoader(config_path=...)``
    3. ``<assethold-repo>/config/daily_strategy.yaml`` (default)

Data-directory lookup order:
    1. ``data_dir`` argument
    2. ``loader.data_dir`` key in config
    3. ``FIDELITY_DATA_DIR`` environment variable
    4. ``<workspace-root>/achantas-data/_finance/fidelity``
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd


@dataclass
class Position:
    """A single holding reconstructed from transaction history."""

    account: str
    account_number: str
    ticker: str
    shares: float
    tradeable: bool
    avg_cost_basis: Optional[float]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; return empty dict if not found or unreadable."""
    try:
        import yaml  # type: ignore[import]

        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _default_config_path() -> Path:
    """Return the default config/daily_strategy.yaml relative to repo root."""
    # loader.py → daily_strategy/ → analysis/ → assethold/ → src/ → repo/
    return Path(__file__).parents[4] / "config" / "daily_strategy.yaml"


class ComparisonLoader:
    """Create synthetic Position objects for arbitrary tickers (watchlist / compare mode)."""

    def load_tickers(self, tickers: list[str]) -> list[Position]:
        """
        Return a synthetic Position for each ticker in *tickers*.

        Positions have shares=0, tradeable=True, avg_cost_basis=None, and
        account="Watchlist" so they flow through SignalEngine without triggering
        the portfolio-weight sub-signal (portfolio_value=0 skips weight scoring).

        Args:
            tickers: List of ticker symbols (case-insensitive; normalised to upper).

        Returns:
            List of Position objects, one per ticker, sorted alphabetically.
        """
        positions = [
            Position(
                account="Watchlist",
                account_number="",
                ticker=t.upper().strip(),
                shares=0.0,
                tradeable=True,
                avg_cost_basis=None,
            )
            for t in tickers
            if t.strip()
        ]
        return sorted(positions, key=lambda p: p.ticker)


class FidelityLoader:
    """Load and parse Fidelity transaction CSV exports."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        config: Optional[dict[str, Any]] = None,
        config_path: Optional[Path] = None,
    ):
        """
        Args:
            data_dir:    Directory containing Fidelity CSV files. Overrides config.
            config:      Loader config dict (``loader`` sub-section of the YAML).
                         When provided, no YAML file is read.
            config_path: Path to the full ``daily_strategy.yaml``. Ignored when
                         ``config`` is passed. Defaults to the repo config file.
        """
        if config is not None:
            self._cfg = config
        else:
            full = _load_yaml(config_path or _default_config_path())
            self._cfg = full.get("loader", {})

        # Configurable parsing parameters
        self._buy_prefixes: tuple[str, ...] = tuple(
            p.upper() for p in self._cfg.get("buy_action_prefixes", ["YOU BOUGHT", "REINVESTMENT"])
        )
        self._sell_prefixes: tuple[str, ...] = tuple(
            p.upper() for p in self._cfg.get("sell_action_prefixes", ["YOU SOLD"])
        )
        self._skip_tickers: frozenset[str] = frozenset(
            self._cfg.get("skip_tickers", ["SPAXX", "QPIGQ", "FCASH", "73102V105"])
        )
        self._employee_patterns: list[str] = [
            p.upper()
            for p in self._cfg.get("employee_account_patterns", ["CENCORA", "EMPLOYEE INV"])
        ]
        self._col: dict[str, str] = {
            "run_date": "Run Date",
            "account": "Account",
            "account_number": "Account Number",
            "action": "Action",
            "symbol": "Symbol",
            "description": "Description",
            "quantity": "Quantity",
            "price": "Price ($)",
            "amount": "Amount ($)",
            **self._cfg.get("columns", {}),
        }

        # Data directory resolution
        self.data_dir = self._resolve_data_dir(data_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> list[Position]:
        """
        Parse all CSVs in data_dir and return current holdings.

        Returns:
            List of Position objects with non-zero net shares, sorted by
            account then ticker.

        Raises:
            FileNotFoundError: If data_dir does not exist or contains no CSVs.
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"Fidelity data directory not found: {self.data_dir}"
            )

        csv_files = sorted(self.data_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {self.data_dir}")

        frames = [
            pd.read_csv(f, header=0, dtype=str, on_bad_lines="skip")
            for f in csv_files
        ]
        combined = pd.concat(frames, ignore_index=True)
        return self._reconstruct_positions(combined)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_data_dir(self, explicit: Optional[Path]) -> Path:
        """Determine the Fidelity data directory from all sources."""
        if explicit is not None:
            return Path(explicit)
        cfg_dir = self._cfg.get("data_dir")
        if cfg_dir:
            return Path(cfg_dir)
        env_dir = os.environ.get("FIDELITY_DATA_DIR")
        if env_dir:
            return Path(env_dir)
        # loader.py → daily_strategy/ → analysis/ → assethold-pkg/ → src/
        # → assethold-repo/ → workspace-hub/
        workspace = Path(__file__).parents[5]
        return workspace / "achantas-data" / "_finance" / "fidelity"

    def _reconstruct_positions(self, df: pd.DataFrame) -> list[Position]:
        """Turn raw transaction rows into a list of Position objects."""
        df = self._normalize(df)

        c = self._col
        # For employee accounts: Symbol is blank → use Description as identifier.
        is_emp = self._is_employee(df[c["account"]])
        no_sym = df[c["symbol"]] == ""
        df.loc[is_emp & no_sym, c["symbol"]] = df.loc[is_emp & no_sym, c["description"]]

        # Keep only share-movement rows (buy / sell).
        action_up = df[c["action"]].str.upper().str.strip()
        is_buy = action_up.str.startswith(self._buy_prefixes[0])
        for prefix in self._buy_prefixes[1:]:
            is_buy = is_buy | action_up.str.startswith(prefix)
        is_sell = action_up.str.startswith(self._sell_prefixes[0])
        for prefix in self._sell_prefixes[1:]:
            is_sell = is_sell | action_up.str.startswith(prefix)

        trade_df = df[is_buy | is_sell].copy()
        trade_df = trade_df[~trade_df[c["symbol"]].isin(self._skip_tickers | {"", "nan"})]

        if trade_df.empty:
            return []

        positions: list[Position] = []
        for (account, ticker), group in trade_df.groupby([c["account"], c["symbol"]]):
            net_shares = group[c["quantity"]].sum()
            if abs(net_shares) < 0.001:
                continue

            acct_num = (
                group[c["account_number"]].iloc[0]
                if c["account_number"] in group.columns
                else ""
            )
            tradeable = not bool(self._is_employee(pd.Series([account])).iloc[0])
            avg_cost = self._calc_avg_cost(group, c)

            positions.append(
                Position(
                    account=str(account),
                    account_number=str(acct_num),
                    ticker=str(ticker),
                    shares=float(net_shares),
                    tradeable=tradeable,
                    avg_cost_basis=avg_cost,
                )
            )

        return sorted(positions, key=lambda p: (p.account, p.ticker))

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names, strip whitespace, coerce numerics."""
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        c = self._col
        for key in ("account", "action", "symbol", "description"):
            col = c[key]
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
            else:
                df[col] = ""

        if c["account_number"] in df.columns:
            df[c["account_number"]] = (
                df[c["account_number"]].fillna("").astype(str).str.strip()
            )

        for key in ("quantity", "price", "amount"):
            col = c[key]
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                df[col] = 0.0

        return df

    def _is_employee(self, accounts: pd.Series) -> pd.Series:
        """Return boolean mask: True where account matches an employee pattern."""
        mask = pd.Series(False, index=accounts.index)
        for pattern in self._employee_patterns:
            mask = mask | accounts.str.upper().str.contains(pattern, na=False)
        return mask

    def _calc_avg_cost(
        self,
        group: pd.DataFrame,
        c: dict[str, str],
    ) -> Optional[float]:
        """Compute simple average cost basis from buy-side rows in the group."""
        action_up = group[c["action"]].str.upper().str.strip()
        is_buy = action_up.str.startswith(self._buy_prefixes[0])
        for prefix in self._buy_prefixes[1:]:
            is_buy = is_buy | action_up.str.startswith(prefix)
        buy_rows = group[is_buy]
        if buy_rows.empty:
            return None
        total_qty = buy_rows[c["quantity"]].sum()
        if total_qty <= 0:
            return None
        # Amount($) is negative for purchases; negate to get total cash spent.
        total_cost = (-buy_rows[c["amount"]]).sum()
        return float(total_cost / total_qty)
