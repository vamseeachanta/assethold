import logging
import sys
import traceback

sys.path.extend(['..'])

from assethold.common.data import AttributeDict
from assethold.finance_components import FinanceComponents


def stock_analysis_by_ticker(ticker):
    print("Analysis for ticker: {}  ... START".format(ticker))
    cfg = AttributeDict({
        'source': 'yfinance',
        'stocks': [{
            'ticker': ticker
        }],
        'period': '5y'
    })
    fc = FinanceComponents(cfg=cfg)
    data_dict = None
    if fc.valid_ticker():
        # fc.cfg['database']['data_exists'] = False
        try:
            fc.get_data()
            data_dict = fc.get_data_dict()
        except:
            fc.fdata.status.update({"Getting data": "Failed"})
            logging.info("StockAnalysis Data Error: (%s)" %
                         traceback.format_exc())
            print("StockAnalysis, Getting data ... FAILED")
        try:
            if data_dict is not None:
                fc.perform_analysis(data_dict)
        except:
            fc.fanalysis.status.update({"Analysis": "Failed"})
            logging.info("StockAnalysis Data Error: (%s)" %
                         traceback.format_exc())
            print("StockAnalysis, Performing analysis  ... FAILED")

        # if data_dict is not None:
        #     fc.save_result_to_db()
        assert (fc.fdata.company_info['stock_ticker'] == ticker)
        df_data = fc.fdata.stock_data_array[0]
        assert (len(df_data) > 0)
        df_ta = fc.fanalysis.ta
        assert (len(df_ta) >= 0)
        df_insider = fc.fanalysis.insider_analysis_by_relation_df
        assert (len(df_insider) >= 0)

    print("Analysis for ticker: {}  ... COMPLETED".format(ticker))


def run_batch_sp500():
    cfg = AttributeDict({
        'source': 'yfinance',
        'stocks': [{
            'ticker': None
        }],
        'period': '5y'
    })
    fc = FinanceComponents(cfg=cfg)
    tickers = fc.fdata.get_tickers_sp500()
    for ticker in tickers:
        stock_analysis_by_ticker(ticker=ticker)


def run_batch_dow():
    cfg = AttributeDict({
        'source': 'yfinance',
        'stocks': [{
            'ticker': None
        }],
        'period': '5y'
    })
    fc = FinanceComponents(cfg=cfg)
    tickers = fc.fdata.get_tickers_dow()
    for ticker in tickers:
        stock_analysis_by_ticker(ticker=ticker)


if __name__ == '__main__':
    run_batch_dow()
    run_batch_sp500()
