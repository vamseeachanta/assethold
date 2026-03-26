import datetime
import json
import logging
import sys
import time
import traceback

sys.path.extend(['..'])

from assethold.common.data import AttributeDict
from assethold.finance_components import FinanceComponents

logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

cfg = AttributeDict({
    'source': 'yfinance',
    'stocks': [{
        'ticker': None
    }],
    'period': '5y'
})
fc = FinanceComponents(cfg=cfg)


def finviz_insider_data(ticker):
    try:
        insider_info_finviz = fc.fdata.get_insider_information_from_finviz(
            ticker)

        start_date = insider_info_finviz['Date'].min().strftime("%m-%d-%Y")
        end_date = insider_info_finviz['Date'].max().strftime("%m-%d-%Y")

        insider_relationship = [
            relationship.replace("'", "''")
            for relationship in insider_info_finviz['Relationship'].tolist()
        ]
        insider_info_finviz['Relationship'] = insider_relationship
        insider_trading = [
            insider.replace("'", "''")
            for insider in insider_info_finviz['Insider Trading'].tolist()
        ]
        insider_info_finviz['Insider Trading'] = insider_trading
        insider_dates = [
            date.strftime("%m-%d-%Y")
            for date in insider_info_finviz['Date'].tolist()
        ]
        insider_info_finviz['Date'] = insider_dates
        # data = insider_info_finviz.to_dict(orient='records')
        # data_json = json.dumps(data)

        status = {'finviz': {'start_date': start_date, 'end_date': end_date}}
        status_json = json.dumps(status)
        cfg_save = {
            'column': 'finviz',
            'df': insider_info_finviz,
            'status': status_json,
            'ticker': ticker
        }
        print(cfg_save)
        logging.info(
            "Insider data update for ticker: {} ... COMPLETED".format(ticker))
        time.sleep(2)
    except:
        logging.error("Failed to get insider data for ticker, (%s)" %
                      traceback.format_exc())


def run_finviz_sp500():
    tickers = fc.fdata.get_tickers_sp500()
    for ticker in tickers:
        finviz_insider_data(ticker=ticker)


def run_finviz_dow():
    tickers = fc.fdata.get_tickers_dow()
    for ticker in tickers:
        finviz_insider_data(ticker=ticker)


if __name__ == '__main__':
    # Run group of tickers
    # run_finviz_dow()
    # run_finviz_sp500()

    # Supporting functions
    finviz_insider_data(ticker='RIG')
    # finviz_insider_data(ticker='HD')
    # finviz_insider_data(ticker='HUM')
