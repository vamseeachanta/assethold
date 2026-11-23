"""Unit tests for SECDataForm.get_trasactionTable (issue #52).

Targets the chained-assignment fix on `preTransactionAmounts`. Under the old
`table_df['preTransactionAmounts'].iloc[i] = ...` form, pandas >= 2.2 writes to
a temporary copy, leaving the column all-None -> `iloc[0] > 0` raises and the
insider buy/sell classification silently breaks. The fix uses positional
`.iloc[row, col]` assignment so the write lands.

Synthetic, hand-built Form-4 transaction tables -- no network, no XML parsing.
"""

import sys
from unittest.mock import MagicMock

import pytest
import pandas as pd

# get_SEC_data does `from sec_edgar_downloader._utils import ...` at import
# time; provide the submodule so the import resolves under the test harness.
sys.modules.setdefault('sec_edgar_downloader', MagicMock())
sys.modules.setdefault('sec_edgar_downloader._utils', MagicMock())

from assethold.modules.stocks.get_SEC_data import SECDataForm

pytestmark = pytest.mark.unit


def _amount(shares, code, price=10.0):
    """Build the nested 'transactionAmounts' dict the parser expects."""
    return {
        'transactionShares': {'value': str(shares)},
        'transactionPricePerShare': {'value': str(price)},
        'transactionAcquiredDisposedCode': {'value': code},
    }


def _row(security, date, shares, code, post, price=10.0):
    return {
        'securityTitle': {'value': security},
        'transactionDate': {'value': date},
        'transactionAmounts': _amount(shares, code, price),
        # parser reads sharesOwnedFollowingTransaction off this column
        'postTransactionAmounts': {
            'sharesOwnedFollowingTransaction': {'value': str(post)}
        },
    }


def test_pre_transaction_amounts_column_is_populated():
    """Acquisition: pre = post - shares; column must not stay None."""
    df = pd.DataFrame([_row('Common Stock', '2026-01-01', 100, 'A', post=600)])
    form = SECDataForm()

    Cost, Transaction, share_ratio, total_shares, noShares = form.get_trasactionTable(df)

    # pre = 600 - 100 = 500 ; post(last) = 600 ; ratio = 600/500 = 1.2 -> Buy
    assert df['preTransactionAmounts'].iloc[0] == 500
    assert share_ratio == 1.2
    assert Transaction == 'Buy'
    assert total_shares == 600
    assert noShares == 100


def test_disposition_classified_as_sale():
    """Disposition: pre = post + shares; ratio < 1 -> Sale."""
    # Sold 200, ending at 800 -> pre = 1000 ; ratio = 800/1000 = 0.8 < 1
    df = pd.DataFrame([_row('Common Stock', '2026-01-02', 200, 'D', post=800)])
    form = SECDataForm()

    Cost, Transaction, share_ratio, total_shares, noShares = form.get_trasactionTable(df)

    assert df['preTransactionAmounts'].iloc[0] == 1000
    assert share_ratio == 0.8
    assert Transaction == 'Sale'
