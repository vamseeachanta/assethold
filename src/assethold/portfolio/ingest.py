# ABOUTME: Fidelity CSV transaction parser supporting both old (2020-2021) and new (2022+) formats.
# ABOUTME: Normalizes column layout, handles BOM/footers, deduplicates overlapping file exports.

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

# Column names after normalization — every row will have these.
NORMALIZED_COLUMNS = [
    "run_date",
    "account",
    "account_number",
    "action",
    "symbol",
    "description",
    "type",
    "price",
    "quantity",
    "commission",
    "fees",
    "accrued_interest",
    "amount",
    "settlement_date",
]

# Old-format header starts with these columns (no Account Number).
_OLD_HEADER_PREFIX = ("Run Date", "Account", "Action")

# New-format header has Account Number in position 2.
_NEW_HEADER_PREFIX = ("Run Date", "Account", "Account Number")

# Lines starting with these are Fidelity footer disclaimers.
_FOOTER_MARKERS = (
    '"informational purposes',
    '"Brokerage services',
    '"recommendation for',
    '"exported and is subject',
    '"purposes. For more',
    '"Financial Services',
    '"Fidelity Insurance',
    "Date downloaded",
)


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load targets.yaml from config/ directory."""
    if config_path is None:
        config_path = Path(__file__).resolve().parents[3] / "config" / "targets.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def _detect_format(header_row: list[str]) -> str:
    """Return 'old' or 'new' based on header columns."""
    stripped = [c.strip() for c in header_row]
    if len(stripped) >= 3 and tuple(stripped[:3]) == _NEW_HEADER_PREFIX:
        return "new"
    if len(stripped) >= 3 and tuple(stripped[:3]) == _OLD_HEADER_PREFIX:
        return "old"
    raise ValueError(f"Unrecognized CSV header: {stripped[:5]}")


def _is_footer_line(line: str) -> bool:
    """True if this line is part of the Fidelity disclaimer footer."""
    stripped = line.strip()
    if not stripped:
        return True
    return any(stripped.startswith(marker) for marker in _FOOTER_MARKERS)


def _clean_numeric(val: str) -> Optional[float]:
    """Parse a numeric string, stripping $, commas, and whitespace."""
    if val is None:
        return None
    cleaned = str(val).strip().replace("$", "").replace(",", "")
    if not cleaned or cleaned == "--":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(val: str) -> Optional[datetime]:
    """Parse MM/DD/YYYY date string."""
    stripped = str(val).strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, "%m/%d/%Y")
    except ValueError:
        return None


def parse_csv(filepath: Path) -> pd.DataFrame:
    """Parse a single Fidelity CSV export into a normalized DataFrame.

    Handles both old format (2020-2021, Quantity before Price) and new format
    (2022+, Account Number column, Price before Quantity).  Strips BOM, blank
    lines, and footer disclaimers.
    """
    text = filepath.read_text(encoding="utf-8-sig")  # strips BOM
    lines = text.splitlines()

    # Find the header line (skip leading blank lines).
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Run Date"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(f"No header row found in {filepath}")

    # Filter out footer lines.
    data_lines = []
    for line in lines[header_idx:]:
        if _is_footer_line(line) and not line.strip().startswith("Run Date"):
            continue
        data_lines.append(line)

    reader = csv.reader(io.StringIO("\n".join(data_lines)))
    header = next(reader)
    fmt = _detect_format(header)

    rows = []
    for raw_row in reader:
        if not raw_row or all(c.strip() == "" for c in raw_row):
            continue
        # Skip footer lines that slipped through.
        if _is_footer_line(",".join(raw_row)):
            continue

        if fmt == "old":
            # Old: Run Date, Account, Action, Symbol, Description, Type,
            #      Quantity, Price, Commission, Fees, Accrued Interest, Amount,
            #      Settlement Date
            row = _pad(raw_row, 13)
            rows.append({
                "run_date": _parse_date(row[0]),
                "account": row[1].strip().strip('"'),
                "account_number": _extract_account_number_old(row[1]),
                "action": row[2].strip(),
                "symbol": row[3].strip(),
                "description": row[4].strip(),
                "type": row[5].strip(),
                "price": _clean_numeric(row[7]),
                "quantity": _clean_numeric(row[6]),
                "commission": _clean_numeric(row[8]),
                "fees": _clean_numeric(row[9]),
                "accrued_interest": _clean_numeric(row[10]),
                "amount": _clean_numeric(row[11]),
                "settlement_date": _parse_date(row[12]) if len(row) > 12 else None,
            })
        else:
            # New: Run Date, Account, Account Number, Action, Symbol,
            #      Description, Type, Price, Quantity, Commission, Fees,
            #      Accrued Interest, Amount, Settlement Date
            row = _pad(raw_row, 14)
            rows.append({
                "run_date": _parse_date(row[0]),
                "account": row[1].strip().strip('"'),
                "account_number": row[2].strip().strip('"'),
                "action": row[3].strip(),
                "symbol": row[4].strip(),
                "description": row[5].strip(),
                "type": row[6].strip(),
                "price": _clean_numeric(row[7]),
                "quantity": _clean_numeric(row[8]),
                "commission": _clean_numeric(row[9]),
                "fees": _clean_numeric(row[10]),
                "accrued_interest": _clean_numeric(row[11]),
                "amount": _clean_numeric(row[12]),
                "settlement_date": _parse_date(row[13]) if len(row) > 13 else None,
            })

    df = pd.DataFrame(rows, columns=NORMALIZED_COLUMNS)
    df["source_file"] = filepath.name
    return df


def _pad(row: list[str], length: int) -> list[str]:
    """Pad a row to a minimum length with empty strings."""
    return row + [""] * max(0, length - len(row))


def _extract_account_number_old(account_field: str) -> str:
    """Extract account number from old-format Account field.

    Old format embeds the number: '"Individual" X78707567' or '"CENCORA" 82897'.
    """
    cleaned = account_field.strip().strip('"')
    match = re.search(r"[A-Z]?\d{5,}", cleaned)
    return match.group(0) if match else ""


def classify_action(action: str) -> str:
    """Classify a Fidelity action string into a canonical type.

    Returns one of: 'buy', 'sell', 'dividend', 'reinvestment', 'interest',
    'transfer', 'other'.
    """
    upper = action.upper().strip()
    if "YOU BOUGHT" in upper:
        return "buy"
    if "YOU SOLD" in upper:
        return "sell"
    if "DIVIDEND" in upper and "REINVESTMENT" not in upper:
        return "dividend"
    if "REINVESTMENT" in upper:
        return "reinvestment"
    if "INTEREST" in upper:
        return "interest"
    if "TRANSFERRED" in upper or "TRANSFER" in upper:
        return "transfer"
    return "other"


def load_all_csvs(
    data_dir: Path,
    *,
    exclude_money_market: bool = True,
    config: Optional[dict] = None,
    prefer_new_format: bool = True,
) -> pd.DataFrame:
    """Load and merge all Fidelity CSV files from a directory.

    Deduplicates transactions that appear in both old-format (YYYY.csv) and
    new-format (date-range) files for the same year.

    Args:
        data_dir: Directory containing Fidelity CSV exports.
        exclude_money_market: Drop money-market symbol rows.
        config: Loaded targets.yaml dict (for money market symbol list).
        prefer_new_format: When duplicates exist, keep the new-format version.

    Returns:
        Deduplicated DataFrame of all transactions, sorted by run_date.
    """
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for fp in csv_files:
        try:
            df = parse_csv(fp)
            if not df.empty:
                frames.append(df)
        except (ValueError, UnicodeDecodeError) as exc:
            print(f"Warning: skipping {fp.name}: {exc}")

    if not frames:
        raise ValueError(f"No parseable CSV files in {data_dir}")

    combined = pd.concat(frames, ignore_index=True)
    # Drop rows that are entirely NA (from empty CSV sections).
    combined = combined.dropna(how="all")

    # Add action classification.
    combined["action_type"] = combined["action"].apply(classify_action)

    # Deduplicate: same date + account_number + symbol + amount = same txn.
    dedup_cols = ["run_date", "account_number", "symbol", "amount"]
    before = len(combined)
    combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
    dupes_dropped = before - len(combined)
    if dupes_dropped > 0:
        print(f"Deduplicated: dropped {dupes_dropped} duplicate transactions")

    # Exclude money-market symbols.
    if exclude_money_market:
        if config is None:
            config = load_config()
        mm_symbols = set(config.get("money_market_symbols", []))
        combined = combined[~combined["symbol"].isin(mm_symbols)]

    combined = combined.sort_values("run_date", ascending=True).reset_index(drop=True)
    return combined
