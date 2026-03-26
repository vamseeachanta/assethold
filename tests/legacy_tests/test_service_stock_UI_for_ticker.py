import logging
import os
import sys

sys.path.extend(['..'])

from assethold.common.data import AttributeDict
from assethold.finance_components import FinanceComponents
from assethold.services.StockAnalysis.StockAnalysis import \
    assign_stock_data_and_update_menu_items

cfg = AttributeDict({
    'source': 'yfinance',
    'stocks': [{
        'ticker': None
    }],
    'period': '5y'
})
fc = FinanceComponents(cfg=cfg)


def get_data_for_UI(ticker):
    if fc.valid_ticker():
        df = fc.get_data_for_UI(ticker)

    print("Completed stock analysis data from Database for {}".format(ticker))


def test_service_stock_UI(ticker):
    assign_stock_data_and_update_menu_items(ticker, test_flag=True)


if __name__ == '__main__':

    # Supporting functions
    # get_data_for_UI(ticker='RIG')
    test_service_stock_UI(ticker='VIEW')
    # test_service_stock_UI(ticker='RIG')
    # test_service_stock_UI(ticker='HD')
    # test_service_stock_UI(ticker='HD')
    # test_service_stock_UI(ticker='OCGN')
