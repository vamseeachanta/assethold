import datetime
import json
import logging
import sys
import time
import traceback

import pandas as pd

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


def insider_analysis(ticker, update_threshold_days=2):
    analysis_dict = fc.get_data_for_UI(ticker=ticker)
    # insider = analysis_dict.get('breakout_trends', {})
    analysis_status = analysis_dict.get('status', {
        'insider': False,
        'institution': False,
        'breakout_trends': False
    })
    insider_status = analysis_status.get('breakout_trends', False)

    analysis_df = fc.get_analysis_data_from_db(ticker=ticker)
    insider_db = fc.get_insider_data_from_db(ticker=ticker)

    if not insider_db.empty:
        insider_finviz_dict = insider_db.finviz.iloc[0]
        insider_finviz = pd.DataFrame(insider_finviz_dict)
        insider_relationship = [
            relationship.replace("'", "''")
            for relationship in insider_finviz['Relationship'].tolist()
        ]
        insider_finviz['Relationship'] = insider_relationship
        insider_trading = [
            insider.replace("'", "''")
            for insider in insider_finviz['Insider Trading'].tolist()
        ]
        insider_finviz['Insider Trading'] = insider_trading

        insider_df = fc.fdata.insider_data_clean_and_add_share_ratio(
            insider_finviz)
        insider = fc.fanalysis.evaluate_insider_trend(insider_df)
        data_json = json.dumps(insider)

        analysis_status['insider'] = True
        analysis_status_json = json.dumps(analysis_status)
        cfg_save = {
            'column': 'insider',
            'data': data_json,
            'status': analysis_status_json,
            'ticker': ticker
        }
        fc.save_analysis_column_to_db(cfg_save)
        logging.info(
            "Insider analysis for ticker: {} ... COMPLETED".format(ticker))
    else:
        logging.info(
            "Insider analysis for ticker: {} ... NOT PERFORMED".format(ticker))


def breakout_trend_analysis(ticker, update_threshold_days=2):
    analysis_dict = fc.get_data_for_UI(ticker=ticker)

    breakout_trends = analysis_dict.get('breakout_trends', {})
    analysis_status = analysis_dict.get('status', {
        'insider': False,
        'institution': False,
        'breakout_trends': False
    })
    breakout_trends_status = analysis_status.get('breakout_trends', False)

    if not breakout_trends_status:
        EOD_db = fc.get_EOD_data_from_db(ticker=ticker)
        EOD_dict = EOD_db['yf'].iloc[0]
        EOD_df = pd.DataFrame(EOD_dict)
        EOD_df.Date = pd.to_datetime(EOD_df.Date, infer_datetime_format=True)
        EOD_df = fc.fdata.get_EOD_with_rolling_averages(EOD_df)
        breakout_trend_df = fc.fanalysis.breakout_trend_analysis(EOD_df)
        breakout_trend_dict = breakout_trend_df.to_dict(orient='records')
        data_json = json.dumps(breakout_trend_dict)

        analysis_status['breakout_trends'] = True
        analysis_status_json = json.dumps(analysis_status)
        cfg_save = {
            'column': 'breakout_trends',
            'data': data_json,
            'status': analysis_status_json,
            'ticker': ticker
        }
        fc.save_analysis_column_to_db(cfg_save)
        logging.info(
            "Breakout trend analysis for ticker: {} ... COMPLETED".format(
                ticker))
    else:
        logging.info(
            "Breakout trend analysis for ticker: {} ... NOT PERFORMED".format(
                ticker))


def run_finviz_dow():
    tickers = fc.fdata.get_tickers_dow()
    for ticker in tickers:
        insider_analysis(ticker=ticker)
        # breakout_trend_analysis(ticker=ticker)


def run_finviz_sp500():
    tickers = fc.fdata.get_tickers_sp500()
    for ticker in tickers:
        insider_analysis(ticker=ticker)
        # breakout_trend_analysis(ticker=ticker)


if __name__ == '__main__':
    run_finviz_dow()
    run_finviz_sp500()

    # Supporting functions
    # insider_analysis(ticker='RIG')
    # insider_analysis(ticker='HD')
    # insider_analysis(ticker='HUM')
    # breakout_trend_analysis(ticker='RIG')
    # breakout_trend_analysis(ticker='HD')
    # breakout_trend_analysis(ticker='HUM')
