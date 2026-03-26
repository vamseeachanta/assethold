from assethold.test.test_service_stock_analysis_run_all_tickers import \
    stock_analysis_by_ticker


def test_stock_analysis_by_ticker(ticker):
    fc = stock_analysis_by_ticker(ticker)
    print("Completed analysis for {}".format(ticker))


if __name__ == '__main__':
    test_stock_analysis_by_ticker(ticker='RIG')

    # test_stock_analysis_by_ticker(ticker='OCGN')
    # test_StockAnalysisbyTicker(ticker='OXY')
    # test_StockAnalysisbyTicker(ticker='SPY')
    # test_StockAnalysisbyTicker(ticker='NIO')
    # test_StockAnalysisbyTicker(ticker='BEAM')
    # test_StockAnalysisbyTicker(ticker='VGENX')
